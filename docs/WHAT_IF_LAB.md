# Molio (formerly Molecular What-If Lab)

The local workspace combines experimental-evidence exploration with a molecular variant editor. It connects related compounds, same-assay measurements, highlighted chemical differences, and a real BRD4 pocket reference. An optional Run comparison worker now performs Boltz-2 protein–ligand complex and affinity prediction. The evidence view itself remains sourced experimental data; molecular dynamics is not implemented.

## Run

From the repository root on Linux (or WSL), with Python 3.10 or newer:

```bash
python -m molecular_lab
```

Open **http://127.0.0.1:8001**. If running through SSH or an IDE on another machine, forward port 8001 to your browser. Use `--port 8080` to choose another port. The server binds to loopback only. Stop it with Ctrl+C.

There are no additional Python runtime dependencies for browsing the bundled BRD4 example. The structures, RDKit-generated molecular drawings, dataset, and pinned 3Dmol.js renderer are bundled. A browser with WebGL is required for 3D; source coordinates and evidence remain accessible if WebGL is unavailable. No CDN, account, GPU, or network connection is needed after obtaining the repository. Source links open external websites only when clicked. Online target setup, described below, also contacts public ChEMBL and RCSB services.

## Set up another protein target

Start with the configured chemistry environment:

```bash
.venv-whatif/bin/python -m molecular_lab --boltz-executable .venv-boltz/bin/boltz
```

The Boltz argument is optional for browsing, online setup and design. On another
machine, install the chemistry extra and configure a supported prediction runtime
as described below. The setup flow does not install software or run inference.

### Start empty: measurements are optional

1. Open **Project library → New project** and search a protein name, gene symbol or UniProt accession. The
   search goes directly to UniProt, without waiting for ChEMBL. Results show the
   species, sequence length and whether the full sequence fits the local runner.
2. Choose **Start empty**. Setup downloads the canonical sequence, domain
   annotations and an available full-sequence AlphaFold DB model. A missing or
   unavailable model does not block the sequence workspace; **Retry model download**
   can retrieve it later. Open the saved workspace when setup finishes.
3. Inspect the protein in 3D. This is a precomputed predicted model, not an
   experimental ligand complex. Confidence colours and residue hover aid inspection.
4. Choose a starting molecule: search PubChem by compound name or CID, use a bundled
   offline example, or paste SMILES. Review the displayed SMILES and source, then
   **Add to workspace**. Each saved molecule shows its SMILES with a Copy button,
   generated free-molecule shape, and **Explore designs**, **Edit SMILES** and
   **Predict** actions. The design page also displays parent and proposed SMILES.
5. For proteins longer than 600 residues, explicitly choose a UniProt domain or a
   40–600 residue range before predicting. The app preserves inclusive canonical
   positions and the exact selected sequence in each job. Cropping can remove
   binding-site interactions and does not model the whole protein’s function.

For example, human **CFTR / P13569** has 1,480 residues: its full AlphaFold model
can be viewed, while this local runner requires a smaller chosen region. A domain
annotation is not evidence of a suitable ligand pocket. The setup neither chooses
a binding region automatically nor treats an arbitrary crop as full CFTR.

No measured activities or comparisons are fabricated for these workspaces. The
activity map and measured-library pages are omitted. Protein sequences and model
sources are retained locally with download URLs and hashes. An AlphaFold display
model is not passed as a template to Boltz. The GPU/runtime and shared Boltz weights
are separate requirements for running predictions, not for opening the workspace.

The current empty-workspace path supports up to 30 user-supplied starting molecules.
It does not yet merge a later ChEMBL import into the same workspace; measured-data
imports below create a separate workspace.

**Compounds reported for this target** is a broader, optional discovery path within
an empty workspace. When UniProt supplies a ChEMBL target link, it considers the
first 100 activity records across assay types and endpoints, showing up to 12
supported molecules and six source records per molecule. This can recover chemistry
that the stricter same-assay importer excludes. Endpoints, relations, units, assay
and document IDs, source flags and mutation annotations remain visible; values
are never averaged, ranked or promoted to comparable experimental observations.
A target-associated assay record is not proof of binding to the selected construct.

