"""Cofactor-aware off-target triage for a declared protein-family panel.

This is a decision-support workflow, not a binding or clinical-safety oracle.
It keeps prospective model evidence separate from retrospective paired assay
references. A candidate may be *validated selective* by a supplied assay yet
still carry a model-disagreement alert; conversely, model-only screening can
only recommend an expanded counterscreen, never declare safety.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .design import score_pose_summary


SCHEMA_VERSION = 1


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read(path):
    return json.loads(Path(path).read_text())


def _source(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _require(value, message):
    if not value:
        raise ValueError(message)


def load_panel(path):
    panel = _read(path)
    _require(panel.get("schema_version") == SCHEMA_VERSION, "Unsupported Sentinel panel schema")
    target = panel.get("target", {})
    _require(isinstance(target.get("id"), str) and target["id"], "Panel target ID is required")
    _require(isinstance(target.get("sequence"), str) and len(target["sequence"]) >= 50,
             "Panel target needs an explicit amino-acid sequence")
    sequence = "".join(target["sequence"].split()).upper()
    _require(all(letter in "ACDEFGHIKLMNPQRSTVWY" for letter in sequence),
             "Panel target sequence must contain standard amino-acid letters only")
    target["sequence"] = sequence
    entries = panel.get("off_target_panel", [])
    _require(entries and len({entry.get("id") for entry in entries}) == len(entries),
             "Panel must have uniquely identified off-target entries")
    _require(all(isinstance(entry.get("id"), str) and entry["id"] for entry in entries),
             "Every off-target requires an ID")
    _require(target["id"] not in {entry["id"] for entry in entries}, "Target cannot be an off-target entry")
    _require(sum(entry.get("role") == "mandatory_primary" for entry in entries) == 1,
             "Panel requires exactly one mandatory_primary off-target")
    policy = panel.get("policy", {})
    _require(_finite(policy.get("minimum_validation_fold", None)) and policy["minimum_validation_fold"] > 1,
             "minimum_validation_fold must exceed 1")
    _require(_finite(policy.get("minimum_model_fold", None)) and policy["minimum_model_fold"] > 1,
             "minimum_model_fold must exceed 1")
    return panel


def load_experiment(path):
    systems = _read(path).get("systems", [])
    _require(systems, "Experiment has no systems")
    lookup = {}
    for system in systems:
        key = (system.get("ligand"), system.get("isoform"))
        _require(all(isinstance(value, str) and value for value in key), "Experiment ligand/isoform required")
        _require(key not in lookup, f"Duplicate experiment case: {key}")
        lookup[key] = system
    return lookup


def _boltz_raw_completion(run_root):
    """Verify raw pilot outputs without converting an interrupted wrapper to success."""
    run_root = Path(run_root).resolve()
    manifest_path = run_root / "run_manifest.json"
    log_path = run_root / "seed-42" / "boltz.log"
    _require(manifest_path.is_file() and log_path.is_file(), "Boltz run manifest/log missing")
    manifest = _read(manifest_path)
    log = log_path.read_text(errors="replace")
    complete = "Number of failed examples: 0" in log and "Predicting DataLoader 0: 100%" in log
    return {
        "status": manifest.get("status"),
        "raw_prediction_log_complete": complete,
        "manifest": _source(manifest_path),
        "log": _source(log_path),
        "warning": (
            "Native affinity files are present after a successful raw prediction log, but the execution wrapper "
            "did not finalize its manifest. Re-run or reconcile before promoting these to a formal benchmark."
            if manifest.get("status") != "completed" else None
        ),
    }


def load_boltz_pair(run_root, experiment, ligand, target_id, off_target_id):
    """Load a same-seed target/off-target Boltz affinity pair with provenance."""
    completion = _boltz_raw_completion(run_root)
    systems = []
    for isoform in (target_id, off_target_id):
        system = experiment.get((ligand, isoform))
        if not system:
            return {"status": "unassessed", "reason": f"No declared {ligand}/{isoform} experiment case"}
        systems.append(system)
    values = {}
    sources = {}
    probabilities = {}
    for system in systems:
        pattern = f"affinity_{system['system_id']}.json"
        matches = sorted(Path(run_root).rglob(pattern))
        if len(matches) != 1:
            return {"status": "unassessed", "reason": f"Expected one native output matching {pattern}"}
        result = _read(matches[0])
        value, probability = result.get("affinity_pred_value"), result.get("affinity_probability_binary")
        if not (_finite(value) and _finite(probability) and 0 <= probability <= 1):
            return {"status": "unassessed", "reason": f"Invalid native Boltz output: {matches[0]}"}
        values[system["isoform"]] = value
        probabilities[system["isoform"]] = probability
        sources[system["isoform"]] = _source(matches[0])
    margin = values[off_target_id] - values[target_id]
    return {
        "status": "raw_completed_unfinalized" if completion["status"] != "completed" else "completed",
        "metric": "Boltz-2 affinity_pred_value log10(IC50/uM)",
        "scores": values,
        "binder_probability": probabilities,
        "target_advantage_log10": margin,
        "target_over_off_target_fold": 10 ** margin,
        "sources": sources,
        "execution": completion,
        "interpretation": (
            "Positive target_advantage_log10 means the target has lower predicted IC50 than the declared off-target. "
            "This is a within-model ranking signal, not an experimental selectivity measurement."
        ),
    }


def load_uma_summary(path, target_id):
    if not path:
        return {"status": "unassessed", "reason": "No UMA pose-sensitivity summary supplied"}
    path = Path(path)
    if not path.is_file():
        return {"status": "unassessed", "reason": f"UMA summary missing: {path}"}
    summary = _read(path)
    try:
        score = score_pose_summary(summary, target_id)
    except (KeyError, TypeError, ValueError) as error:
        return {"status": "unassessed", "reason": f"Invalid UMA summary: {error}"}
    return {
        "status": "supported" if score["lead_eligible"] else "not_supported",
        "source": _source(path),
        **score,
        "interpretation": (
            "UMA exchange is a local capped-pocket potential-energy stress test. It is not a binding affinity, "
            "free energy, or whole-proteome off-target score."
        ),
    }


def load_assay_pair(paths, ligand, target_id, off_target_id):
    matched = []
    for path in paths:
        data = _read(path)
        grouped = {}
        for row in data.get("measurements", []):
            if row.get("ligand") != ligand or row.get("isoform") not in (target_id, off_target_id):
                continue
            key = (row.get("assay_id"), row.get("endpoint"))
            grouped.setdefault(key, {})[row["isoform"]] = row
        for (assay_id, endpoint), group in grouped.items():
            if set(group) != {target_id, off_target_id}:
                continue
            if not all(_finite(group[iso].get("value_nM")) and group[iso]["value_nM"] > 0
                       for iso in (target_id, off_target_id)):
                continue
            ratio = group[off_target_id]["value_nM"] / group[target_id]["value_nM"]
            matched.append({
                "assay_id": assay_id,
                "endpoint": endpoint,
                "values_nM": {iso: group[iso]["value_nM"] for iso in (target_id, off_target_id)},
                "target_over_off_target_fold": ratio,
                "target_advantage_log10": math.log10(ratio),
                "source_url": group[target_id].get("source_url"),
                "source": _source(path),
                "conditions": {iso: group[iso].get("conditions", {}) for iso in (target_id, off_target_id)},
                "interpretation": "Paired same-source inhibition reference; endpoint must not be mixed with another assay type.",
            })
    if not matched:
        return {"status": "unavailable", "reason": "No paired reference found for this ligand/target/off-target"}
    return {"status": "available", "pairs": matched}


def load_geometry_pair(path, experiment, ligand, target_id, off_target_id):
    if not path:
        return {"status": "unassessed", "reason": "No Boltz geometry diagnostic file supplied"}
    path = Path(path)
    if not path.is_file():
        return {"status": "unassessed", "reason": f"Geometry diagnostic file missing: {path}"}
    data = _read(path)
    cases = {case.get("system_id"): case for case in data.get("cases", [])}
    pair = {}
    for isoform in (target_id, off_target_id):
        system = experiment.get((ligand, isoform))
        if not system or system["system_id"] not in cases:
            return {"status": "unassessed", "reason": f"No geometry diagnostic for {ligand}/{isoform}"}
        case = cases[system["system_id"]]
        diagnostic = case.get("diagnostic", {})
        pair[isoform] = {"structure": case.get("structure"), "diagnostic": diagnostic}
    failed = []
    manual = []
    for isoform, value in pair.items():
        diagnostic = value["diagnostic"]
        chirality = diagnostic.get("chirality", {}).get("status")
        if diagnostic.get("ligand_ccd_matches_expected") is False or chirality == "mismatch_or_unassigned":
            failed.append(isoform)
        elif chirality in (None, "unassessed", "unresolved", "unavailable"):
            manual.append(isoform)
    return {
        "status": "identity_or_chirality_failure" if failed else "manual_review_required" if manual else "diagnostic_only",
        "source": _source(path), "by_isoform": pair, "failed_isoforms": failed,
        "manual_review_isoforms": manual,
        "interpretation": "Geometry diagnostics check identity/chirality where possible; no distance cutoff establishes valid heme coordination.",
    }


def _model_gate(boltz, minimum_fold):
    if boltz.get("status") not in ("completed", "raw_completed_unfinalized"):
        return {"status": "unassessed", "reason": boltz.get("reason", "No completed pair")}
    fold = boltz["target_over_off_target_fold"]
    return {
        "status": "supported" if fold >= minimum_fold else "off_target_alert",
        "threshold_fold": minimum_fold,
        "observed_fold": fold,
        "reason": (
            "Predicted target margin clears the model-screening policy."
            if fold >= minimum_fold else
            "Predicted target margin is below the model-screening policy; counter-screen required."
        ),
    }


def assess_candidate(panel, experiment, boltz_root, assay_paths, ligand, geometry_path=None):
    target = panel["target"]
    primary = next(entry for entry in panel["off_target_panel"] if entry["role"] == "mandatory_primary")
    target_id, off_target_id = target["id"], primary["id"]
    boltz = load_boltz_pair(boltz_root, experiment, ligand, target_id, off_target_id)
    uma = load_uma_summary(panel.get("uma_summaries", {}).get(ligand), target_id)
    assays = load_assay_pair(assay_paths, ligand, target_id, off_target_id)
    geometry = load_geometry_pair(geometry_path, experiment, ligand, target_id, off_target_id)
    policy = panel["policy"]
    model_gate = _model_gate(boltz, policy["minimum_model_fold"])
    validation = []
    if assays["status"] == "available":
        for pair in assays["pairs"]:
            selective = pair["target_over_off_target_fold"] >= policy["minimum_validation_fold"]
            validation.append({
                **pair,
                "threshold_fold": policy["minimum_validation_fold"],
                "status": "validated_selective" if selective else "validated_not_selective",
            })
    pending = [entry for entry in panel["off_target_panel"] if entry["id"] != off_target_id]
    primary_validation = validation[0] if validation else None
    if primary_validation:
        decision = primary_validation["status"]
    else:
        decision = "needs_assay" if model_gate["status"] == "supported" else "off_target_risk"
    alerts = []
    if boltz.get("execution", {}).get("warning"):
        alerts.append("Boltz execution manifest is unfinished; raw outputs must be reconciled before formal use.")
    if model_gate["status"] == "off_target_alert":
        alerts.append("Model screen does not show the configured target margin over the mandatory close paralog.")
    if uma["status"] == "not_supported":
        alerts.append("UMA pose/boundary stress test does not support a robust target-preference call.")
    if geometry["status"] == "identity_or_chirality_failure":
        alerts.append("Boltz geometry has a ligand-identity or chirality failure; affinity score is not interpretable for: " +
                      ", ".join(geometry["failed_isoforms"]) + ".")
    elif geometry["status"] == "manual_review_required":
        alerts.append("Boltz geometry needs manual ligand identity/chirality review for: " +
                      ", ".join(geometry["manual_review_isoforms"]) + ".")
    elif geometry["status"] == "unassessed":
        alerts.append("Boltz geometry diagnostics have not been run.")
    if primary_validation and model_gate["status"] != "unassessed":
        agreement = (primary_validation["status"] == "validated_selective") == (model_gate["status"] == "supported")
        if not agreement:
            alerts.append("Experimental reference and model-screening gate disagree; do not calibrate from this single case.")
    if pending:
        alerts.append("Expanded CYP off-target panel remains unassessed: " + ", ".join(item["id"] for item in pending) + ".")
    next_action = (
        "Advance only with the declared paired assay and expanded counterscreen."
        if decision == "validated_selective" else
        "Do not advance as selective; redesign or run a paired counterscreen before further optimization."
        if decision == "validated_not_selective" else
        "Run a paired target/off-target inhibition assay and validate geometry before a selectivity claim."
    )
    return {
        "ligand": ligand,
        "target": target,
        "mandatory_primary_off_target": primary,
        "decision": decision,
        "decision_scope": (
            "Retrospective paired-assay validation; this does not establish prospective model accuracy."
            if primary_validation else "Prospective model triage only; no selectivity claim is authorized."
        ),
        "boltz": boltz,
        "model_screen": model_gate,
        "uma_local_chemistry": uma,
        "boltz_geometry": geometry,
        "paired_assay_validation": validation,
        "unassessed_off_targets": pending,
        "alerts": alerts,
        "recommended_next_action": next_action,
    }


def _number(value, digits=3):
    return f"{value:.{digits}g}" if _finite(value) else "–"


def markdown_report(report):
    rows = [
        "# Selectivity Sentinel report", "",
        "This is decision support for a declared target-family panel. It does not establish that a candidate binds, "
        "is safe, or is clinically selective.", "",
        f"Target: **{report['panel']['target']['id']}** — policy thresholds: "
        f"{report['panel']['policy']['minimum_model_fold']:g}× model screen and "
        f"{report['panel']['policy']['minimum_validation_fold']:g}× paired-reference validation.", "",
        "| Candidate | Decision | Boltz target/off-target | UMA local test | Paired reference |",
        "|---|---|---:|---|---:|",
    ]
    for card in report["cards"]:
        boltz = card["boltz"]
        assay = card["paired_assay_validation"]
        validation = _number(assay[0]["target_over_off_target_fold"]) + "×" if assay else "–"
        rows.append(
            f"| {card['ligand']} | {card['decision']} | "
            f"{_number(boltz.get('target_over_off_target_fold'))}× | {card['uma_local_chemistry']['status']} | {validation} |"
        )
    for card in report["cards"]:
        rows += ["", f"## {card['ligand']}", "", f"**Decision:** `{card['decision']}`. {card['decision_scope']}", ""]
        if card["boltz"].get("status") in ("completed", "raw_completed_unfinalized"):
            rows.append(
                "Boltz target advantage: **" + _number(card["boltz"]["target_over_off_target_fold"]) +
                "×** (raw within-model IC50-like ranking; not an assay measurement)."
            )
        if card["paired_assay_validation"]:
            reference = card["paired_assay_validation"][0]
            rows.append(
                f"Paired {reference['endpoint']} reference: **{_number(reference['target_over_off_target_fold'])}×** "
                f"target over {card['mandatory_primary_off_target']['id']} (policy {reference['threshold_fold']:g}×)."
            )
        rows += ["", "Alerts:"]
        rows += [f"- {alert}" for alert in card["alerts"]] or ["- None"]
        rows += ["", "Next action: " + card["recommended_next_action"]]
    return "\n".join(rows) + "\n"


def html_report(report):
    cards = []
    for card in report["cards"]:
        boltz = card["boltz"]
        validation = card["paired_assay_validation"]
        assay = validation[0] if validation else None
        badge = card["decision"].replace("_", " ")
        cards.append(
            "<article class='card'>"
            f"<h2>{html.escape(card['ligand'])}</h2><p class='badge {html.escape(card['decision'])}'>{html.escape(badge)}</p>"
            "<dl>"
            f"<dt>Target</dt><dd>{html.escape(card['target']['id'])}</dd>"
            f"<dt>Mandatory off-target</dt><dd>{html.escape(card['mandatory_primary_off_target']['id'])}</dd>"
            f"<dt>Boltz screen</dt><dd>{_number(boltz.get('target_over_off_target_fold'))}× target advantage</dd>"
            f"<dt>UMA local chemistry</dt><dd>{html.escape(card['uma_local_chemistry']['status'])}</dd>"
            f"<dt>Boltz geometry</dt><dd>{html.escape(card['boltz_geometry']['status'])}</dd>"
            f"<dt>Paired assay reference</dt><dd>{_number(assay['target_over_off_target_fold']) + '× ' + html.escape(assay['endpoint']) if assay else 'not supplied'}</dd>"
            "</dl><h3>What the user should know</h3><ul>" +
            "".join(f"<li>{html.escape(alert)}</li>" for alert in card["alerts"]) +
            f"</ul><p><strong>Next action:</strong> {html.escape(card['recommended_next_action'])}</p></article>"
        )
    policy = report["panel"]["policy"]
    return """<!doctype html><html lang='en'><meta charset='utf-8'><title>Selectivity Sentinel</title>
