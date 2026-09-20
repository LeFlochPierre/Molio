"""Build a portable, offline demo from the downloaded PDBs and saved test results."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dist(a, b):
    return math.dist(a['p'], b['p'])


def structure(pdb, ligand):
    raw = (ROOT / 'data/raw' / (pdb + '.pdb')).read_bytes()
    atoms = []
    for line in raw.decode().splitlines():
        if not line.startswith(('ATOM  ', 'HETATM')) or line[21] != 'A' or line[16] not in (' ', 'A'):
            continue
        element = line[76:78].strip().upper()
        if element in ('H', 'D') or line[17:20] == 'HOH':
            continue
        atoms.append({'id': int(line[6:11]), 'name': line[12:16].strip(), 'res': line[17:20].strip(),
                      'num': line[22:27].strip(), 'e': element,
                      'p': [float(line[30:38]), float(line[38:46]), float(line[46:54])]})
    lig = [a for a in atoms if a['res'] == ligand]
    heme = [a for a in atoms if a['res'] == 'HEM']
    fe = next(a for a in heme if a['e'] == 'FE')
    donor = min((a for a in lig if a['e'] == 'N'), key=lambda a: dist(a, fe))
    sulfur = min((a for a in atoms if a['res'] == 'CYS' and a['e'] == 'S'), key=lambda a: dist(a, fe))
    residue_ids = {(a['res'], a['num']) for a in atoms if a['res'] not in ('HEM', ligand)
                   and any(dist(a, b) <= 5.0 for b in lig)}
    pocket = [a for a in atoms if (a['res'], a['num']) in residue_ids or
              (a['res'], a['num']) == (sulfur['res'], sulfur['num'])]
    visible = []
    for group, members in [('pocket', pocket), ('heme', heme), ('ligand', lig)]:
        visible.extend({**a, 'group': group} for a in members)
    # Bonds are display hints, not a prepared chemical topology.
    radius = {'C': .76, 'N': .71, 'O': .66, 'S': 1.05, 'FE': 1.32}
    bonds = []
    for i, a in enumerate(visible):
        for j in range(i):
            b = visible[j]
            if a['group'] != b['group'] or a['e'] == 'FE' or b['e'] == 'FE':
                continue
            if .5 < dist(a,b) < radius.get(a['e'],.75) + radius.get(b['e'],.75) + .35:
                bonds.append([i,j])
    backbone = [a['p'] for a in atoms if a['name'] == 'CA' and a['res'] not in ('HEM',ligand)]
    return {'pdb': pdb, 'chain': 'A', 'ligandCode': ligand, 'atoms': visible, 'bonds': bonds,
            'backbone': backbone, 'center': fe['p'], 'fe': fe, 'donor': donor, 'sulfur': sulfur,
            'feN': dist(fe,donor), 'feS': dist(fe,sulfur), 'pocketResidues':len(residue_ids),
            'sha256': hashlib.sha256(raw).hexdigest(), 'source': 'https://www.rcsb.org/structure/'+pdb}


def main():
    data = {'B1': structure('6M7X','JD7'), 'B2': structure('4FDH','0T3')}
    summary = json.loads((ROOT/'runs/demo-v2/summary.json').read_text())
    data['synthetic'] = [{'ligand':r['ligand'], 'isoform':r['isoform'], 'score':r['descriptor_eV']}
                         for r in summary['results']]
    template = (ROOT/'demo/template.html').read_text()
    (ROOT/'demo/index.html').write_text(template.replace('__DEMO_DATA__', json.dumps(data).replace('</','<\\/')))
    print('Built demo/index.html — offline, embedded real PDB coordinates')


if __name__ == '__main__': main()
