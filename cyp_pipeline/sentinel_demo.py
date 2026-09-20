"""Generate the portable IsoForm workspace.

The page displays existing evidence, embeds reference protein coordinates and
can submit prepared UMA jobs through the optional local Sentinel server.
New molecules require preparation and evidence before a selectivity decision.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .screening import catalog_payload
from .calibrated_selectivity import handoff_catalog


def _distance(first, second):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _pdb_atom(line):
    """Parse the standard coordinate columns used by the downloaded PDB."""
    try:
        return {
            "serial": int(line[6:11]),
            "name": line[12:16].strip(),
            "residue": line[17:20].strip(),
            "chain": line[21].strip(),
            "residue_number": int(line[22:26]),
            "element": (line[76:78].strip() or line[12:16].strip()[0]).upper(),
            "xyz": [float(line[30:38]), float(line[38:46]), float(line[46:54])],
        }
    except (IndexError, ValueError):
        return None


def structure_view(pdb_path, chain="A", ligand_code="0T3"):
    """Create a small, actual-coordinate payload for the offline canvas viewer.

    Protein atoms are selected only for display: a whole residue is included if
    it has a heavy atom within 5 Å of the crystallographic ligand.  The display
    must not be confused with a calculation-ready quantum/MLIP cluster.
    """
    pdb_path = Path(pdb_path)
    records = []
    for line in pdb_path.read_text(errors="replace").splitlines():
        if line.startswith('ENDMDL'):
            break
        if line.startswith(("ATOM  ", "HETATM")):
            atom = _pdb_atom(line)
            if atom and atom["chain"] == chain and atom["element"] != "H" and line[16] in (' ', 'A'):
                records.append(atom)
    ligand = [atom for atom in records if atom["residue"] == ligand_code]
    heme = [atom for atom in records if atom["residue"] == "HEM"]
    if not ligand or not heme:
        raise ValueError(f"{pdb_path} does not contain {ligand_code} and HEM in chain {chain}")
    iron = next((atom for atom in heme if atom["element"] == "FE"), None)
    if iron is None:
        raise ValueError(f"{pdb_path} has no heme iron in chain {chain}")

    near_residues = {
        (atom["residue"], atom["residue_number"])
        for atom in records
        if atom["residue"] not in {ligand_code, "HEM", "HOH"}
        and any(_distance(atom["xyz"], ligand_atom["xyz"]) <= 5.0 for ligand_atom in ligand)
    }
    pocket = [
        atom for atom in records
        if (atom["residue"], atom["residue_number"]) in near_residues
    ]
    axial_sulfur = min(
        (atom for atom in records if atom["residue"] == "CYS" and atom["name"] == "SG"),
        key=lambda atom: _distance(atom["xyz"], iron["xyz"]),
    )
    axial_residue = [
        atom for atom in records
        if atom["residue"] == axial_sulfur["residue"] and atom["residue_number"] == axial_sulfur["residue_number"]
    ]
    selected = []
    seen = set()
    for group, atoms in (("pocket", pocket), ("heme", heme), ("ligand", ligand), ("axial", axial_residue)):
        for atom in atoms:
            if atom["serial"] not in seen:
                seen.add(atom["serial"])
                selected.append({
                    "p": [round(value, 3) for value in atom["xyz"]],
                    "e": atom["element"],
                    "group": group,
                    "label": f"{atom['residue']} {atom['residue_number']} · {atom['name']}",
                })
    # Retain every Cα. Sampling by the atom-record index broke the trace into
    # disconnected pieces and made the global protein shape disappear.
    backbone = [
        [round(value, 3) for value in atom["xyz"]]
        for atom in records if atom["name"] == "CA"
    ]
    return {
        "pdb": pdb_path.stem,
        "chain": chain,
        "ligand_code": ligand_code,
        "ligand_label": {"0T3": "R-fadrozole", "JD7": "S-fadrozole", "YSY": "Osilodrostat"}.get(ligand_code, ligand_code),
        "atoms": selected,
        "backbone": backbone,
        "center": [round(value, 3) for value in iron["xyz"]],
        "iron": [round(value, 3) for value in iron["xyz"]],
        "donor": [round(value, 3) for value in min(ligand, key=lambda atom: _distance(atom["xyz"], iron["xyz"]))["xyz"]],
        "sulfur": [round(value, 3) for value in axial_sulfur["xyz"]],
        "iron_to_nearest_ligand_atom": round(min(_distance(iron["xyz"], atom["xyz"]) for atom in ligand), 3),
        "iron_to_axial_sulfur": round(_distance(iron["xyz"], axial_sulfur["xyz"]), 3),
        "pocket_residue_count": len(near_residues),
    }


def _candidate_payload(card):
    assay = card["paired_assay_validation"][0] if card["paired_assay_validation"] else None
    boltz = card["boltz"]
    return {
        "label": card["ligand"],
        "decision": card["decision"],
        "decision_scope": card["decision_scope"],
        "target": card["target"]["id"],
        "off_target": card["mandatory_primary_off_target"]["id"],
        "boltz_fold": boltz.get("target_over_off_target_fold"),
        "boltz_status": boltz.get("status"),
        "model_gate": card["model_screen"]["status"],
        "uma": card["uma_local_chemistry"]["status"],
        "geometry": card["boltz_geometry"]["status"],
        "assay_fold": assay.get("target_over_off_target_fold") if assay else None,
        "assay_endpoint": assay.get("endpoint") if assay else None,
        "alerts": card["alerts"],
        "next_action": card["recommended_next_action"],
    }


def _embedded_json(value):
    # Prevent a candidate label or PDB field from ending the script element.
    return json.dumps(value, separators=(",", ":")).replace("</", "<\\/")


def _structure_fallback(structure):
    """A coordinate-derived SVG stays visible even when JavaScript is blocked."""
    points = structure["backbone"] or [atom["p"] for atom in structure["atoms"]]
    if not points:
        return '<p class="viewer-error">No coordinates available for this structure.</p>'
    center = [sum(p[i] for p in points) / len(points) for i in range(3)]
    radius = max(_distance(p, center) for p in points) or 1
    def project(point):
        x, y, z = [point[i] - center[i] for i in range(3)]
        return (350 + (x * .878 + z * .479) * 175 / radius,
                230 + (y * .929 - (-x * .479 + z * .878) * -.37) * 175 / radius)
    paths = []
    for a, b in zip(points, points[1:]):
        if _distance(a, b) < 4.8:
            x, y = project(a)
            u, v = project(b)
            paths.append(f'<path d="M{x:.2f},{y:.2f}L{u:.2f},{v:.2f}"/>')
    dots = []
    for atom in structure["atoms"]:
        if atom["group"] in ("ligand", "heme"):
            x, y = project(atom["p"])
            color = "#c48824" if atom["group"] == "heme" else "#087965"
            dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.3" fill="{color}"/>')
    return ('<svg viewBox="0 0 700 460" role="img" aria-label="Protein reference coordinates">'
            '<g stroke="#4387a3" stroke-width="3.5" stroke-linecap="round">'
            + "".join(paths) + '</g>' + "".join(dots) + '</svg>')


def interactive_html(report, structure, structures=None):
    """Embed a light interface, isolated 3D renderer and existing evidence."""
    panel = report["panel"]
    target = panel["target"]
    payload = {
        "target": {"id": target["id"], "sequence": target["sequence"],
                   "binding_site": target.get("binding_site", "")},
        "policy": panel["policy"],
        "next_tier": [entry["id"] for entry in panel["off_target_panel"]
                      if entry["role"] != "mandatory_primary"],
        "candidates": {card["ligand"]: _candidate_payload(card) for card in report["cards"]},
        "structure": structure,
        "structures": structures or {target["id"]: structure},
        "screening": catalog_payload(),
        "calibrated_candidates": handoff_catalog(),
    }
    assets = Path(__file__).with_name("web")
    page = (assets / "sentinel.html").read_text()
    replacements = {
        "__STYLE__": (assets / "sentinel.css").read_text(),
        "__VIEWER__": (assets / "viewer.js").read_text(),
        "__APP__": (assets / "calibrated.js").read_text() + '\n' + (assets / "sentinel.js").read_text(),
        "__FALLBACK__": _structure_fallback(structure),
        "__DATA__": _embedded_json(payload),
    }
    for marker, content in replacements.items():
        page = page.replace(marker, content)
    return page


def write_interactive_demo(result_path, structure_path, out):
    report = json.loads(Path(result_path).read_text())
    if not report.get("cards"):
        raise ValueError("Sentinel result has no candidate cards")
    structure = structure_view(structure_path)
    structures = {report['panel']['target']['id']: structure}
    b1 = Path(structure_path).with_name('6M7X.pdb')
    if Path(structure_path).stem.upper() == '4FDH' and b1.is_file():
        structures['CYP11B1'] = structure_view(b1, ligand_code='JD7')
    if Path(structure_path).stem.upper() == '4FDH':
        from .structure_library import reference_views
        structures.update(reference_views(Path(structure_path).resolve().parents[2]))
    out = Path(out)
    out.write_text(interactive_html(report, structure, structures))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, help="Sentinel result.json to embed")
    parser.add_argument("--structure", required=True, help="Experimental PDB used only as a reference coordinate view")
    parser.add_argument("--out", required=True, help="New self-contained HTML path")
    args = parser.parse_args(argv)
    try:
        print(write_interactive_demo(args.result, args.structure, args.out))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
