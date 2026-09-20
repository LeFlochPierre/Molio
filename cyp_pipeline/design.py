"""Active-learning campaign support for CYP11B1/CYP11B2 ligand design.

This module deliberately separates molecule proposal from the expensive UMA
exchange-cycle calculation.  A candidate becomes a lead only after all valid
pose calculations pass the target-exchange and robust-selectivity gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
ENZYMES = ("CYP11B1", "CYP11B2")
BASE_POCKET_RESIDUES = [
    110, 113, 116, 130, 231, 310, 313, 314, 315, 316, 318,
    378, 379, 380, 381, 382, 383, 450, 487, 488,
]
DISCRIMINATING_RESIDUES = [109, 112, 320, 404]


DEFAULT_CANDIDATES = [
    {
        "id": "S-fadrozole",
        "name": "S-fadrozole",
        "smiles": "N#Cc1ccc([C@@H]2CCCc3cncn32)cc1",
        "parent_id": None,
        "modification": "calculated seed",
        "rationale": "Unresolved B1/B2 seed and starting scaffold for B1-directed analogs.",
        "hypothesis_priority_eV": 0.0,
        "status": "calculated",
    },
    {
        "id": "R-fadrozole",
        "name": "R-fadrozole",
        "smiles": "N#Cc1ccc([C@H]2CCCc3cncn32)cc1",
        "parent_id": None,
        "modification": "calculated stereochemical reference",
        "rationale": "Known wrong-direction reference for a CYP11B1 campaign.",
        "hypothesis_priority_eV": -0.05,
        "status": "calculated",
    },
    {
        "id": "S-para-carboxamide",
        "name": "S-fadrozole para-carboxamide",
        "smiles": "NC(=O)c1ccc([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "replace nitrile with primary carboxamide",
        "rationale": "Adds a stronger neutral donor/acceptor pattern for the B1 Arg404 region.",
        "hypothesis_priority_eV": 0.08,
        "status": "proposed",
    },
    {
        "id": "S-para-N-methylcarboxamide",
        "name": "S-fadrozole para-N-methylcarboxamide",
        "smiles": "CNC(=O)c1ccc([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "replace nitrile with N-methyl carboxamide",
        "rationale": "Tests the Arg404-directed amide while adding a small hydrophobic contact.",
        "hypothesis_priority_eV": 0.06,
        "status": "proposed",
    },
    {
        "id": "S-para-sulfonamide",
        "name": "S-fadrozole para-sulfonamide",
        "smiles": "NS(=O)(=O)c1ccc([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "replace nitrile with sulfonamide",
        "rationale": "Provides two neutral acceptors and one donor near the B1 Arg404 region.",
        "hypothesis_priority_eV": 0.07,
        "status": "proposed",
    },
    {
        "id": "S-para-methylsulfone",
        "name": "S-fadrozole para-methylsulfone",
        "smiles": "CS(=O)(=O)c1ccc([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "replace nitrile with methyl sulfone",
        "rationale": "Tests a neutral, strongly polarized Arg404-facing group without a donor.",
        "hypothesis_priority_eV": 0.05,
        "status": "proposed",
    },
    {
        "id": "S-meta-hydroxy",
        "name": "S-fadrozole meta-hydroxy",
        "smiles": "N#Cc1cc(O)c([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "add meta hydroxyl",
        "rationale": "Tests a compact donor/acceptor for the B1 Ser112/His109 polar region.",
        "hypothesis_priority_eV": 0.07,
        "status": "proposed",
    },
    {
        "id": "S-meta-methoxy",
        "name": "S-fadrozole meta-methoxy",
        "smiles": "COc1cc(C#N)ccc1[C@@H]1CCCc2cncn21",
        "parent_id": "S-fadrozole",
        "modification": "add meta methoxy",
        "rationale": "Separates hydrogen-bond acceptance and steric effects near residues 109/112.",
        "hypothesis_priority_eV": 0.04,
        "status": "proposed",
    },
    {
        "id": "S-meta-fluoro",
        "name": "S-fadrozole meta-fluoro",
        "smiles": "N#Cc1cc(F)c([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "add meta fluorine",
        "rationale": "Low-size steric/electronic probe for the B1 Val320 versus B2 Ala320 difference.",
        "hypothesis_priority_eV": 0.05,
        "status": "proposed",
    },
    {
        "id": "S-meta-fluoro-carboxamide",
        "name": "S-fadrozole meta-fluoro para-carboxamide",
        "smiles": "NC(=O)c1cc(F)c([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "combine meta fluorine and para carboxamide",
        "rationale": "Combines the Val320 size probe with the Arg404-directed polar group.",
        "hypothesis_priority_eV": 0.09,
        "status": "proposed",
    },
    {
        "id": "S-pyridyl-nitrile",
        "name": "S-fadrozole pyridyl nitrile",
        "smiles": "N#Cc1ncc([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "replace one phenyl carbon with ring nitrogen",
        "rationale": "Adds a directional acceptor while retaining the nitrile and approximate size.",
        "hypothesis_priority_eV": 0.06,
        "status": "proposed",
    },
    {
        "id": "S-para-methylester",
        "name": "S-fadrozole para-methyl ester",
        "smiles": "COC(=O)c1ccc([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "replace nitrile with methyl ester",
        "rationale": "Neutral acceptor-rich control for the carboxamide hypothesis.",
        "hypothesis_priority_eV": 0.03,
        "status": "proposed",
    },
    {
        "id": "S-para-carboxylic-acid",
        "name": "S-fadrozole para-carboxylic acid",
        "smiles": "O=C(O)c1ccc([C@@H]2CCCc3cncn32)cc1",
        "parent_id": "S-fadrozole",
        "modification": "replace nitrile with carboxylic acid",
        "rationale": "Strong Arg404 interaction hypothesis; requires explicit protonation-state comparison.",
        "hypothesis_priority_eV": 0.04,
        "status": "proposed",
        "flags": ["protomer_sensitive"],
    },
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _canonical_and_features(smiles):
    """Return RDKit-normalized structure data when RDKit is available."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
        from rdkit.Chem import rdFingerprintGenerator
    except ImportError:
        return {
            "canonical_smiles": smiles,
            "fingerprint_bits": sorted(_fallback_fingerprint(smiles)),
            "features": {},
            "structure_backend": "smiles-token-fallback",
        }
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit rejected SMILES: {smiles}")
    centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
    if any(label == "?" for _, label in centers):
        raise ValueError(f"Unassigned stereocenter in {smiles}")
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=2048, includeChirality=True
    )
    fingerprint = generator.GetFingerprint(mol)
    return {
        "canonical_smiles": Chem.MolToSmiles(mol, isomericSmiles=True),
        "fingerprint_bits": list(fingerprint.GetOnBits()),
        "features": {
            "formal_charge": int(Chem.GetFormalCharge(mol)),
            "molecular_weight": float(Descriptors.MolWt(mol)),
            "cLogP": float(Crippen.MolLogP(mol)),
            "TPSA_A2": float(rdMolDescriptors.CalcTPSA(mol)),
            "H_bond_donors": int(Lipinski.NumHDonors(mol)),
            "H_bond_acceptors": int(Lipinski.NumHAcceptors(mol)),
            "rotatable_bonds": int(Lipinski.NumRotatableBonds(mol)),
            "chiral_centers": [{"atom_index": i, "assignment": label} for i, label in centers],
        },
        "structure_backend": "RDKit",
    }


