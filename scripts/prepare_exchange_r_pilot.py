"""Build the matched provisional R-fadrozole four-energy exchange cycle."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('ISOFORM_SOURCE_ROOT', ROOT / 'research/source-preparation'))
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_exchange_pilot import atom, build, load, rotation, water_pose, RES


def heme_coordinates(domain):
    return {entry["name"]: domain["xyz"][entry["index"]]
            for entry in domain["atom_map.json"]
            if entry["residue"] == "HEM" and entry["element"] != "H"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--free-ligand", type=Path,
                        default=ROOT / "runs/exchange-free-R-fadrozole-01/prepared_component.json")
    parser.add_argument("--out", type=Path, default=ROOT / "prepared/exchange-R-pilot-v1")
    parser.add_argument("--add-residue", type=int, action="append", default=[],
                        help="add numbered protein residue to the capped pocket")
    args = parser.parse_args()
    residues = sorted(set(RES + args.add_residue))
    args.out.mkdir(parents=True, exist_ok=False)

    b1, b2 = load("CYP11B1_S"), load("CYP11B2_R")
    h1, h2 = heme_coordinates(b1), heme_coordinates(b2)
    names = sorted(h1)
    transform, source_center, target_center, alignment_rmsd = rotation(
        np.asarray([h2[name] for name in names]),
        np.asarray([h1[name] for name in names]))
    experimental_r = [atom(entry, b2["xyz"][entry["index"]])
                      for entry in b2["atom_map.json"] if entry["residue"] == "0T3"]
    if len(experimental_r) != 30:
        raise ValueError("Expected 30 R-fadrozole atoms")

    manifest = json.loads((ROOT / "prepared/exchange-pilot-v1/manifest.json").read_text())
    manifest["ligand"] = "R-fadrozole"
    manifest["preparation_protocol"] = (
        "capped-pocket-exchange-R-pilot-v1; same residue and cap protocol as S pilot; "
        "experimental B2/R pose; modeled B1/R pose by proper-rotation heme alignment")
    free_r = json.loads(args.free_ligand.read_text())
    free_water = copy.deepcopy(manifest["enzymes"]["CYP11B1"]["free_water"])
    audits = {}

    for enzyme, domain in (("CYP11B1", b1), ("CYP11B2", b2)):
        scaffold, fixed, caps, ledger = build(domain, residues)
        ligand = copy.deepcopy(experimental_r)
        if enzyme == "CYP11B1":
            for entry in ligand:
                position = np.asarray(entry["position"])
                entry["position"] = ((position - source_center) @ transform
                                     + target_center).tolist()
        water = water_pose(scaffold, ligand, free_water["atoms"])
        charge = sum(row["formal_charge"] for row in ledger)
        for name, guest, donor in (("cluster_ligand", ligand, "ligand_N06"),
                                   ("cluster_water", water, "bound_water_O")):
            atoms = copy.deepcopy(scaffold) + guest
            bounds = [{"ids": ["heme_FE", donor], "min_A": 1.8, "max_A": 2.8},
                      {"ids": ["heme_FE", "res450_SG"], "min_A": 2.0, "max_A": 2.9}]
            component = {
                "atoms": atoms,
                "fixed_ids": fixed,
                "scaffold_ids": [entry["id"] for entry in scaffold],
                "state": {"charge": charge, "multiplicity": 2,
                          "convention": ("Provisional ferric low-spin doublet; heme net -1; "
                                         "Cys450 thiolate; standard residue states; neutral guest; "
                                         "isolated H-capped pocket")},
                "review": {"approved": False, "provisional": True},
                "coordination": bounds,
                "preparation": manifest["preparation_protocol"],
                "provenance": {
                    "source_hashes": domain["hashes"],
                    "selected_residue_numbers": residues,
                    "cap_bonds": caps,
                    "charge_ledger": ledger,
                    "pose_kind": ("modeled_water_replacement" if name == "cluster_water"
                                  else "experimental_R_pose" if enzyme == "CYP11B2"
                                  else "modeled_heme_aligned_R_pose"),
                    "heme_alignment_RMSD_A": alignment_rmsd,
                    "notes": "Provisional matched R cycle; pose/boundary/spin sensitivity required.",
                },
            }
            manifest["enzymes"][enzyme][name] = component
            positions = {entry["id"]: np.asarray(entry["position"]) for entry in atoms}
            distances = [float(np.linalg.norm(positions[b["ids"][0]] - positions[b["ids"][1]]))
                         for b in bounds]
            all_positions = np.asarray([entry["position"] for entry in atoms])
            pair = np.linalg.norm(all_positions[:, None, :] - all_positions[None, :, :], axis=2)
            np.fill_diagonal(pair, np.inf)
            if min(distances) < 1.8 or float(pair.min()) < 0.65:
                raise ValueError(f"Invalid initial geometry for {enzyme}/{name}")
            audits[f"{enzyme}/{name}"] = {
                "atoms": len(atoms), "fixed_atoms": len(fixed), "charge": charge,
                "coordination_A": distances, "minimum_pair_distance_A": float(pair.min()),
            }
        manifest["enzymes"][enzyme]["free_water"] = copy.deepcopy(free_water)
        manifest["enzymes"][enzyme]["free_ligand"] = copy.deepcopy(free_r)

    sys.path.insert(0, str(SOURCE))
    import prepare_whole
    original, _ = prepare_whole.read_source(SOURCE / "inputs/4FDH.pdb")
    topology, *_ = prepare_whole.component(original, "0T3", SOURCE / "inputs/JD7.cif")
    for parts in manifest["enzymes"].values():
        component = parts["cluster_ligand"]
        component["covalent_bounds"] = [
            {"ids": ["ligand_" + left.name, "ligand_" + right.name],
             "min_A": 0.85, "max_A": 1.85} for left, right in topology.bonds()]
        coordinates = {entry["id"]: np.asarray(entry["position"])
                       for entry in component["atoms"]}
        center = coordinates["ligand_C03"]
        neighbors = ["ligand_C02", "ligand_N04", "ligand_C10"]
        component["chirality_checks"] = [{
            "center": "ligand_C03", "neighbors": neighbors,
            "reference_volume_A3": float(np.linalg.det(
                np.asarray([coordinates[name] - center for name in neighbors]))),
        }]
        parts["cluster_water"]["covalent_bounds"] = [
            {"ids": ["bound_water_O", f"bound_water_H{i}"], "min_A": 0.7, "max_A": 1.3}
            for i in (1, 2)]

    sys.path.insert(0, str(ROOT))
    from cyp_pipeline.exchange import validate_manifest
    validate_manifest(manifest)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.out / "preparation_audit.json").write_text(json.dumps(audits, indent=2) + "\n")
    print(json.dumps(audits, indent=2))


if __name__ == "__main__":
    main()
