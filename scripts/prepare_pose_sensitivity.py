"""Create matched eight-component manifests for B2/S pose sensitivity.

The B1 and water/free references start from the converged baseline geometries.
Only the original modeled B2/S ligand pose is rotated rigidly around its Fe-N
coordination axis. Each output remains a complete eight-component cycle.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cyp_pipeline.exchange import structure_valid, validate_manifest


def rotate_about_axis(point, origin, axis, angle_radians):
    vector = np.asarray(point, dtype=float) - origin
    axis = axis / np.linalg.norm(axis)
    rotated = (vector * math.cos(angle_radians)
               + np.cross(axis, vector) * math.sin(angle_radians)
               + axis * np.dot(axis, vector) * (1.0 - math.cos(angle_radians)))
    return (origin + rotated).tolist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--angle", type=float, required=True,
                        help="Rigid ligand rotation in degrees around the Fe-N axis")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--enzyme", choices=("CYP11B1", "CYP11B2"), default="CYP11B2",
                        help="Enzyme whose modeled ligand pose is perturbed")
    parser.add_argument("--baseline-run", type=Path,
                        default=Path("runs/exchange-pilot-v1-02"))
    parser.add_argument("--source-manifest", type=Path,
                        default=Path("prepared/exchange-pilot-v1/manifest.json"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    baseline_run = args.baseline_run if args.baseline_run.is_absolute() else root / args.baseline_run
    source_manifest = (args.source_manifest if args.source_manifest.is_absolute()
                       else root / args.source_manifest)
    original = json.loads(source_manifest.read_text())
    converged = json.loads((baseline_run / "input.json").read_text())

    # Start all components from the final converged baseline structures so every
    # cycle re-evaluates all eight energies while avoiding needless optimization.
    for enzyme, parts in converged["enzymes"].items():
        for name, component in parts.items():
            relaxation = baseline_run / enzyme / name / "relaxation.json"
            if relaxation.exists():
                component["atoms"] = json.loads(relaxation.read_text())["atoms"]

    # Replace B2 ligand-bound geometry with the original modeled pose, then make
    # a rigid perturbation that preserves Fe-N distance and ligand stereochemistry.
    source = copy.deepcopy(original["enzymes"][args.enzyme]["cluster_ligand"])
    positions = {atom["id"]: np.asarray(atom["position"], dtype=float)
                 for atom in source["atoms"]}
    fe = positions["heme_FE"]
    donor = positions["ligand_N06"]
    axis = donor - fe
    angle = math.radians(args.angle)
    for atom in source["atoms"]:
        if atom["id"] not in source["scaffold_ids"]:
            atom["position"] = rotate_about_axis(atom["position"], donor, axis, angle)
    source["provenance"]["pose_sensitivity"] = {
        "kind": "rigid_rotation_about_Fe_N_axis",
        "angle_degrees": args.angle,
        "enzyme": args.enzyme,
        "source": str(source_manifest.resolve()),
        "purpose": "Local starting-pose sensitivity; not an independently docked pose",
    }
    if not structure_valid(source["atoms"], source):
        raise ValueError("Rotated ligand failed covalent or stereochemistry checks")
    coordinates = np.asarray([atom["position"] for atom in source["atoms"]])
    pair_distances = np.linalg.norm(coordinates[:, None, :] - coordinates[None, :, :], axis=2)
    np.fill_diagonal(pair_distances, np.inf)
    minimum_pair_distance = float(pair_distances.min())
    if minimum_pair_distance < 0.65:
        raise ValueError(f"Rotated pose has a catastrophic overlap: {minimum_pair_distance:.3f} A")
    source["provenance"]["pose_sensitivity"]["minimum_pair_distance_A"] = minimum_pair_distance
    converged["enzymes"][args.enzyme]["cluster_ligand"] = source
    converged["sensitivity"] = source["provenance"]["pose_sensitivity"]
    validate_manifest(converged)

    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "manifest.json").write_text(json.dumps(converged, indent=2) + "\n")
    print(json.dumps({"manifest": str(args.out / "manifest.json"),
                      "angle_degrees": args.angle}, indent=2))


if __name__ == "__main__":
    main()
