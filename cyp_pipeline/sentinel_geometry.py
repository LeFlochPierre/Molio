"""Collect optional Boltz geometry diagnostics for Selectivity Sentinel.

Run this with the Boltz environment, where Gemmi/RDKit and the trusted Boltz
molecule cache are available. The output is diagnostic-only: a close Fe--N
distance or matching chirality does not prove binding or selectivity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .benchmark_geometry import analyze_boltz_structure


def _source(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--boltz-root", required=True)
    parser.add_argument("--ccd-cache", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        experiment_path, root = Path(args.experiment), Path(args.boltz_root)
        experiment = json.loads(experiment_path.read_text())
        result = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                  "experiment": _source(experiment_path), "boltz_root": str(root.resolve()), "cases": []}
        for system in experiment["systems"]:
            matches = sorted(root.rglob(f"{system['system_id']}_model_0.cif"))
            if len(matches) != 1:
                diagnostic = {"status": "unassessed", "reason": "Expected one rank-zero Boltz structure"}
                source = None
            else:
                source = _source(matches[0])
                diagnostic = analyze_boltz_structure(
                    matches[0], system["ligand"], ccd_dir=args.ccd_cache
                )
            result["cases"].append({"system_id": system["system_id"], "ligand": system["ligand"],
                                    "isoform": system["isoform"], "structure": source,
                                    "diagnostic": diagnostic})
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            raise ValueError(f"Refusing to overwrite: {out}")
        out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(out)
        return 0
    except (OSError, KeyError, TypeError, ValueError, ImportError, RuntimeError) as error:
        print(f"error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
