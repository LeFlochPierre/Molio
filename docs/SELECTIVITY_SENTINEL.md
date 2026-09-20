# Selectivity Sentinel

The demo now also includes **Screen more proteins**, an expandable
multi-target preparation planner. See [Screening framework](SCREENING_FRAMEWORK.md)
for current capabilities, hardware requirements and the explicit boundary
between planning and actual model execution. The three next-tier CYP proteins
remain unassessed; adding them to a plan does not create predictions.

For real energy/force execution on additional prepared pockets, use the new
**Run prepared pockets · UMA** mode and [input guide](UMA_POCKETS.md). It accepts
arbitrary protein IDs with full atomistic preparation, not raw PDBs/sequences.

Selectivity Sentinel is a cofactor-aware, target-family **triage** workflow.
Given a declared target sequence, a curated off-target panel, a candidate, and
completed model outputs, it generates an evidence card that distinguishes:

- `validated_selective`: a paired reference meets the user-declared selectivity
  threshold for the target over its mandatory close paralog;
- `validated_not_selective`: the paired reference fails that threshold;
- `off_target_risk`: model-only evidence fails the target-margin policy; and
- `needs_assay`: model-only evidence is insufficient for any selectivity claim.

These are research decisions, not binding, safety, or clinical claims. A model
screen never produces a `validated_*` result without a supplied paired assay.

## What the pipeline does

```text
Target sequence + declared target-family panel + candidate
    -> target / mandatory-paralog Boltz pair
    -> optional UMA local heme-pocket perturbation check
    -> paired reference comparison, when available
    -> explicit pending counterscreens and next action
```

Boltz score differences are used only within the same model/seed/protocol.
UMA is a local capped-pocket geometry/energy stress test, not a global binding
affinity or proteome-wide off-target predictor. Never average UMA energies and
Boltz IC50-like values.

The first panel is deliberately narrow: CYP11B2 as target, CYP11B1 as its
mandatory close-paralog counter-screen, and CYP11A1/CYP17A1/CYP19A1 visible as
required-but-unassessed next-tier screens. The sequence is present in the panel
for traceability. Automatic genome-wide off-target discovery requires a curated
sequence/structure database and remains future work.

## Reproduce the working demo

The demo reads actual raw one-seed Boltz-2 outputs already produced for the
eight CYP cases. The native wrapper did not finalize after outputs were written,
so the report intentionally raises that alert and does not promote the output
to a formal model benchmark.

First produce optional structure diagnostics in the Boltz environment:

```bash
.venv-boltz/bin/python -m cyp_pipeline.sentinel_geometry \
  --experiment configs/extended-selectivity-benchmark.json \
  --boltz-root runs/benchmark-extended-boltz-pilot-v1 \
  --ccd-cache .cache/boltz/mols \
  --out runs/selectivity-sentinel-geometry-v1.json
```

```bash
python3 -m cyp_pipeline.sentinel \
  --panel configs/selectivity-sentinel-cyp11b2.json \
  --experiment configs/extended-selectivity-benchmark.json \
  --boltz-root runs/benchmark-extended-boltz-pilot-v1 \
  --geometry runs/selectivity-sentinel-geometry-v1.json \
  --assays data/benchmarks/fadrozole_assays.json \
  --assays data/benchmarks/osilodrostat_baxdrostat_assays.json \
  --ligand 'Osilodrostat (LCI699)' \
  --ligand Baxdrostat \
  --out runs/selectivity-sentinel-demo
```

With the declared 10-fold engineering policy, the paired references demonstrate
both outcomes:

| Candidate, CYP11B2 target | Paired endpoint | CYP11B2 over CYP11B1 | Demonstration |
|---|---|---:|---|
| Osilodrostat | IC50 | 3.57-fold | `validated_not_selective` |
| Baxdrostat | Ki | 100.8-fold | `validated_selective` |

The different endpoints are never numerically combined. Baxdrostat is a
directional/model-calibration reference for Boltz, whose output is IC50-like;
it is not a valid numerical Boltz IC50-error target. The report keeps this
distinction visible.

## Interactive browser demo

Generate a self-contained interface from the completed Sentinel report and an
experimental reference structure:

