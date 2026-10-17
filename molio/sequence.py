"""Map PDB sequence records to an explicitly requested UniProt region."""
import hashlib
from pathlib import Path

AMINO_ACIDS = dict(zip(
    'ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split(),
    'ARNDCQEGHILKMFPSTWYV',
))

def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def domain_sequence(pdb_path, accession, *, start, end, chain='A'):
    """Map continuous SEQRES using explicit DBREF and expression-tag metadata."""
    lines = Path(pdb_path).read_text().splitlines()
    rows = [line for line in lines if line.startswith('SEQRES') and line[11:12] == chain]
    if not rows:
        raise ValueError(f'No SEQRES chain {chain}: {pdb_path}')
    residues = [residue for row in rows for residue in row[19:70].split()]
    if {int(row[13:17]) for row in rows} != {len(residues)}:
        raise ValueError(f'Incomplete or inconsistent SEQRES: {pdb_path}')
    refs = [line for line in lines if line.startswith('DBREF ') and line[12:13] == chain]
    if len(refs) != 1 or refs[0][33:41].strip() != accession:
        raise ValueError(f'Expected one DBREF for {accession}: {pdb_path}')
    ref = refs[0]
    pdb_start, pdb_end = int(ref[14:18]), int(ref[20:24])
    db_start, db_end = int(ref[55:60]), int(ref[62:67])
    if pdb_end - pdb_start != db_end - db_start or not db_start <= start <= end <= db_end:
        raise ValueError(f'Unsupported DBREF residue mapping: {pdb_path}')
    if any(ref[index:index + 1].strip() for index in (18, 24, 60, 67)):
        raise ValueError(f'Insertion codes require explicit mapping: {pdb_path}')
    tags = {}
    for line in lines:
        if not line.startswith('SEQADV') or line[16:17] != chain:
            continue
        if 'EXPRESSION TAG' not in line[49:]:
            raise ValueError(f'Unexpected sequence modification: {line.strip()}')
        if line[22:23].strip():
            raise ValueError(f'Insertion code in expression tag: {line.strip()}')
        tags[int(line[18:22])] = line[12:15]
    positions = set(range(pdb_start, pdb_end + 1)) | set(tags)
    first, last = min(positions), max(positions)
    if len(positions) != len(residues) or positions != set(range(first, last + 1)):
        raise ValueError(f'SEQRES cannot be mapped from DBREF and SEQADV: {pdb_path}')
    for number, residue in tags.items():
        if residues[number - first] != residue:
            raise ValueError(f'SEQADV/SEQRES mismatch at {number}: {pdb_path}')
    offset = pdb_start - db_start
    selected = residues[start + offset - first:end + offset - first + 1]
    try:
        sequence = ''.join(AMINO_ACIDS[residue] for residue in selected)
    except KeyError as error:
        raise ValueError(f'Noncanonical SEQRES residue: {error.args[0]}') from error
    return sequence, {
        'path': str(Path(pdb_path).resolve()), 'sha256': _sha(pdb_path),
        'chain': chain, 'source': 'PDB SEQRES mapped by DBREF and SEQADV',
        'uniprot_accession': accession, 'uniprot_start': start, 'uniprot_end': end,
        'source_construct_length': len(residues), 'sequence_length': len(sequence),
        'sequence_sha256': hashlib.sha256(sequence.encode()).hexdigest(),
        'dbref': ref.strip(), 'expression_tags_removed': sorted(tags),
    }
