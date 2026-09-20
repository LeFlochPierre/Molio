# Project handoff — 2026-09-19

Implementation began following the user's explicit request to start. The original team brief is preserved. Its earlier plan-only instruction was superseded by that request. This handoff did not exist at the start of the session.

## Verified environment

- Execution directory: `/home/ubuntu/HackProject`; hostname `brev-x2wre4mk2`.
- Python 3.10.12; 4 logical CPUs; approximately 16 GB RAM.
- `nvidia-smi` exists but cannot communicate with the NVIDIA driver.
- numpy, torch, ASE, RDKit, fairchem and MACE are absent; no packages installed.
- BioNeMo/Rosalind interfaces, credentials, budget, deadline and chemistry reviewer availability remain unknown. No secrets inspected.
- `.git` is an empty read-only directory in this environment, not a usable checkout; no commit was created.

## Delivered

Dependency-free Python CLI; validated preparation contract; raw PDB retrieval/provenance and inventory; four-system experiment manifest; constrained optimization; backend command/resident-factory interfaces; identical-fragment deformation calculation; baseline geometry; explicit unresolved states; protocol/model/preparation comparison checks; saved artifacts and static HTML report. Ten automated tests cover meaningful numerical and failure paths.

Both starting PDBs were downloaded after sandbox network access required escalation. They remain raw structures, not calculation-ready clusters. Synthetic four-system demo is runnable and marked throughout; it makes no scientific preference prediction. No real MLIP calculations or assay validation have run.

## First scientific milestone

One reviewed experimental complex → one compatible real backend invocation → inspectable relaxation and fragment result. Review the proposed protocol before real calculations. The main blocker is prepared chemistry plus verified model/compute access, not pipeline orchestration.

## Five-person ownership and checkpoints

1. Benchmark owner: sources, stereospecific assay table, endpoint comparability, evidence gaps. Deliver labels to evaluator.
2. Preparation owner: explicit cluster, hydrogens/caps, charge/spin, fixed atoms and modeled poses. Review with model owner before approving input JSON.
3. Model/compute owner: restore/locate GPU access, choose and validate model, implement backend adapter, measure runtime/memory. Deliver one real energy/force call.
4. Workflow owner: CLI/contracts and artifact integration. Already bootstrapped; integrate reviewed input and adapter together.
5. Evaluation/demo owner: inspect baseline and geometry, curate comparisons, run sensitivity and quantum-reference feasibility assessment, improve visualization if time allows.

Checkpoint A: freeze one preparation and protocol. B: run one complex and inspect chemistry together. C: expand to four complexes consistently. D: challenge results with sensitivity and references. E: present evidence and unresolved cases. Confirm remaining hackathon time before assigning calendar hours. Stretch ligands and service integration follow a reproducible core.

## Next commands

See README for demo, tests, real runs and report generation. `examples/prepared-system.template.json` intentionally fails validation until completed. `configs/backend.example.json` intentionally refuses execution until placeholders are replaced. Do not use synthetic fixtures as real chemical inputs.


## MLIP integration update

The user requested model setup while GPU provisioning is unavailable. Added `cyp_pipeline/mlip.py`, explicit CPU/GPU configs, setup script, version inventory and `docs/MLIP_QUICKSTART.md`. Installed Python 3.12 environment `.venv-mlip`, fairchem-core 2.22.0, torch 2.13.0+cpu and ASE 3.29.0; this supersedes the earlier absent-packages note for that environment only. System Python remains dependency-free.

Verified FAIR Chemistry imports and its local-checkpoint API. Sixteen tests pass in the MLIP environment, including state mapping and an analytic ASE calculator; system Python passes fourteen and skips the two optional ASE tests. Adapter explicitly resets ASE result caching when changing electronic states while retaining the model in memory.

Checkpoint download was attempted with network permission and denied by Hugging Face's UMA access gate. The user must obtain access and authenticate via `hf auth login` in the terminal. No model inference ran. `runs/uma-cpu-smoke-01/result.json` records missing weights, not an energy result. The remaining scientific preparation requirements are unchanged.


