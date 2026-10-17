# Molio repository cleanup

The repository now contains the Molio application, its reference data, tests, documentation and current demo media. The earlier IsoForm CYP/UMA application has been retired.

## Recovery point

The branch `archive/isoform-before-molio-cleanup` preserves commit `2b66d3a` before this cleanup. Use `git show archive/isoform-before-molio-cleanup:path/to/file` to inspect an old file without restoring the old application. The unrelated untracked Git-output file was backed up to `/tmp/molio-cleanup-untracked-20261017.tar` before removal; this temporary backup is local only.

## Removed

- The CYP pipeline, its configurations, research fixtures, prepared inputs, generated runs, obsolete tests and ALCHEMI skill.
- IsoForm-specific deployment files, dependency lock, handoff documents and planning material.
- Superseded logo concepts, video recorders, earlier walkthrough media, redundant large animated exports and reproducible SVG card intermediates.
- Generated build metadata and bytecode caches.

The current README tour, screenshots, provenance exports, pipeline artwork and regeneration scripts remain.

## Names and compatibility

- Python package: `molio` (formerly `molecular_lab`).
- Installed command: `molio`; direct launch: `python -m molio`.
- Active scripts and tests use Molio or feature names. Current guides use descriptive names such as `GUIDE.md` and `ROADMAP.md`.
- New installations default to `work/molio`. Existing `work/whatif` is used automatically if the new directory does not exist. `--project-dir` overrides this choice.
- Existing environments, saved projects, SQLite data, prediction results and model caches have been preserved. Browser storage identifiers remain compatible with existing notes.
- Historical scientific records retain their original paths and metadata. Old filenames inside those records are provenance, not active dependencies.

The sequence mapper required by the BRD4 reference workflow now lives in `molio/sequence.py`, with explicit region bounds and the existing mapping checks retained. Molio no longer imports the retired pipeline.

## Development

Run `python -m unittest discover -s tests`. Chemistry tests require the `chemistry` extra. Browser checks require the `browser` extra and Playwright Chromium; checks that require a saved workspace accept explicit workspace and project-directory arguments. See the repository README for installation and optional Boltz setup.

## Verification of this cleanup

All 63 unit tests pass in the existing RDKit environment. The wheel builds and installs in an isolated environment, where the `molio` command and bundled reference dataset load successfully. Offline browser smoke checks cover startup, navigation and design using local Chrome. No new GPU predictions were needed for this structural cleanup.
