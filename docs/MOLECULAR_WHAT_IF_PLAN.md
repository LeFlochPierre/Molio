# Molecular What-If Lab: implementation plan

Date: 2026-09-29. Status: evidence/3D slice and SMILES variant workflow implemented; bounded Boltz comparison worker implemented; scientific validation remains open.

Update 2026-10-08: sequence-first workspaces now support UniProt search, optional
AlphaFold DB model downloads, an empty molecule library and user-supplied SMILES.
Measured ChEMBL series are optional. Existing design generation and prediction
setup work with unmeasured inputs. Large proteins require an explicit 40–600 residue
region; the full protein model remains viewable. Verified live with CFTR setup and
design-to-prediction handoff, without starting inference or claiming CFTR validation.

Implementation details and launch commands: [What-If Lab guide](WHAT_IF_LAB.md). Source selection and identity checks: [data audit](WHAT_IF_DATA_AUDIT.md). The first slice uses nine same-assay compounds, seven curated comparisons, and one explicitly labelled experimental pocket reference. It uses a standard-library Python server, plain JavaScript, and bundled 3Dmol.js to keep local setup dependency-free. Proposals now persist in SQLite; the editor computes descriptors, core differences, and neighbours from the nine-compound local library. Two bounded edit families retrieve measured precedents in either direction, and both the compound library and proposal previews support generated 3D conformers. These are explicitly distinguished from experimental bound poses. Guided structural edits now populate the variant editor, and an interactive log-scale activity map connects measured compounds to 3D inspection and proposal creation. These suggestions are not ranked leads or synthetic routes. FastAPI, generic pair discovery, online neighbour retrieval and a drawing sketcher remain future architecture. A bounded Boltz-2 worker now supports local single-sequence batches of up to three explicit molecular structures, persistent jobs, cancellation and native result/3D inspection. This pilot does not meet the full model-validation milestone.

## Purpose and first user

Help a medicinal chemist investigating a compound series answer: **Which small chemical change should I test next, and what evidence supports that experiment?**

The core loop is select a measured compound, compare a related compound, inspect the chemical difference and available structures, propose a variant, and export a justified experimental shortlist. Folding is a supporting capability, not the product's central claim.

Success means a chemist can identify a useful comparison and save a testable hypothesis in under five minutes using the curated example. Validate that with two or three chemists before broadening the product. Novelty is a hypothesis about the connected workflow, not a claim that molecular editing or activity-cliff tools do not exist.

## Release boundaries

Local browser application, served on loopback by default. A Python service owns chemistry, retrieval, persistent projects, and background jobs. Cached public examples work offline after setup. Prediction is optional and requires a verified runtime. Online multi-user hosting is later work requiring authentication, per-user isolation, and compute quotas.

First release includes one curated target, a measured compound series, matched molecular comparisons, linked 2D/3D inspection, proposed edits, prediction job integration, and shortlist export. Sequence input supports structure prediction and explicit target mapping; it does not silently borrow assays from a related protein.

Defer universal sequence-to-drug discovery, unrestricted molecule generation, synthesis planning, protein design, whole-protein molecular dynamics, and numerical claims about clinical safety. Do not retain the old energy-to-fold calibration in the new product.

## First demonstrator: selection gate

Investigate human BRD4 bromodomain 1 as an initial candidate, not a finalized benchmark. Select it only after checking all of the following; otherwise choose another compact, noncovalent, cofactor-free target with better evidence:

- Accessible protein–ligand experimental structures with verified ligand identities, domain boundaries, mutations, and residue mapping.
- Approximately 50–200 usable measurements if available, including at least five related molecular pairs from comparable assays. Prefer a smaller coherent series over an arbitrary size target.
- Several meaningful chemical changes and a range of measured activities; missing data must remain unknown.
- At least one pair with structures for both members if possible. Otherwise clearly separate experimental structures, aligned conformers, and newly predicted poses.
- Source attribution, permitted redistribution, and downloadable source records recorded in a data manifest.

