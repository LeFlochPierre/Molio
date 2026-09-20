# CYP11B1/CYP11B2 model benchmark

`configs/experiment.json` preserves the original four fadrozole cases. The
expanded eight-case benchmark is `configs/extended-selectivity-benchmark.json`:

| Case | Structural reference | Interpretation |
| --- | --- | --- |
| R-fadrozole / CYP11B1 | CYP11B1 scaffold from 6M7X | Crossed ligand pose must be modeled |
| R-fadrozole / CYP11B2 | 4FDH, ligand 0T3 | Experimental complex available |
| S-fadrozole / CYP11B1 | 6M7X, ligand JD7 | Experimental complex available |
| S-fadrozole / CYP11B2 | CYP11B2 scaffold from 4FDH | Crossed ligand pose must be modeled |
| Osilodrostat (LCI699) / CYP11B1 | CYP11B1 mutant/metyrapone scaffold from 7E7F | Osilodrostat pose must be modeled; not an experimental osilodrostat structure |
| Osilodrostat (LCI699) / CYP11B2 | 7M8V, ligand YSY | Experimental complex available |
| Baxdrostat / CYP11B1 | CYP11B1 mutant/metyrapone scaffold from 7E7F | Modeled pose required |
| Baxdrostat / CYP11B2 | CYP11B2/osilodrostat scaffold from 7M8V | Modeled pose required |

