"""Reproducible BRD4 pose diagnostics, separate from native model outputs.

Run: python -m molio.pose_checks work/whatif/experiments
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

REFERENCE = Path(__file__).resolve().parent / 'data/structures/3SVG.pdb'
THRESHOLDS = {'severe_contact_below_A': 1.2, 'nearby_residue_within_A': 4.0,
              'pocket_centroid_beyond_A': 6.0, 'protein_ca_rmsd_above_A': 2.0}
LIMITATION = ('Project screening heuristics, not validated acceptance thresholds. A clear screen does not '
              'establish correct bonding, stereochemistry, protonation, binding or affinity. The reference '
              'ODR is a different ligand: centroid distance is not ligand-pose RMSD.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atoms(text, reference=False):
    rows = []
    for line in text.splitlines():
        if not line.startswith(('ATOM  ', 'HETATM')): continue
        if reference and line[16:17] not in (' ', 'A'): continue
        if (not reference and line[16:17].strip()) or line[26:27].strip():
            raise ValueError('Alternate conformers or insertion codes require explicit mapping')
        element = line[76:78].strip().title()
        if not element: raise ValueError('Missing PDB element')
        if element in ('H', 'D'): continue
        rows.append({'line': line, 'chain': line[21:22], 'residue': int(line[22:26]),
                     'name': line[12:16].strip(), 'resname': line[17:20].strip(), 'element': element,
                     'xyz': [float(line[a:b]) for a,b in ((30,38),(38,46),(46,54))]})
    return rows


def diagnose(pose, smiles, reference=REFERENCE):
    import numpy as np
    from rdkit import Chem
    pose, reference = Path(pose), Path(reference)
    result = {'schema_version': 1, 'method': 'BRD4 mapped C-alpha Kabsch alignment and heavy-atom distances v1',
              'pose_sha256': digest(pose), 'reference_sha256': digest(reference),
              'reference_alternate_policy': 'Use blank or A altloc records; discard other reference alternates. Predicted alternate conformers are unsupported.',
              'thresholds': THRESHOLDS.copy(), 'limitation': LIMITATION}
    try:
        predicted, ref = atoms(pose.read_text()), atoms(reference.read_text(), reference=True)
        if not predicted or not all(np.isfinite(a['xyz']).all() for a in predicted+ref):
            raise ValueError('Empty pose or nonfinite coordinates')
        protein = [a for a in predicted if a['chain']=='A']
        ligand = [a for a in predicted if a['chain']=='L']
        reference_ligand = [a for a in ref if a['chain']=='A' and a['resname']=='ODR' and a['residue']==169]
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None or not protein or not ligand or not reference_ligand:
            raise ValueError('Expected a valid molecule, protein A, ligand L and reference ODR A169')
        if Counter(a['element'] for a in ligand) != Counter(a.GetSymbol() for a in molecule.GetAtoms() if a.GetAtomicNum()>1):
            raise ValueError('Ligand element composition differs from the input molecule')
        pca = [a for a in protein if a['name']=='CA']
        rca = [a for a in ref if a['chain']=='A' and a['name']=='CA' and 44<=a['residue']<=168]
        if len(pca)!=125 or len(rca)!=125 or {a['residue'] for a in pca}!=set(range(1,126)):
            raise ValueError('Expected 125 unique predicted C-alpha residues numbered 1–125')
        pca.sort(key=lambda a:a['residue']);rca.sort(key=lambda a:a['residue'])
        if [a['residue'] for a in rca]!=list(range(44,169)) or any(p['resname']!=r['resname'] for p,r in zip(pca,rca)):
            raise ValueError('Protein residue identities do not match BRD4 44–168')
        p=np.array([a['xyz'] for a in pca]);q=np.array([a['xyz'] for a in rca])
        pc,qc=p.mean(0),q.mean(0)
        u,_,vt=np.linalg.svd((p-pc).T@(q-qc));correction=np.eye(3);correction[2,2]=np.linalg.det(u@vt)
        rotation=u@correction@vt
        rmsd=float(np.sqrt(np.mean(np.sum(((p-pc)@rotation-(q-qc))**2,axis=1))))
        lig=np.array([a['xyz'] for a in ligand]);prot=np.array([a['xyz'] for a in protein])
        ref_lig=np.array([a['xyz'] for a in reference_ligand])
        centroid=float(np.linalg.norm(((lig-pc)@rotation+qc).mean(0)-ref_lig.mean(0)))
        distances=np.linalg.norm(lig[:,None,:]-prot[None,:,:],axis=2)
        close=np.argwhere(distances<THRESHOLDS['severe_contact_below_A'])
        nearby={}
        for index,atom in enumerate(protein):
            distance=float(distances[:,index].min())
            if distance<=THRESHOLDS['nearby_residue_within_A']:
                key=atom['residue'];old=nearby.get(key)
                if old is None or distance<old['minimum_distance_A']:
                    nearby[key]={'predicted_residue':key,'uniprot_residue':key+43,'resname':atom['resname'],'minimum_distance_A':round(distance,3)}
        flags=[]
        if len(close):flags.append('Very short protein–ligand contacts')
        if centroid>THRESHOLDS['pocket_centroid_beyond_A']:flags.append('Ligand centre far from the reference pocket')
        if rmsd>THRESHOLDS['protein_ca_rmsd_above_A']:flags.append('Protein differs substantially from the reference')
        # Transform the DIFFERENT reference ligand into the model frame for context.
        overlay=(ref_lig-qc)@rotation.T+pc
        lines=[]
        for atom,xyz in zip(reference_ligand,overlay):
            line=atom['line'];lines.append(line[:21]+'R'+line[22:30]+''.join(f'{v:8.3f}' for v in xyz)+line[54:])
        result.update(status='review' if flags else 'screen_clear', flags=flags,
            mapped_ca_count=125, protein_ca_rmsd_A=round(rmsd,4),
            ligand_centroid_distance_A=round(centroid,4), minimum_protein_ligand_distance_A=round(float(distances.min()),4),
            severe_contact_count=len(close), element_composition_matches=True,
            nearby_residues=sorted(nearby.values(),key=lambda r:r['minimum_distance_A']),
            reference_overlay_pdb='\n'.join(lines)+'\nEND\n',
            reference_note='Aligned experimental ODR from 3SVG, chain R in this overlay. Different ligand; context only.')
    except (ValueError, IndexError, KeyError) as exc:
        result.update(status='unavailable', reason=str(exc), flags=['Pose diagnostics could not be completed'])
    return result


def diagnose_generic(pose, smiles):
    """Target-independent atom identity and contact checks, without reference mapping."""
    import numpy as np
    from rdkit import Chem
    result = {'schema_version': 1, 'method': 'Ligand element composition and heavy-atom distances v1',
              'pose_sha256': digest(pose), 'thresholds': THRESHOLDS.copy(),
              'limitation': 'Limited atom and contact checks only. Reference alignment and pocket placement have not been checked for this imported target. Bonds, stereochemistry, cofactors and affinity are not validated.',
              'mapped_ca_count': 0, 'protein_ca_rmsd_A': None, 'ligand_centroid_distance_A': None,
              'reference_overlay_pdb': None, 'numbering': 'model'}
    try:
        predicted = atoms(Path(pose).read_text())
        protein = [a for a in predicted if a['chain'] == 'A']
        ligand = [a for a in predicted if a['chain'] == 'L']
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None or not protein or not ligand or not all(np.isfinite(a['xyz']).all() for a in predicted):
            raise ValueError('Expected finite protein A and ligand L coordinates')
        if Counter(a['element'] for a in ligand) != Counter(a.GetSymbol() for a in molecule.GetAtoms() if a.GetAtomicNum() > 1):
            raise ValueError('Ligand element composition differs from the input molecule')
        distances = np.linalg.norm(np.array([a['xyz'] for a in ligand])[:,None,:] - np.array([a['xyz'] for a in protein])[None,:,:], axis=2)
        close = int((distances < THRESHOLDS['severe_contact_below_A']).sum())
        nearby = {}
        for i,atom in enumerate(protein):
            distance = float(distances[:,i].min()); residue = atom['residue']
            if distance <= THRESHOLDS['nearby_residue_within_A'] and distance < nearby.get(residue, {}).get('minimum_distance_A', float('inf')):
                nearby[residue] = {'predicted_residue': residue, 'resname': atom['resname'], 'minimum_distance_A': round(distance,3)}
        result.update(status='review' if close else 'limited', flags=['Very short protein–ligand contacts'] if close else [],
            severe_contact_count=close, minimum_protein_ligand_distance_A=round(float(distances.min()),4),
            element_composition_matches=True, nearby_residues=sorted(nearby.values(),key=lambda r:r['minimum_distance_A']))
    except (ValueError, IndexError, KeyError) as exc:
        result.update(status='unavailable',reason=str(exc),flags=['Pose diagnostics could not be completed'])
    return result


def audit_saved(directory):
    """Write derived sidecars without modifying immutable model or job records."""
    directory=Path(directory).resolve()
    results=[]
    for record in sorted(directory.glob('*/job.json')):
        job=json.loads(record.read_text())
        for case in job['cases']:
            if case['status']!='complete' or not case.get('prediction'):continue
            base=(record.parent/case['id']).resolve()
            pose=(base/case['prediction']['pose']).resolve()
            if not base.is_relative_to(record.parent) or not pose.is_relative_to(base):
                raise ValueError('Artifact path escapes experiment')
            expected=next(a['sha256'] for a in case['prediction']['artifacts'] if a['file']==case['prediction']['pose'])
            if digest(pose)!=expected:raise ValueError('Pose artifact changed since inference')
            diagnostic=(diagnose if job.get('pose_check_mode','brd4')=='brd4' else diagnose_generic)(pose,case['smiles'])
            target=base/'pose_checks.json';temp=target.with_suffix('.tmp')
            temp.write_text(json.dumps(diagnostic,indent=2,allow_nan=False));temp.replace(target)
            results.append({'job':job['id'],'case':case['id'],'status':diagnostic['status']})
    return results


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    print(json.dumps(audit_saved(parser.parse_args().directory),indent=2))