Do not claim a dramatic activity cliff until the assay context and chemical identities have been checked. First implementation deliverable is a short data audit selecting the target and example pairs.

## User experience

Desktop workspace: compound browser on the left, linked 2D molecular comparison and large 3D pocket viewer in the centre, evidence and experiment notes on the right. A bottom tray holds shortlisted candidates and completed/running jobs. On smaller screens these become tabs.

1. Open the bundled example or create a project from a target identifier, sequence, structure, or assay CSV.
2. Browse compounds by measured activity, chemical series, and evidence coverage.
3. Select a related pair. Highlight their common core and changed atoms in 2D. Display comparable measured differences, with assay/source links.
4. Inspect the actual available structures: ribbon/surface/atoms, pocket isolation, residue labels, distance measurements, synchronized cameras, and pose overlays.
5. Propose a molecule using SMILES initially; add an embedded 2D sketcher after the first comparison workflow works. Preserve the parent compound, atom mapping, and stated reason for the edit.
6. Explore a bounded set of curated fragment replacements or measured neighbours. Show which suggestions are observed compounds and which are untested proposals.
7. Request predictions for a shortlist, initially at most three molecules per batch. Display real job stages and load completed structures as they become available.
8. Pin candidates with a hypothesis and export an experimental shortlist with compounds, evidence, model results, and unresolved questions.

An optional 'Challenge this idea' action retrieves contradictory comparable observations, alternative poses, and evidence gaps. Its first implementation uses explicit retrieval rules, not invented explanations from an LLM.

Changing a selection must never display stale coordinates or results from a previous compound. Every displayed pose must identify its protein, ligand, source, and experiment.

## Reference data and chemistry pipeline

Sources: ChEMBL for target/assay/compound records, RCSB PDB for experimental structures, and optional BindingDB supplementation after duplicate-source handling is implemented. Retrieve target-specific subsets and cache source responses; do not mirror entire databases for the MVP.

Pipeline:

`source records → identity checks → normalized assay records → comparison groups → molecular pairs → structures → user proposals → optional predictions → shortlist`

- Store original SMILES, standardized representation, stereochemistry, source IDs, and standardization version. Retain salt/parent relationships and flag unspecified stereocentres; never silently collapse distinct stereoisomers or tautomers.
- Preserve assay ID, target/construct, organism, endpoint, relation operator, units, original value, document, and source record. Keep Ki, Kd, and IC50 separate.
- For positive exact measurements, permit conversion to pActivity after unit normalization. Do not turn censored measurements such as '>10000 nM' into exact values. Do not average incompatible assays.
- Default numerical pair comparisons to the same assay and endpoint with matching target context. Cross-assay observations are supporting context unless comparability is explicitly established.
- Use RDKit for parsing, descriptors, common-substructure mapping, and bounded single-cut matched-pair discovery. Require an explicit changed fragment and attachment mapping; fingerprint similarity alone does not establish a matched pair.
- Cache each comparison with its source measurements. Retain replicates and disagreement. A structural explanation is a hypothesis, not demonstrated causation.
- Candidate selection starts with observed neighbours and chemist edits. Curated replacement rules preserve the selected core and validate valence/attachment points. Chemical validity is not a synthesis-feasibility guarantee.

## Prediction and AlphaFold decision

Use experimental complexes when relevant ones exist. Do not refold a known protein merely to animate the workflow.

Boltz-2 is the proposed first live complex-prediction provider: protein sequence plus ligand, with explicit MSA/template configuration and native confidence/affinity-related outputs. Confirm supported chemistry and current model documentation before enabling affinity. Preserve native metrics and units; structural confidence is not affinity and a model score is not an experimental measurement.

AlphaFold structure import is supported as an input path. An optional AlphaFold/ColabFold execution adapter can follow after runtime, access terms, and hardware are checked. AlphaFold is not being renamed as Boltz: the UI names the actual provider for every result.

Protein-alone prediction and protein–ligand complex prediction are separate job types. A complex prediction may change the protein coordinates. User sequences require explicit identity/construct mapping before attaching experimental target evidence.