<style>body{font:16px system-ui,sans-serif;background:#f6f8fb;color:#172033;margin:0;padding:32px;max-width:1050px}
h1{margin-bottom:4px}.sub{color:#586174}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}.card{background:#fff;border:1px solid #dce2eb;border-radius:14px;padding:20px;box-shadow:0 2px 8px #1720330d}.badge{display:inline-block;text-transform:uppercase;font-size:.75rem;font-weight:700;border-radius:99px;padding:5px 8px;background:#fff4d4;color:#7d5100}.validated_selective{background:#d9f4e3;color:#12653a}.validated_not_selective,.off_target_risk{background:#ffe0e0;color:#9d2222}dt{font-weight:650;margin-top:10px}dd{margin:2px 0}li{margin:7px 0}</style>
<h1>Selectivity Sentinel</h1><p class='sub'>Cofactor-aware target-family triage. A warning system, not a clinical or binding claim.</p>
<p>Policy: __MODEL__× model-screen margin; __VALIDATION__× paired-assay selectivity margin.</p><section class='grid'>__CARDS__</section></html>""".replace(
        "__MODEL__", _number(policy["minimum_model_fold"])
    ).replace("__VALIDATION__", _number(policy["minimum_validation_fold"])).replace("__CARDS__", "".join(cards))


def write_report(panel_path, experiment_path, boltz_root, assay_paths, ligands, out, geometry_path=None):
    panel = load_panel(panel_path)
    experiment = load_experiment(experiment_path)
    cards = [assess_candidate(panel, experiment, boltz_root, assay_paths, ligand, geometry_path) for ligand in ligands]
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "panel": panel,
        "sources": {"panel": _source(panel_path), "experiment": _source(experiment_path),
                    "assays": [_source(path) for path in assay_paths],
                    "geometry": _source(geometry_path) if geometry_path else None},
        "cards": cards,
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "result.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (out / "report.md").write_text(markdown_report(report))
    (out / "report.html").write_text(html_report(report))
    return out / "report.html"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", required=True, help="Declared target/off-target panel JSON")
    parser.add_argument("--experiment", required=True, help="Experiment case map with Boltz system IDs")
    parser.add_argument("--boltz-root", required=True, help="Native Boltz run root")
    parser.add_argument("--assays", action="append", default=[], help="Paired assay reference JSON; repeatable")
    parser.add_argument("--geometry", help="Optional diagnostics from cyp_pipeline.sentinel_geometry")
    parser.add_argument("--ligand", action="append", required=True, help="Candidate ligand label; repeatable")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        path = write_report(args.panel, args.experiment, args.boltz_root, args.assays, args.ligand, args.out,
                            args.geometry)
        print(path)
        return 0
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
