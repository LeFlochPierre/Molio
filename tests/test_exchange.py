import copy
import json
from pathlib import Path
import tempfile
import unittest
from cyp_pipeline.core import ValidationError
from cyp_pipeline.exchange import COMPONENTS, ENZYMES, exchange_energy, run_cycle, validate_manifest


def fixture():
    def atom(i, el, pos): return {'id': i, 'element': el, 'position': pos}
    scaffold = [atom('fe','Fe',[0,0,0]),atom('s','S',[0,0,-2.3])]
    ligand = [atom('n','N',[0,0,2.2]),atom('h','H',[0,0,3.2])]
    water = [atom('o','O',[0,0,2.2]),atom('h1','H',[0.8,0,2.8]),atom('h2','H',[-0.8,0,2.8])]
    def component(atoms, cluster=False, donor=None):
        d = {'atoms':copy.deepcopy(atoms), 'state':{'charge':0,'multiplicity':1,'convention':'synthetic fixture'},
             'review':{'provisional':True}, 'preparation':'Synthetic test only', 'fixed_ids':[]}
        if cluster:
            d.update(scaffold_ids=['fe','s'], fixed_ids=['s'], coordination=[
                {'ids':['fe',donor],'min_A':2,'max_A':2.5}, {'ids':['fe','s'],'min_A':2,'max_A':2.5}])
        return d
    parts = {'cluster_ligand':component(scaffold+ligand,True,'n'),
             'cluster_water':component(scaffold+water,True,'o'),
             'free_water':component(water), 'free_ligand':component(ligand)}
    return {'schema_version':1,'ligand':'synthetic','preparation_protocol':'test',
            'geometry_mode':'relax', 'optimizer':json.loads(Path('configs/protocol.json').read_text()),
            'enzymes':{e:copy.deepcopy(parts) for e in ENZYMES}}


class Backend:
    metadata = {'name':'test', 'synthetic':True}
    def __init__(self, fail=False): self.calls=0; self.fail=fail
    def evaluate(self, atoms, state):
        energies = [-100, -10, -90, -15, -103, -10, -90, -15]
        n=self.calls; self.calls+=1
        if self.fail and n == 2: raise ValueError('injected failure')
        return energies[n], [[0,0,0] for a in atoms]


class ExchangeTests(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(exchange_energy(dict(zip(COMPONENTS,[-100,-10,-90,-15]))), -5)
        with self.assertRaises(ValidationError): exchange_energy({'cluster_ligand':1})

    def test_eight_outputs_and_sign(self):
        with tempfile.TemporaryDirectory() as d:
            backend=Backend(); r=run_cycle(fixture(),backend,Path(d)/'run')
            self.assertEqual(backend.calls,8)
            self.assertEqual(r['enzymes']['CYP11B1']['exchange_energy_eV'],-5)
            self.assertEqual(r['delta_B2_minus_B1_eV'],-3)
            self.assertEqual(r['status'],'synthetic_demo')
            self.assertIsNone(r['energy_model_preference'])
            self.assertEqual(len(list((Path(d)/'run').glob('*/*/result.json'))),8)

    def test_missing_unbalanced_and_reference_mismatch(self):
        mutations = [lambda m:m['enzymes']['CYP11B1'].pop('free_water'),
                     lambda m:m['enzymes']['CYP11B1']['free_ligand']['atoms'].pop(),
                     lambda m:m['enzymes']['CYP11B1']['cluster_water']['state'].update(charge=1),
                     lambda m:m['enzymes']['CYP11B1']['free_water']['atoms'][0].update(position=[1,1,1]),
                     lambda m:m['enzymes']['CYP11B1']['cluster_water'].update(fixed_ids=[])]
        for mutate in mutations:
            m=fixture();mutate(m)
            with self.assertRaises(ValidationError): validate_manifest(m)

    def test_failure_does_not_produce_selectivity(self):
        with tempfile.TemporaryDirectory() as d:
            r=run_cycle(fixture(),Backend(fail=True),Path(d)/'run')
            self.assertEqual(r['status'],'unresolved')
            self.assertIsNone(r['delta_B2_minus_B1_eV'])
            self.assertEqual(len(list((Path(d)/'run').glob('*/*/result.json'))),8)

    def test_nonconvergence_does_not_score(self):
        class Stuck:
            metadata={'synthetic':True}
            def evaluate(self, atoms, state): return 0, [[1,0,0] for a in atoms]
        with tempfile.TemporaryDirectory() as d:
            r=run_cycle(fixture(),Stuck(),Path(d)/'run')
            self.assertEqual(r['status'],'unresolved')
            self.assertIsNone(r['delta_B2_minus_B1_eV'])

    def test_invalid_coordination_does_not_score(self):
        m=fixture();m['enzymes']['CYP11B1']['cluster_ligand']['atoms'][2]['position']=[0,0,20]
        with tempfile.TemporaryDirectory() as d:
            r=run_cycle(m,Backend(),Path(d)/'run')
            self.assertEqual(r['status'],'unresolved')
            self.assertIsNone(r['delta_B2_minus_B1_eV'])