## Continuation record — verified A100 and exchange-cycle work

Recorded 2026-09-19T18:57:26.594487+00:00. This section supersedes earlier environment/readiness statements; the earlier text is retained as history.

### Historical preparation decisions supplied by the user

The user supplied the prior handoff in `/home/ubuntu/codex_history.md` and the attached `/home/ubuntu/.codex/attachments/278c92bb-036a-49fc-8a1e-b4367c02b33d/pasted-text.txt`. It records earlier CPU UMA v1.2.1 access and smoke tests, and a 224-atom incomplete draft. Its charge +1 was a diagnostic parity workaround, not a validated chemical charge. Its provisional Fe(III) doublet, neutral ligand/propionates and methylthiolate assumptions must not be silently applied to the separate 462-atom charge -3 input. The earlier fragment-deformation calculation is no longer the requested descriptor.

### Current user-approved objective

Relax all four components per enzyme. For each enzyme, exchange energy = E(cluster+ligand) + E(free water) - E(cluster+water) - E(free ligand). Compare delta = exchange(CYP11B2) - exchange(CYP11B1); negative favors B2 within this potential-energy model. Compare the same ligand stereoisomer across enzymes. This is not a binding free energy or validated selectivity ratio.

### Verified work and evidence

- A100 GPU and isolated CUDA environment work: `/home/ubuntu/uma-crosscheck-niv-462/.venv-uma-s11/bin/python`. GPU execution requires access outside the tool sandbox.
- Current calculation uses UMA `uma-s-1p1`, OMol, batch preset. Configuration: `configs/uma-s-1p1-a100.json`. Do not silently substitute the historical v1.2.1 model.
- 462-atom single-point cross-check passed against the A6000 reference; charge -3, multiplicity 2, no relaxation. Evidence: `/home/ubuntu/uma-crosscheck-niv-462/results/20260919T183757698313Z/`.
- Four-component runner: `python -m cyp_pipeline.exchange`. Documentation: `docs/EXCHANGE_CYCLE.md`. It checks matching scaffolds/references, atom/charge balance and convergence; incomplete inputs cannot produce a selectivity result. All 22 tests passed at the last suite run.
- Free water converged in 6 steps: -2079.865051076495 eV, final maximum force 0.017774432667253065 eV/angstrom. Evidence: `runs/exchange-free-water-01/`.
- Free S-fadrozole reconstructed from 6M7X/JD7 and its local CCD graph: 30 atoms, neutral singlet. Gradient descent hit 300 steps without convergence; that run remains unresolved. Subsequent ASE BFGS converged in 45 steps: -19199.577231074447 eV, maximum force 0.01821814302548643 eV/angstrom. Post-relaxation S chirality and broad bond-length checks passed. Evidence: `runs/exchange-free-S-fadrozole-bfgs-01/`.
- Both free references are included identically for both enzymes in `prepared/exchange-cycle-progress.json`. Four enzyme-specific cluster entries remain null.
- All 229 heavy atoms in the 462-atom input uniquely matched 6M7X chain A within 0.01 angstrom. Recovered labels and tentative hydrogen parents: `runs/readiness-20260919T184134Z/recovered-462-mapping-candidates.json`. This is not a validated cap/bond/charge ledger.
- Saved earlier local Codex chat received the 462-atom input already prepared; it did not contain the generating script. Additional files in `/home/ubuntu/whole-protein-pilot-niv20260919/` provided the successful ligand-builder function. Full-protein attempts there failed; B1/S and B2/R pilots are not a matched selectivity pair.

### Remaining work

Validate hydrogen/cap assignments and charge ledger, define fixed cluster boundaries, construct the matched CYP11B2/S-fadrozole pose, prepare ligand-replaced-by-water clusters for both enzymes, then relax and validate all four cluster components. Keep preparation provisional unless an actual review occurs. No complete exchange-cycle or selectivity result exists yet. Current task details: `runs/readiness-20260919T184134Z/NEXT_STEPS.md`.


## Provisional exchange pilot launched

