# Historical CYP pipeline notes

This is the preserved pre-sharing README. It contains successive research
snapshots, including statements that became outdated as the project evolved.
Follow the [current README](../README.md) for setup and the supported demo.
Paths in this historical document are relative to the repository root. Large
intermediate runs and model caches referenced here are not distributed.

**Current requested calculation:** relaxed four-energy ligand/water exchange for each enzyme. Use [the exchange-cycle workflow](docs/EXCHANGE_CYCLE.md) and `python -m cyp_pipeline.exchange`; the older `cyp_pipeline run` command below computes a different, legacy fragment-deformation descriptor. The A100 UMA v1.1 cross-check and provisional exchange runs have completed.

**New: multi-target screening plans.** The interactive demo can now build a
CPU-only plan across five curated CYP proteins, accept custom molecule/sequence
inputs and export preparation gaps without fabricating binding predictions.
See [the screening framework guide](docs/SCREENING_FRAMEWORK.md).

**New: prepared-pocket UMA batches.** Upload and check complete atomistic
pockets, view their actual coordinates, then run energy/force evaluations with
arbitrary protein IDs. See [the prepared-pocket guide](docs/UMA_POCKETS.md).
These totals do not constitute binding affinity or cross-protein selectivity.

**Current result:** S-fadrozole remains unresolved because its pose-sensitivity range crosses zero (-0.060203 to +0.080973 eV). R-fadrozole is the current provisional CYP11B2 lead: its valid pose range is -0.675412 to -0.664623 eV. See `runs/fadrozole-selectivity-v1/REPORT.md`. This is a model-screening result, not an affinity or validated selectivity ratio.


An executable starting point for the four-complex R/S-fadrozole × CYP11B1/CYP11B2 experiment. It separates reviewed chemical preparation from calculations and keeps synthetic demonstrations visibly labeled. No scientific selectivity result has been produced.

## Cross-model benchmark

The [benchmark workflow](docs/BENCHMARKING.md) compares model-native scores:
UMA exchange energies, Boltz-2 affinity predictions, and imported GNINA/Vina
scores. The original four fadrozole cases stay in `configs/experiment.json`;
`configs/extended-selectivity-benchmark.json` adds osilodrostat and baxdrostat.
Chai-1, AlphaFold 3 and DiffDock are pose comparators; RFdiffusion does not
supply a comparable small-molecule selectivity score.

```bash
python3 -m cyp_pipeline.benchmark_boltz prepare configs/extended-selectivity-benchmark.json runs/benchmark-inputs --msa-mode server
python3 -m cyp_pipeline.benchmark report --experiment configs/extended-selectivity-benchmark.json --assays data/benchmarks/fadrozole_assays.json --assays data/benchmarks/osilodrostat_baxdrostat_assays.json --inventory-root runs --out runs/model-benchmark-01
```

Preparing inputs and reporting do not run external models. Use the documented
Boltz runner for inference, then import its run directory with `--boltz-run`.
Missing predictions remain marked as not run. The assay reference is a small,
study-specific cellular IC50 comparison; it does not establish model accuracy.

## IsoForm web app

The interactive app is **IsoForm**. It opens on a live R/S-fadrozole paired screen, with the actual prepared B1/B2 pockets side by side. UMA runs produce an energy-direction card and an explicitly hypothetical Boltzmann energy-fold proxy—not predicted binding selectivity. Use **Prepare more targets → Build inputs** for the five-protein reference library and Boltz pose-input files. New references are not automatically complete UMA pockets. See [IsoForm: use, automatic inputs and energy interpretation](docs/ISOFORM.md).

## Selectivity Sentinel evidence engine

The [Selectivity Sentinel](docs/SELECTIVITY_SENTINEL.md) turns a declared
target-family panel, model outputs, local UMA checks, and paired assay evidence
into an inspectable off-target-risk card. It never calls a molecule safe or
selective from a model alone. The CYP11B2 demo contains both a deliberately
not-selective reference (osilodrostat under the declared 10-fold policy) and a
selective reference (baxdrostat), while preserving model-disagreement and
unassessed-off-target alerts.

