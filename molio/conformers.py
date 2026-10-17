"""Deterministic, bounded free-molecule conformers, never protein-bound poses."""
from functools import lru_cache


@lru_cache(maxsize=128)
def conformer(smiles):
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem
    m = Chem.MolFromSmiles(smiles)
    if m is None or m.GetNumAtoms() > 100:
        return dict(status='unavailable', molblock=None, reason='Invalid or oversized molecule')
    unassigned = sum(tag == '?' for _, tag in Chem.FindMolChiralCenters(m, includeUnassigned=True))
    m = Chem.AddHs(m)
    settings = AllChem.ETKDGv3()
    settings.randomSeed = 42
    settings.maxIterations = 100
    with rdBase.BlockLogs():
        status = AllChem.EmbedMolecule(m, settings)
        if status != 0:
            return dict(status='unavailable', molblock=None, reason='Conformer embedding failed; the 2D structure remains available')
        optimization = None
        if AllChem.MMFFHasAllMoleculeParams(m):
            optimization = AllChem.MMFFOptimizeMolecule(m, maxIters=150)
    m = Chem.RemoveHs(m)
    return dict(status='generated', molblock=Chem.MolToMolBlock(m), method='RDKit ETKDGv3, seed 42; MMFF optimization up to 150 iterations',
                optimization_converged=optimization == 0, rdkit_version=rdBase.rdkitVersion,
                provenance='Generated free-molecule conformer. Not an experimental or predicted bound pose.',
                stereochemistry_note='Unspecified tetrahedral stereochemistry: the displayed shape is one illustrative realization.' if unassigned else None)