def _fallback_fingerprint(smiles):
    bits = set()
    wrapped = f"^^{smiles}$$"
    for size in (2, 3, 4):
        for start in range(len(wrapped) - size + 1):
            token = wrapped[start:start + size].encode()
            bits.add(int.from_bytes(hashlib.sha256(token).digest()[:2], "big"))
    return bits


def tanimoto(left, right):
    left, right = set(left), set(right)
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def score_pose_summary(summary, target_isoform, signal_floor_eV=0.05, minimum_pose_count=3):
    if target_isoform not in ENZYMES:
        raise ValueError(f"Unsupported target isoform: {target_isoform}")
    cycles = summary.get("cycles") or []
    if not cycles:
        raise ValueError("Pose summary contains no cycles")
    deltas = [float(row["B2_minus_B1_eV"]) for row in cycles]
    target_key = "B1_exchange_eV" if target_isoform == "CYP11B1" else "B2_exchange_eV"
    target_exchange = [float(row[target_key]) for row in cycles]
    oriented = deltas if target_isoform == "CYP11B1" else [-value for value in deltas]
    robust_selectivity = min(oriented)
    worst_target_exchange = max(target_exchange)
    passes_selectivity = robust_selectivity > signal_floor_eV
    passes_target_exchange = worst_target_exchange < 0.0
    passes_pose_count = len(cycles) >= minimum_pose_count
    return {
        "target_isoform": target_isoform,
        "pose_count": len(cycles),
        "delta_B2_minus_B1_range_eV": [min(deltas), max(deltas)],
        "target_exchange_range_eV": [min(target_exchange), max(target_exchange)],
        "robust_selectivity_eV": robust_selectivity,
        "selectivity_margin_over_floor_eV": robust_selectivity - signal_floor_eV,
        "worst_target_exchange_eV": worst_target_exchange,
        "passes_selectivity_gate": passes_selectivity,
        "passes_target_exchange_gate": passes_target_exchange,
        "minimum_pose_count": minimum_pose_count,
        "passes_pose_count_gate": passes_pose_count,
        "lead_eligible": passes_selectivity and passes_target_exchange and passes_pose_count,
    }


