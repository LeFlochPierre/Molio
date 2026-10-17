import tempfile
import json
from pathlib import Path
import unittest

from molecular_lab.pose_checks import atoms, diagnose, REFERENCE, audit_saved, digest
from molecular_lab.proposals import available
from molecular_lab.server import load_dataset


@unittest.skipUnless(available(),'RDKit and NumPy required')
class PoseCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.pose=Path(self.temp.name)/'pose.pdb'
        self.smiles=next(c['smiles'] for c in load_dataset()['compounds'] if c['id']=='CHEMBL1828986')
        self.lines=[]
        for a in atoms(REFERENCE.read_text(),reference=True):
            line=a['line']
            if a['chain']=='A' and line.startswith('ATOM') and 44<=a['residue']<=168:
                self.lines.append(line[:16]+' '+line[17:22]+f"{a['residue']-43:4}"+line[26:])
            elif a['resname']=='ODR' and a['chain']=='A':
                self.lines.append(line[:16]+' '+line[17:21]+'L'+line[22:])
        self.write(self.lines)

    def write(self,lines):self.pose.write_text('\n'.join(lines)+'\n')

    def test_reference_mapping_and_rigid_transform_invariance(self):
        result=diagnose(self.pose,self.smiles)
        self.assertEqual(result['status'],'screen_clear',result)
        self.assertEqual(result['mapped_ca_count'],125)
        self.assertAlmostEqual(result['protein_ca_rmsd_A'],0)
        self.assertAlmostEqual(result['ligand_centroid_distance_A'],0)
        transformed=[]
        for line in self.lines:
            x,y,z=[float(line[a:b]) for a,b in ((30,38),(38,46),(46,54))]
            transformed.append(line[:30]+f'{-y+10:8.3f}{x-15:8.3f}{z+3:8.3f}'+line[54:])
        self.write(transformed);moved=diagnose(self.pose,self.smiles)
        self.assertEqual(moved['status'],'screen_clear')
        self.assertAlmostEqual(moved['protein_ca_rmsd_A'],0)
        self.assertAlmostEqual(moved['ligand_centroid_distance_A'],0)
        overlay=atoms(moved['reference_overlay_pdb']);ligand=[a for a in atoms(self.pose.read_text()) if a['chain']=='L']
        self.assertEqual(len(overlay),len(ligand))
        for a,b in zip(overlay,ligand):
            for x,y in zip(a['xyz'],b['xyz']):self.assertAlmostEqual(x,y,places=3)

    def test_outside_pocket_and_severe_overlap(self):
        translated=[]
        for line in self.lines:
            if line[21]=='L':line=line[:30]+f'{float(line[30:38])+25:8.3f}'+line[38:]
            translated.append(line)
        self.write(translated);result=diagnose(self.pose,self.smiles)
        self.assertEqual(result['status'],'review')
        self.assertGreater(result['ligand_centroid_distance_A'],20)
        overlapping=list(self.lines);index=next(i for i,l in enumerate(overlapping) if l[21]=='L')
        overlapping[index]=overlapping[index][:30]+overlapping[0][30:54]+overlapping[index][54:]
        self.write(overlapping);result=diagnose(self.pose,self.smiles)
        self.assertGreater(result['severe_contact_count'],0)
        self.assertIn('Very short protein–ligand contacts',result['flags'])

    def test_audit_preserves_native_records_and_checks_artifact_hash(self):
        root=Path(self.temp.name)/'experiments';base=root/'job'/'case';base.mkdir(parents=True)
        pose=base/'pose.pdb';pose.write_text(self.pose.read_text())
        job={'id':'job','cases':[{'id':'case','status':'complete','smiles':self.smiles,
             'prediction':{'pose':'pose.pdb','artifacts':[{'file':'pose.pdb','sha256':digest(pose)}]}}]}
        record=base.parent/'job.json';record.write_text(json.dumps(job));before=record.read_bytes()
        audit_saved(root)
        self.assertEqual(record.read_bytes(),before)
        self.assertEqual(json.loads((base/'pose_checks.json').read_text())['status'],'screen_clear')
        pose.write_text(pose.read_text()+'REMARK changed\n')
        with self.assertRaisesRegex(ValueError,'changed since inference'):audit_saved(root)

    def test_mismatch_and_nonfinite_cannot_pass(self):
        bad=list(self.lines);bad[0]=bad[0][:17]+'ALA'+bad[0][20:]
        # Alter the C-alpha identity too; mapping uses explicit C-alpha residue names.
        index=next(i for i,l in enumerate(bad) if l[12:16].strip()=='CA')
        bad[index]=bad[index][:17]+'ALA'+bad[index][20:]
        self.write(bad);self.assertEqual(diagnose(self.pose,self.smiles)['status'],'unavailable')
        self.write(self.lines);self.assertEqual(diagnose(self.pose,'CC')['status'],'unavailable')
        bad=list(self.lines);bad[0]=bad[0][:30]+'     nan'+bad[0][38:]
        self.write(bad);self.assertEqual(diagnose(self.pose,self.smiles)['status'],'unavailable')

if __name__=='__main__':unittest.main()
