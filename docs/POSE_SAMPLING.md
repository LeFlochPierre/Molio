# Symmetric pose sampling

Relaxation through `python -m cyp_pipeline.exchange` now defaults to ensemble sampling. `--single-pose` explicitly requests the historical behavior; the Python `run_cycle` API remains the legacy primitive. Single-point mode is unchanged.

Prepare the retained source-topology and cap bond ledger (same bounds as the existing external audit), then run:

```sh
python scripts/prepare_pose_search.py prepared/exchange-pilot-v1/manifest.json --out prepared/pose-search-v1/manifest.json
python -m cyp_pipeline.exchange prepared/pose-search-v1/manifest.json --backend configs/uma-s-1p1-a100.json --out runs/pose-search-v1
```

Use the existing UMA Python environment. Preparation additionally needs OpenMM. `--check-only` validates the contract without loading the backend. `--resume` reuses completed accepted/rejected poses only when manifest, shared settings and backend metadata match; an interrupted pose is restarted using the original optimization settings.

Defaults: rotations [0,360) in 15-degree steps; tilt offsets [-20,20] in 10-degree steps; RMSD 0.25 Å; temperature 310 K. A shared `--sampling-settings settings.json` overrides any of `rotation_start_deg`, `rotation_stop_deg`, `rotation_step_deg`, `tilt_start_deg`, `tilt_stop_deg`, `tilt_step_deg`, `rmsd_threshold_A`, `temperature_K`. No per-isoform grid overrides are allowed. Rotation upper endpoint is exclusive and tilt upper endpoint inclusive when reached by the step. All components have the same 120 seed IDs by default. Rotations visit separated sectors and zero tilt first; every prefix is identical across isoforms.

The entire guest is rotated rigidly about Fe–donor and tilted about the intersection of its plane and the heme plane, pivoting at the donor. Thus both Fe–donor distance and donor coordinates remain exact during seed generation. Tilt is relative to the post-rotation starting plane angle, not a replacement absolute angle. The heme normal uses NA/NB/NC/ND; fadrozole plane uses N06/C05/C07. Other atom naming requires `sampling_frame.heme_plane_ids` and `guest_plane_ids` on each cluster. Water uses its three-atom plane and Fe–O axis. These are starting-pose transformations, not additional relaxation constraints.

The apo reference in this exchange model is **water-bound**, not an empty cluster. Its water orientations receive the same grid and relaxation. Free ligand/water receive the same rigid rotation/tilt seeds, are relaxed once per seed, and are reused identically for both isoforms. Their rigid-body seeds do not constitute an internal conformer search. There are 720 unique relaxations at defaults (480 clusters + 240 free references). The existing optimizer protocol, boundary, charge and multiplicity are passed through unchanged.

Every initial and final pose receives coordination, all retained source/cap bond, guest bond, fixed-boundary and supplied signed-volume stereochemistry checks. Nonconverged or failed poses are rejected with explicit reasons in their `result.json`. Missing audit ledgers fail preflight. Failed seeds remain in the attempted count; accepted/rejected counts are reported separately. No seed is silently omitted or replaced.

Deduplication uses atom-ID matched **all-heavy-atom RMSD** after a proper rotation fit of scaffold heavy atoms; the guest is never independently aligned. Free references use whole-molecule alignment. Energy-ordered leader clustering retains the lowest-energy representative of each group, with each member within 0.25 Å of that representative. This avoids chain merging. There is no atom-permutation symmetry correction. All-heavy RMSD can dilute small guest changes in a large cluster, and water H orientations cannot distinguish otherwise identical heavy-atom minima under this requested metric.

For distinct minima, `p_i = exp(-(E_i-E_min)/(k_B T))/sum_j exp(-(E_j-E_min)/(k_B T))`. Primary energy is `sum_i p_i E_i`, not a free energy or a degeneracy-weighted mean over starting seeds. Minimum energy is the lowest **observed valid** relaxed energy, not a proven global minimum. Cluster populations count each deduplicated representative once. Exchange remains `cluster_ligand + free_water - cluster_water - free_ligand`; minimum-based exchange uses the minimum of each component.

`result.json`, `REPORT.md` and `convergence.csv/json` update after each complete matched seed. All minima, populations and cluster memberships are in JSON, with the lowest five in the report. Convergence recomputes clustering and weights for each matched prefix. Completion of a grid does not prove physical convergence. The raw accepted relaxed-energy range is reported per component. The ΔΔE spread is the sum of the four bound/apo ranges across both isoforms; shared free references cancel. If |ΔΔE| does not exceed that conservative spread or the existing signal floor, selectivity is unresolved and no preferred isoform is emitted. Signed numerical diagnostics are retained for inspection. Incomplete or synthetic calculations never emit a directional claim.