def _campaign_path(path):
    path = Path(path)
    return path / "campaign.json" if path.is_dir() or not path.suffix else path


def load_campaign(path):
    campaign_path = _campaign_path(path)
    data = json.loads(campaign_path.read_text())
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported campaign schema: {data.get('schema_version')}")
    return campaign_path, data


def save_campaign(path, campaign):
    path = _campaign_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    campaign["updated_at"] = utc_now()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(campaign, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)
    return path


def create_campaign(target_isoform="CYP11B1"):
    if target_isoform not in ENZYMES:
        raise ValueError(f"Unsupported target isoform: {target_isoform}")
    candidates = []
    for template in DEFAULT_CANDIDATES:
        candidate = dict(template)
        candidate.setdefault("flags", [])
        candidate.update(_canonical_and_features(candidate["smiles"]))
        candidates.append(candidate)
    counter = "CYP11B2" if target_isoform == "CYP11B1" else "CYP11B1"
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": f"{target_isoform.lower()}-selectivity-v1",
        "created_at": now,
        "updated_at": now,
        "objective": {
            "target_isoform": target_isoform,
            "counter_isoform": counter,
            "descriptor": "relaxed_ligand_water_exchange_eV",
            "delta_definition": "exchange(CYP11B2) - exchange(CYP11B1)",
            "signal_floor_eV": 0.05,
            "minimum_pose_count": 3,
            "target_exchange_gate": "all tested target exchange energies < 0 eV",
            "selectivity_gate": (
                "minimum pose delta > +0.05 eV" if target_isoform == "CYP11B1"
                else "maximum pose delta < -0.05 eV"
            ),
        },
        "preparation_gate": {
            "required_before_new_analog_ranking": True,
            "baseline_pocket_residues": BASE_POCKET_RESIDUES,
            "added_discriminating_residues": DISCRIMINATING_RESIDUES,
            "expanded_pocket_residues": sorted(set(BASE_POCKET_RESIDUES + DISCRIMINATING_RESIDUES)),
            "reason": (
                "The current pocket omits B1/B2 differences at residues 109, 112, 320, and 404; "
                "analog design must include them before comparing chemistry hypotheses."
            ),
            "status": "required",
        },
        "model": {
            "kind": "chiral Morgan-fingerprint kernel active learning",
            "minimum_observations_for_surrogate": 4,
            "current_mode": "diversity_plus_chemistry_prior",
            "uncertainty_policy": "favor candidates dissimilar to calculated molecules",
        },
        "candidates": candidates,
        "observations": [],
    }


def ingest_summary(campaign, candidate_id, summary_path):
    candidate = next((row for row in campaign["candidates"] if row["id"] == candidate_id), None)
    if candidate is None:
        raise ValueError(f"Unknown candidate: {candidate_id}")
    path = Path(summary_path).resolve()
    summary = json.loads(path.read_text())
    metrics = score_pose_summary(
        summary,
        campaign["objective"]["target_isoform"],
        campaign["objective"]["signal_floor_eV"],
        campaign["objective"].get("minimum_pose_count", 3),
    )
    required_residues = set(campaign["preparation_gate"]["expanded_pocket_residues"])
    observed_protocols = []
    protocol_gate = True
    for cycle in summary.get("cycles", []):
        run_input = Path(cycle["run"]) / "input.json"
        if not run_input.exists():
            protocol_gate = False
            continue
        manifest = json.loads(run_input.read_text())
        residues = set(manifest["enzymes"]["CYP11B1"]["cluster_ligand"]
                       .get("provenance", {}).get("selected_residue_numbers", []))
        observed_protocols.append({
            "run": str(run_input.parent),
            "preparation_protocol": manifest.get("preparation_protocol"),
            "selected_residue_numbers": sorted(residues),
        })
        protocol_gate = protocol_gate and required_residues <= residues
    observation = {
        "candidate_id": candidate_id,
        "source": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "ingested_at": utc_now(),
        "summary_status": summary.get("status"),
        "passes_expanded_pocket_gate": protocol_gate,
        "eligible_for_surrogate": protocol_gate and metrics["passes_pose_count_gate"],
        "eligible_for_model": protocol_gate,
        "model_weight": 1.0 if metrics["passes_pose_count_gate"] else 0.35,
        "observed_protocols": observed_protocols,
        **metrics,
    }
    campaign["observations"] = [
        row for row in campaign["observations"] if row["candidate_id"] != candidate_id
    ] + [observation]
    candidate["status"] = "lead" if observation["lead_eligible"] else "calculated"
    return observation


