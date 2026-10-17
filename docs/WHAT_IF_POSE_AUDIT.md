# BRD4 pose-screen audit

The new automated screen was applied to 19 completed local prediction artifacts.
All 19 had the expected ligand element composition and 125 mapped BRD4 C-alpha
residues. None triggered the project's limited distance/RMSD review heuristics.

Across these poses, protein C-alpha RMSD to 3SVG ranged from 0.2977 to 0.4684 Å.
After protein alignment, ligand centroid distance from the reference ODR centroid
ranged from 0.4939 to 1.8774 Å. These are pocket-context diagnostics, not ligand-pose
RMSDs or validation of affinity. ODR is a different reference ligand.

The audit includes the newer nine-prediction batch
`218aa745-00e0-4813-a59b-49deb7115370`, which was allowed to finish before the app
was restarted. Original job records and model outputs were preserved. Derived
`pose_checks.json` sidecars retain the method, thresholds, source hashes and
interpretation limits.

Verification included synthetic displaced/clashing ligands, rigid-transform
invariance, wrong protein/ligand identities, nonfinite coordinates, source-pose
hash checks and original-record preservation. All 176 regression tests completed
successfully (six optional skips). Desktop/mobile browser checks passed, including
all nine complexes in the latest batch, reference overlay toggling, residue
highlighting, export and viewer cleanup. The new inference result-parser path
was also checked against the six original repeat outputs; native scores were unchanged.

See [pose diagnostic definitions and limitations](WHAT_IF_LAB.md#pose-diagnostics-and-experimental-overlay).
Missing next steps include local MSA support, chemical bond/stereochemistry checks,
a broader measured benchmark and bounded automated candidate screening.