```bash
python3 -m cyp_pipeline.sentinel_demo \
  --result runs/selectivity-sentinel-demo-v3/result.json \
  --structure data/raw/4FDH.pdb \
  --out runs/selectivity-sentinel-demo-v3/demo.html
```

Open `demo.html` in a browser (or serve its folder). The lighter interface has
one candidate selector, an analysis-mode selector and one run button. Sequence
settings and detailed evidence are expandable. The four-step pathway shows
input validation, structure checks, evaluation and the result. In live mode,
progress comes from the eight UMA component artifacts, not a timer.

The protein viewer loads immediately without network assets. Switch between
CYP11B2 (4FDH) and CYP11B1 (6M7X), or between the full C-alpha trace and the
binding pocket. Drag/arrow keys rotate and scrolling or +/- zooms. A static
coordinate preview remains available with JavaScript disabled. The rendering
fix corrects a five-argument canvas transform that previously threw before
drawing, and retains all C-alpha atoms to preserve backbone continuity.

The structure is a reference CYP11B2/R-fadrozole complex; it is explicitly not
claimed to be a predicted pose for osilodrostat, baxdrostat, or a molecule the
user enters. Saved-evidence mode reads the existing report. Live mode calls the
local UMA API described below. A non-reference candidate remains
`needs_assay` until matched model inputs, geometry review, and a paired assay
are supplied to the command-line workflow.

For optional browser regression checks, install Playwright and its Chromium
runtime in a separate test environment and run
`python scripts/check_sentinel_browser.py`. It checks rendering, rotation,
protein switching, mobile overflow, both assay outcomes, input validation and
the static fallback. Add `--live` to launch one actual R-fadrozole UMA CPU job
through the browser and verify the resulting artifact.

## Local browser-to-UMA execution

Serve the generated page through the local Sentinel API (rather than
`python -m http.server`) to let the browser start a real UMA calculation for
the allow-listed, prepared R- or S-fadrozole CYP11B2/CYP11B1 pair:

```bash
python3 -m cyp_pipeline.sentinel_server \
  --site runs/selectivity-sentinel-demo-v3/demo.html \
  --port 8000 --bind 0.0.0.0 \
  --enable-uma
```

The server copies the selected manifest, freezes its coordinates, writes an
immutable job input, runs actual UMA four-component exchange evaluation, and
returns artifact status to the browser. Results are saved under
`runs/selectivity-sentinel-web-jobs/`. The exchange endpoint deliberately accepts
only a preset identifier—never arbitrary sequences, SMILES, paths, or commands.
New candidates must pass the normal structure/pose, charge/spin, and geometry
review process before they can be added as a preset.
The separate prepared-pocket endpoint accepts checked coordinate JSON for
single-point energy/force batches; it does not extend the exchange formula to
unprepared targets. See [its input contract](UMA_POCKETS.md).

The default is the local CPU UMA configuration. On a working A100 host, use
the hash-pinned CUDA config:

```bash
python3 -m cyp_pipeline.sentinel_server \
  --site runs/selectivity-sentinel-demo-v3/demo.html \
  --port 8000 --bind 0.0.0.0 \
  --backend configs/uma-s-1p1-a100.json \
  --enable-uma
```

This is genuine UMA model execution, but only a frozen-coordinate exploratory
potential-energy descriptor using provisional inputs. It is not a pose search,
free-energy calculation, binding prediction, safety screen, or a validated
selectivity conclusion.

## Adding a new candidate

1. Add target/off-target cases and a traceable ligand identity to an experiment
   manifest.
2. Prepare and run the same model protocol for target and each panel member.
3. Validate ligand identity, chirality, heme coordination, and clashes before
   importing scores.
4. Add UMA only for reviewed high-risk poses; expand its cluster/pose ensemble
   consistently across the target/paralog pair.
5. Run a paired biological counterscreen. Until then, retain `needs_assay` or
   `off_target_risk`; do not label the molecule selective.

Before saying this framework is patent-novel, conduct a dedicated prior-art
search. Its defensible project contribution is the explicit cofactor/geometry
gates, provenance, disagreement alerts, and abstention behavior.