PubChem search supplies chemical identities and stereochemical SMILES, not evidence
of activity on the selected protein. The bundled anisole, benzamide and pyridine
examples let you try design and prediction without internet; they are explicitly
not suggested as known binders. Imported molecules retain source attribution and
supporting records, which also travel with prediction inputs. Lookup snapshots and
previously found suggestions are saved locally. Provider failures do not remove
the examples or the manual SMILES option.

**Available protein research & sequence** shows function annotations, up to 30 PDB
cross-references and the amino-acid sequence from the downloaded UniProt record,
including references outside the strict ligand-bound importer. Existing starter
workspaces gain these options without rebuilding or replacing their contents.

### Optional: start with measured evidence

1. The app opens on **Molio**. Click **Start** to choose a workspace, without loading a protein or its 3D viewer.
   Choose a new protein, or open BRD4 explicitly from **Your project library** for the demo.
   From an open workspace, click **Project library** in the header or the target card in the sidebar.
2. Choose **New project** and search a protein name (for example, carbonic anhydrase II), gene symbol, or UniProt accession.
   Check the species and UniProt accession, then choose **Check measured data**.
3. Select a measured series and an experimental reference. The descriptions show
   the assay, protein construct length, PDB chain, resolution and reference ligand.
4. Click **Create local workspace**. Progress covers source downloads, chemistry
   preparation and 3D conformers. Click **Open workspace** when it finishes.
5. Use Explore, Design, Runs and Saved as before. **Project library**
   switches back to BRD4 or another downloaded workspace.

Imported datasets and proposals live under `work/whatif/workspaces/lab-…/`.
Prediction jobs retain a workspace ID in the shared experiment directory; the
single worker prevents concurrent GPU runs across targets. Requests and browser
notes are scoped to the workspace in the URL, so two browser tabs can work on
different targets. Existing BRD4 proposals and historical jobs are preserved.
Save editor drafts before switching targets: switching reloads the page.

The importer currently supports single proteins with a UniProt accession, a
confidence-9 binding assay containing exact, positive, unflagged IC50 measurements
in nM, and a suitable X-ray reference. It scans at most 500 activity records and
12 X-ray constructs prefiltered by length and mutation annotations; lack of a result means **not found in this bounded search**, not
that the protein has no useful chemistry. Individual provider/download failures are
reported as an incomplete lookup, not as absence of structures. It rejects incomplete assay downloads
(over 1,000 records), duplicates/replicate measurements, salts, unsupported
chemistry and annotated assay mutations. One assay and publication stay together.

Up to 12 molecules are selected around a fingerprint-similarity centre, without
ranking by activity. Up to eight related comparisons are selected by similarity;
these are not asserted single-edit matched pairs. Original measurements, source
JSON/PDB records, download URLs and SHA-256 hashes are retained. The full source
assay remains in the workspace even when only a subset is displayed.

References must match the chosen UniProt accession and contain a protein construct
of 40–600 ordinary amino acids without an annotated mutation. The importer selects
an ordinary organic reference ligand near that chain, excludes common additives,
and retains blank/A alternate coordinates for display. Raw PDB coordinates remain
in the sources. A nearby reference ligand is context, not an assigned bound pose
for any imported compound. Assay and structural constructs can still differ.

Predictions use the selected deposited protein construct, including any expression
tags. Boltz weights are shared across targets; there is no separate trained model
to download for each protein. The current protocol omits MSA, templates, metals,
cofactors and other chains. This matters particularly for metalloenzymes such as
carbonic anhydrase. Imported-target outputs use element-composition and short-contact
checks; their reference alignment and pocket placement are explicitly unchecked.
Only the bundled BRD4 protocol retains its specialized alignment and ODR overlay.

ChEMBL-specific search retries transient provider failures, then tries alternative ChEMBL filters
and reviewed UniProt records with ChEMBL target links. This recovers gene-name
searches such as CFTR during a ChEMBL search outage. Results identify their source;
For this measured-data path, UniProt supplies target identity only. **Check measured data** still requires ChEMBL assay
data and a compatible RCSB structure, so finding a target does not guarantee that
the current importer can create a workspace for it.

