"""Rebuild a provisional, matched capped-pocket exchange cycle from mapped domains."""
import copy, hashlib, json, math, os, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('ISOFORM_SOURCE_ROOT', ROOT/'research/source-preparation'))
OUT=ROOT/'prepared/exchange-pilot-v1'
RES=[110,113,116,130,231,310,313,314,315,316,318,378,379,380,381,382,383,450,487,488]

def save(p,d): p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def load(name):
 p=SOURCE/name
 data={f:json.loads((p/f).read_text()) for f in ['atom_map.json','singlepoint_request.json','charge_ledger.json','preparation_report.json']}
 data['hashes']={str(p/f):hashlib.sha256((p/f).read_bytes()).hexdigest() for f in data}
 data['xyz']=np.array(data['singlepoint_request.json']['positions_angstrom'])
 return data

def atom(a,x):
 prefix=f"res{a['residue_number']}" if a['chain']=='A' else 'heme' if a['residue']=='HEM' else 'ligand'
 return {'id':prefix+'_'+a['name'],'element':a['element'],'position':list(map(float,x)),
         'source':{k:a[k] for k in ['index','chain','residue','residue_number','name','origin']}}

def build(d, residues=None):
 residues=RES if residues is None else sorted(set(residues))
 amap=d['atom_map.json']; xyz=d['xyz']
 by={(int(a['residue_number']),a['name']):a for a in amap if a['chain']=='A'}
 selected=[a for a in amap if (a['chain']=='A' and int(a['residue_number']) in residues) or a['residue']=='HEM']
 atoms=[atom(a,xyz[a['index']]) for a in selected]
 fixed=[a['id'] for a in atoms if a['source']['chain']=='A' and a['source']['name'] in ('N','CA','C','O')]
 caps=[]
 for n in residues:
  for name,neighbor,other,length in [('N',n-1,'C',1.01),('C',n+1,'N',1.09)]:
   if neighbor in residues:continue
   a,b=by[n,name],by[neighbor,other];pa,pb=xyz[a['index']],xyz[b['index']]
   assert 1.1<np.linalg.norm(pb-pa)<1.7
   cap={'id':f'res{n}_{name}_Hcap','element':'H','position':(pa+length*(pb-pa)/np.linalg.norm(pb-pa)).tolist()}
   atoms.append(cap);fixed.append(cap['id']);caps.append({'parent':f'res{n}_{name}','cap':cap['id'],'removed_peptide_partner':f'res{neighbor}_{other}','length_A':length})
 ledger=[r for r in d['charge_ledger.json'] if (r['chain']=='A' and int(r['residue_number']) in residues) or r['residue']=='HEM']
 return atoms,fixed,caps,ledger

def rotation(x,y):
 xc,yc=x.mean(0),y.mean(0);u,s,vt=np.linalg.svd((x-xc).T@(y-yc));r=u@vt
 if np.linalg.det(r)<0:u[:,-1]*=-1;r=u@vt
 return r,xc,yc,float(np.sqrt(np.mean(np.sum(((x-xc)@r-(y-yc))**2,axis=1))))

def water_pose(scaffold,ligand,reference):
 lookup={a['id']:np.array(a['position']) for a in scaffold+ligand};fe=lookup['heme_FE'];direction=lookup['ligand_N06']-fe;direction/=np.linalg.norm(direction)
 oxygen=fe+2.2*direction
 seed=np.eye(3)[int(np.argmin(abs(direction)))];e1=np.cross(direction,seed);e1/=np.linalg.norm(e1);e2=np.cross(direction,e1)
 coords=np.array([a['position'] for a in reference]);o=next(i for i,a in enumerate(reference) if a['element']=='O');hs=[i for i,a in enumerate(reference) if a['element']=='H']
 # Preserve relaxed water bond lengths/angle; bisector points away from Fe.
 v1,v2=coords[hs]-coords[o];theta=math.acos(np.dot(v1,v2)/np.linalg.norm(v1)/np.linalg.norm(v2))/2
 lengths=[np.linalg.norm(v1),np.linalg.norm(v2)];heavy=np.array([a['position'] for a in scaffold if a['element']!='H' and a['id']!='heme_FE'])
 candidates=[]
 for angle in np.linspace(0,2*np.pi,72,endpoint=False):
  axis=np.cos(angle)*e1+np.sin(angle)*e2
  h=[oxygen+lengths[k]*(np.cos(theta)*direction+(-1 if k else 1)*np.sin(theta)*axis) for k in range(2)]
  score=float(np.min(np.linalg.norm(np.array(h)[:,None,:]-heavy[None,:,:],axis=2)))
  candidates.append((score,h))
 _,h=max(candidates,key=lambda x:x[0])
 return [{'id':'bound_water_O','element':'O','position':oxygen.tolist()}]+[{'id':f'bound_water_H{k+1}','element':'H','position':p.tolist()} for k,p in enumerate(h)]