def _predict(candidate, observed, candidate_by_id):
    if not observed:
        return 0.0, 1.0, []
    neighbors = []
    for row in observed:
        reference = candidate_by_id[row["candidate_id"]]
        similarity = tanimoto(candidate["fingerprint_bits"], reference["fingerprint_bits"])
        neighbors.append((similarity, row["robust_selectivity_eV"], row["candidate_id"],
                          float(row.get("model_weight", 1.0))))
    neighbors.sort(reverse=True)
    weights = [max(similarity, 1e-6) ** 4 * quality for similarity, _, _, quality in neighbors]
    predicted = sum(weight * row[1] for weight, row in zip(weights, neighbors)) / sum(weights)
    uncertainty = 1.0 - neighbors[0][0]
    return predicted, uncertainty, [
        {"candidate_id": cid, "similarity": similarity, "robust_selectivity_eV": score,
         "model_weight": quality}
        for similarity, score, cid, quality in neighbors[:3]
    ]


def rank_candidates(campaign, batch_size=5):
    all_observed = campaign["observations"]
    observed = [row for row in all_observed if row.get("eligible_for_model")]
    failed_ids = {row["candidate_id"] for row in campaign.get("failures", [])}
    by_id = {row["id"]: row for row in campaign["candidates"]}
    use_surrogate = len(observed) >= campaign["model"]["minimum_observations_for_surrogate"]
    ranked = []
    for candidate in campaign["candidates"]:
        if candidate["id"] in {row["candidate_id"] for row in all_observed} | failed_ids:
            continue
        prediction, uncertainty, neighbors = _predict(candidate, observed, by_id)
        prior = float(candidate.get("hypothesis_priority_eV", 0.0))
        # Before four calculated chemotypes, uncertainty mainly drives broad learning.
        beta = 0.20 if use_surrogate else 0.12
        acquisition = prediction + prior + beta * uncertainty
        if "protomer_sensitive" in candidate.get("flags", []):
            acquisition -= 0.04
        ranked.append({
            "candidate_id": candidate["id"],
            "name": candidate["name"],
            "canonical_smiles": candidate["canonical_smiles"],
            "prediction_mode": "kernel_surrogate" if use_surrogate else "seed_similarity_exploration",
            "predicted_robust_selectivity_eV": prediction,
            "uncertainty": uncertainty,
            "chemistry_prior_eV": prior,
            "acquisition_score": acquisition,
            "rationale": candidate["rationale"],
            "flags": candidate.get("flags", []),
            "nearest_observations": neighbors,
        })
    ranked.sort(key=lambda row: (-row["acquisition_score"], row["candidate_id"]))
    return ranked[:batch_size]


