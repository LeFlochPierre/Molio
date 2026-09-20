import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
try:
    import numpy as np
except ImportError:
    np = None
if np is not None:
    from cyp_pipeline import pose_sampling as ps


def source():
    m = json.loads(Path('prepared/exchange-pilot-v1/manifest.json').read_text())
    for parts in m['enzymes'].values():
        for name,s in parts.items():
            if name.startswith('cluster_'): s['audit_bonds'] = s['covalent_bounds'][:1]
            if name=='free_water':
                o=next(a['id'] for a in s['atoms'] if a['element']=='O')
                s['covalent_bounds']=[dict(ids=[o,a['id']],min_A=.7,max_A=1.4) for a in s['atoms'] if a['element']=='H']
    return m


@unittest.skipIf(np is None, 'Optional NumPy pose-sampling dependency is not installed')
class PoseTests(unittest.TestCase):
    def test_default_grid_and_validation(self):
        c=ps.configuration(); seeds=ps.seed_grid(c)
        self.assertEqual(len(seeds),120)
        self.assertEqual(len({(s['rotation_deg'],s['tilt_deg']) for s in seeds}),120)
        self.assertEqual({s['tilt_deg'] for s in seeds},{-20,-10,0,10,20})
        self.assertNotIn(360,{s['rotation_deg'] for s in seeds})
        for bad in ({'rotation_step_deg':0},{'temperature_K':float('nan')},{'rotation_stop_deg':361},{'per_enzyme':{}}):
            with self.assertRaises(ValueError): ps.configuration(bad)

    def test_grid_preserves_donor_scaffold_distances_and_stereochemistry(self):
        s=source()['enzymes']['CYP11B1']['cluster_ligand']; p={a['id']:a['position'] for a in s['atoms']}
        guest=[a['id'] for a in s['atoms'] if a['id'] not in s['scaffold_ids']]
        for seed in ps.seed_grid(ps.configuration()):
            pose=ps.make_pose(s,seed); q={a['id']:a['position'] for a in pose['atoms']}
            for i in s['scaffold_ids']+['ligand_N06']: self.assertEqual(p[i],q[i])
            for i in guest:
                for j in guest: self.assertAlmostEqual(math.dist(p[i],p[j]),math.dist(q[i],q[j]),places=10)
            self.assertEqual(ps.audit(pose['atoms'],s),[])

    def test_dedup_and_stable_boltzmann(self):
        s=source()['enzymes']['CYP11B1']['cluster_ligand']; a=copy.deepcopy(s['atoms']); b=copy.deepcopy(a)
        for atom in b:
            if atom['id'] not in s['scaffold_ids']: atom['position'][0]+=5
        def record(i,e,atoms): return dict(seed_id=i,status='accepted',energy_eV=e,atoms=atoms)
        rows=[record('a',-100000,a),record('duplicate',-99999.99,a),record('b',-99999.98,b)]
        result=ps.ensemble(rows,s,ps.configuration())
        self.assertEqual(result['minima_count'],2)
        ratio=math.exp(-.02/(ps.KB_EV_K*310))
        self.assertAlmostEqual(result['minima'][1]['population'],ratio/(1+ratio),places=9)
        self.assertAlmostEqual(result['boltzmann_energy_eV'],-100000+.02*ratio/(1+ratio),places=8)
        self.assertEqual(result['minima'][0]['members'],['a','duplicate'])
        self.assertIsNone(ps.ensemble([],s,ps.configuration()))

    def test_scaffold_alignment_does_not_fit_ligand_away(self):
        s=source()['enzymes']['CYP11B1']['cluster_ligand']; a=s['atoms']; b=copy.deepcopy(a)
        r=ps.rotation([1,2,3],75)
        for atom in b: atom['position']=(r@atom['position']+np.array([3,5,7])).tolist()
        self.assertLess(ps.heavy_rmsd(a,b,s['scaffold_ids']),1e-10)
        for atom in b:
            if atom['id'] not in s['scaffold_ids']: atom['position'][0]+=5
        self.assertGreater(ps.heavy_rmsd(a,b,s['scaffold_ids']),.25)

    def test_audits_detect_fixed_bond_coordination_chirality(self):
        s=source()['enzymes']['CYP11B1']['cluster_ligand']; a=copy.deepcopy(s['atoms'])
        next(x for x in a if x['id']==s['fixed_ids'][0])['position'][0]+=1
        self.assertTrue(any('fixed_boundary' in x for x in ps.audit(a,s)))
        a=copy.deepcopy(s['atoms']); next(x for x in a if x['id']=='ligand_N06')['position'][0]+=20
        errors=ps.audit(a,s)
        self.assertTrue(any('coordination' in x for x in errors)); self.assertTrue(any('bond_integrity' in x for x in errors))
        a=copy.deepcopy(s['atoms']); p={x['id']:x for x in a}; checks=s['chirality_checks'][0]; i,j=checks['neighbors'][:2]
        p[i]['position'],p[j]['position']=p[j]['position'],p[i]['position']
        self.assertTrue(any('stereochemistry' in x for x in ps.audit(a,s)))

    def test_run_symmetric_resume_and_failure_logging(self):
        m=source(); settings={'rotation_stop_deg':30,'tilt_start_deg':0,'tilt_stop_deg':0}
        class Backend: metadata={'synthetic':True}
        calls=[]
        def relaxation(backend,atoms,state,fixed,protocol,folder):
            calls.append((copy.deepcopy(state),fixed,protocol))
            if len(calls)==1: raise ValueError('injected failure')
            return dict(atoms=atoms,energy_eV=-100.,converged=True,history=[])
        with tempfile.TemporaryDirectory() as d, patch('cyp_pipeline.ase_relax.relax_bfgs',relaxation):
            out=Path(d)/'run'; r=ps.run_search(m,Backend(),out,settings)
            self.assertEqual(len(calls),12)  # Six unique components, two seeds.
            self.assertEqual(r['completed_seed_count'],2)
            self.assertIsNone(r['energy_model_preference'])
            for state,fixed,protocol in calls: self.assertEqual(protocol,m['optimizer'])
            rejection=json.loads((out/'CYP11B1/cluster_ligand/pose_0000/result.json').read_text())
            self.assertEqual(rejection['status'],'rejected'); self.assertIn('injected failure',str(rejection['reasons']))
            rerun=ps.run_search(m,Backend(),out,settings,resume=True)
            self.assertEqual(len(calls),12); self.assertEqual(r,rerun)
            with self.assertRaises(ValueError): ps.run_search(m,Backend(),out,{**settings,'temperature_K':300},resume=True)
            self.assertEqual(len(json.loads((out/'convergence.json').read_text())),2)

    def test_spread_suppresses_direction(self):
        m=source(); histories={e:{} for e in ps.ENZYMES}
        for e in ps.ENZYMES:
            for k in ps.COMPONENTS:
                a=m['enzymes'][e][k]['atoms']
                histories[e][k]=[dict(seed_id='a',status='accepted',atoms=a,energy_eV=-100),dict(seed_id='b',status='accepted',atoms=a,energy_eV=-99)]
        r=ps.summarize(m,histories,ps.configuration(),2)
        self.assertEqual(r['status'],'unresolved');self.assertIsNone(r['energy_model_preference'])
        self.assertEqual(r['pose_to_pose_delta_spread_eV'],4)

if __name__=='__main__': unittest.main()
