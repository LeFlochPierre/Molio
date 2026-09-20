# Relaxed ligand/water exchange cycle

This is the requested selectivity calculation. It supersedes the fragment-deformation plan for this experiment. The legacy `python -m cyp_pipeline run` command still implements fragment deformation and must not be used to obtain the four-energy cycle.

For each enzyme, the reaction is:

`cluster-water + free ligand -> cluster-ligand + free water`

After relaxing each structure, compute:

`exchange = E(cluster_ligand) + E(free_water) - E(cluster_water) - E(free_ligand)`

Then:

`delta = exchange(CYP11B2) - exchange(CYP11B1)`

Negative delta favors CYP11B2 within this potential-energy model; positive favors CYP11B1. This is not a binding free energy, selectivity ratio, or experimentally calibrated prediction. The free-molecule terms cancel in the enzyme difference when references match, but all four terms are explicitly calculated and saved for each enzyme for traceability.

## Inputs still needed

Copy `examples/exchange-cycle.template.json` to a new prepared manifest. Its null entries deliberately fail validation before model loading. Provide all four component structures for both enzymes. The existing 462-atom single-point coordinates cannot supply their missing atom mappings, replacement-water pose, or preparation assumptions. The 224-atom diagnostic draft is a different input and must not be substituted silently.

Each component needs:

- `atoms`: objects with unique `id`, standard element symbol `element`, and `position` in angstrom.
- `state`: integer `charge`, positive integer `multiplicity`, and explanatory `convention`.
- `fixed_ids`: explicitly selected boundary atoms for clusters; an empty list for free molecules. All other atoms relax.
- `preparation`: explanation of protonation, caps, electronic state, stereochemistry, and pose construction.
- `review`: either `approved: true` with a reviewer name, or `provisional: true` for an explicitly assumption-based exploratory run. Never invent approval.

Each cluster additionally needs `scaffold_ids` (the enzyme/heme/caps retained during ligand-water exchange) and `coordination` bounds for Fe-donor and Fe-axial S. Each bound is `{"ids": ["fe", "donor"], "min_A": 2.0, "max_A": 2.6}`; these example numbers are not prescribed chemical bounds. Use preparation-specific justified bounds.

The ligand- and water-bound clusters must retain exactly the same scaffold atom IDs/elements and fixed boundary positions. Water means neutral H2O in this cycle; a hydroxide/proton-exchange model requires a separately balanced cycle. Both sides must have equal elemental composition and total charge. Both enzymes must use identical free-water and free-ligand input objects. This structural contract cannot independently validate chemistry.

## Run on the A100

From `/home/ubuntu/HackProject`:

```bash
/home/ubuntu/uma-crosscheck-niv-462/.venv-uma-s11/bin/python -m cyp_pipeline.exchange prepared/exchange-cycle.json --check-only
/home/ubuntu/uma-crosscheck-niv-462/.venv-uma-s11/bin/python -m cyp_pipeline.exchange prepared/exchange-cycle.json --backend configs/uma-s-1p1-a100.json --out runs/exchange-01
```

`geometry_mode` is `relax`, as requested. The optimizer settings are the existing pilot settings: maximum 300 steps and force tolerance 0.02 eV/angstrom. No result is accepted as converged merely because the step limit was reached.

Each of the eight component directories contains its input, initial/final XYZ when available, relaxation history and result. The top-level `result.json` contains the four energies per enzyme, each exchange energy, and the B2-minus-B1 difference. Invalid preparation is rejected before loading UMA. Calculation failures and nonconvergence are saved; a missing/failed term prevents a selectivity difference. Provisional and synthetic runs remain explicitly labeled.

Software validation: arithmetic/sign, eight-component execution, missing inputs, mass/charge balance, shared references, fixed boundaries, coordination, failure persistence and nonconvergence are covered by tests. These tests do not replace real prepared inputs or establish chemical accuracy.