def render_report(campaign, ranking):
    objective = campaign["objective"]
    observations = {row["candidate_id"]: row for row in campaign["observations"]}
    lines = [
        f"# {objective['target_isoform']} selectivity design campaign",
        "",
        f"Target: **{objective['target_isoform']}** over **{objective['counter_isoform']}**.",
        "",
        "A molecule is lead-eligible only when every accepted pose has favorable target exchange "
        "and the complete selectivity range clears the 0.05 eV engineering floor. These are "
        "UMA potential-energy screening criteria, not affinity or free-energy predictions.",
        "",
        "## Preparation gate",
        "",
        f"Status: **{campaign['preparation_gate']['status']}**. " + campaign["preparation_gate"]["reason"],
        "",
        "Required added residues: " + ", ".join(map(str, campaign["preparation_gate"]["added_discriminating_residues"])),
        "",
        "## Existing observations",
        "",
        "| Candidate | Poses | Robust target selectivity (eV) | Expanded pocket | Lead eligible |",
        "|---|---:|---:|---|---|",
    ]
    for candidate in campaign["candidates"]:
        row = observations.get(candidate["id"])
        if row:
            lines.append(
                f"| {candidate['name']} | {row['pose_count']} | {row['robust_selectivity_eV']:+.6f} | "
                f"{'yes' if row.get('passes_expanded_pocket_gate') else 'no'} | "
                f"{'yes' if row['lead_eligible'] else 'no'} |"
            )
    if campaign.get("failures"):
        lines += ["", "## Excluded preparations or runs", "",
                  "| Candidate | Stage | Reason |", "|---|---|---|"]
        for failure in campaign["failures"]:
            lines.append(
                f"| {failure['candidate_id']} | {failure['stage']} | {failure['reason']} |"
            )
    lines += [
        "",
        "## Next proposed batch",
        "",
        "| Rank | Candidate | Acquisition | Predicted robust selectivity (eV) | Uncertainty | Hypothesis |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for index, row in enumerate(ranking, 1):
        lines.append(
            f"| {index} | {row['name']} | {row['acquisition_score']:+.4f} | "
            f"{row['predicted_robust_selectivity_eV']:+.4f} | {row['uncertainty']:.3f} | "
            f"{row['rationale']} |"
        )
    model_observations = sum(row.get("eligible_for_model", False)
                             for row in campaign["observations"])
    robust_observations = sum(row.get("eligible_for_surrogate", False)
                              for row in campaign["observations"])
    lines += [
        "",
        f"The ranking currently uses {model_observations} expanded-pocket observations, including "
        f"{robust_observations} full pose set(s). Single-pose observations receive lower model weight. "
        "At four or more distinct calculated candidates, the campaign switches to the fingerprint "
        "kernel surrogate and balances predicted selectivity with uncertainty.",
        "",
    ]
    return "\n".join(lines)


def initialize(path, target_isoform):
    campaign = create_campaign(target_isoform)
    defaults = {
        "S-fadrozole": ROOT / "runs/exchange-pose-sensitivity-v1/summary.json",
        "R-fadrozole": ROOT / "runs/exchange-R-pose-sensitivity-v1/summary.json",
    }
    for candidate_id, summary in defaults.items():
        if summary.exists():
            ingest_summary(campaign, candidate_id, summary)
    campaign_path = save_campaign(path, campaign)
    ranking = rank_candidates(campaign)
    report = campaign_path.parent / "REPORT.md"
    report.write_text(render_report(campaign, ranking))
    queue = campaign_path.parent / "next_batch.json"
    queue.write_text(json.dumps({"generated_at": utc_now(), "candidates": ranking}, indent=2) + "\n")
    return campaign_path, report, queue


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a B1/B2 design campaign")
    init.add_argument("--out", type=Path, required=True)
    init.add_argument("--target", choices=ENZYMES, default="CYP11B1")
    ingest = sub.add_parser("ingest", help="add a pose-sensitivity summary")
    ingest.add_argument("campaign", type=Path)
    ingest.add_argument("candidate_id")
    ingest.add_argument("summary", type=Path)
    rank = sub.add_parser("rank", help="regenerate candidate ranking and report")
    rank.add_argument("campaign", type=Path)
    rank.add_argument("--batch-size", type=int, default=5)
    args = parser.parse_args(argv)

    if args.command == "init":
        paths = initialize(args.out, args.target)
        print(json.dumps({"campaign": str(paths[0]), "report": str(paths[1]), "queue": str(paths[2])}, indent=2))
        return

    campaign_path, campaign = load_campaign(args.campaign)
    if args.command == "ingest":
        observation = ingest_summary(campaign, args.candidate_id, args.summary)
        save_campaign(campaign_path, campaign)
        print(json.dumps(observation, indent=2))
    ranking = rank_candidates(campaign, getattr(args, "batch_size", 5))
    (campaign_path.parent / "next_batch.json").write_text(
        json.dumps({"generated_at": utc_now(), "candidates": ranking}, indent=2) + "\n"
    )
    (campaign_path.parent / "REPORT.md").write_text(render_report(campaign, ranking))
    print(json.dumps(ranking, indent=2))


if __name__ == "__main__":
    main()
