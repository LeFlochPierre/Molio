# First real BRD4 comparison — 2026-10-02

The local Boltz-2 integration completed actual structure and affinity inference
for two compounds. This is a working pipeline check, not independent model validation.

Run: `7e4cc294-a74b-4a87-98ad-c3f3c94f3230`.
Artifacts: `work/whatif/experiments/7e4cc294-a74b-4a87-98ad-c3f3c94f3230/`.
Open **Run comparison** in the app to inspect both completed complexes and export
the record. Model weights and outputs remain local and are excluded from Git.

| Source compound | Source assay IC50 (nM) | Native model affinity | Model binder probability | Structure confidence |
| --- | ---: | ---: | ---: | ---: |
| CHEMBL1828983, ethyl ester | 7,700 | -0.0731 | 0.8525 | 0.9732 |
| CHEMBL1828984, acid | 51,200 | 0.6985 | 0.6516 | 0.9766 |

The [documented native affinity output](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md)
is log10(IC50 in micromolar), with lower values indicating stronger predicted
binding. The model and assay agree on the direction for this pair. Their absolute
values do not match, and the agreement on two old published molecules is not a
held-out accuracy result. These molecules may overlap the model training data.
No scores were fitted to these measurements and no winner was automatically saved.

## Protocol and checks

- Boltz 2.2.1, isolated Python 3.12 environment, NVIDIA RTX PRO 6000 Blackwell.
- BRD4 O60885 residues 44–168, mapped from 3SVG SEQRES/DBREF; expression tag removed.
- Explicit SMILES; neither input has an unspecified tetrahedral stereocentre.
- Empty MSA, no templates/conditioning, seed 42, 3 recycles, 200 structure steps,
  1 structure sample, 200 affinity steps, 5 affinity samples, no kernels.
- Both exited successfully and passed required metric, finite coordinate, chain
  and ligand heavy-atom count checks. Inputs, outputs and checkpoints are hashed.
- Wall time was approximately 3 minutes 53 seconds including first-use downloads.
  The first candidate took ~174 seconds; the second ~57 seconds. These are observations
  from this machine, not a general runtime guarantee.
- A separate geometry sanity check aligned 125 mapped protein C-alpha atoms to
  3SVG using Kabsch alignment. Protein C-alpha RMSDs were 0.436 Å (ester) and
  0.463 Å (acid). Predicted ligand centroid distances from reference ODR's centroid
  after alignment were 0.835 Å and 0.820 Å. ODR is a **different** ligand; these are
  pocket-location checks, not ligand-pose RMSDs or proof of correct binding geometry.
- Chromium inspected both real predicted complexes, switching between the 21- and
  19-heavy-atom ligands, explicit stereo selection gating, JSON export, viewer
  disposal and mobile results layout. No JavaScript errors were observed.

The remaining scientific work is MSA-backed prediction, matched repeat seeds,
chemical/geometry validation and a broader measured evaluation set. A bounded
variant search can then use the fixed protocol to generate hypotheses for
experimental testing. Clinical efficacy, safety and synthesis feasibility are
not assessed by this workflow.