No physical folding movie is implied. Show real process stages and completed models. Any interpolation used for visual transitions is a visual effect, not simulation evidence. Molecular dynamics is deferred.

Before scheduling a job, check interpreter, package/model version, weights, GPU/VRAM, input size, disk space, and supported input chemistry. Benchmark one representative job before setting time or capacity promises. The current host's GPU/model availability is unknown.

Public-sequence reference retrieval can be automated. Sending user sequences to an external MSA/prediction service requires a visible, explicit user choice; support local MSA files. Single-sequence mode, if supported, must be identified as such.

## Technical design

Proposed application package: `molecular_lab/`, separate from legacy CYP entrypoints during migration.

- Python API with FastAPI; RDKit chemistry service; SQLite project store; immutable source/model artifacts in project directories.
- TypeScript/Vite browser UI with Mol* for macromolecular visualization and RDKit-generated 2D depictions. Bundle assets for local use rather than relying on runtime CDN access. Verify licenses and pin dependencies during implementation.
- A local worker launches configured model executables with bounded structured inputs. Browser requests cannot supply executable commands or arbitrary filesystem paths.
- Persist job transitions: queued, preparing, running, validating, complete, failed, cancelled, interrupted. Recover interrupted jobs on restart; cache reuse requires matching input/model/configuration hashes.
- Expose progress through server-sent events or polling, with real logs and completed artifacts. Cancellation terminates the worker process tree. Stale responses cannot mutate a newer selection.
- Retain source structures in mmCIF/PDB and preserve chain/residue/insertion-code mappings. Geometry overlays use explicit atom mappings rather than nearest-coordinate guesses.

Core entities: Project, Target, Compound, AssayObservation, Comparison, StructureArtifact, Proposal, PredictionJob, PredictionResult, and ShortlistItem. Each references immutable source IDs/hashes. Export JSON plus CSV/SDF and available structures; unknown values stay null.

Proposed API groups: `/projects`, `/targets`, `/compounds`, `/comparisons`, `/structures`, `/proposals`, `/jobs`, and `/shortlists`. Final endpoint shapes follow the data contracts rather than the legacy CYP API.

## Reuse and cleanup

Reuse selectively: job progress and subprocess handling patterns in `sentinel_server.py`; backend isolation and preflight patterns in `mlip.py`; source hashing/input bundles in `auto_inputs.py`; assay/provenance logic in `benchmark.py` and `sentinel.py`; useful geometry audits with their tests.

Audit before reuse: existing geometry and validation code contains Fe/heme, ligand, and CYP assumptions. Existing similarity-based 'uncertainty' is heuristic and must not become a calibrated confidence score. The current custom viewer may be useful as a fallback, but the new interface needs general macromolecular rendering and atom selection.

Retire from the default user journey: CYP-only menus, retrospective energy-to-fold fits, frozen-pocket fold proxies, old campaign suggestions, video-production controls, and duplicate historical reports.

Migration order:

1. Inventory tracked modules, data, tests, and generated artifacts; identify dependencies and preserve scientific source records.
2. Build the new vertical slice beside the existing application.
3. Make the new app the documented default once its acceptance checks pass.
4. Move legacy documentation to a clearly marked archive, then remove unused code/assets after checking references. Preserve relevant attribution and provenance. Do not mass-delete `prepared/`, `runs/`, or `data/` by name.

The user has authorized routine cleanup; no further blanket approval is needed. This plan itself performs no deletions.

## Implementation milestones and acceptance criteria

### 1. Evidence-backed vertical slice (estimated 1–2 days)

Select and audit the first target/series; define data contracts; create importer and cached fixture; serve the first comparison workspace with real 2D structures and experimental 3D coordinates.

Done when at least five sourced related pairs are inspectable, a comparable measured activity difference can be reproduced from source records, structure identities are correct, and the example works from a local launch without GPU inference.

### 2. Interactive what-if loop (estimated 1–2 additional days)