[RCSB 6M7X](https://www.rcsb.org/structure/6M7X) and
[RCSB 4FDH](https://www.rcsb.org/structure/4FDH) identify the observed enantiomers
and heme. An observed crystal pose is a structural reference, not a measured
selectivity ratio. The crossed poses have no experimental reference in these
two structures.

7E7F and 7M8V are available locally with provenance. An experimental baxdrostat/CYP
structure is not represented in this workspace; AF3 predictions are available below. Crystal structures are starting
geometry/provenance, not selectivity labels. A Boltz-2 input is template-free
and records its canonical 34--503 sequence source separately from the
case-specific structural scaffold.

## Experimental reference

The paired baxdrostat AlphaFold 3 inputs and verified protein FASTA sequences are
stored in [the AF3 validation dataset](../data/validation/baxdrostat-af3-v1/README.md).
Both cases retain heme and use the same 34–503 constructs as the Boltz benchmark.
AF3 prediction is complete (three seeds, five samples per seed and enzyme).
Selected mmCIF structures, all samples, confidence files and provenance are
stored in that dataset. Chemical preparation for energy calculations remains pending.

[Roumen et al. (2007), Table 5](https://pmc.ncbi.nlm.nih.gov/articles/PMC2039848/)
reports human CYP11B inhibition in V79MZ cells:

| Ligand | CYP11B1 IC50 (nM) | CYP11B2 IC50 (nM) | B1/B2 IC50 ratio from reported means |
| --- | ---: | ---: | ---: |
| R-fadrozole | 118.6 +/- 8.9 | 6.0 +/- 1.9 | 19.77, favors B2 |
| S-fadrozole | 39.5 +/- 4.4 | 171.2 +/- 51.7 | 0.231, favors B1 by 4.33-fold |

The corresponding calculated log10 ratios are +1.296 and -0.637. Values and
source metadata are recorded in
[`data/benchmarks/fadrozole_assays.json`](../data/benchmarks/fadrozole_assays.json).

These are cellular functional IC50 measurements, not Kd/Ki measurements. The
study used 500 nM 11-deoxycorticosterone after one hour of inhibitor
preincubation, followed by one hour for B1 versus three hours for B2. Preserve
that timing difference when interpreting selectivity. The article does not
specify the error type or replicate count for these +/- values; do not assign
SD/SEM labels or derive confidence intervals for the calculated ratios.

The added references are kept in
[`data/benchmarks/osilodrostat_baxdrostat_assays.json`](../data/benchmarks/osilodrostat_baxdrostat_assays.json):
osilodrostat has a paired human CYP11B1/CYP11B2 V79-4 IC50 reference of 2.5
and 0.7 nM (B1/B2 = 3.57, B2-favored), reported in the FDA non-clinical review.
Baxdrostat has human Ki values of 1310 and 13 nM (B1/B2 = 100.8,
B2-favored) from Bogman et al. The latter is a Ki reference, so it is only a
directional comparison to Boltz's IC50-like output; it is not a Boltz ratio
error target. The files preserve assay-specific limitations rather than mixing
the measurements into one potency scale.

Use this small reference as a retrospective, assay-specific comparison. It does
not establish model calibration or general performance, and possible training
overlap must remain explicit.

## Which models answer which question?

| Method | Role in this benchmark | Score or output |
| --- | --- | --- |
| UMA exchange cycle | Our mechanistic energy descriptor | Four relaxed energies per enzyme; exchange energy in eV |
| Boltz-2, open-source model | Primary learned affinity comparator | `affinity_pred_value`: log10(IC50 in micromolar), lower is stronger |
| GNINA | Independent docking/scoring comparator | `CNNaffinity`: predicted pK, higher is stronger; retain empirical score separately |
| AutoDock Vina | Conventional docking baseline | Docking score in kcal/mol, lower is favorable |
| Chai-1 / AlphaFold 3 | Independent complex-structure checks | Poses and structural confidence; no native calibrated affinity estimate |
| DiffDock-L | Additional pose generator | Poses and pose confidence; requires a separate affinity scorer |
| RoseTTAFold All-Atom | Optional structure comparator from the RoseTTAFold family | Protein/small-molecule structures, including metal inputs |
| RFdiffusion, including RFdiffusion3 | Different scientific task | Designs new proteins; not a native scorer of fixed fadrozole/CYP complexes |

Sources: [Boltz prediction contract](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md),
[GNINA score definitions](https://gnina.github.io/gnina/rsc_workshop2021/),
[Vina documentation](https://autodock-vina.readthedocs.io/en/latest/docking_basic.html),
[Chai-1](https://github.com/chaidiscovery/chai-lab),
[AlphaFold 3 outputs](https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md),
[DiffDock FAQ](https://github.com/gcorso/DiffDock#faq),
[RoseTTAFold All-Atom inputs](https://github.com/baker-laboratory/RoseTTAFold-All-Atom#predicting-protein-small-molecule-complexes),
and [RFdiffusion3 small-molecule binder design](https://github.com/RosettaCommons/foundry/blob/production/models/rfd3/docs/examples/sm_binder_design.md).

RFdiffusion3 can design a protein around a small molecule. That capability does
not provide the affinity comparison for the two existing CYP sequences. It would
be relevant to a later enzyme or protein-binder design experiment.

Newer hosted Boltz-2.1/BoltzMol workflows are optional additional comparators.
Their API reports `binding_confidence` and a normalized `optimization_score` for
ranking within a run. Those fields must not be imported as open-source Boltz-2
`affinity_pred_value` or converted to an IC50 ratio.
See [the current hosted API metric definitions](https://api.boltz.bio/docs/api/guides/predictions/)
and [the June 2026 release](https://www.boltz.com/boltzmol-boltzprot-api).

## Scores and selectivity

Preserve each method's raw units. Calculate matched B2-minus-B1 differences and
report which enzyme the method favors. Agreement between methods is a result to
inspect, not evidence of experimental accuracy by itself.

For open-source Boltz-2, let `y = affinity_pred_value`. Then:

```text
pIC50 = 6 - y
raw_delta = y(B2) - y(B1)
B2_preference_log10 = y(B1) - y(B2)
predicted_IC50_B1_over_B2 = 10 ** B2_preference_log10
```

Positive `B2_preference_log10` means predicted B2 selectivity. A value of 1
corresponds to a predicted tenfold IC50 ratio. These are algebraic conversions of
the model output, not experimental measurements. Boltz's separate
`affinity_probability_binary` estimates binder/decoy likelihood; a difference in
that probability is not a fold-selectivity estimate. Structural confidence such
as ipTM or pLDDT is also not affinity.

For GNINA, compare `CNNaffinity(B2) - CNNaffinity(B1)`: positive favors B2 on its
pK scale. Keep that endpoint distinct from IC50. For UMA exchange and Vina,
negative B2-minus-B1 favors B2 under their respective scoring models. Do not
exponentiate these energy descriptors into experimental selectivity ratios or
average them with Boltz/GNINA scores. IC50 is assay-dependent and is not
automatically Kd or Ki; use matched assay endpoints and conditions for validation.

## Heme and stereochemistry

All primary comparisons must retain heme and verify the ligand enantiomer.
Generate Boltz inputs with separate protein, `HEM`, and fadrozole entities,
requesting affinity for fadrozole only. Boltz supports CCD codes or SMILES for
ligands and one affinity ligand per input. Use reviewed protein constructs and
cached MSAs, with identical settings between the paired enzymes.

The official Boltz documentation warns about affinity to cofactor targets.
Its [affinity implementation](https://github.com/jwohlwend/boltz/blob/main/src/boltz/model/models/boltz2.py)
constructs a receptor pair mask from protein tokens. Heme can participate in
structure prediction, but including it does not establish accurate treatment of
iron coordination in the affinity score. Treat CYP metal/cofactor selectivity as
an unvalidated application, and report heme-present inputs explicitly.

Do not silently strip heme during receptor preparation. A heme-removed run is a
separate sensitivity experiment. GNINA's
[documented atom mappings](https://github.com/gnina/gnina#training) include iron,
but accepting that atom type does not demonstrate a calibrated heme coordination
energy. Similarly, Vina's
[specialized zinc protocol](https://autodock-vina.readthedocs.io/en/latest/docking_zinc.html)
is not an iron/heme parameterization.

Check predicted chirality, Fe-to-ligand donor distance, Fe-to-axial sulfur distance,
heme geometry, and clashes before interpreting scores. Set geometry criteria from
reviewed preparation and the crystal references. Do not reinterpret a covalent
bond input as an automatically valid coordination model. Match protonation,
tautomer, heme/electronic-state assumptions, protein construct, waters, and pocket
definition wherever the methods permit; record unresolved differences.

`cyp_pipeline.benchmark_geometry.analyze_boltz_structure(path,
expected_ligand="S-fadrozole", ccd_dir=".cache/boltz/mols")` provides optional
diagnostics in the Boltz environment. It parses coordinates with
[Gemmi](https://gemmi.readthedocs.io/en/stable/analysis.html) and assigns chirality
from predicted 3D coordinates using
[RDKit](https://www.rdkit.org/docs/source/rdkit.Chem.rdmolops.html), mapped by CCD
atom names. Supply only the trusted molecule cache used by Boltz. The helper
reports nearest ligand nitrogen and nearest protein cysteine sulfur, without
asserting that proximity establishes coordination. Missing CCD data or unmatched
atoms leave chirality unassessed/unresolved; no distance threshold is calibrated.

## Reproducible comparison

1. Freeze input identities, structures, atom mappings, cofactor handling, and
   protocol identifiers before inspecting scores. Record package/checkpoint
   versions, seeds, sampling settings, MSA hashes, templates, restraints, runtime,
   and hardware. Separate independent cofolding from template-guided runs.
2. Run all four cases with the same declared number of independent replicates.
   Pair B1/B2 observations by ligand, replicate, method, metric, and protocol.
   Report failed or geometrically invalid runs as such. Sampling spread describes
   reproducibility, not model calibration uncertainty.
3. For native complexes, measure symmetry-aware ligand heavy-atom RMSD after
   protein alignment and report chirality/coordination checks separately. For
   crossed poses, report geometry and method agreement without assigning
   experimental RMSD accuracy. GNINA can score shared prepared poses as well as
   its own docked poses; label these as distinct protocols.
4. Compare selectivity direction for each enantiomer. When matched experimental
   measurements are available, compare per-ligand log-selectivity errors. Four
   complexes give only two ligands; do not claim useful correlation statistics,
   calibrated performance, or significance from that sample size.
5. Expand to an independently curated ligand panel with matched B1/B2 assays for
   an accuracy benchmark. Record measurement uncertainty, censored values, assay
   conditions, and possible structure/affinity training overlap. Both reference
   PDB entries predate Boltz-2, Chai-1, and AlphaFold 3 releases. This pilot has
   not established exclusion from training and is not a prospective benchmark.

## Boltz inputs and execution

Prepare the eight heme-containing inputs from the extended experiment:

```bash
python3 -m cyp_pipeline.benchmark_boltz prepare configs/extended-selectivity-benchmark.json runs/benchmark-inputs --msa-mode server
```

The adapter uses a shared 470-residue domain corresponding to UniProt positions
34-503, mapped from the local PDB metadata, and records the input provenance.
This is an explicit construct choice for an exploratory comparison, pending
chemistry review. It does not establish protonation or iron electronic states;
inspect the generated manifest before interpreting results.

With the separately installed Boltz executable and sufficient compute, first
run one seed, inspect all geometry diagnostics, then run three independent
seeds. Some local installations have an incompatible Triton kernel stack; use
`--no-kernels` as a recorded fallback rather than changing packages mid-study:

```bash
python3 -m cyp_pipeline.benchmark_boltz run runs/benchmark-inputs/manifest.json runs/benchmark-boltz --boltz-executable .venv-boltz/bin/boltz --cache .cache/boltz --seeds 42 43 44 --timeout-seconds 3600 --no-kernels
```

The adapter defaults to three recycling steps, 200 structure sampling steps, one
structure diffusion sample, 200 affinity sampling steps, and five affinity
diffusion samples. The selected MSA-server mode requires network access; record
the resulting MSA files for reproducibility. Input preparation alone does not
install models, download checkpoints, or produce predictions. The runner records
execution outcomes for subsequent report import.

## Local report

Create a report for the four cases and the curated assays, including
missing-result status:

```bash
python3 -m cyp_pipeline.benchmark report --experiment configs/extended-selectivity-benchmark.json --assays data/benchmarks/fadrozole_assays.json --assays data/benchmarks/osilodrostat_baxdrostat_assays.json --out runs/model-benchmark-01
```

Import native UMA exchange results with repeated `--uma-result PATH` arguments,
native prepared Boltz run directories with repeated `--boltz-run PATH`, or other
model scores with `--observations normalized.json`. Use fresh report directories.
The report does not execute external models, and missing outputs must remain
missing until those calculations finish.

For example, after the Boltz run above has finished:

```bash
python3 -m cyp_pipeline.benchmark report --experiment configs/experiment.json --assays data/benchmarks/fadrozole_assays.json --boltz-run runs/benchmark-boltz --out runs/model-benchmark-02
```

Example normalized records below are illustrative only. The numbers are invented
to show a matched pair, so `synthetic` is deliberately `true`. Real records use
`synthetic: false` only after importing actual completed outputs.

```json
{
  "observations": [
    {
      "system_id": "S-fadrozole-CYP11B1",
      "method": "GNINA",
      "metric": "CNNaffinity_pK",
      "value": 7.0,
      "replicate": "42",
      "protocol_id": "a-shared-preparation-and-scoring-protocol",
      "model_version": "version-and-checkpoint",
      "status": "completed",
      "synthetic": true,
      "source_path": "path/to/native/B1-output"
    },
    {
      "system_id": "S-fadrozole-CYP11B2",
      "method": "GNINA",
      "metric": "CNNaffinity_pK",
      "value": 6.0,
      "replicate": "42",
      "protocol_id": "a-shared-preparation-and-scoring-protocol",
      "model_version": "version-and-checkpoint",
      "status": "completed",
      "synthetic": true,
      "source_path": "path/to/native/B2-output"
    }
  ]
}
```

Normalized records support `GNINA` / `CNNaffinity_pK` and `Vina` /
`docking_score_kcal_mol`. Import `Boltz-2` / `log10_IC50_uM` through its native
run directory and `UMA-exchange` through its native exchange result, preserving
their execution and validity checks. Keep synthetic/provisional observations
separate from completed scientific results.
