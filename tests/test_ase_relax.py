import importlib.util
import tempfile
import unittest
from pathlib import Path
from cyp_pipeline.ase_relax import relax_bfgs
from cyp_pipeline.backends import HarmonicDemo

@unittest.skipUnless(importlib.util.find_spec('ase'), 'ASE required')
class BFGSTests(unittest.TestCase):
    def test_fixed_atoms_and_physical_energy(self):
        atoms=[{'id':'fixed','element':'H','position':[0.,0.,0.],'demo_target':[1.,0.,0.]},
               {'id':'free','element':'H','position':[3.,0.,0.],'demo_target':[2.,0.,0.]}]
        protocol={'max_step_A':0.1,'force_tolerance_eV_A':0.001,'max_steps':100}
        with tempfile.TemporaryDirectory() as folder:
            r=relax_bfgs(HarmonicDemo(),atoms,{},['fixed'],protocol,Path(folder))
            self.assertTrue(r['converged'])
            self.assertEqual(r['atoms'][0]['position'],[0.,0.,0.])
            self.assertAlmostEqual(r['energy_eV'],0.5,places=5)
            self.assertAlmostEqual(r['atoms'][1]['position'][0],2.,places=3)
