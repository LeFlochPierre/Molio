"""Small, transparent structural edits; not synthetic routes or ranked leads."""
from .proposals import available
from .edit_evidence import RULES, recognize

EDITS = (
    (RULES[0][1], RULES[0][2]),
    ('Alcohol → ketone', '[CH:1]([OH:2])([#6:3])[#6:4]>>[C:1](=[O:2])([#6:3])[#6:4]'),
    (RULES[1][1], RULES[1][2]),
    ('Carboxylic acid → ethyl ester', '[C:1](=[O:2])[OH:3]>>[C:1](=[O:2])[O:3]CC'),
)


def suggest(payload, dataset):
    if not isinstance(payload, dict) or set(payload) != {'parent_id'}:
        raise ValueError('Expected a parent_id only')
    parent = next((c for c in dataset['compounds'] if c['id']==payload['parent_id']), None)
    if parent is None:
        raise ValueError('Unknown measured parent')
    if not available():
        raise RuntimeError('Guided edits need the chemistry extra in the server environment.')
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdChemReactions
    original = Chem.MolFromSmiles(parent['smiles'])
    known = {}
    for c in dataset['compounds']:
        known.setdefault(Chem.MolToSmiles(Chem.MolFromSmiles(c['smiles'])), []).append(c['id'])
    seen, suggestions = set(), []
    for label, smarts in EDITS:
        with rdBase.BlockLogs():
            reaction = rdChemReactions.ReactionFromSmarts(smarts)
            for products in reaction.RunReactants((original,), maxProducts=16):
                if len(products) != 1:
                    continue
                molecule = products[0]
                try:
                    Chem.SanitizeMol(molecule)
                except ValueError:
                    continue
                for atom in molecule.GetAtoms():
                    atom.SetAtomMapNum(0)
                smiles = Chem.MolToSmiles(molecule)
                if smiles in seen or recognize(parent['smiles'], smiles) is None:
                    continue
                seen.add(smiles)
                suggestions.append(dict(label=label, smiles=smiles, known_compound_ids=known.get(smiles, []),
                    hypothesis=f'Does the {label.lower()} change alter IC50 when this molecule and its parent are tested side by side in the same target assay?'))
                if len(suggestions) == 8:
                    break
        if len(suggestions) == 8:
            break
    return dict(parent_id=parent['id'], suggestions=suggestions,
        note='Structural ideas only. No synthesis route, potency prediction, or ranking is implied. Stereochemistry still needs review.')