def main():
 OUT.mkdir(exist_ok=False)
 b1,b2=load('CYP11B1_S'),load('CYP11B2_R')
 scaffold1,*_=build(b1);scaffold2,*_=build(b2)
 def heme(d):return {a['name']:d['xyz'][a['index']] for a in d['atom_map.json'] if a['residue']=='HEM' and a['element']!='H'}
 h1,h2=heme(b1),heme(b2);names=sorted(h1);assert set(names)==set(h2)
 r,xc,yc,rms=rotation(np.array([h1[n] for n in names]),np.array([h2[n] for n in names]))
 lig=[atom(a,b1['xyz'][a['index']]) for a in b1['atom_map.json'] if a['residue']=='JD7'];assert len(lig)==30
 m=json.loads((ROOT/'prepared/exchange-cycle-progress.json').read_text());m['preparation_protocol']='capped-pocket-exchange-pilot-v1; same numbered residues; neutral H caps on cut peptide N/C; fixed backbone heavy atoms/caps; no crystal waters; ferric doublet; deprotonated propionates; modeled B2/S pose by heme alignment'
 m['optimizer']['method']='ase_bfgs';m['optimizer']['max_steps']=400
 audits={}
 for enzyme,d in [('CYP11B1',b1),('CYP11B2',b2)]:
  scaffold,fixed,caps,ledger=build(d);ligand=copy.deepcopy(lig)
  if enzyme=='CYP11B2':
   for a in ligand:a['position']=((np.array(a['position'])-xc)@r+yc).tolist()
  water=water_pose(scaffold,ligand,m['enzymes'][enzyme]['free_water']['atoms'])
  charge=sum(x['formal_charge'] for x in ledger)
  for name,guest,donor in [('cluster_ligand',ligand,'ligand_N06'),('cluster_water',water,'bound_water_O')]:
   atoms=copy.deepcopy(scaffold)+guest
   # Explicitly provisional bounds applied before looking at energies.
   bounds=[{'ids':['heme_FE',donor],'min_A':1.8,'max_A':2.8},{'ids':['heme_FE','res450_SG'],'min_A':2.0,'max_A':2.9}]
   component={'atoms':atoms,'fixed_ids':fixed,'scaffold_ids':[a['id'] for a in scaffold],
    'state':{'charge':charge,'multiplicity':2,'convention':'Provisional ferric low-spin doublet; heme net -1 (porphyrin -2, two propionates -1 each, Fe +3); Cys450 thiolate; standard residue states; neutral guest; isolated H-capped pocket'},
    'review':{'approved':False,'provisional':True},'coordination':bounds,'preparation':m['preparation_protocol'],
    'provenance':{'source_hashes':d['hashes'],'selected_residue_numbers':RES,'cap_bonds':caps,'charge_ledger':ledger,
      'pose_kind':'modeled_water_replacement' if name=='cluster_water' else 'experimental_heavy_pose' if enzyme=='CYP11B1' else 'modeled_heme_aligned_S_pose',
      'heme_alignment_RMSD_A':rms,'notes':'Rebuilt cluster; not the original 462-atom input. Protonation, spin, boundaries and pose need sensitivity checks.'}}
   z={'H':1,'C':6,'N':7,'O':8,'S':16,'Fe':26};assert (sum(z[a['element']] for a in atoms)-charge)%2==1
   ids={a['id']:np.array(a['position']) for a in atoms};coord=[float(np.linalg.norm(ids[b['ids'][0]]-ids[b['ids'][1]])) for b in bounds]
   assert all(b['min_A']<=v<=b['max_A'] for b,v in zip(bounds,coord)),coord
   positions=np.array([a['position'] for a in atoms]);dist=np.linalg.norm(positions[:,None,:]-positions[None,:,:],axis=2);np.fill_diagonal(dist,np.inf)
   assert float(dist.min())>0.65, (enzyme,name,float(dist.min()))
   m['enzymes'][enzyme][name]=component
   audits[enzyme+'/'+name]={'atoms':len(atoms),'fixed_atoms':len(fixed),'charge':charge,'coordination_A':coord,'minimum_pair_distance_A':float(dist.min())}
 # Record explicit covalent and stereochemical guards in the generated manifest.
 sys.path.insert(0,str(SOURCE));import prepare_whole as source_builder
 original,_=source_builder.read_source(source_builder.INPUT/'6M7X.pdb')
 topology,*_=source_builder.component(original,'JD7',source_builder.INPUT/'JD7.cif')
 for parts in m['enzymes'].values():
  for name,component in parts.items():
   if name in ('cluster_ligand','free_ligand'):
    component['covalent_bounds']=[{'ids':['ligand_'+a.name,'ligand_'+b.name],'min_A':0.85,'max_A':1.85} for a,b in topology.bonds()]
    coords={a['id']:np.array(a['position']) for a in component['atoms']};center='ligand_C03';neighbors=['ligand_C02','ligand_N04','ligand_C10']
    component['chirality_checks']=[{'center':center,'neighbors':neighbors,'reference_volume_A3':float(np.linalg.det(np.array([coords[n]-coords[center] for n in neighbors])))}]
   elif name=='cluster_water':
    component['covalent_bounds']=[{'ids':['bound_water_O','bound_water_H'+str(i)],'min_A':0.7,'max_A':1.3} for i in [1,2]]
 sys.path.insert(0,str(ROOT));from cyp_pipeline.exchange import validate_manifest
 validate_manifest(m);save(OUT/'manifest.json',m);save(OUT/'preparation_audit.json',audits)
 print(json.dumps(audits,indent=2))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=OUT)
 parser.add_argument('--add-residue',type=int,action='append',default=[],help='add numbered protein residue to the capped pocket')
 args=parser.parse_args()
 RES=sorted(set(RES+args.add_residue))
 OUT=args.out;main()