Add changed-fragment highlighting, bounded pair discovery, SMILES edits, validation, simple descriptors, proposal history, and shortlist export. Add a sketcher if integration fits the milestone; SMILES entry remains a usable fallback.

Done when a user can create a valid untested variant, distinguish it from measured compounds, inspect available context, and export a hypothesis with traceable evidence. Unposed edits must not masquerade as bound 3D structures.

### 3. Real prediction integration (estimated 1–3 additional days after runtime availability)

Implement Boltz adapter, preflight, persistent jobs, cancellation, native result parsing, geometry checks, and 3D result comparison. Start with one target and a small supported ligand set.

Done when one fresh job completes using actual model inference and its immutable inputs, native outputs, versions, timing, failures, and exported result are inspectable. Mock integration tests do not count as real inference acceptance.

### 4. Chemist usability and cleanup (estimated 0.5–1 day plus feedback availability)

Observe two or three chemists completing the core task. Record confusing steps, usefulness of evidence, and whether exported hypotheses are actionable. Simplify navigation and migrate the default README/entrypoint. Remove confirmed dead material.

Estimates describe implementation effort, not guaranteed elapsed completion or inference runtime. A convincing first vertical slice is the first deliverable; the complete pipeline may take roughly 4–8 working days, depending on data quality and compute setup.

## Verification

Test scientific boundaries: units, censored values, endpoint grouping, duplicate observations, stereoisomer identity, fragment mapping, and experimental/predicted provenance separation.

Test workflow boundaries: import failures, cache invalidation, persistent job failures/restart/cancellation, unsupported model output, selection races, and export reproducibility.

Browser acceptance: select two compounds, inspect the right structures, highlight the edit, create a proposal, queue or clearly report unavailable prediction, and export a shortlist. Offline curated mode must never simulate a successful model job.

Assess model outputs against held-out measurements where a coherent evaluation set exists; do not tune on a demo series and advertise its agreement as independent validation.

## Sources checked for this design

- Boltz input, templates, MSA, and affinity documentation: https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md
- AlphaFold 3 pipeline and access/setup documentation: https://github.com/google-deepmind/alphafold3
- ChEMBL API: https://www.ebi.ac.uk/chembl/api/data/docs
- ChEMBL search overview: https://www.ebi.ac.uk/training/online/courses/chembl-quick-tour/accessing-chembl-data/searching-using-the-web-interface/
- BindingDB services: https://ww.bindingdb.org/rwd/bind/BindingDBRESTfulAPI.jsp
- Existing interactive design product, relevant to novelty assessment: https://www.biosolveit.de/SeeSAR
- Existing molecular replacement resource: https://www.swissbioisostere.ch/

## 2026-10-02: comparison experiments

Added the Run comparison interface and a Boltz 2.2.1 worker. The current host has
a working NVIDIA RTX PRO 6000 Blackwell GPU (~96 GB VRAM), unlike the historical
legacy backend notes. Installed the separate Python 3.12 inference environment.
The first fixed-protocol batch tests the known ester/acid pair, with explicit
structures and no external MSA service. See WHAT_IF_LAB.md for setup and limits.

Next: inspect actual poses against the pocket reference, add local MSA input and
repeat matched seeds, then evaluate a broader coherent measured set. Only after
that should bounded variant generation feed a repeated candidate-selection loop.
Model settings should stay fixed while searching chemical edits; tuning settings
to make a favourite molecule score better would invalidate the comparison.

Both pilot candidates completed real structure and affinity inference. Results,
runtime and geometry sanity checks are recorded in [the pilot report](WHAT_IF_BOLTZ_PILOT.md).

## 2026-10-05: matched repeat runs

Implemented one- or three-seed comparisons (42/43/44), bounded to three molecules.
The UI defaults to three seeds and preserves every run and pose. Per-candidate
mean/range/sample SD and matched-seed differences describe sampling variation;
incomplete pairs cannot establish a consistent direction. This does not establish
calibrated uncertainty or replace measured validation. Earlier runs remain readable.

Remaining sequence: MSA-backed inference, stronger pose checks, a larger coherent
measured evaluation set, then a bounded propose–predict–compare–refine loop.