A reproducible capped-pocket builder now fills all four cluster components: `scripts/prepare_exchange_pilot.py`; manifest and preparation audit: `prepared/exchange-pilot-v1/`. Ligand clusters contain 450 atoms, water clusters 423, all charge -3/doublet; 102 backbone/cap atoms are fixed. No crystal waters are retained. B2/S is a heme-aligned modeled pose; the selected residue identities match between enzymes. All assumptions remain provisional. This is a new matched model, not the original 462-atom input.

The complete eight-component BFGS run is in `runs/exchange-pilot-v1-01/`. Read its live result and per-component progress files before reporting completion. Geometry guards include Fe coordination, ligand covalent distances/chirality and water O-H distances. Force tolerance stays 0.02 eV/A, maximum 400 steps per component. `scripts/audit_exchange_bonds.py` provides a separate final source-topology bond/fixed-boundary audit.

Exchange and BFGS tests passed. A broader run encountered unrelated newly added benchmark-test helper errors; do not describe the entire current repository suite as passing without rechecking.

## Completed provisional exchange pilot

`runs/exchange-pilot-v1-02/` completed all eight relaxed components at the 0.02 eV/angstrom force threshold. CYP11B1 exchange is -1.8056932769786727 eV; CYP11B2 exchange is -1.8658962796671403 eV; B2 minus B1 is -0.06020300268846768 eV. The final bond/fixed-boundary audit passed for all four clusters. See `runs/exchange-pilot-v1-02/REPORT.md` and `result.json`. The full test suite subsequently passed 43 tests.

Interpret only as a provisional potential-energy result. CYP11B2/S is a modeled heme-aligned pose, the selected pocket omits the surrounding protein and solvent, and protonation/spin/boundary sensitivity remains untested. The next active task is pose sensitivity because the magnitude is only slightly above the 0.05 eV pilot signal floor.

## Pose sensitivity conclusion

Complete eight-component cycles for baseline, -15 degree and +15 degree B2/S starting poses produced B2-minus-B1 values of -0.06020300268846768, +0.08097255285520077 and -0.047432995756025775 eV. All converged and passed final bond/fixed-boundary audits. The range crosses zero, so the provisional selectivity result is unresolved. See `runs/exchange-pose-sensitivity-v1/REPORT.md` and `summary.json`. Do not report the baseline B2 direction alone as a prediction.

## Current lead: R-fadrozole for CYP11B2

The R-fadrozole baseline and valid modeled-B1/R pose cycles all favor CYP11B2. Their B2-minus-B1 range is -0.6754116793267713 to -0.6646232126281575 eV, entirely beyond the -0.05 eV floor. The invalid -10 degree broken-bond run and rejected -15 degree overlap are excluded and documented. The current provisional lead is R-fadrozole; S-fadrozole remains unresolved. See `runs/fadrozole-selectivity-v1/REPORT.md` and `runs/exchange-R-pose-sensitivity-v1/`.

## CYP11B1 design campaign — September 19, 2026

The design target is CYP11B1 over CYP11B2. Added an expanded pocket with residues 109, 112, 320 and 404, an active-learning campaign registry in `design/cyp11b1-selectivity-v1/`, and stereochemistry-preserving analog preparation in `scripts/prepare_design_candidate.py`.

Expanded-pocket S-fadrozole passed baseline and ±15 degree modeled CYP11B2 pose cycles. B2-minus-B1 ranges from +0.282164668 to +0.398223050 eV, and every complete cluster passed the source-bond/fixed-boundary audit. S-fadrozole is the current provisional CYP11B1 lead for this protocol.

Analog baselines: para-carboxamide gives B1 exchange -2.532182508 eV and delta +0.050991521 eV; meta-fluoro para-carboxamide gives B1 exchange -2.523384482 eV and delta -0.009626311 eV. Meta-hydroxy is excluded because CYP11B1 relaxation opened the conserved ligand C03-C02 bond. See `runs/cyp11b1-design-results-v1/REPORT.md`. The full system-Python suite passes 58 tests with 6 optional-dependency skips.
