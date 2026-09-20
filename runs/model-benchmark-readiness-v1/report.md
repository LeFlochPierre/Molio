# CYP11B1 / CYP11B2 model benchmark

Status: exploratory pilot. Model predictions and experimental measurements are identified separately.

| Ligand | Method | B1 score | B2 score | B2 - B1 | Unit | Pairs | Preference | Status |
|---|---|---:|---:|---:|---|---:|---|---|
| R-fadrozole | UMA-exchange | - | - | - | eV | 0 | - | not_run |
| R-fadrozole | Boltz-2 | - | - | - | log10(IC50 / uM) | 0 | - | not_run |
| R-fadrozole | GNINA | - | - | - | pK | 0 | - | not_run |
| R-fadrozole | Vina | - | - | - | kcal/mol | 0 | - | not_run |
| S-fadrozole | UMA-exchange | - | - | - | eV | 0 | - | not_run |
| S-fadrozole | Boltz-2 | - | - | - | log10(IC50 / uM) | 0 | - | not_run |
| S-fadrozole | GNINA | - | - | - | pK | 0 | - | not_run |
| S-fadrozole | Vina | - | - | - | kcal/mol | 0 | - | not_run |

Lower scores favor binding for Boltz-2 and Vina, and lower potential energy for UMA exchange. Higher CNNaffinity favors binding for GNINA. Values from different methods are not averaged.

A single replicate is a pilot. Multiple seeds measure sampling variability, not model accuracy. Agreement among models is not experimental validation. Heme/metal selectivity remains unvalidated.

Chai-1, AlphaFold 3 and DiffDock-L are pose comparisons. Structural confidence is not affinity. RFdiffusion is a protein-design model and has no comparable selectivity endpoint here.

See docs/BENCHMARKING.md for the protocol, sources and additional model limitations.

## Comparison Details

- R-fadrozole, UMA-exchange: No model outputs imported
- R-fadrozole, Boltz-2: No model outputs imported
- R-fadrozole, GNINA: No model outputs imported
- R-fadrozole, Vina: No model outputs imported
- S-fadrozole, UMA-exchange: No model outputs imported
- S-fadrozole, Boltz-2: No model outputs imported
- S-fadrozole, GNINA: No model outputs imported
- S-fadrozole, Vina: No model outputs imported

## Experimental References

| Ligand | B1 IC50 (nM) | B2 IC50 (nM) | B1 / B2 | Preference |
|---|---:|---:|---:|---|
| R-fadrozole | 118.6 | 6 | 19.77 | CYP11B2 |
| S-fadrozole | 39.5 | 171.2 | 0.2307 | CYP11B1 |

These are study-specific cellular IC50 values, not binding constants. The source protocol uses different substrate incubation times for B1 and B2. Two enantiomers do not establish general model accuracy.

- Roumen-2007-V79MZ-human: https://link.springer.com/article/10.1007/s10822-007-9128-9
- Roumen-2007-V79MZ-human: https://link.springer.com/article/10.1007/s10822-007-9128-9

## Existing Artifacts

These files were inventoried only. They are not automatically treated as benchmark scores.

- /home/ubuntu/HackProject/runs/demo-v1/R-fadrozole-CYP11B1/result.json: Synthetic software test (synthetic_demo)
- /home/ubuntu/HackProject/runs/demo-v1/R-fadrozole-CYP11B2/result.json: Synthetic software test (synthetic_demo)
- /home/ubuntu/HackProject/runs/demo-v1/S-fadrozole-CYP11B1/result.json: Synthetic software test (synthetic_demo)
- /home/ubuntu/HackProject/runs/demo-v1/S-fadrozole-CYP11B2/result.json: Synthetic software test (synthetic_demo)
- /home/ubuntu/HackProject/runs/demo-v2/R-fadrozole-CYP11B1/result.json: Synthetic software test (synthetic_demo)
- /home/ubuntu/HackProject/runs/demo-v2/R-fadrozole-CYP11B2/result.json: Synthetic software test (synthetic_demo)
- /home/ubuntu/HackProject/runs/demo-v2/S-fadrozole-CYP11B1/result.json: Synthetic software test (synthetic_demo)
- /home/ubuntu/HackProject/runs/demo-v2/S-fadrozole-CYP11B2/result.json: Synthetic software test (synthetic_demo)
- /home/ubuntu/HackProject/runs/exchange-free-S-fadrozole-01/result.json: Component or diagnostic result; not paired selectivity (unresolved)
- /home/ubuntu/HackProject/runs/exchange-free-S-fadrozole-bfgs-01/result.json: Component or diagnostic result; not paired selectivity (completed)
- /home/ubuntu/HackProject/runs/exchange-free-water-01/result.json: Component or diagnostic result; not paired selectivity (completed)
- /home/ubuntu/HackProject/runs/exchange-pilot-v1-01/CYP11B1/cluster_ligand/result.json: Component or diagnostic result; not paired selectivity (completed)
- /home/ubuntu/HackProject/runs/exchange-pilot-v1-01/CYP11B1/cluster_water/result.json: Component or diagnostic result; not paired selectivity (completed)
- /home/ubuntu/HackProject/runs/exchange-pilot-v1-01/CYP11B1/free_ligand/result.json: Component or diagnostic result; not paired selectivity (completed)
- /home/ubuntu/HackProject/runs/exchange-pilot-v1-01/CYP11B1/free_water/result.json: Component or diagnostic result; not paired selectivity (completed)
- /home/ubuntu/HackProject/runs/exchange-pilot-v1-01/result.json: Exchange candidate; import explicitly with --uma-result after validation (unresolved)
- /home/ubuntu/HackProject/runs/provisional-6M7X-S-fadrozole-charge1/result.json: Legacy deformation calculation, outside the current exchange benchmark (failed)
- /home/ubuntu/HackProject/runs/provisional-6M7X-S-fadrozole-v2/result.json: Legacy deformation calculation, outside the current exchange benchmark (failed)
- /home/ubuntu/HackProject/runs/provisional-6M7X-S-fadrozole/result.json: Legacy deformation calculation, outside the current exchange benchmark (failed)
- /home/ubuntu/HackProject/runs/uma-cpu-smoke-01/result.json: Component or diagnostic result; not paired selectivity (failed)
- /home/ubuntu/HackProject/runs/uma-water-01/result.json: Component or diagnostic result; not paired selectivity (passed)
- /home/ubuntu/HackProject/runs/uma-water-02/result.json: Component or diagnostic result; not paired selectivity (passed)
- /home/ubuntu/uma-crosscheck-niv-462/results/20260919T183757698313Z/candidate_result.json: Component or diagnostic result; not paired selectivity (completed)
