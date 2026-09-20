"""Audit all retained source-topology bonds and new cap bonds after relaxation."""
import argparse,json,math,os
from pathlib import Path
from openmm import app
p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path)
p.add_argument('--source-root',type=Path,default=Path(os.environ.get('ISOFORM_SOURCE_ROOT',Path(__file__).resolve().parents[1]/'research/source-preparation')))
args=p.parse_args()
manifest=json.loads((args.run/'input.json').read_text())
report={'status':'passed','scope':'Broad bond-length and fixed-boundary checks; not chemical validation','components':{}}
for enzyme,source in [('CYP11B1','CYP11B1_S'),('CYP11B2','CYP11B2_R')]:
 pdb=app.PDBFile(str(args.source_root/source/'prepared.pdb'))
 def identity(a):
  r=a.residue
  if r.chain.id=='A':return f'res{r.id}_{a.name}'
  if r.name=='HEM':return 'heme_'+a.name
  return None
 bonds=[(identity(a),identity(b)) for a,b in pdb.topology.bonds()]
 for name in ['cluster_ligand','cluster_water']:
  path=args.run/enzyme/name/'relaxation.json';s=manifest['enzymes'][enzyme][name]
  if not path.exists():report['components'][enzyme+'/'+name]={'status':'missing'};report['status']='unresolved';continue
  final=json.loads(path.read_text())['atoms'];lookup={a['id']:a for a in final};initial={a['id']:a for a in s['atoms']}
  checks=[(a,b) for a,b in bonds if a in lookup and b in lookup]
  checks.extend((c['parent'],c['cap']) for c in s['provenance']['cap_bonds'])
  violations=[]
  for a,b in checks:
   elements={lookup[a]['element'],lookup[b]['element']}
   bounds=(1.7,2.9) if 'Fe' in elements else (0.7,1.4) if 'H' in elements else (1.3,2.2) if 'S' in elements else (0.95,1.85)
   distance=math.dist(lookup[a]['position'],lookup[b]['position'])
   if not bounds[0]<=distance<=bounds[1]:violations.append({'ids':[a,b],'distance_A':distance,'bounds_A':bounds})
  moved=[i for i in s['fixed_ids'] if math.dist(lookup[i]['position'],initial[i]['position'])>1e-10]
  ok=not violations and not moved
  report['components'][enzyme+'/'+name]={'status':'passed' if ok else 'failed','bonds_checked':len(checks),'bond_violations':violations,'moved_fixed_atoms':moved}
  if not ok:report['status']='unresolved'
(args.run/'bond_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
