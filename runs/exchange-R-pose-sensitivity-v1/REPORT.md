# CYP11B1/R-fadrozole pose sensitivity

Conclusion: **robust**. All tested poses agree beyond the signal floor.

| CYP11B1/R-fadrozole starting pose | B1 exchange (eV) | B2 exchange (eV) | B2−B1 (eV) | Single-run direction |
|---|---:|---:|---:|---|
| baseline | -1.293135938 | -1.957759151 | -0.664623213 | CYP11B2 |
| -5 degrees | -1.288745598 | -1.957759743 | -0.669014145 | CYP11B2 |
| +5 degrees | -1.282345459 | -1.957757139 | -0.675411679 | CYP11B2 |
| +10 degrees | -1.293124705 | -1.957759377 | -0.664634672 | CYP11B2 |

Sensitivity range: **-0.675411679 to -0.664623213 eV**.
Engineering signal floor: ±0.05 eV.

The full range lies beyond the signal floor and consistently favors CYP11B2. The perturbations are local starting-pose tests; they do not establish a thermodynamic ensemble or validate the modeled pose.

## Final CYP11B1 ligand geometry differences

| Relaxed pose pair | Ligand atom RMSD (angstrom) |
|---|---:|
| baseline vs -5 degrees | 0.0340 |
| baseline vs +5 degrees | 0.0278 |
| baseline vs +10 degrees | 0.0418 |
| -5 degrees vs +5 degrees | 0.0466 |
| -5 degrees vs +10 degrees | 0.0745 |
| +5 degrees vs +10 degrees | 0.0393 |

All 4 cycles contain four relaxed energies for each enzyme and passed their per-component convergence and geometry checks. See `summary.json` for paths to each machine-readable run.
