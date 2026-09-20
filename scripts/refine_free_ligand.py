"""BFGS refinement of the saved unconverged free-ligand reference."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ase import Atoms
from ase.optimize import BFGS
from cyp_pipeline.backends import load_backend
from cyp_pipeline.core import checked_evaluate
from cyp_pipeline.workflow import save,xyz
root=Path(__file__).resolve().parents[1]
previous=root/'runs/exchange-free-S-fadrozole-01'
out=root/'runs/exchange-free-S-fadrozole-bfgs-01';out.mkdir(exist_ok=False)
s=json.loads((previous/'input.json').read_text());s['atoms']=json.loads((previous/'relaxation.json').read_text())['atoms']
config=json.loads((previous/'backend_config.json').read_text())
save(out/'input.json',s);save(out/'backend_config.json',config)
save(out/'protocol.json',{'optimizer':'ASE BFGS','max_steps':200,'max_step_A':0.05,'force_tolerance_eV_A':0.02,'restart_from':str(previous)})
result={'status':'running','component':'free_ligand','energy_eV':None};save(out/'result.json',result)
start=time.monotonic()
try:
 backend=load_backend(config);checked_evaluate(backend,s['atoms'],s['state'])
 atoms=Atoms(symbols=[a['element'] for a in s['atoms']],positions=[a['position'] for a in s['atoms']],pbc=False)
 atoms.info.update(charge=s['state']['charge'],spin=s['state']['multiplicity']);backend.calculator.reset();atoms.calc=backend.calculator
 optimizer=BFGS(atoms,maxstep=0.05,logfile=str(out/'optimization.log'),trajectory=str(out/'optimization.traj'))
 converged=bool(optimizer.run(fmax=0.02,steps=200))
 for a,pos in zip(s['atoms'],atoms.positions.tolist()):a['position']=pos
 energy,forces=checked_evaluate(backend,s['atoms'],s['state'])
 xyz(out/'after.xyz',s['atoms']);save(out/'forces.json',forces);save(out/'candidate_component.json',s)
 result.update(status='completed' if converged else 'unresolved',converged=converged,energy_eV=energy,steps=optimizer.nsteps,final_fmax_eV_A=max(sum(x*x for x in f)**0.5 for f in forces),backend=backend.metadata,post_relaxation_stereochemistry='pending validation')
except Exception as exc:result.update(status='failed',reason=f'{type(exc).__name__}: {exc}')
result['runtime_seconds']=time.monotonic()-start;save(out/'result.json',result);print(json.dumps(result,indent=2))
raise SystemExit(0 if result['status']=='completed' else 1)