```bash
.venv-boltz/bin/python -m cyp_pipeline.sentinel_geometry --experiment configs/extended-selectivity-benchmark.json --boltz-root runs/benchmark-extended-boltz-pilot-v1 --ccd-cache .cache/boltz/mols --out runs/selectivity-sentinel-geometry.json
python3 -m cyp_pipeline.sentinel --panel configs/selectivity-sentinel-cyp11b2.json --experiment configs/extended-selectivity-benchmark.json --boltz-root runs/benchmark-extended-boltz-pilot-v1 --geometry runs/selectivity-sentinel-geometry.json --assays data/benchmarks/fadrozole_assays.json --assays data/benchmarks/osilodrostat_baxdrostat_assays.json --ligand 'Osilodrostat (LCI699)' --ligand Baxdrostat --out runs/selectivity-sentinel-demo
```

Generate the self-contained interactive browser demo from a Sentinel result:

```bash
python3 -m cyp_pipeline.sentinel_demo --result runs/selectivity-sentinel-demo-v3/result.json --structure data/raw/4FDH.pdb --out runs/selectivity-sentinel-demo-v3/demo.html
```

It replays existing evidence and lets the user inspect the CYP11B2 reference
structure in 3D. It does not run Boltz or UMA in the browser or treat the
reference structure as a predicted pose for a newly entered molecule.

To let the browser launch the two prepared R/S-fadrozole UMA exchange jobs,
serve it through the allow-listed local API instead of `python -m http.server`:

```bash
python3 -m cyp_pipeline.sentinel_server --site runs/selectivity-sentinel-demo-v3/demo.html --port 8000 --bind 0.0.0.0 --enable-uma
```

The page then calls real UMA frozen-coordinate exchange calculations and
displays their saved artifacts. This is not a general sequence-to-binding
service: arbitrary new protein or ligand inputs remain blocked pending normal
chemistry preparation and review. On a GPU that passes `nvidia-smi`, add
`--backend configs/uma-s-1p1-a100.json`; otherwise the default is the explicit
CPU fallback.

## Interactive demo

Open [demo/index.html](demo/index.html) in a browser, or serve the repository locally:

```bash
python3 -m http.server 8000
```

Then visit `http://localhost:8000/demo/`. The demo is self-contained and works offline. It embeds the downloaded PDB coordinates for 6M7X and 4FDH, lets you rotate and zoom the pocket view, switch between CYP11B1/CYP11B2, play a guided tour of the five workflow modules, and inspect the synthetic software-check scores. Those scores are explicitly labeled as artificial; the page does not claim a real selectivity result.

## Run now (Python 3.10+, no dependencies)

From the repository root:

```bash
python3 -m cyp_pipeline doctor
python3 -m unittest discover -s tests -v
python3 -m cyp_pipeline demo --out runs/my-demo
```

Open `runs/my-demo/report.html` in a browser. The four synthetic fixtures test orchestration, constraints, convergence, energy subtraction and reporting. They are four-atom harmonic examples, **not CYP structures or MLIP predictions**. Use a fresh output directory for each run; existing runs are never overwritten.

## Real MLIP backend: CPU now, GPU later

FAIR Chemistry 2.22.0 and CPU PyTorch are installed locally in `.venv-mlip`. The UMA adapter and CPU/GPU configs are ready. **Checkpoint download is blocked by Hugging Face model access**; no real UMA predictions have run. Follow [the MLIP quickstart](docs/MLIP_QUICKSTART.md) to authenticate, download and run the water smoke test before using a reviewed CYP input.

```bash
.venv-mlip/bin/python -m cyp_pipeline.mlip preflight
.venv-mlip/bin/python -m unittest discover -s tests -v
```

## Real experiment

```bash
python3 -m cyp_pipeline fetch 6M7X --out data/raw/6M7X.pdb
python3 -m cyp_pipeline fetch 4FDH --out data/raw/4FDH.pdb
python3 -m cyp_pipeline inspect data/raw/6M7X.pdb
python3 -m cyp_pipeline validate prepared/system.json
python3 -m cyp_pipeline run prepared/system.json --backend configs/backend.local.json --out runs/real-01
python3 -m cyp_pipeline report runs/real-01/result.json runs/real-02/result.json --out runs/report.html
```

The two PDB files have already been downloaded in this workspace, with source URLs and SHA-256 sidecars. Skip `fetch` if they exist. Fetching needs network access. Inspection inventories residues, alternate locations and models; it does not prepare chemistry.

