# Scientific scope

IsoForm is an exploratory research workspace, not a validated all-protein
binding predictor. Its executable paired demo uses provisional, supplied
R/S-fadrozole pocket preparations for CYP11B1 and CYP11B2.

## Default: retrospective energy-to-fold fit

The default screen now recomputes the team's supplied relaxed osilodrostat and
baxdrostat exchange scores, then applies
`log10(S) = 2.13893364745 * (X_B1 - X_B2)`. The selected training fits are
3.23× and 103.36× B2 preference. This is an empirical coefficient learned using
both known targets after a 360-combination pose/assay search, not a physical
conversion or independent prediction. Original minima remain selectable;
for baxdrostat they give 5.86× under the same coefficient.

Pose robustness is unresolved for both compounds; failed B2 convergence
prevents a metyrapone fold from being reported. A fitted ratio exceeding the
illustrative 10× screen is not a validated selectivity verdict. The coefficient
is not transferred to the live frozen-pocket workflow or arbitrary targets.
The API recomputes supplied outputs without new inference. Underlying poses,
convergence logs and assay citations were not independently re-audited.
See [the calibrated workflow](CALIBRATED_SELECTIVITY.md).

## Live UMA

For each protein:

`exchange = cluster_ligand + free_water - cluster_water - free_ligand`

`delta = exchange(B2) - exchange(B1)`

Negative delta favors B2 **in this potential-energy descriptor**; positive
delta favors B1. The web demo holds all coordinates fixed. It does not sample
an ensemble or supply binding free energies, solvent or entropy corrections.
Provisional chemistry, geometry, spin and pocket boundaries remain limitations.

The prominently labeled energy-fold proxy is
`exp(abs(delta_eV)/(kB_eV_per_K * 298.15))`. It is a hypothetical transformation
of potential energies, not a binding-affinity ratio, experimental selectivity,
probability or confidence. Binding `fold_selectivity` remains null in exports.
An extreme proxy is warned about rather than presented as an extreme biological
effect. No assay threshold is applied to this proxy. Full requirements and
checks are described in [the IsoForm guide](ISOFORM.md).

## Saved references

The osilodrostat/baxdrostat demonstrations use separately labeled existing
paired assay records, with a 10× policy threshold. Their IC50 and Ki endpoints
are not interchangeable. Model disagreements, stereochemical failures and
unassessed off-targets are retained. Passing one paired-assay policy does not
establish broad selectivity or clinical safety.

## Expanded panel

Five curated steroidogenic CYP references support structure inspection and
pose-input generation. A reference contains its deposited ligand, not a newly
predicted pose of the selected drug. New model poses still need chemical
preparation and review before UMA. Custom sequences and SMILES do not unlock
unsupported model jobs. Generic pocket total energies cannot rank different
proteins by binding strength.

The new 53-second video captures the retrospective reanalysis, including
original-minima sensitivity and the convergence stop. It does not launch UMA.
The earlier 54-second video separately records a genuine new frozen-pocket UMA
run, saved assays and input generation. Neither recording mocks numerical
outputs; scene pacing is editorial, not a runtime benchmark.
