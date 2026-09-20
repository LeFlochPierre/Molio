# Expandable screening framework

The current expansion is a **working CPU-only screening planner**, not an
automated five-target binding prediction system. It extends the existing
browser without changing the saved assay interpretation or UMA exchange formula.
There is now also a real **prepared-pocket batch runner** for arbitrary protein
IDs; see [Run UMA pockets](UMA_POCKETS.md). That route requires complete prepared
coordinates and returns total energies/forces, not binding/selectivity scores.

## What works now

- Select an intended target and a curated counter-screen panel.
- The supplied catalog contains CYP11B2, CYP11B1, CYP11A1, CYP17A1 and CYP19A1.
- Select a known demo candidate or enter a new candidate name and SMILES.
- Provide a custom protein sequence (single FASTA record or raw sequence).
- Check whether the existing allow-listed UMA input manifests are present,
  match the selected preset, and pass schema/geometry checks.
- See preparation gaps, target-selection reasons, hardware needs and next steps.
- Download a JSON plan with catalog/input hashes and a reproducible plan ID.

This stage neither loads model weights nor starts a job. Every target's new
binding assessment remains `not_run`; no assay scores are transferred to new
compounds or targets. Existing saved evidence is still available in the
separate **Review evidence** mode.

For R/S-fadrozole with CYP11B2 (or CYP11B1) as the intended target, a complete
local checkout normally reports 2 of 5 proteins with applicable prepared UMA
inputs. These are provisional inputs, not validated chemistry. The remaining
three require preparation. If an input file is missing or invalid on a new
machine, the plan reports that instead of claiming availability.

For other compounds, custom sequences or a different intended target, the
existing pair protocol is not automatically reused. Naming a new molecule
"R-fadrozole" cannot unlock a preset. Registered target IDs cannot accept an
overridden sequence; sequence variants must use the custom-target route.

RDKit is optional in the **server interpreter**. If present, it parses new
SMILES and records syntax, canonical representation and unassigned tetrahedral
centers. This is not complete stereochemistry/protonation validation. Without
RDKit, the plan explicitly reports that the SMILES has not been chemically
checked; no new molecule becomes calculation-ready.

## Browser

From the project root, start the server (no GPU, weights or UMA environment
are required for planning):

```bash
python3 -m cyp_pipeline.sentinel_server \
  --site runs/selectivity-sentinel-demo-v3/demo.html \
  --port 8000 --bind 0.0.0.0
```

Forward port 8000, visit `/demo.html`, and select
**Screen more proteins** in the action menu. Choose a candidate,
intended target and panel, then **Check panel**. For custom compounds,
choose **New candidate** and enter SMILES; for custom proteins, choose
**New protein sequence**. A custom sequence is an additional target alongside
the selected panel, not an identity match or automatic homology search.

In planning mode the viewer shows the original experimental references; it
does not fabricate structures for additional targets. In **Run prepared
pockets · UMA** it shows checked uploaded coordinates.

The existing **Run CYP pair · UMA** mode still requires `--enable-uma`,
a compatible interpreter/checkpoint/backend and runtime preflight. It remains
limited to the prepared R/S-fadrozole B2/B1 pair. Its sign is always B2 minus B1,
regardless of the intended target in a previously generated plan.

After updating this code, restart an older server process and hard-refresh the
browser. A plain `python -m http.server` cannot provide the planning API.

## Command line and API

```bash
python3 -m cyp_pipeline.screening --candidate r_fadrozole --target CYP11B2

python3 -m cyp_pipeline.screening \
  --candidate custom --name 'Example input only' --smiles 'CCO' \
  --target CYP11B2 --out runs/example-screen-plan.json
```

The ethanol SMILES above is just an input-format example, not a CYP ligand claim.
For a sequence, use `--target custom --sequence-file protein.fasta`. Export
refuses to overwrite an existing output file. The default panel is
`steroidogenic_p450`; `--panel cyp11_pair` selects the original pair only.

`GET /api/screen-catalog` returns the catalog and registered candidate IDs.
`POST /api/screen-plan` takes a bounded JSON request:

```json
{
  "candidate_id": "r_fadrozole",
  "target_id": "CYP11B2",
  "panel_id": "steroidogenic_p450"
}
```

For `candidate_id: custom`, provide `smiles` and optionally `candidate_name`.
For `target_id: custom`, provide `target_sequence`. Unknown fields are rejected;
the request cannot provide filesystem paths, commands or execution settings.
Planning does not call `/api/jobs` or write server-side artifacts. Export is an
explicit browser download or CLI action.

## Extending to a new family

The default registry is `cyp_pipeline/data/screening_catalog.json`, packaged
with the Python module. A catalog contains target IDs with labels, families
and reasons for screening, plus named panels containing those IDs. Supply a
curated alternate catalog with `--catalog path/to/catalog.json` to the CLI or
server. Adding a catalog entry **does not authorize a new model executor**.

The next milestones are:

1. Prepare and review the three additional CYP targets, including structures,
   ligand states, relevant cofactors, pocket boundaries and electronic states.
2. Add checked structural-model adapters, retaining native outputs and failures.
3. Benchmark held-out compounds against compatible experimental endpoints;
   compare simple baselines, Boltz-only and workflows that include UMA.
4. Demonstrate a second target family before making broader generalization claims.
5. Add target discovery using ligand/sequence/pocket evidence, with explicit
   coverage and applicability limits. This is not implemented yet.

The supplied panel was curated for the original CYP project. It may be
irrelevant to an arbitrary custom protein; its biological relevance must be
reviewed. Do not interpret a missing score as a non-binder, a preparation check
as model validation, or raw UMA total energies as cross-protein affinities.

## Hardware and verification

Planning, report generation and the browser viewer need no GPU. The small
prepared UMA calculations also support a CPU backend; larger batches benefit
from GPU execution. Boltz's maintainers support CPU inference but describe it
as significantly slower than GPU inference ([official repository](https://github.com/jwohlwend/boltz)).
No GPU model/VRAM requirement is asserted for new panels until their actual
inputs and workloads have been tested.

```bash
python3 -m unittest tests.test_screening tests.test_sentinel_demo tests.test_sentinel_server -v
# Optional Playwright environment; no model jobs are launched by default:
python scripts/check_sentinel_browser.py
```

Browser checks cover the real planning API, downloads, five-protein coverage,
custom targets/compounds, input rejection, mobile layout and the original 3D
viewer/reference evidence. Use `--live` only when intentionally testing the
existing real UMA pair as well; `--live-batch` tests the new prepared-pocket
execution route on the existing R-fadrozole example. Neither is run by default.
