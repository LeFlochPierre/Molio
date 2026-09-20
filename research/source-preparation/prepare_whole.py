"""Prepare complete crystallized enzyme domains, residues 34-503, for a UMA pilot.

This is an assumption-based isolated-molecule model, not an affinity calculation.
Original protein/heme/ligand heavy coordinates are retained. Missing residues and
hydrogens are modeled and recorded. The mitochondrial leader and expression tags
are outside this explicitly defined domain. No full-protein relaxation is done.
"""
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import random
import shlex
import time

os.environ.setdefault('OPENMM_CPU_THREADS', '4')
import numpy as np
from scipy.spatial import cKDTree
from rdkit import Chem
import openmm as mm
from openmm import app, unit
from pdbfixer import PDBFixer

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'inputs'


def save(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def ccd_table(path, category):
    lines = path.read_text().splitlines()
    i = next(i for i, line in enumerate(lines) if line.startswith(category + '.'))
    columns = []
    while lines[i].startswith(category + '.'):
        columns.append(lines[i].strip().split('.', 1)[1]); i += 1
    tokens = []
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith(('#', '_')) or line == 'loop_': break
        tokens.extend(shlex.split(line)); i += 1
    assert len(tokens) % len(columns) == 0
    return [dict(zip(columns, tokens[j:j+len(columns)])) for j in range(0, len(tokens), len(columns))]


def read_source(path):
    lines = path.read_text().splitlines()
    picked = {}
    for line in lines:
        if not line.startswith(('ATOM  ', 'HETATM')) or line[21] != 'A': continue
        name, res, num = line[12:16].strip(), line[17:20].strip(), int(line[22:26])
        element = line[76:78].strip().title()
        if element in ('H', 'D'): continue
        key = (res, num, name)
        rank = (float(line[54:60]), line[16] == ' ', line[16] == 'A')
        if key not in picked or rank > picked[key][0]:
            picked[key] = (rank, dict(name=name, res=res, num=num, element=element,
                xyz=[float(line[j:j+8]) for j in (30,38,46)], line=line, source='experimental'))
    atoms = [item[1] for item in picked.values()]
    seq = {a['num']: a['res'] for a in atoms if a['line'].startswith('ATOM  ') and 34 <= a['num'] <= 503}
    for line in lines:
        if line.startswith('REMARK 465') and len(line) > 26 and line[19] == 'A':
            try: num = int(line[21:26])
            except ValueError: continue
            if 34 <= num <= 503: seq[num] = line[15:18].strip()
    assert sorted(seq) == list(range(34, 504)), sorted(set(range(34, 504)) - seq.keys())
    return atoms, seq


def component(atoms, resname, template):
    """Build covalent CCD graph; Fe-N coordination is recorded separately.

    RDKit adds H to heavy-atom geometry, preserving that geometry. Heme uses a
    porphyrin dianion, two anionic propionates, Fe(III), net charge -1.
    """
    rows = ccd_table(template, '_chem_comp_atom')
    bondrows = ccd_table(template, '_chem_comp_bond')
    observed = {a['name']: a for a in atoms if a['res'] == resname}
    heavy = [r for r in rows if r['type_symbol'] != 'H']
    assert set(observed) == {r['atom_id'] for r in heavy}
    mol = Chem.RWMol(); names = {}; formal = {}
    for row in heavy:
        name = row['atom_id']; element = row['type_symbol'].title()
        q = 3 if element == 'Fe' else int(row['charge'])
        a = Chem.Atom(element); a.SetFormalCharge(q)
        if element == 'Fe': a.SetNoImplicit(True)
        names[name] = mol.AddAtom(a); formal[name] = q
    orders = {'SING':Chem.BondType.SINGLE, 'DOUB':Chem.BondType.DOUBLE, 'TRIP':Chem.BondType.TRIPLE}
    coordination = []
    for row in bondrows:
        left, right = row['atom_id_1'], row['atom_id_2']
        if left not in names or right not in names: continue
        if 'FE' in (left, right):
            coordination.append((left, right)); continue
        mol.AddBond(names[left], names[right], orders[row['value_order']])
    mol = mol.GetMol(); Chem.SanitizeMol(mol)
    conf = Chem.Conformer(len(heavy)); conf.Set3D(True)
    for name, idx in names.items(): conf.SetAtomPosition(idx, observed[name]['xyz'])
    mol.AddConformer(conf)
    Chem.AssignAtomChiralTagsFromStructure(mol, replaceExistingTags=True)
    mol = Chem.AddHs(mol, addCoords=True)
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    conf = mol.GetConformer()
    topology = app.Topology(); chain = topology.addChain('L' if resname != 'HEM' else 'H')
    residue = topology.addResidue(resname, chain, str(next(iter(observed.values()))['num']))
    topoatoms = []; mapping = []; hcount = collections.Counter()
    inverse = {i:name for name, i in names.items()}
    for a in mol.GetAtoms():
        idx = a.GetIdx(); symbol = a.GetSymbol()
        if idx in inverse: name = inverse[idx]
        else:
            parent = a.GetNeighbors()[0].GetIdx(); hcount[parent] += 1
            name = f'H{parent:02d}{hcount[parent]}'
        topoatoms.append(topology.addAtom(name, app.Element.getBySymbol(symbol), residue))
        mapping.append({'name':name,'element':symbol,'formal_charge':a.GetFormalCharge(),
                        'origin':'experimental' if idx in inverse else 'modeled_hydrogen'})
    for b in mol.GetBonds(): topology.addBond(topoatoms[b.GetBeginAtomIdx()], topoatoms[b.GetEndAtomIdx()])
    for left, right in coordination: topology.addBond(topoatoms[names[left]], topoatoms[names[right]])
    xyz = np.array(conf.GetPositions())
    for name, idx in names.items(): assert np.max(np.abs(xyz[idx]-observed[name]['xyz'])) < 1e-10
    charge = Chem.GetFormalCharge(mol)
    if resname == 'HEM': assert charge == -1 and mol.GetNumAtoms() == 73
    else: assert charge == 0 and mol.GetNumAtoms() == 30
    return topology, xyz * unit.angstrom, charge, mapping, Chem.FindMolChiralCenters(mol, includeUnassigned=True)


def prepare(pdb, label, ligand):
    started = time.time(); out = ROOT / label; out.mkdir(exist_ok=False)
    source = INPUT / f'{pdb}.pdb'
    original, seq = read_source(source)
    protein = [a for a in original if a['line'].startswith('ATOM  ') and 34 <= a['num'] <= 503]
    original_lookup = {(a['num'],a['name']):np.array(a['xyz']) for a in protein}
    missing_residues = sorted(set(seq) - {a['num'] for a in protein})
    seqnames = [seq[i] for i in range(34,504)]
    lines = [f'SEQRES {j//13+1:3d} A {len(seqnames):4d}  ' + ' '.join(seqnames[j:j+13])
             for j in range(0,len(seqnames),13)]
    lines += [a['line'][:16]+' '+a['line'][17:] for a in protein]
    lines += ['TER','END']
    (out/'protein_heavy_source.pdb').write_text('\n'.join(lines)+'\n')
    print(label, 'building missing protein atoms', missing_residues, flush=True)
    fixer = PDBFixer(filename=str(out/'protein_heavy_source.pdb'), platform=mm.Platform.getPlatformByName('CPU'))
    fixer.findMissingResidues(); fixer.findNonstandardResidues()
    assert not fixer.nonstandardResidues
    fixer.findMissingAtoms()
    missing_heavy = {f'{r.name}:{r.id}':[a.name for a in atoms] for r,atoms in fixer.missingAtoms.items()}
    fixer.addMissingAtoms(seed=20260919)
    residues = list(fixer.topology.residues()); assert len(residues) == 470
    for num, residue in zip(range(34,504), residues):
        assert residue.name == seq[num], (num, residue.name, seq[num])
        residue.id = str(num)
    model = app.Modeller(fixer.topology, fixer.positions)
    component_info = {}
    for resname in ('HEM',ligand):
        template = INPUT / ('HEM.cif' if resname == 'HEM' else 'JD7.cif')
        topology, xyz, charge, mapping, chiral = component(original, resname, template)
        if resname != 'HEM':
            assert len(chiral) == 1 and chiral[0][1] == ('S' if ligand == 'JD7' else 'R'), chiral
        model.add(topology, xyz)
        component_info[resname] = dict(charge=charge, atom_count=len(mapping), chirality=chiral, atoms=mapping)
    water = [a for a in original if a['res']=='HOH']
    wt = app.Topology(); wc = wt.addChain('W')
    for a in water:
        residue = wt.addResidue('HOH',wc,str(a['num']))
        wt.addAtom('O',app.element.oxygen,residue)
    if water: model.add(wt, np.array([a['xyz'] for a in water])*unit.angstrom)
    # CYX here means no sulfur hydrogen. It is assigned a thiolate charge below,
    # not interpreted as a disulfide. The Fe-S bond is added after H placement.
    variants = ['CYX' if r.chain.id=='A' and r.id=='450' else None for r in model.topology.residues()]
    print(label, 'adding protein and water hydrogens', flush=True)
    random.seed(20260919); np.random.seed(20260919)
    chosen = model.addHydrogens(forcefield=None, pH=7.4, variants=variants,
                               platform=mm.Platform.getPlatformByName('CPU'))
    allres = list(model.topology.residues())
    ledger = []
    for residue, variant in zip(allres,chosen):
        if residue.chain.id=='A':
            q = {'ASP':-1,'GLU':-1,'LYS':1,'ARG':1}.get(residue.name,0)
            if variant in ('ASH','GLH','LYN'): q = 0
            if variant == 'HIP': q = 1
            if variant == 'HIN': q = -1
            if residue.id=='450':
                assert residue.name=='CYS' and not any(a.name=='HG' for a in residue.atoms())
                q -= 1
            if residue.id=='34': q += 1
            if residue.id=='503': q -= 1
        elif residue.name=='HEM': q = -1
        else: q = 0
        ledger.append(dict(chain=residue.chain.id,residue_number=residue.id,residue=residue.name,
                           variant=variant,formal_charge=q))
    charge = sum(row['formal_charge'] for row in ledger)
    atoms = list(model.topology.atoms()); xyz = np.array(model.positions.value_in_unit(unit.angstrom))
    z = [a.element.atomic_number for a in atoms]
    electrons = sum(z)-charge; assert electrons%2 == 1
    fe = next(a for a in atoms if a.element.symbol=='Fe')
    sg = next(a for a in atoms if a.residue.chain.id=='A' and a.residue.id=='450' and a.name=='SG')
    donor = next(a for a in atoms if a.residue.name==ligand and a.name=='N06')
    model.topology.addBond(fe,sg); model.topology.addBond(fe,donor)
    # Verify original heavy coordinates and the continuous reconstructed sequence.
    changes = []; modeled_atoms = []; amap = []
    for a in atoms:
        k = (int(a.residue.id),a.name)
        original_atom = a.residue.chain.id=='A' and k in original_lookup
        if original_atom: changes.append(float(np.linalg.norm(xyz[a.index]-original_lookup[k])))
        origin = ('modeled_hydrogen' if a.element.symbol=='H' else 'experimental')
        if a.residue.chain.id=='A' and not original_atom and a.element.symbol!='H':
            origin = 'modeled_missing_heavy_atom'; modeled_atoms.append(a.index)
        amap.append(dict(index=a.index,name=a.name,element=a.element.symbol,chain=a.residue.chain.id,
                         residue=a.residue.name,residue_number=a.residue.id,origin=origin))
    assert max(changes)<1e-6
    pres = [r for r in allres if r.chain.id=='A']
    peptide_distances=[]
    for left,right in zip(pres,pres[1:]):
        c=next(a for a in left.atoms() if a.name=='C'); n=next(a for a in right.atoms() if a.name=='N')
        peptide_distances.append(float(np.linalg.norm(xyz[c.index]-xyz[n.index])))
    assert all(1.1<d<1.7 for d in peptide_distances), (min(peptide_distances),max(peptide_distances))
    adjacency=[set() for a in atoms]
    for a,b in model.topology.bonds(): adjacency[a.index].add(b.index); adjacency[b.index].add(a.index)
    clashes=[]
    for i,j in sorted(cKDTree(xyz).query_pairs(1.9)):
        if j in adjacency[i] or any(j in adjacency[k] for k in adjacency[i]): continue
        nh=(z[i]==1)+(z[j]==1); limit=1.0 if nh==2 else 1.2 if nh==1 else 1.9
        d=float(np.linalg.norm(xyz[i]-xyz[j]))
        if d<limit: clashes.append(dict(indices=[i,j],distance_A=d,threshold_A=limit,
                                       atoms=[amap[i],amap[j]]))
    catastrophic=[c for c in clashes if c['distance_A']<0.65]
    assert not catastrophic, catastrophic
    # Check the independently parameterizable protein/water charge in Amber14.
    check = app.Modeller(model.topology, model.positions)
    check.delete([r for r in check.topology.residues() if r.name in ('HEM',ligand)])
    ff=app.ForceField('amber14-all.xml','amber14/tip3p.xml')
    system=ff.createSystem(check.topology, nonbondedMethod=app.NoCutoff, constraints=None)
    nb=next(f for f in system.getForces() if isinstance(f,mm.NonbondedForce))
    ffcharge=sum(nb.getParticleParameters(i)[0].value_in_unit(unit.elementary_charge) for i in range(nb.getNumParticles()))
    assert abs(ffcharge-(charge+1))<1e-5,(ffcharge,charge)
    with (out/'prepared.pdb').open('w') as f: app.PDBFile.writeFile(model.topology,model.positions,f,keepIds=True)
    (out/'prepared.xyz').write_text(str(len(atoms))+'\n'+f'{label}; complete domain 34-503; charge={charge}; multiplicity=2; isolated pilot\n'+
        '\n'.join(f'{a.element.symbol} {xyz[a.index,0]:.10f} {xyz[a.index,1]:.10f} {xyz[a.index,2]:.10f}' for a in atoms)+'\n')
    request=dict(label=label,atomic_numbers=z,positions_angstrom=xyz.tolist(),charge=charge,
                 spin_multiplicity=2,operation='energy')
    save(out/'singlepoint_request.json',request); save(out/'charge_ledger.json',ledger)
    save(out/'atom_map.json',amap); save(out/'components.json',component_info)
    save(out/'geometry_checks.json',dict(close_nonbonded_contacts=clashes,catastrophic_overlaps=catastrophic,
        peptide_bond_range_A=[min(peptide_distances),max(peptide_distances)],
        Fe_N_A=float(np.linalg.norm(xyz[fe.index]-xyz[donor.index])),Fe_S_A=float(np.linalg.norm(xyz[fe.index]-xyz[sg.index]))))
    report=dict(status='needs_loop_repair' if clashes else 'prepared_assumption_based_pilot',pdb=pdb,chain='A',domain_residue_range=[34,503],
        protein_residues=470,atom_count=len(atoms),crystal_waters=len(water),charge=charge,spin_multiplicity=2,
        electron_count=electrons,formula=dict(collections.Counter(a.element.symbol for a in atoms)),
        reconstructed_residues=missing_residues,missing_existing_residue_heavy_atoms=missing_heavy,
        modeled_heavy_atom_indices=modeled_atoms,max_original_protein_heavy_atom_displacement_A=max(changes),
        protein_and_water_amber_charge=ffcharge,close_nonbonded_contact_count=len(clashes),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),preparation_seconds=time.time()-started,
        interpretation='One isolated whole-domain geometry, not binding free energy or selectivity.',
        assumptions=['Protein domain residues 34-503; mitochondrial precursor and expression tags excluded.',
          'Missing internal loops and terminal Asn503 modeled by PDBFixer; not experimental coordinates.',
          'Standard pH 7.4 residue forms; automatic neutral histidine tautomer choices; no pKa calculation.',
          'Charged N/C termini; axial Cys450 thiolate; ferric low-spin doublet imposed.',
          'Heme propionates deprotonated; neutral fadrozole; source-chain crystallographic waters retained.',
          'No bulk solvent, salt, membrane, protein relaxation, or spin-state search.',
          'B1/S and B2/R are separate feasibility pilots, not a matched-ligand selectivity pair.'])
    save(out/'preparation_report.json',report)
    print(json.dumps({k:report[k] for k in ['status','atom_count','charge','protein_residues','crystal_waters','close_nonbonded_contact_count','preparation_seconds']}),flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('isoform',choices=['B1','B2']);args=p.parse_args()
    prepare(*({'B1':('6M7X','CYP11B1_S','JD7'),'B2':('4FDH','CYP11B2_R','0T3')}[args.isoform]))
