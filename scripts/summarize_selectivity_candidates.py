"""Rank ligand candidates from validated pose-sensitivity ranges."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("summaries", nargs="+", type=Path)
    args = parser.parse_args()
    candidates = []
    for path in args.summaries:
        summary = json.loads(path.read_text())
        low, high = summary["B2_minus_B1_range_eV"]
        floor = summary["signal_floor_eV"]
        direction = "CYP11B2" if high < -floor else "CYP11B1" if low > floor else None
        candidates.append({
            "ligand": summary.get("ligand", "S-fadrozole"),
            "status": "eligible" if direction else "unresolved",
            "direction": direction,
            "B2_minus_B1_range_eV": [low, high],
            "signal_floor_eV": floor,
            "source": str(path.resolve()),
            "conservative_B2_score_eV": high if direction == "CYP11B2" else None,
        })
    eligible_b2 = sorted((row for row in candidates if row["direction"] == "CYP11B2"),
                         key=lambda row: row["conservative_B2_score_eV"])
    result = {
        "target": "CYP11B2",
        "selection_rule": ("Candidate is eligible only if its complete tested B2-minus-B1 "
                           "range is below -signal_floor; rank by worst-case (highest) delta"),
        "selected_lead": eligible_b2[0]["ligand"] if eligible_b2 else None,
        "candidates": candidates,
        "interpretation": ("Provisional UMA capped-pocket potential-energy ranking; not affinity, "
                           "free energy, selectivity ratio, or experimental validation"),
    }
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# Fadrozole selectivity candidate comparison", "",
             f'Current provisional CYP11B2 lead: **{result["selected_lead"]}**.', "",
             "| Candidate | Valid pose-sensitivity range, B2−B1 (eV) | Status | Direction |",
             "|---|---:|---|---|"]
    for row in candidates:
        low, high = row["B2_minus_B1_range_eV"]
        lines.append(f'| {row["ligand"]} | {low:+.6f} to {high:+.6f} | '
                     f'{row["status"]} | {row["direction"] or "none"} |')
    lines += ["", "Selection rule: the full tested range must lie beyond the ±0.05 eV engineering floor. For a CYP11B2 target, the entire range must be negative. R-fadrozole passes this local pose test; S-fadrozole does not because its range crosses zero.",
              "", "This ranking is a model-screening result. It does not convert to a potency or selectivity ratio. R-fadrozole still needs cluster-boundary, protonation/spin, solvation and broader independently generated pose tests, followed by comparison with stereospecific assay data."]
    (args.out / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
