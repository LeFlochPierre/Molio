"""Prepare and relax a provisional isolated-water reference with the cycle backend."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cyp_pipeline.backends import load_backend
from cyp_pipeline.core import relax, checked_evaluate
from cyp_pipeline.workflow import save, xyz

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', required=True)
p.add_argument('--input', help='Prepared free-molecule component JSON; defaults to water')
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
config = json.loads((root/'configs/uma-s-1p1-a100.json').read_text())
protocol = json.loads((root/'configs/protocol.json').read_text())
s = {'atoms': [{'id':'water_O','element':'O','position':[0.,0.,0.]},
               {'id':'water_H1','element':'H','position':[0.96,0.,0.]},
               {'id':'water_H2','element':'H','position':[-0.24,0.93,0.]}],
     'state': {'charge':0,'multiplicity':1,'convention':'Isolated neutral singlet H2O; no solvent or embedding'},
     'fixed_ids':[], 'review':{'approved':False,'provisional':True},
     'preparation':'Explicit three-atom water, initialized with approximate geometry and relaxed without constraints using UMA OMol.'}
if args.input:
    s = json.loads(Path(args.input).read_text())
    if s.get('fixed_ids') != []:
        raise ValueError('Free molecule must have no fixed atoms')
save(out/'input.json',s); save(out/'backend_config.json',config);save(out/'protocol.json',protocol)
xyz(out/'before.xyz',s['atoms'])
result={'status':'running','component':'free_ligand' if args.input else 'free_water','energy_eV':None}
save(out/'result.json',result)
start=time.monotonic()
try:
    backend=load_backend(config)
    calculation=relax(backend,s['atoms'],s['state'],[],protocol)
    save(out/'relaxation.json',calculation);xyz(out/'after.xyz',calculation['atoms'])
    final_energy,forces=checked_evaluate(backend,calculation['atoms'],s['state'])
    save(out/'forces.json',forces)
    result.update(status='completed' if calculation['converged'] else 'unresolved',
                  energy_eV=final_energy,converged=calculation['converged'],
                  steps=calculation['history'][-1]['step'],
                  final_fmax_eV_A=calculation['history'][-1]['free_fmax_eV_A'],
                  backend=backend.metadata)
    if calculation['converged']:
        save(out/'prepared_component.json',{**s,'atoms':calculation['atoms']})
except Exception as exc:
    result.update(status='failed',reason=f'{type(exc).__name__}: {exc}')
result['runtime_seconds']=time.monotonic()-start
save(out/'result.json',result)
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['status']=='completed' else 1)
