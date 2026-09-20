"""Bounded, identity-checked reference downloads. No model inference or chemistry repair."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .benchmark_boltz import AMINO_ACIDS

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = json.loads((Path(__file__).with_name('data') / 'structure_catalog.json').read_text())
MAX_DOWNLOAD = 8 * 1024 * 1024


def inspect_reference(raw, spec):
    lines = raw.decode('ascii').splitlines()
    if not lines or not lines[0].startswith('HEADER') or lines[0][62:66].strip() != spec['pdb']:
        raise ValueError('Downloaded file has the wrong PDB identifier')
    refs = [line for line in lines if line.startswith('DBREF ') and line[12:13] == spec['chain']]
    if not refs or any(line[33:41].strip() != spec['accession'] for line in refs):
        raise ValueError('Protein accession / chain does not match the curated reference')
    rows = [line for line in lines if line.startswith('SEQRES') and line[11:12] == spec['chain']]
    residues = [residue for line in rows for residue in line[19:70].split()]
    if not residues or {int(line[13:17]) for line in rows} != {len(residues)}:
        raise ValueError('Incomplete SEQRES sequence')
    try:
        sequence = ''.join(AMINO_ACIDS[r] for r in residues)
    except KeyError as error:
        raise ValueError('Nonstandard construct residues need review') from error
    observed = {line[17:20].strip() for line in lines if line.startswith('HETATM') and line[21:22] == spec['chain']}
    if not {'HEM', spec['ligand_code']} <= observed:
        raise ValueError('Expected heme / reference ligand not found in the selected chain')
    return {'sequence': sequence, 'sequence_source': 'PDB SEQRES experimental construct; includes deposited tags / modifications',
            'dbref': [line.strip() for line in refs],
            'sequence_modifications': [line.strip() for line in lines if line.startswith('SEQADV') and line[16:17] == spec['chain']],
            'sha256': hashlib.sha256(raw).hexdigest()}


def get_reference(target, root=ROOT, download=False):
    if target not in REFERENCES:
        return {'status': 'unmapped', 'target_id': target, 'reason': 'No curated structure mapping for this target.'}
    spec = REFERENCES[target]
    path = Path(root) / 'data/raw' / (spec['pdb'] + '.pdb')
    url = f"https://files.rcsb.org/download/{spec['pdb']}.pdb"
    try:
        if path.exists():
            raw = path.read_bytes()
        elif download:
            with urlopen(Request(url, headers={'User-Agent': 'IsoForm-research/1.0'}), timeout=20) as response:
                raw = response.read(MAX_DOWNLOAD + 1)
            if len(raw) > MAX_DOWNLOAD:
                raise ValueError('Reference download exceeds 8 MiB')
            inspect_reference(raw, spec)  # Never cache an error page or a different protein.
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open('xb') as handle:
                    handle.write(raw)
            except FileExistsError:
                raw = path.read_bytes()  # Another request populated the cache.
        else:
            return {'status': 'download_available', 'target_id': target, **spec, 'source_url': url}
        metadata = inspect_reference(raw, spec)
        return {'status': 'available', 'target_id': target, **spec, **metadata,
                'source_url': url, 'citation_url': f"https://www.rcsb.org/structure/{spec['pdb']}",
                'path': str(path.relative_to(root))}
    except (OSError, ValueError, UnicodeError) as error:
        return {'status': 'unavailable', 'target_id': target, **spec, 'reason': str(error), 'source_url': url}


def library(root=ROOT, download=False, targets=None):
    keys = list(REFERENCES if targets is None else dict.fromkeys(targets))
    with ThreadPoolExecutor(max_workers=5) as pool:
        return dict(zip(keys, pool.map(lambda key: get_reference(key, root, download), keys)))


def reference_views(root=ROOT):
    from .sentinel_demo import structure_view
    result = {}
    for target, row in library(root).items():
        if row['status'] != 'available':
            continue
        try:
            view = structure_view(Path(root) / row['path'], row['chain'], row['ligand_code'])
        except ValueError:
            continue
        view.update(ligand_label=row['ligand_label'], source_url=row['citation_url'], sha256=row['sha256'])
        result[target] = view
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Fetch only missing curated PDB files from RCSB')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    rows = library(args.root, args.download)
    for key, row in rows.items():
        print(f"{key}: {row['status']} · {row.get('pdb', '')} · {row.get('reason', row.get('sha256', ''))}")
    return 0 if all(r['status'] == 'available' for r in rows.values()) else 2


if __name__ == '__main__':
    raise SystemExit(main())
