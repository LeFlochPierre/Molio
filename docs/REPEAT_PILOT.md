# BRD4 matched-seed pilot — 2026-10-05

Six fresh Boltz-2 predictions completed: the ester/acid pair at matched seeds 42, 43 and 44.

Run: `8d8683fd-bbd7-4b52-a678-f47a92a648b4`. Local artifacts: `work/whatif/experiments/8d8683fd-bbd7-4b52-a678-f47a92a648b4/`.

| Compound | Mean native affinity | Min | Max | Sample SD |
| --- | ---: | ---: | ---: | ---: |
| CHEMBL1828983 | -0.0903 | -0.1168 | -0.0731 | 0.0233 |
| CHEMBL1828984 | 0.6561 | 0.5811 | 0.6985 | 0.0651 |

Native affinity is log10(IC50 in micromolar); lower indicates stronger predicted binding.
These descriptive statistics summarize model sampling, not experimental replicates or calibrated uncertainty.

| Seed | Ester score | Acid score | Acid − ester |
| --- | ---: | ---: | ---: |
| 42 | -0.0731 | 0.6985 | 0.7716 |
| 43 | -0.0811 | 0.6886 | 0.7697 |
| 44 | -0.1168 | 0.5811 | 0.6979 |

All three paired differences favour the ester; mean acid-minus-ester difference: 0.7464.
The source assay also favours the ester (7,700 versus 51,200 nM IC50). This two-compound,
single-sequence result is not independent validation: old published compounds may overlap
model training data, absolute affinity calibration is untested, and no MSA was used.

Each run used the same protein construct, model checkpoints and sampling settings.
Only the random seed varied. Every command, input hash, model output, pose and checkpoint
hash is preserved in the job record. The earlier single-seed pilot was not reused as a
new replicate. See [the original protocol](BOLTZ_PILOT.md) and
[repeat workflow](GUIDE.md#repeated-comparisons).

Next: support audited local MSA input, strengthen pose validation, and evaluate a broader
coherent measured set before using repeated scores in automatic candidate selection.
