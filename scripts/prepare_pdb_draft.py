#!/usr/bin/env python3
"""Create a visibly unapproved 6M7X preparation draft from PDB coordinates.

This is an inventory-to-draft utility, not an automatic chemistry preparer.
It intentionally leaves protonation, charge, spin, caps and review unresolved.
"""
import argparse, hashlib, json, math
from collections import defaultdict
from pathlib import Path

def atom(line):
    name=line[12:16].strip(); res=line[17:20].strip(); chain=line[21:22] or '_'; num=line[22:27].strip()
    element=(line[76:78].strip() or name[0]).upper()
    return {'name':name,'res':res,'chain':chain,'num':num,'element':element,
            'xyz':[float(line[30:38]),float(line[38:46]),float(line[46:54])]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('pdb'); ap.add_argument('out'); args=ap.parse_args()
    raw=Path(args.pdb).read_bytes(); lines=raw.decode(errors='replace').splitlines()
    atoms=[]
    for line in lines:
        if line.startswith(('ATOM  ','HETATM')) and line[16:17] in (' ','A'):
            try: atoms.append(atom(line))
            except ValueError: pass
    ligand=[a for a in atoms if a['chain']=='A' and a['res']=='JD7' and a['num']=='601']
    heme=[a for a in atoms if a['chain']=='A' and a['res']=='HEM']
    fe=next(a for a in heme if a['name']=='FE')
    sg=min((a for a in atoms if a['chain']=='A' and a['res']=='CYS' and a['name']=='SG'), key=lambda a: math.dist(a['xyz'],fe['xyz']))
    pocket=[]
    for a in atoms:
        if a['chain']=='A' and a['res'] not in ('HOH','JD7','HEM') and min(math.dist(a['xyz'],x['xyz']) for x in ligand)<5.0:
            pocket.append(a)
    selected=ligand+heme+[sg]+pocket
    out_atoms=[]; ids={}
    for i,a in enumerate(selected):
        key=f"{a['chain']}:{a['res']}:{a['num']}:{a['name']}"
        if key in ids: continue
        ids[key]=f"{a['chain']}_{a['res']}_{a['num']}_{a['name']}"
        role='ligand' if a in ligand else 'heme' if a in heme else 'axial' if a is sg else 'pocket'
        out_atoms.append({'id':ids[key],'element':a['element'],'role':role,'position':a['xyz']})
    feid=ids[f"A:HEM:{fe['num']}:{fe['name']}"]; nid=ids[f"A:JD7:601:{min((a for a in ligand if a['element']=='N'),key=lambda a:math.dist(a['xyz'],fe['xyz']))['name']}"]; sgid=ids[f"A:CYS:{sg['num']}:{sg['name']}"]
    system={'schema_version':1,'system_id':'6M7X-S-fadrozole-CYP11B1-draft','ligand':'S-fadrozole','isoform':'CYP11B1',
      'comparison_group':'fadrozole-cyp11-v1-DRAFT','pose':{'kind':'experimental','source':'https://www.rcsb.org/structure/6M7X','chain':'A','ligand_code':'JD7'},
      'review':{'approved':False,'reviewer':'','date_utc':'','note':'Automatic coordinate draft; chemistry review required.'},'atoms':out_atoms,
      'fragment_ids':[a['id'] for a in out_atoms if a['role'] in ('ligand','heme','axial')],
      'fixed_ids':[a['id'] for a in out_atoms if a['role']=='pocket'],
      'cluster_state':{'charge':None,'multiplicity':None,'convention':''},'fragment_state':{'charge':None,'multiplicity':None,'convention':''},
      'coordination':[{'ids':[feid,nid],'min_A':2.0,'max_A':2.6,'observed_A':math.dist(fe['xyz'],min((a for a in ligand if a['element']=='N'),key=lambda a:math.dist(a['xyz'],fe['xyz']))['xyz'])},
                      {'ids':[feid,sgid],'min_A':2.0,'max_A':2.7,'observed_A':math.dist(fe['xyz'],sg['xyz'])}],
      'preparation':{k:'' for k in ('protonation','oxidation_state','caps','boundary','stereochemistry','reference_coordination','fragment_definition','pocket_geometry')},
      'provenance':{'pdb':args.pdb,'sha256':hashlib.sha256(raw).hexdigest(),'selection':'chain A; JD7 601; HEM; nearest CYS SG; non-water residues within 5 Å of ligand','atom_count':len(out_atoms),'pocket_atom_count':len(pocket)}}
    Path(args.out).parent.mkdir(parents=True,exist_ok=True); Path(args.out).write_text(json.dumps(system,indent=2)+'\n')
    print(json.dumps(system['provenance'],indent=2))
if __name__=='__main__': main()
