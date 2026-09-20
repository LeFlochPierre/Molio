# Historical source-preparation snapshot

This small snapshot supplies the mapped source domains required by the
historical preparation/audit scripts. It was copied from the original
`whole-protein-pilot-niv20260919` workspace; the original is unchanged.

- `prepare_whole.py`: original project preparation helper.
- `inputs/`: 4FDH/6M7X experimental PDBs and HEM/JD7 CCD records.
- `CYP11B1_S/`, `CYP11B2_R/`: final source-domain coordinates, atom maps,
  charge ledgers, requests and preparation/geometry declarations.
- `preparation_environment_lock.txt`: original package-version inventory.

These are provisional isolated-domain preparations with modeled hydrogens and
missing regions. They are not new experimental structures or a universal
chemistry-preparation method. Read their reports before use. Atom maps and
original path/hash metadata are preserved, not silently relabeled.

Historical preparation scripts use this directory by default; set
`ISOFORM_SOURCE_ROOT` or the script's `--source-root` option to use an alternate
snapshot. They need the chemistry dependencies recorded here (including
OpenMM, RDKit and PDBFixer). Rebuilding or relaxing chemistry is a separate
research task, not part of the dependency-free app startup. The live browser
demo uses the already supplied, self-contained manifests under `prepared/`.

No weights, inference caches, original-host virtual environments, superseded
attempts, or large full-protein inference trajectories are copied here.