The fresh six-prediction pilot completed successfully. See [matched-seed results](WHAT_IF_REPEAT_PILOT.md).

### Pose-screen follow-up

Implemented mapped BRD4 alignment, ligand element-composition checks, pocket-centre
and short-contact flags, nearby-residue highlighting and a separately labelled
experimental ODR overlay. Saved poses are auditable through derived sidecars with
artifact hash checks; no inference rerun is needed. These are limited geometry
screens, not comprehensive chemical validation. Local MSA support, a broader
measured benchmark and automated bounded variant screening remain open.

### First generated-design loop

Implemented Explore variations: bounded one-step ether/ester/aryl-fluorine edits,
ring-scaffold preservation, structure deduplication, descriptor/3D comparison and
selection of up to two ideas. Server-verified designs save as unmeasured proposals;
the existing run panel opens with the parent baseline and both selected designs.
Generation is unranked and requires an explicit run action. This is the first
propose–predict–compare loop; automated iterative optimization and broader
chemistry rules remain future work.

The first parent-plus-two-design trial completed real inference; see [design trial results](WHAT_IF_DESIGN_TRIAL.md).


## 2026-10-06: full-page workspace redesign

Replaced the dense modal workflow with full pages: Explore, Design, Runs and
Saved, plus dedicated library, activity map, protein pocket, editor and notes
pages. A persistent navigation rail and closable workspace tabs preserve drafts
and selections while moving between tasks; browser Back/Forward and direct page
links work. Mobile uses a bottom navigation bar and a reference menu.

Runs separates comparison setup, saved results and the 3D inspector. Evidence,
SMILES, protocol settings and detailed diagnostics use expandable sections.
Larger white 3D canvases, consistent icons, spacing and shorter page introductions
make the main actions easier to find. Hidden molecular views release their WebGL
contexts and restore the camera when reopened. Prediction behavior is unchanged.

Browser acceptance covers navigation, proposal/design handoff, actual saved
prediction artifacts and mobile layout. Chemist usability sessions remain open;
this implementation does not replace direct feedback from intended users.


## 2026-10-06: online target setup and isolated workspaces

Added ChEMBL protein search, a bounded assay/structure preview and asynchronous
local workspace creation. Users choose one measured series and one accession-matched
PDB reference. The importer prepares molecular depictions, 3D conformers, comparisons
and source snapshots; each target has separate proposals and browser notes.

The existing predictor now snapshots the selected target's protein construct and
workspace ID, while sharing the Boltz runtime and one GPU job queue. Imported
results use generic contact/element checks, never BRD4 residue mapping or ODR
alignment. BRD4 remains the bundled offline demo with its historical jobs intact.

Live setup was exercised with human carbonic anhydrase II, 12 compounds from
CHEMBL2173731 and 3K34/SUA. No new-target inference accuracy is claimed. Broader
assay endpoints, exhaustive search, construct-aware reference alignment, cofactors,
MSA support and calibrated model evaluation remain future work.


## 2026-10-09: Molea workspace and welcome redesign

Molea is the new working display name; the Python package, storage paths and CLI
remain compatible. A logo and simple Start screen lead into saved workspaces and
protein search. Each workspace now opens on a molecule gallery with real generated
conformer thumbnails, protein context and experiment status. Individual molecules
open a focused 3D page with SMILES, source information and design/prediction actions.

The visual system uses soft lavender and mint, rounded surfaces, more space, native
emoji and a decorative molecule on the welcome screen. Desktop navigation, closable
tabs, browser history and mobile navigation remain available. Initial loading,
interactive requests and setup tasks have distinct status indicators; active runs
show completed cases and can be opened from any working page. Reduced-motion
preferences suppress decorative/loading animation. No model behavior or scientific
interpretation changed.

Browser checks cover welcome and Start, isolated workspace/molecule drill-down,
3D rendering, direct links, design handoff, loading/error recovery, run progress
presentation and mobile navigation. Chemist usability feedback remains open.
