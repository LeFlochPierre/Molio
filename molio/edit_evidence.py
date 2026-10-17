"""Evidence for bounded, explicitly recognized whole-molecule edits.

A single reaction must reproduce the proposal's complete connectivity. This is
not a fingerprint-based transfer of assay values or a general reaction model.
Stereochemical transfer is deliberately not asserted.
"""
from functools import lru_cache

RULES = (
    ('ketone_to_alcohol', 'Ketone → alcohol', '[C:1](=[O:2])([#6:3])[#6:4]>>[C:1]([O:2])([#6:3])[#6:4]'),
    ('ethyl_ester_to_acid', 'Ethyl ester → carboxylic acid', '[C:1](=[O:2])[O:3][CH2:4][CH3:5]>>[C:1](=[O:2])[OH:3]'),
)


def connectivity(molecule):
    from rdkit import Chem
    m = Chem.Mol(molecule)
    Chem.RemoveStereochemistry(m)
    for atom in m.GetAtoms():
        atom.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)


@lru_cache(maxsize=256)
def recognize(left_smiles, right_smiles):
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdChemReactions
    left, right = Chem.MolFromSmiles(left_smiles), Chem.MolFromSmiles(right_smiles)
    if left is None or right is None:
        return None
    if connectivity(left) == connectivity(right):
        return None
    for rule_id, label, smarts in RULES:
        with rdBase.BlockLogs():
            reaction = rdChemReactions.ReactionFromSmarts(smarts)
            for source, destination, direction in [(left, right, 1), (right, left, -1)]:
                for products in reaction.RunReactants((source,), maxProducts=32):
                    if len(products) != 1:
                        continue
                    product = products[0]
                    try:
                        Chem.SanitizeMol(product)
                    except ValueError:
                        continue
                    if connectivity(product) == connectivity(destination):
                        return dict(id=rule_id, label=label if direction == 1 else 'Reverse of ' + label.lower(), direction=direction)
    return None


def evidence_for_edit(left_smiles, right_smiles, dataset):
    from .evidence import compare_observations
    edit = recognize(left_smiles, right_smiles)
    base = dict(scope=f'{len(dataset["compounds"])} compounds and {len(dataset["pairs"])} comparisons from this workspace’s assay; no wider edit-evidence search has been run.',
                method='One recognized reaction must reproduce the complete molecular connectivity. Stereochemistry is not matched.',
                supported_edits=[r[1] for r in RULES], prediction=None, evidence=[])
    if not dataset.get('assay'):
        base['scope'] = 'No measured activity has been imported into this workspace. These are structural ideas only.'
    if edit is None:
        return dict(base, status='unsupported_or_no_match', edit=None,
                    summary='No supported edit evidence found in this small library.',
                    next_experiment='If this is a meaningful chemical change, measure the proposal alongside its parent in the same assay. Missing evidence does not imply inactivity.')
    compounds = {c['id']: c for c in dataset['compounds']}
    rows = []
    for pair in dataset['pairs']:
        left, right = compounds[pair['left']], compounds[pair['right']]
        known = recognize(left['smiles'], right['smiles'])
        if known is None or known['id'] != edit['id']:
            continue
        if known['direction'] != edit['direction']:
            left, right = right, left
        measured = compare_observations(left['observation'], right['observation'])
        rows.append(dict(pair_id=pair['id'], left_id=left['id'], right_id=right['id'],
                         left_observation=left['observation'], right_observation=right['observation'],
                         left_source=left['source_url'], right_source=right['source_url'], **measured))
    lower = sum(r['fold_lower_ic50_right'] > 1 for r in rows)
    higher = sum(r['fold_lower_ic50_right'] < 1 for r in rows)
    unchanged = len(rows) - lower - higher
    if rows:
        if lower == len(rows) or higher == len(rows):
            direction = 'lower' if lower else 'higher'
            summary = f'IC50 was {direction} after this edit in {len(rows)} measured comparison' + ('s.' if len(rows) != 1 else '.')
        else:
            summary = f'The results differ: {lower} comparisons had lower IC50, {higher} higher, and {unchanged} unchanged.'
        summary += ' These examples share one assay and publication; they are not independent replications.'
    else:
        summary = 'This edit is recognized, but no comparable measurement was found in the local library.'
    return dict(base, status='evidence_found' if rows else 'no_observations', edit=edit, evidence=rows,
                summary=summary, counts=dict(lower=lower, higher=higher, unchanged=unchanged),
                next_experiment='Measure the proposal and its parent side by side using the same target assay, with replicates. Include a known transformation pair as a reference control. Test whether the direction transfers to this chemical context; do not assume its magnitude will.',
                limitation='These observations support a testable hypothesis, not a potency prediction. Structural contacts do not establish a mechanism.')
