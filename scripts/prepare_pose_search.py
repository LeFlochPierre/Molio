"""Attach the existing source-topology audit ledger to a sampling manifest."""
import argparse
import copy
import json
import os
from pathlib import Path
from openmm import app


def prepare(manifest, source_root):
    m = copy.deepcopy(manifest)
    for enzyme,source in [('CYP11B1','CYP11B1_S'),('CYP11B2','CYP11B2_R')]:
        pdb_path = source_root/source/'prepared.pdb'
        pdb = app.PDBFile(str(pdb_path))
        def identity(a):
            r = a.residue
            if r.chain.id == 'A': return f'res{r.id}_{a.name}'
            if r.name == 'HEM': return 'heme_'+a.name
            return None
        bonds = [(identity(a),identity(b)) for a,b in pdb.topology.bonds()]
        for name in ('cluster_ligand','cluster_water'):
            s = m['enzymes'][enzyme][name]; lookup = {a['id']:a for a in s['atoms']}
            pairs = [(a,b) for a,b in bonds if a in lookup and b in lookup]
            pairs.extend((b['parent'],b['cap']) for b in s['provenance']['cap_bonds'])
            ledger = []
            for a,b in pairs:
                elements = {lookup[a]['element'],lookup[b]['element']}
                low,high = (1.7,2.9) if 'Fe' in elements else (0.7,1.4) if 'H' in elements else (1.3,2.2) if 'S' in elements else (0.95,1.85)
                ledger.append(dict(ids=[a,b],min_A=low,max_A=high))
            s['audit_bonds'] = ledger
            s['audit_bonds_source'] = str(pdb_path)
        # The previous runner omitted a free-water bond audit. Use exactly the
        # O-H bounds already specified for the corresponding bound water.
        water = m['enzymes'][enzyme]['free_water']
        oxygen = next(a['id'] for a in water['atoms'] if a['element']=='O')
        bounds = m['enzymes'][enzyme]['cluster_water']['covalent_bounds'][0]
        water['covalent_bounds'] = [dict(ids=[oxygen,a['id']],min_A=bounds['min_A'],max_A=bounds['max_A'])
                                   for a in water['atoms'] if a['element']=='H']
    return m


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--source-root',type=Path,default=Path(os.environ.get('ISOFORM_SOURCE_ROOT',Path(__file__).resolve().parents[1]/'research/source-preparation')))
    a = p.parse_args(); m = prepare(json.loads(a.manifest.read_text()),a.source_root)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x') as f: json.dump(m,f,indent=2,allow_nan=False)

if __name__=='__main__': main()
