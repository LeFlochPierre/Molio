"""Bounded one-step design ideas retaining the parent's ring scaffold."""
import hashlib
from .proposals import available, analyze

# Deliberately narrow edits. These are structure transformations, not reaction routes.
RULES = (
    ('shorten_ether', 'Ethoxy → methoxy', '[c:1][O:2][CH2:3][CH3:4]>>[c:1][O:2][CH3:3]',
     'Shorten an aromatic ether side chain by one carbon.'),
    ('shorten_ester', 'Ethyl ester → methyl ester', '[C:1](=[O:2])[O:3][CH2:4][CH3:5]>>[C:1](=[O:2])[O:3][CH3:4]',
     'Shorten the ester alkyl group while retaining the ester.'),
    ('extend_ether', 'Methoxy → ethoxy', '[c:1][O:2][CH3:3]>>[c:1][O:2][CH2:3]C',
     'Extend an aromatic ether side chain by one carbon.'),
    ('aryl_fluorine', 'Aromatic H → F', '[cH:1]>>[c:1]F',
     'Replace one aromatic hydrogen with fluorine; each position is a separate idea.'),
)


def explore(payload, dataset):
    if not isinstance(payload, dict) or set(payload)!={'parent_id'}:
        raise ValueError('Expected parent_id only')
    parent=next((c for c in dataset['compounds'] if c['id']==payload['parent_id']),None)
    if parent is None:raise ValueError('Choose a measured parent')
    if not available():raise RuntimeError('Explore variations requires the chemistry extra')
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdChemReactions, Descriptors, rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold
    mol=Chem.MolFromSmiles(parent['smiles'])
    canonical=Chem.MolToSmiles(mol)
    scaffold=Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(mol))
    known={Chem.MolToSmiles(Chem.MolFromSmiles(c['smiles'])):c['id'] for c in dataset['compounds']}
    def properties(m):
        return {'molecular_weight':round(Descriptors.MolWt(m),2),'clogp':round(Descriptors.MolLogP(m),2),
                'tpsa':round(rdMolDescriptors.CalcTPSA(m),2)}
    candidates=[];seen={canonical}
    for rule_id,label,smarts,reason in RULES:
        with rdBase.BlockLogs():
            reaction=rdChemReactions.ReactionFromSmarts(smarts)
            products=reaction.RunReactants((mol,),maxProducts=16)
            for product in products:
                if len(product)!=1:continue
                m=product[0]
                try:Chem.SanitizeMol(m)
                except ValueError:continue
                for atom in m.GetAtoms():atom.SetAtomMapNum(0)
                smiles=Chem.MolToSmiles(m)
                if smiles in seen or len(Chem.GetMolFrags(m))!=1 or m.GetNumHeavyAtoms()>80:continue
                if Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(m))!=scaffold:continue
                seen.add(smiles)
                identifier=hashlib.sha256((parent['id']+'|'+rule_id+'|'+smiles).encode()).hexdigest()[:20]
                candidates.append({'id':identifier,'rule':rule_id,'label':label,'reason':reason,'smiles':smiles,
                    'descriptors':properties(m),'known_compound_id':known.get(smiles),'activity':None,
                    'hypothesis':f'Does {label.lower()} change affinity relative to {parent["id"]}? Compare matched model seeds, then test both molecules in the same assay.'})
                if len(candidates)>=8:break
        if len(candidates)>=8:break
    return {'parent_id':parent['id'],'parent_descriptors':properties(mol),'candidates':candidates,
            'scope':'Up to eight one-step structural ideas with the same ring scaffold. No synthesis route, potency improvement or novelty beyond the local library is claimed.'}


def shortlist(payload, dataset, store):
    if not isinstance(payload,dict) or set(payload)!={'parent_id','design_ids'}:
        raise ValueError('Expected parent_id and design_ids')
    ids=payload['design_ids']
    if not isinstance(ids,list) or not 1<=len(ids)<=2 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('Choose one or two distinct designs; the parent is the baseline')
    generated=explore({'parent_id':payload['parent_id']},dataset)
    known={c['id']:c for c in generated['candidates']}
    if any(i not in known for i in ids):raise ValueError('Unknown design for this parent; regenerate the ideas')
    selected=[known[i] for i in ids]
    # Recompute on the server; client cannot inject chemistry, scores or provenance.
    analyses=[]
    for design in selected:
        if design['known_compound_id']:continue
        result=analyze({'parent_id':payload['parent_id'],'smiles':design['smiles'],
                        'name':design['label']+' · '+design['id'][:6], 'hypothesis':design['hypothesis']},dataset)
        result['design_origin']={'rule':design['rule'],'design_id':design['id'],'scope':generated['scope']}
        analyses.append(result)
    saved=iter(store.save_batch(analyses))
    candidate_ids=[payload['parent_id']]
    for design in selected:
        candidate_ids.append(design['known_compound_id'] or next(saved)['id'])
    return {'candidate_ids':candidate_ids,'parent_id':payload['parent_id'],'prediction_started':False}
