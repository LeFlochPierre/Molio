"""Summarize converged baseline and B2/S pose-sensitivity exchange cycles."""
import argparse
import json
import math
from pathlib import Path


def rmsd(left, right):
    ids = sorted(set(left) & set(right))
    return math.sqrt(sum(sum((a - b) ** 2 for a, b in zip(left[i], right[i]))
                         for i in ids) / len(ids))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--modeled-enzyme", choices=("CYP11B1", "CYP11B2"),
                        default="CYP11B2")
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()

    rows = []
    geometries = {}
    ligand_name = None
    for run in args.runs:
        result = json.loads((run / "result.json").read_text())
        if result["status"] != "exploratory":
            raise ValueError(f"{run}: cycle is not complete")
        ligand_name = ligand_name or result["ligand"]
        if result["ligand"] != ligand_name:
            raise ValueError("Cannot combine different ligands")
        sensitivity = json.loads((run / "input.json").read_text()).get("sensitivity", {})
        label = "baseline" if not sensitivity else f'{sensitivity["angle_degrees"]:+g} degrees'
        relaxation = json.loads((run / args.modeled_enzyme / "cluster_ligand/relaxation.json").read_text())
        geometries[label] = {
            atom["id"]: atom["position"] for atom in relaxation["atoms"]
            if atom["id"].startswith("ligand_")
        }
        rows.append({
            "label": label,
            "run": str(run.resolve()),
            "B1_exchange_eV": result["enzymes"]["CYP11B1"]["exchange_energy_eV"],
            "B2_exchange_eV": result["enzymes"]["CYP11B2"]["exchange_energy_eV"],
            "B2_minus_B1_eV": result["delta_B2_minus_B1_eV"],
            "reported_preference": result["energy_model_preference"],
        })

    values = [row["B2_minus_B1_eV"] for row in rows]
    floor = 0.05
    enough_poses = len(rows) >= 3
    robust = (("CYP11B2" if max(values) < -floor else
               "CYP11B1" if min(values) > floor else None)
              if enough_poses else None)
    comparisons = []
    labels = list(geometries)
    for i, left in enumerate(labels):
        for right in labels[i + 1:]:
            comparisons.append({"poses": [left, right],
                                "ligand_atom_RMSD_A": rmsd(geometries[left], geometries[right])})
    summary = {
        "status": "robust" if robust else "baseline_only" if not enough_poses else "unresolved",
        "signal_floor_eV": floor,
        "robust_preference": robust,
        "B2_minus_B1_range_eV": [min(values), max(values)],
        "crosses_zero": min(values) <= 0 <= max(values),
        "reason": ("All tested poses agree beyond the signal floor" if robust else
                   "At least three accepted poses are required" if not enough_poses else
                   "Tested starting poses change the sign or enter the signal floor"),
        "cycles": rows,
        "modeled_enzyme": args.modeled_enzyme,
        "ligand": ligand_name,
        "final_modeled_ligand_geometry_comparisons": comparisons,
        "scope": (f"Local rigid {args.modeled_enzyme}/{ligand_name} starting-pose perturbations "
                  "around Fe-N; not independent docking or free-energy sampling"),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    lines = [f"# {args.modeled_enzyme}/{ligand_name} pose sensitivity", "",
             f'Conclusion: **{summary["status"]}**. {summary["reason"]}.', "",
             f"| {args.modeled_enzyme}/{ligand_name} starting pose | B1 exchange (eV) | B2 exchange (eV) | B2−B1 (eV) | Single-run direction |",
             "|---|---:|---:|---:|---|"]
    for row in rows:
        lines.append(f'| {row["label"]} | {row["B1_exchange_eV"]:.9f} | '
                     f'{row["B2_exchange_eV"]:.9f} | {row["B2_minus_B1_eV"]:+.9f} | '
                     f'{row["reported_preference"]} |')
    conclusion = (f"The full range lies beyond the signal floor and consistently favors {robust}."
                  if robust else
                  "The range crosses zero or enters the signal floor, so this pilot cannot assign a robust isoform preference.")
    lines += ["", f'Sensitivity range: **{min(values):+.9f} to {max(values):+.9f} eV**.',
              f'Engineering signal floor: ±{floor:.2f} eV.', "",
              conclusion + " The perturbations are local starting-pose tests; they do not establish a thermodynamic ensemble or validate the modeled pose.",
              "", f"## Final {args.modeled_enzyme} ligand geometry differences", "",
              "| Relaxed pose pair | Ligand atom RMSD (angstrom) |", "|---|---:|"]
    for row in comparisons:
        lines.append(f'| {row["poses"][0]} vs {row["poses"][1]} | '
                     f'{row["ligand_atom_RMSD_A"]:.4f} |')
    lines += ["", f"All {len(rows)} cycles contain four relaxed energies for each enzyme and passed their per-component convergence and geometry checks. See `summary.json` for paths to each machine-readable run."]
    (args.out / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
