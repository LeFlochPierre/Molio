"""Extract a provisional isolated fadrozole enantiomer from its crystal structure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('ISOFORM_SOURCE_ROOT', ROOT / 'research/source-preparation'))
sys.path.insert(0, str(SOURCE))
import prepare_whole
from openmm import unit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("enantiomer", choices=("R", "S"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    domain, pdb, residue = ({
        "R": ("CYP11B2_R", "4FDH", "0T3"),
        "S": ("CYP11B1_S", "6M7X", "JD7"),
    }[args.enantiomer])
    pdb_path = SOURCE / "inputs" / f"{pdb}.pdb"
    template = SOURCE / "inputs/JD7.cif"
    original, _ = prepare_whole.read_source(pdb_path)
    topology, positions, charge, mapping, chirality = prepare_whole.component(
        original, residue, template)
    observed = [label for _, label in chirality]
    if observed != [args.enantiomer]:
        raise ValueError(f"Expected {args.enantiomer}, found {observed}")
    coordinates = positions.value_in_unit(unit.angstrom).tolist()
    coordinate_by_name = {atom["name"]: np.asarray(xyz, dtype=float)
                          for atom, xyz in zip(mapping, coordinates)}
    center = coordinate_by_name["C03"]
    neighbors = ("C02", "N04", "C10")
    chiral_volume = float(np.linalg.det(
        np.asarray([coordinate_by_name[name] - center for name in neighbors])))
    component = {
        "atoms": [{"id": "ligand_" + atom["name"],
                   "element": atom["element"], "position": xyz}
                  for atom, xyz in zip(mapping, coordinates)],
        "state": {"charge": charge, "multiplicity": 1,
                  "convention": f"Neutral isolated {args.enantiomer}-fadrozole singlet"},
        "fixed_ids": [],
        "covalent_bounds": [
            {"ids": ["ligand_" + left.name, "ligand_" + right.name],
             "min_A": 0.85, "max_A": 1.85}
            for left, right in topology.bonds()
        ],
        "chirality_checks": [{"center": "ligand_C03",
                               "neighbors": ["ligand_" + name for name in neighbors],
                               "reference_volume_A3": chiral_volume}],
        "review": {"approved": False, "provisional": True},
        "preparation": (f"Experimental {pdb} chain A {residue} heavy coordinates; "
                        "local CCD covalent graph; RDKit-added hydrogens; no solvent or embedding."),
        "provenance": {
            "source_domain": domain,
            "chirality": chirality,
            "mapping": mapping,
            "source_hashes": {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (pdb_path, template, Path(prepare_whole.__file__))
            },
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(component, indent=2) + "\n")
    print(json.dumps({"output": str(args.out), "atoms": len(mapping),
                      "charge": charge, "chirality": chirality}, indent=2))


if __name__ == "__main__":
    main()