1. Use `configs/experiment.json` to track the four systems. The crossed enantiomer/protein pairs require modeled poses.
2. Copy `examples/prepared-system.template.json` and populate it after chemical preparation. It deliberately fails validation until reviewed. See [preparation contract](docs/PREPARATION.md).
3. Review/freeze `configs/protocol.json` before examining real scores. Defaults are proposed pilot settings, not calibrated scientific thresholds.
4. Connect a suitable model using [the backend contract](docs/BACKENDS.md). Neither BioNeMo nor Rosalind access is assumed. The default example refuses execution until placeholders are replaced.
5. Run one reviewed experimental complex first. Inspect energy/force plausibility and all geometries before expanding.
6. Repeat with alternative poses, boundaries and constraints. Compare only matching protocols, backend metadata and fragment contracts; interpret changed-protocol sensitivity separately.

## Calculation

The constrained full cluster imposes pocket geometry. The workflow extracts the reviewed fragment (ligand + heme + axial thiolate, including any reviewed caps), evaluates its physical energy, then relaxes **the identical fragment** with the same charge, multiplicity and backend. The primary descriptor is:

`E_deform = E_fragment(imposed geometry) - E_fragment(relaxed reference)`

The fragment is optimized without positional restraints. Reviewed coordination bounds must hold before/after cluster relaxation and after reference relaxation; otherwise the result is unresolved. This is a local reference minimum, not a guaranteed global minimum. Model forces must exclude artificial restraint penalties. Fixed cluster atoms are imposed by the optimizer and contribute no artificial energy term.

The deterministic optimizer uses backtracking gradient descent with maximum displacement and free-atom force convergence. It is a conservative initial implementation; large systems may benefit from a validated ASE optimizer adapter in future. A successful invocation does not establish model accuracy or valid stereochemistry.

`delta = E_deform(B2) - E_deform(B1)`: negative suggests B2 under the hypothesis that smaller deformation is favorable. This is **not** a binding free energy or calibrated affinity predictor. Baselines include ligand–pocket atom pairs closer than a fixed cutoff, minimum separation, and reviewed coordination distances. The close-pair count is a simple geometric baseline, not a van der Waals energy. No fitted baseline or claim of MLIP improvement is implemented without assay data.

Each run stores input/protocol snapshots, hashes, backend metadata, runtime, convergence traces, coordinates (`before.xyz`, `after.xyz`, `reference.xyz`), geometry checks and result JSON. Failures during calculation are saved; invalid input is rejected before a run is created. Reports escape metadata and need no external assets. CLI exit codes: 0 success, 1 failed/unresolved calculation, 2 invalid setup.

## Layout

- `cyp_pipeline/`: CLI, validation, optimizer, backend adapters, comparison and HTML reporting.
- `configs/`: proposed frozen protocol, experiment manifest and backend template.
- `examples/`: deliberately incomplete preparation template.
- `tests/`: numerical, scientific-comparison and failure-path checks.
- `data/raw/`: downloaded structures and inventories (ignored by git).
- `runs/`: immutable calculation directories and reports (ignored by git).
- `CODEX_PROJECT_HANDOFF.md`: verified environment and next team milestones.

The core is independently runnable. Automated protonation/capping, docking, checkpoint access, quantum reference jobs, assay curation, service integration and interactive molecular visualization remain follow-up work, dependent on chemistry review and actual compute/service access.

## CYP11B1 molecular design campaign

The current relaxed four-energy results now feed an iterative CYP11B1-over-CYP11B2 design campaign. The registry, initial analog library, robust target/selectivity gates, and active-learning ranking are in `design/cyp11b1-selectivity-v1/`. Candidate preparation preserves the S stereocenter and heme-binding nitrogen while embedding the shared scaffold into both enzyme poses. See [the design campaign guide](docs/DESIGN_CAMPAIGN.md).

As of September 19, 2026, expanded-pocket S-fadrozole is the current provisional CYP11B1 lead: three accepted poses give B2-minus-B1 values from +0.282165 to +0.398223 eV. Para-carboxamide improves the B1 exchange term but reduces the single-pose selectivity signal to +0.050992 eV; meta-fluoro para-carboxamide is nonselective at -0.009626 eV. See `runs/cyp11b1-design-results-v1/REPORT.md`.