Online search/setup requires internet. Downloaded evidence, 3D structures and
workspace browsing are local. Preview tasks are transient: after restarting the
server, check a target's data again before importing. Completed workspaces persist.

Verified with a real **human carbonic anhydrase II / CHEMBL205** download: 12
compounds from **CHEMBL2173731**, and **3K34 / SUA** as the structural reference.
This validates data setup and browsing, not new-target prediction accuracy.

Public interfaces: [ChEMBL API](https://www.ebi.ac.uk/chembl/api/data/docs),
[RCSB Search API](https://search.rcsb.org/), and
[RCSB Data API](https://data.rcsb.org/index.html), and
[UniProt API](https://www.uniprot.org/help/programmatic_access).

```bash
.venv-whatif/bin/python -m unittest tests.test_whatif_targets
.venv-whatif/bin/python -m unittest tests.test_whatif_starter
# Live UniProt/AlphaFold setup in a temporary workspace; no inference:
python scripts/check_whatif_starter.py
# Check compound discovery in a temporary copy of a saved LRP1 starter workspace:
python scripts/check_whatif_compounds.py --workspace lab-YOUR_LRP1_WORKSPACE_ID --live
# Requires a running app, RDKit, Playwright and internet. Saves a workspace;
# it does not start a model prediction.
python scripts/check_whatif_targets.py --live-import
# Or check an existing imported workspace without downloading another:
python scripts/check_whatif_targets.py --workspace lab-YOUR_WORKSPACE_ID
```

## Workspace navigation

The app uses full pages instead of stacked dialogs. The main navigation provides:

- **Workspace:** the central hub for the target, molecules and experiments. Open a
  molecule card for its interactive 3D shape, SMILES, provenance and next actions.
- **Measured series / Protein & inputs:** compare measured compounds, or manage
  sequence-first protein inputs and add molecules.
- **Design:** generate small edits, inspect their 3D shapes and select ideas.
- **Runs:** prepare a new comparison, review results, or open the 3D inspector.
- **Saved:** revisit and export saved proposals.

The reference navigation opens the molecule library, activity map, and a dedicated
protein-pocket page. On a phone, the five main pages use a bottom navigation bar;
**Reference** in the header opens the remaining pages.

Open pages appear as tabs below the header. Switching pages keeps the current
selection, unsaved editor text, scroll position, and molecule camera view. Use a
tab's **×**, a page's close button, or Escape to close it. Closing the editor
abandons its unsaved draft; switching away keeps it. Reloading restores the current
page but does not restore unsaved editor drafts. Saved proposals and jobs retain
their existing persistence. Closing Runs does not cancel an active prediction;
use the run's Cancel action explicitly.

Molecule cards slowly rotate their actual generated 3D conformers. Use **Pause
rotation** to stop them; hovering or focusing a card also pauses it. Off-screen
cards and hidden pages stop rendering, and the gallery shares one WebGL renderer.
System reduced-motion preferences disable automatic rotation. Shaded helix and
gear illustrations accompany the workspace; the gears turn only for active runs.

An initial loading screen clears when the workspace is ready. A small task panel
reports searches, model downloads and molecule preparation. Active model runs show
completed predictions, not estimated time or synthetic percentages; you can keep
using other pages. Motion respects the system’s reduced-motion preference.

Detailed evidence, SMILES, prediction settings, geometry checks and provenance are
expandable. Core measurements and the distinction between generated shapes,
experimental structures and predicted poses remain visible. Hash URLs (for example
`/#/design` and `/#/pocket`) support direct links and browser Back/Forward.

## Explore

1. Pick one of seven chemical comparisons from the left sidebar. The two molecular drawings share an aligned common core; amber highlights atoms outside the exact-bond common substructure.
2. Read the measured IC50 values and their ratio. Both records are from the same BRD4 assay. Lower IC50 means greater potency in that assay, not a binding free energy or a clinical benefit.
3. Open **Protein pocket** from the reference navigation to rotate and zoom the experimental BRD4 structure. Switch between pocket and whole-protein framing, add a translucent surface, or show nearby crystal waters. Click a residue button to focus it.
4. Click an atom to inspect its identity. Enable **Measure**, then click two visible atoms to display a distance. Click another atom to start a new measurement; **Reset** clears measurements and returns to the pocket.
5. Open **Notes & sources** to inspect sources and write a question for the next experiment, then **Shortlist** the comparison. Notes and selected comparisons persist in this browser. Export downloads a JSON package containing the selected measurements, chemical structures as SMILES, atom mappings, notes, source hashes, and structural caveats. With no shortlist, Export saves the current comparison.
6. **Molecule library** opens the experimental library sorted by IC50.

The 3D reference deliberately stays on **3SVG / ODR** when comparisons change. None of the selected compounds is silently substituted into the crystal. The related alcohol compound has unspecified assay stereochemistry while the deposited ligand is stereochemically resolved; this is explicitly shown when relevant.

## What is implemented

- Nine compounds from one sourced assay, seven curated related comparisons.
- Recomputed concentration ratios; exact measurements only; endpoint and assay checks.
- Original source JSON, publication metadata, source URLs and SHA-256 hashes.
- Aligned 2D molecular depictions and changed-atom highlighting.
- Interactive experimental 3D context, nearby-residue focus, surfaces, waters, and distance measurement.
- Search, compound library, persistent local notes, and evidence-rich JSON export.

SMILES-based proposals, editing, AlphaFold DB model downloads and optional local Boltz-2 comparison jobs are implemented. A drawing editor and local AlphaFold inference remain future work. See the local Boltz comparison pilot section below for runtime setup and scientific limits.

## Rebuild the dataset

This rebuild script is deliberately limited to the audited BRD4 assay. Use **Targets** in the app to import other supported protein targets. It refuses unsupported measurements and duplicate compound records rather than silently merging them.

```bash
python -m venv .venv-whatif-build
.venv-whatif-build/bin/pip install rdkit==2026.3.6
.venv-whatif-build/bin/python scripts/build_whatif_dataset.py \
  --source-dir molecular_lab/data/sources
```

To retrieve the public source records again into a separate directory:

```bash
.venv-whatif-build/bin/python scripts/build_whatif_dataset.py \
  --source-dir /tmp/whatif-sources --download
```

The builder overwrites the derived fixture and drawings; review the diff before committing refreshed public data. Upstream changes can alter the fixture. Original source snapshots remain the reproducible starting point for the shipped version.

## Verification

```bash
python -m unittest tests.test_molecular_lab -v
python -m pip install '.[browser]'
python -m playwright install chromium
python scripts/check_whatif_browser.py --screenshots /tmp/whatif-preview
python scripts/check_molea_studio.py
python scripts/check_whatif_navigation.py
python scripts/check_whatif_startup.py
```

Browser checks start and stop their own temporary local server. They block external HTTP requests and exercise actual WebGL rendering, atom picking, comparison selection, filtering, notes, exports, and mobile layout. They do not mock model jobs or claim prediction acceptance. Navigation checks
also exercise page history, preserved drafts and selections, closable tabs, surface
rendering and mobile navigation.

## Implementation choices

For this local workspace, the server uses Python's standard library and the UI uses plain JavaScript/CSS with **3Dmol.js 2.5.5**, rather than introducing FastAPI, a Node build, and Mol* immediately. This reduces setup friction while delivering the required atom selection, pocket rendering, surfaces, and measurements. Persistent proposals use SQLite; optional prediction jobs persist as local JSON records and artifact directories. SQLite is not needed for the bundled fixture and browser-local comparison notes.

The existing CYP application remains available through `python -m cyp_pipeline.sentinel_server`. Its source/prepared research artifacts have not been deleted. The new slice does not reuse CYP-specific energy calibration or ligand/protein assumptions.


## Create a molecular variant

The existing experimental browser still works without optional dependencies.
Variant previews require RDKit in the **server's** Python environment:

```bash
python -m venv .venv-whatif
.venv-whatif/bin/pip install '.[chemistry]'
.venv-whatif/bin/python -m molecular_lab
```

If `.venv-whatif` is already configured, use the final command to start it.
On Windows, use WSL: the current server imports Unix `fcntl` for worker locking.
A server started with another interpreter may still report RDKit unavailable;
restart with the configured interpreter.

1. Choose **Create a variant of A/B** beneath a measured compound.
2. Edit its SMILES. A debounced preview checks syntax/valence, aligns the parent
   and variant where a common core is available, and highlights changed atoms.
3. Compare molecular weight, calculated logP, polar surface area, and hydrogen
   bond donor/acceptor counts. These are descriptors, not affinity predictions.
4. Inspect related measured compounds. Search is currently limited to the nine
   cached compounds, using Morgan radius-2 fingerprints and Tanimoto similarity.
   There is no live ChEMBL search or activity transfer to proposals.
5. Name the idea, record the experiment it would test, and **Save proposal**.
6. Open **Saved** to see saved ideas and export their full JSON records.

Identical parent structures cannot be saved as variants. Invalid structures,
mixtures, metals, and inputs over the supported size limit are rejected.
Unspecified tetrahedral stereochemistry and exact matches to existing measured
compounds are flagged. Every proposal retains null activity and bound pose,
plus its source parent, calculated properties, software version, and evidence.

Proposals survive browser and server restarts in `work/whatif/proposals.sqlite3`
(relative to the launch directory; ignored by Git). Select another local project
with `--project-dir /path/to/project`. Comparison notes remain in browser storage;
proposal hypotheses are stored in SQLite. There is no cloud synchronization.

## Calmer 3D interaction

The reference model rotates slowly on opening, with a visible **Pause rotation**
button. Dragging, zooming, selecting a residue, starting a measurement, or opening
the variant editor pauses it. **Rotate model** resumes rotation. Reduced-motion
preferences disable automatic rotation, and background tabs stop rotating.
This is camera motion around fixed experimental coordinates, not a simulation.

Evidence is available on the separate **Notes & sources** page and in expandable
comparison details. Protein context has its own **Protein pocket** page, with a
larger viewer. Detailed provenance remains accessible without crowding the main
comparison.

Chemistry checks: `.venv-whatif/bin/python -m unittest tests.test_whatif_proposals`.
The browser acceptance script now also tests proposal previews, invalid input,
persistent saves, exports, rotation, and reduced motion; run it from an environment
containing both RDKit and Playwright.

## Evidence for an edit

The bundled measured-series page initially selects **Ketone → alcohol**, showing two measured comparisons from
the same assay. The evidence panel states the observed direction, retains the
original measurements, and suggests a side-by-side experiment with the parent.
It does not assign either measured value to a new proposal.

Two deliberately bounded edit families are implemented, in either direction:

- Ketone ↔ alcohol.
- Ethyl ester ↔ carboxylic acid.

A reaction must reproduce the **whole proposed molecule's connectivity** before
its evidence is retrieved. Adding another substituent at the same time does not
qualify as the same single edit. Stereochemistry is not matched by these rules;
that limitation is visible under **How strong is this evidence?**. Unsupported
changes receive an evidence-gap message, not an inactivity verdict.

The search covers only the nine-compound fixture and seven curated comparisons.
The two ketone/alcohol examples are from one assay/publication, not independent
replications. The ester-to-acid example has higher IC50 and is retained rather
than hidden. There is no broad online search, affinity prediction, or uncertainty
calibration. Both comparison exports and newly saved proposals include the
matched source measurements, matching method, limitations, and suggested test.
Previously saved proposals retain their historical snapshots.

## Interactive 3D molecules and hover

Measured compound cards, the compound library, and variant previews now display
interactive 3D molecules. Drag to rotate, scroll to zoom, or hover over an atom
for a purple highlight and atom label. **2D chemistry** switches the main cards
back to their aligned drawings.

These molecular shapes are generated with RDKit ETKDGv3 (seed 42), with bounded
MMFF optimization where parameters are available. They are **free-molecule
conformers, not experimentally observed or predicted binding poses**. An input
with unspecified stereochemistry is shown as one illustrative realization.
A generated shape is not an ensemble or a conformational population estimate.
Generation failure is an explicit unavailable state, with 2D drawings retained.

The BRD4 protein remains the separately labelled experimental 3SVG reference.
Its background is white; hovering highlights the corresponding residue and
label. Hovering pauses camera rotation, and hover hints do not replace active
distance measurements. No molecule is silently inserted into the protein.

`molecular_lab/data/conformers.json` and `edit-evidence.json` are reproducible
outputs of `scripts/build_whatif_dataset.py`; the bundled version supports offline
browsing without RDKit. New proposal analysis still requires the chemistry extra.

## Guided exploration and the activity map

Open **Activity map** in the reference navigation to see all nine measured compounds on a
logarithmic IC50 axis. Select a row with the mouse or keyboard to inspect its
3D conformer and source record. The positions come from recorded concentrations;
they are not model predictions or a ranking of untested proposals.

**Design from this molecule** opens the variant editor with that compound as
the parent. The new **Start with a chemical idea** section offers applicable
ketone/alcohol and ethyl-ester/acid transformations. Choosing an edit fills the
SMILES and proposes an editable experimental question, then runs the usual
validation, 3D preview, descriptors, and evidence matching.

The suggestions are bounded structural edits, not synthesis routes or an
optimization algorithm. An exact match to a measured compound is labelled
**Already measured in this library**. Parents without an applicable supported
edit retain manual SMILES input. Suggestions do not assign activity or a bound
pose to a proposal. Saving still requires the explicit Save proposal action.

**Expand view** opens the protein panel across the workspace. The same real
viewer, hover highlights, rotation, and measurement controls continue working.
Use the close control or Escape to return to the comparison. The main navigation
links jump directly to molecules, evidence, and the pocket; reduced-motion
preferences disable smooth scrolling.

## Local Boltz comparison pilot

Open **Run comparison** to select 1–3 measured compounds or saved proposals. Where a
source leaves stereochemistry unspecified, explicitly choose an enumerated
stereoisomer. Its prediction does not inherit the source assay measurement.
The browser shows native model outputs, job failures and downloadable JSON records;
completed complexes open in an interactive white-background 3D viewer.

The optional worker requires a dedicated **Python 3.12 / Boltz 2.2.1** environment
and a CUDA GPU. Keep it separate from the app's Python 3.13 environment:

```bash
python3.12 -m venv .venv-boltz
.venv-boltz/bin/python -m pip install boltz==2.2.1
.venv-whatif/bin/python -m molecular_lab --port 8001 \
  --boltz-executable .venv-boltz/bin/boltz
```

If system Python lacks `ensurepip`, an existing pip can bootstrap the environment:
`.venv-whatif/bin/python -m pip --python .venv-boltz/bin/python install boltz==2.2.1`
after creating the Python 3.12 environment with `--without-pip`.

Without the executable, curated browsing and proposal editing still work; the run
button explains the missing runtime. Preflight checks the Boltz version, CUDA
access, disk space and checkpoint presence. First use downloads the CCD library
and model weights into `work/whatif/boltz-cache`; no sequence is submitted to an
MSA service. `--boltz-cache` and `--project-dir` change the local storage locations.
One batch can be active per server; run only one server for a project directory.

The fixed initial protocol uses BRD4 UniProt O60885 residues 44–168, extracted
from the audited 3SVG SEQRES/DBREF mapping with the expression tag removed.
It uses single-sequence mode (empty MSA), no template or pocket conditioning,
seed 42, 3 recycles, 200 structure sampling steps, 1 structure sample, and
200 affinity steps with 5 affinity samples. Kernels are disabled for portability.
This is an exploratory integration pilot, not a validated ranking protocol.
MSA-backed runs and full chemical/pose validation remain future work. One- and
three-seed comparisons and limited pose screening are implemented; see below.

Model output meanings follow the [Boltz prediction documentation](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md):

- `affinity_pred_value`: native log10(IC50 in µM), lower predicts stronger binding;
  intended for comparisons among active molecules. Not a measured IC50.
- `affinity_probability_binary`: model binder probability, not a guarantee of activity.
- `confidence_score`: structural confidence, not binding strength.

Jobs persist under `PROJECT/experiments/UUID/`: selected source records, immutable
JSON-compatible YAML inputs, command/settings, stdout/stderr logs, model outputs,
checkpoint/input/artifact hashes and timestamps. Failures never receive made-up
scores. A restart marks unfinished work interrupted; cancellation stops the
process group. Each candidate has a two-hour timeout. Completed candidates in a
partially failed batch remain inspectable. Basic result checks cover required
metrics, finite coordinates, A/L chains and ligand heavy-atom count. They do **not**
establish correct bonding, absence of clashes, pocket occupancy or experimental
binding. JSON export contains provenance and native metrics; coordinate artifacts
remain in the local experiment directory.

The initial two-compound smoke test uses CHEMBL1828983 (ethyl ester) and
CHEMBL1828984 (acid), both without unassigned tetrahedral stereocentres. These old
published examples may overlap model training data. Agreement with this pair
would not constitute independent validation, and the search must not optimize
against the two observed values.

## Repeated comparisons

**Run comparison → Three matched seeds** runs each selected molecule at seeds
42, 43 and 44. Up to three candidates means at most nine predictions, executed
sequentially on the local GPU. The one-seed option remains available for a quick
pipeline check. The first molecule you select is the comparison baseline.

The summary shows each candidate's completed count, mean native affinity score,
observed minimum/maximum and sample standard deviation. Comparisons use only
**matched seeds**: candidate minus baseline for the same seed. Negative differences
favour the candidate. A consistent direction is reported only when all three
matched pairs completed; failures, cancellations and unfinished runs remain
visible and cannot be silently dropped to claim consistency. Every seed's pose
and original metrics remain inspectable and are retained in the JSON export.

These repeats characterize sampling variation under one protocol. They are not
experimental replicates, confidence intervals or calibrated model uncertainty.
A consistently favourable score can still be wrong. MSA-backed prediction,
broader measured validation, and automatic bounded candidate generation remain
future steps. Earlier one-seed saved jobs continue to display their original
results without being relabelled as repeat evidence.

Verify completed real repeats in the browser without starting new inference:

```bash
/tmp/whatif-build-env/bin/python scripts/check_whatif_prediction_results.py \
  --url http://127.0.0.1:8001 --screenshots /tmp/whatif-repeat-results
```

Use your own Playwright environment when the example path is unavailable.

## Pose diagnostics and experimental overlay

**Inspect predicted complex** now includes a reproducible BRD4 geometry screen.
It checks ligand heavy-element composition against the selected SMILES, maps all
125 protein C-alpha residues to reference 3SVG residues 44–168, and applies a
proper rigid Kabsch alignment. It reports protein C-alpha RMSD, the predicted
ligand centroid distance from reference ODR's centroid, very short protein–ligand
contacts, and nearby protein residues. Click a nearby residue to highlight it;
labels use UniProt numbering while model coordinates retain residues 1–125.

The optional cyan **experimental ODR overlay** transforms the reference ligand
into the predicted protein's coordinate frame. ODR is a different molecule from
most candidates. The overlay gives pocket context; its centroid displacement is
not a ligand RMSD, an exact pose comparison or evidence of affinity.

The project's initial review thresholds are explicit heuristics:

- Protein–ligand heavy-atom separation below 1.2 Å flags a very short contact.
- Ligand centroid more than 6 Å from the aligned ODR centroid flags pocket location.
- Protein C-alpha RMSD above 2 Å flags a large change from the reference.
- Residues within 4 Å of ligand heavy atoms appear in the neighbour list.

These thresholds are not chemically validated acceptance criteria. A result with
no flags can still have incorrect bonds, stereochemistry, protonation, contacts,
or binding. Missing/mismatched residue mapping or ligand element composition
makes the screen unavailable rather than passing it. Protein reference alternates
use blank/A records; other reference altlocs are omitted explicitly. Predicted
alternate conformers and insertion codes are unsupported by this initial mapper.

Native affinity summaries retain all completed runs; the table separately counts
flagged and unchecked poses. There is no silent removal of unfavourable results.
New inference records include the diagnostics. Existing model outputs can be
audited without rerunning inference:

```bash
.venv-whatif/bin/python -m molecular_lab.pose_checks work/whatif/experiments
```

The audit verifies each source pose against its saved artifact hash and writes
`pose_checks.json` beside the candidate outputs. It does not alter model outputs
or the original job JSON. The server attaches matching sidecars to displayed and
exported records. Each diagnostic records pose/reference hashes, method,
thresholds and limitations. Input and output bond chemistry remain unvalidated.

## Explore variations

Open **Explore variations**, choose a measured starting molecule, and inspect a
small set of one-step designs. The initial rules shorten/extend an aromatic ether,
shorten an ethyl ester to a methyl ester, or replace one aromatic hydrogen with
fluorine. RDKit validates products, removes duplicate structures and requires the
parent's ring scaffold to remain unchanged. Generation is bounded to eight ideas;
this is a limited rule set, not exhaustive chemical-space search or a synthesis route.

Each idea includes its chemical change, a testable question, calculated size/logP/
polar surface area and an interactive parent/design conformer comparison. The
shapes are free-molecule conformers, not binding poses. A local-library match is
labelled; absence from our nine compounds is not a global novelty claim.

Select one or two designs and choose **Save & prepare comparison**. The server
regenerates and verifies the selected design IDs before saving unmeasured ideas
as proposals in one database transaction. Existing measured structures use their
library IDs. The prediction panel opens with the parent first as baseline, then
the selected variants. Define any unresolved stereochemistry, review one- versus
three-seed settings, and start the run. No prediction starts merely from generating
or saving ideas. The objective is to investigate improved predicted affinity
relative to the parent; generation itself does not rank potency or assign activity.

The first design trial uses CHEMBL1828983 and two side-chain shortenings: its
ethoxy group to methoxy, and its ethyl ester to methyl ester. Both are absent from
the bundled library. This trial uses one seed to exercise the complete design
loop; it cannot establish repeat consistency or experimental improvement.


## Molio visual identity

The minimal welcome screen shows the top-left brand, central 3D logo and wordmark,
and one white Start button. The logo enlarges on hover while continuing to move.
It uses an original smooth 3D sculpture inspired by the supplied
Molio reference: a continuous rounded M with blue-violet shoulders and attached mint/cyan tips, with a rounded vector
wordmark. The refined logo uses rounded beads, slimmer connections and a smaller central
ball. It turns about its vertical axis every 20 seconds with a slight tilt. The
tips and centre follow a restrained, slightly delayed sway while their flexible connections remain
joined. Drag the logo or use arrow keys to turn it. With the logo focused, Space pauses/resumes and Home resets its view; automatic motion respects reduced-motion preferences and stops
when the page is hidden. The logo has a static SVG fallback and matching app icon.
This decorative shape is independent of scientific structures and prediction jobs.

The local mesh is reproducibly generated with NumPy using
`python scripts/build_molio_logo.py`. The browser needs no new library or remote
assets; `molio-logo.json`, `logo.svg` and `molio-wordmark.svg` ship with the app.

### Project library

After Start, the entrance shows a three-column library of local projects (two columns on tablets, one on phones). Each card names the protein and species, shows the molecule count, and opens that target’s workspace. New project reveals the existing protein search and setup flow; measurements remain optional.

Cards display still previews of saved protein coordinates, rotating only the hovered or keyboard-focused card, labelled experimental or predicted. Sequence-only projects remain accessible with a clear placeholder. Previews use static 2D thumbnails and move a single live WebGL canvas into the hovered or focused card. This avoids sharing frame time across every card and copying rendered pixels during animation. Motion is capped at 30 fps, stops when idle or hidden, respects reduced motion, and can be paused. Coordinates load only as cards enter view; the renderer and pending requests are released when leaving the library. Opening the library does not start a prediction or download new models from external services.

The library background is decorative, with five bead-cluster shapes. It starts
with randomized positions across the viewport and continuously recycles molecules
from the left or bottom as they drift diagonally upward and rotate. Desktop uses
12 sprites and mobile uses nine. **Pause motion** stops the background and hover
previews; hidden pages and reduced-motion settings also stop animation.
