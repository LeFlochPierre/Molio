"""Create a complete continuation manifest from a saved exchange run."""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cyp_pipeline.exchange import validate_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    manifest = json.loads((args.run / "input.json").read_text())
    continued = []
    for enzyme, parts in manifest["enzymes"].items():
        for name, component in parts.items():
            relaxation = args.run / enzyme / name / "relaxation.json"
            if relaxation.exists():
                component["atoms"] = json.loads(relaxation.read_text())["atoms"]
                component.setdefault("provenance", {})["optimization_restart_from"] = str(
                    relaxation.resolve())
                continued.append(f"{enzyme}/{name}")
    # The exchange contract intentionally requires byte-for-byte identical free
    # references for both enzymes. Use the B1 snapshots for both after restart.
    for name in ("free_water", "free_ligand"):
        manifest["enzymes"]["CYP11B2"][name] = copy.deepcopy(
            manifest["enzymes"]["CYP11B1"][name])
    manifest["continuation"] = {
        "previous_run": str(args.run.resolve()),
        "components_restarted_from_saved_geometry": continued,
        "force_tolerance_unchanged": True,
    }
    validate_manifest(manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
