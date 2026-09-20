"""Write a readable summary of the eight component results and their provenance."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);args=p.parse_args()
r=json.loads((args.run/'result.json').read_text())
lines=['# S-fadrozole ligand/water exchange pilot','',f"Calculation status: **{r['status']}**. Preparation is provisional.",'',
       '| Relaxed component | CYP11B1 energy (eV) | CYP11B2 energy (eV) |','|---|---:|---:|']
for name in ('cluster_ligand','free_water','cluster_water','free_ligand'):
 values=[]
 for enzyme in ('CYP11B1','CYP11B2'):
  c=r['enzymes'][enzyme]['components'][name];values.append(f"{c['energy_eV']:.9f}" if c['energy_eV'] is not None else c['status'])
 lines.append('| '+name+' | '+' | '.join(values)+' |')
lines+=['','Exchange = cluster_ligand + free_water - cluster_water - free_ligand.','']
for enzyme,row in r['enzymes'].items():
 value=row['exchange_energy_eV'];lines.append(f"- {enzyme} exchange: {value:.9f} eV" if value is not None else f'- {enzyme}: unresolved')
delta=r.get('delta_B2_minus_B1_eV')
if delta is not None:
 lines+=['',f'B2 minus B1 = **{delta:+.9f} eV**.',f"Energy-model preference: **{r['energy_model_preference']}**."]
else:lines+=['','No selectivity difference is available.']
lines+=['','## Convergence','', '| Component | BFGS steps in this invocation | Maximum free-atom force (eV/angstrom) |','|---|---:|---:|']
for enzyme,row in r['enzymes'].items():
 for name in row['components']:
  f=args.run/enzyme/name/'relaxation.json'
  if f.exists():
   h=json.loads(f.read_text())['history'][-1];lines.append(f"| {enzyme}/{name} | {h['step']} | {h['free_fmax_eV_A']:.6f} |")
lines+=['','The final force threshold is 0.02 eV/angstrom. Zero steps means a previously relaxed starting geometry already passed. The input snapshot records the preceding run where applicable.','',
 '## Interpretation and files','',
 'This is an isolated capped-pocket potential-energy pilot, not a binding free energy, selectivity ratio or validated experimental prediction. The selected residue identities match across enzymes; differences reflect this local geometry model. CYP11B2/S uses a heme-aligned modeled pose. Both metal states assume a ferric doublet. The cluster has no retained crystal water, bulk solvent or embedding. Pose, boundary, protonation and spin sensitivity remain untested.','',
 '[Machine-readable results](result.json), [input snapshot](input.json), [bond and boundary audit](bond_audit.json). Each enzyme/component folder contains its coordinates, progress, BFGS trajectory and detailed result.','',
 'The initial run is preserved, including the unconverged B2 ligand component. A converged continuation does not overwrite that evidence.']
(args.run/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(args.run/'REPORT.md')
