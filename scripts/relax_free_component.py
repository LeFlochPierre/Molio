"""Relax a prepared free molecule with UMA and ASE BFGS."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cyp_pipeline.ase_relax import relax_bfgs
from cyp_pipeline.backends import load_backend
from cyp_pipeline.exchange import structure_valid
from cyp_pipeline.workflow import save, xyz


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--backend", type=Path, default=Path("configs/uma-s-1p1-a100.json"))
    parser.add_argument("--protocol", type=Path, default=Path("configs/protocol.json"))
    args = parser.parse_args()
    component = json.loads(args.input.read_text())
    if component.get("fixed_ids") != []:
        raise ValueError("Free component must have no fixed atoms")
    config = json.loads(args.backend.read_text())
    protocol = json.loads(args.protocol.read_text())
    protocol.update(method="ase_bfgs", max_steps=400)
    args.out.mkdir(parents=True, exist_ok=False)
    save(args.out / "input.json", component)
    save(args.out / "backend_config.json", config)
    save(args.out / "protocol.json", protocol)
    xyz(args.out / "before.xyz", component["atoms"])
    result = {"status": "running", "energy_eV": None}
    save(args.out / "result.json", result)
    started = time.monotonic()
    try:
        backend = load_backend(config)
        relaxation = relax_bfgs(backend, component["atoms"], component["state"], [],
                                protocol, args.out)
        save(args.out / "relaxation.json", relaxation)
        xyz(args.out / "after.xyz", relaxation["atoms"])
        valid = structure_valid(relaxation["atoms"], component)
        result.update(status="completed" if relaxation["converged"] and valid else "unresolved",
                      energy_eV=relaxation["energy_eV"], converged=relaxation["converged"],
                      structure_valid=valid, steps=relaxation["history"][-1]["step"],
                      final_fmax_eV_A=relaxation["history"][-1]["free_fmax_eV_A"],
                      backend=backend.metadata)
        if result["status"] == "completed":
            prepared = dict(component, atoms=relaxation["atoms"])
            prepared.setdefault("provenance", {})["relaxation_result"] = str(
                (args.out / "result.json").resolve())
            save(args.out / "prepared_component.json", prepared)
    except Exception as exc:
        result.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
    result["runtime_seconds"] = time.monotonic() - started
    save(args.out / "result.json", result)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
