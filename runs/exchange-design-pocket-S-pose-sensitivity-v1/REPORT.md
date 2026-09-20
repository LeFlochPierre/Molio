# CYP11B2/S-fadrozole pose sensitivity

Conclusion: **robust**. All tested poses agree beyond the signal floor.

| CYP11B2/S-fadrozole starting pose | B1 exchange (eV) | B2 exchange (eV) | B2−B1 (eV) | Single-run direction |
|---|---:|---:|---:|---|
| baseline | -2.321688106 | -2.039523438 | +0.282164668 | CYP11B1 |
| -15 degrees | -2.321682852 | -1.923459802 | +0.398223050 | CYP11B1 |
| +15 degrees | -2.321694778 | -1.980721969 | +0.340972809 | CYP11B1 |

Sensitivity range: **+0.282164668 to +0.398223050 eV**.
Engineering signal floor: ±0.05 eV.

The full range lies beyond the signal floor and consistently favors CYP11B1. The perturbations are local starting-pose tests; they do not establish a thermodynamic ensemble or validate the modeled pose.

## Final CYP11B2 ligand geometry differences

| Relaxed pose pair | Ligand atom RMSD (angstrom) |
|---|---:|
| baseline vs -15 degrees | 0.1666 |
| baseline vs +15 degrees | 0.1075 |
| -15 degrees vs +15 degrees | 0.1041 |

All 3 cycles contain four relaxed energies for each enzyme and passed their per-component convergence and geometry checks. See `summary.json` for paths to each machine-readable run.
