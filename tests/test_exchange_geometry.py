import unittest
from cyp_pipeline.exchange import structure_valid

class GeometryGuards(unittest.TestCase):
    def test_chiral_inversion_and_bond_break_rejected(self):
        atoms=[{'id':'c','position':[0,0,0]}, {'id':'a','position':[1,0,0]},
               {'id':'b','position':[0,1,0]}, {'id':'d','position':[0,0,1]}]
        settings={'chirality_checks':[{'center':'c','neighbors':['a','b','d'],'reference_volume_A3':1}],
                  'covalent_bounds':[{'ids':['c','a'],'min_A':0.8,'max_A':1.2}]}
        self.assertTrue(structure_valid(atoms,settings))
        atoms[-1]['position']=[0,0,-1]
        self.assertFalse(structure_valid(atoms,settings))
        atoms[-1]['position']=[0,0,1];atoms[1]['position']=[3,0,0]
        self.assertFalse(structure_valid(atoms,settings))
