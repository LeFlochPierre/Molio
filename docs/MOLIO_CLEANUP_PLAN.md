# Molio-only cleanup audit

Audited 17 October 2026. This is a removal/migration plan, not a deletion log. No application code, projects, environments or research records were removed.

## Main finding

Molio's active application is `molecular_lab/`. Most of the old CYP/UMA/IsoForm project can leave the active repository, but **do not delete `cyp_pipeline/` yet**: `molecular_lab/experiments.py:48` imports `_domain_sequence` from `cyp_pipeline.benchmark_boltz` for bundled BRD4 predictions. That helper needs its amino-acid mapping and hashing helper too. Imported targets normally use their saved prediction sequence instead.

The dependency finding comes from source/import and reference inspection, not a complete runtime proof. The cleanup should include focused tests and a clean-package smoke check.

## Preserve first

- `molecular_lab/` including its bundled `data/`, upstream source snapshots, structures, depictions and vendored libraries.
- `tests/test_molecular_lab.py` and every `tests/test_whatif_*.py` test. These cover the current Molio app.
- `work/whatif/workspaces/`, `work/whatif/proposals.sqlite3`, and `work/whatif/experiments/`: real saved projects, hypotheses and experiment evidence. Preserve the full workspace tree, including per-project stores.
- `work/whatif/boltz-cache/`, the runtime freeze and `.venv-boltz/` / `.venv-whatif/` while using this configured installation. They are local, ignored runtime assets, not obsolete source code.
- Main README, license and third-party notices. Remove old notices only after the corresponding distributed code/data is removed; retain Molio's data/library attributions.
- `docs/WHAT_IF_*.md` and `docs/MOLECULAR_WHAT_IF_PLAN.md`: active usage guidance, provenance and scientific audits despite the old names.
- Current README media and original illustration sources. `docs/media/pipeline/*-card.svg` are rebuildable intermediate files; the original six PNGs, prompts, published PNG cards and build scripts preserve the artwork workflow.

**Git snapshot:** the audit found `molecular_lab/`, current Molio tests, scripts and media untracked, alongside modified tracked README/packaging files. A commit/tag of the existing tracked history alone would not preserve those untracked additions. Create a deliberate source snapshot that includes Molio, and separately back up ignored local research data before removal work. Do not indiscriminately add model weights or environments to Git.

## Remove from the active tree after migration; archive research history

| Path | Reason / condition |
| --- | --- |
| `cyp_pipeline/` | Old application; first move and verify the shared sequence mapper in Molio. |
| Root `configs/`, `examples/`, `demo/`, `design/` | Legacy CYP/UMA configuration, templates and demos; update old commands/docs/CI together. |
| Root `data/` | Legacy research data. Distinct from **`molecular_lab/data/`**, which stays. Archive with the legacy project. |
| `prepared/`, `research/`, `runs/` | Old preparation, experiments and presentation records. Archive outside the active tree rather than discard unique scientific work. Current app data is in `work/whatif/`. |
| `requirements-mlip-cpu.lock.txt` | Old MLIP/UMA runtime lock, not Molio's Boltz runtime. |
| `CODEX_PROJECT_HANDOFF.md`, `CYP_Hackathon_Team_Plan.md` | Old handoff and hackathon plans. |
| `.agents/skills/isoform-alchemi/` | Legacy agent workflow if no longer maintaining the IsoForm/UMA branch. |
| `molecular_lab/web/brand-concepts/` and `brand-concepts.html`, `.css`, `.js` | Previous naming/logo chooser; not loaded by the current app entry page. Remove its package-data glob at the same time. Keep `logo.svg`, `molio-wordmark.svg`, `molio-logo.js` and `molio-logo.json`. |

Legacy tests to remove with the old package (not independently while that package remains supported):

- `tests/test_agent_integration.py`
- `tests/test_ase_relax.py`
- `tests/test_benchmark.py`
- `tests/test_benchmark_boltz.py`
- `tests/test_benchmark_geometry.py`
- `tests/test_benchmark_uma.py`
- `tests/test_calibrated_selectivity.py`
- `tests/test_design.py`
- `tests/test_energy_proxy.py`
- `tests/test_exchange.py`
- `tests/test_exchange_geometry.py`
- `tests/test_isoform.py`
- `tests/test_isoform_previews.py`
- `tests/test_mlip.py`
- `tests/test_pipeline.py`
- `tests/test_portability.py`
- `tests/test_pose_sampling.py`
- `tests/test_screening.py`
- `tests/test_sentinel.py`
- `tests/test_sentinel_demo.py`
- `tests/test_sentinel_server.py`
- `tests/test_uma_batch.py`

Legacy documents to archive with IsoForm; fix any remaining links from the active README:

- `docs/ALCHEMI_AGENT_INTEGRATION.md`
- `docs/BACKENDS.md`
- `docs/BENCHMARKING.md`
- `docs/CALIBRATED_SELECTIVITY.md`
- `docs/DESIGN_CAMPAIGN.md`
- `docs/EXCHANGE_CYCLE.md`
- `docs/GETTING_STARTED.md`
- `docs/ISOFORM.md`
- `docs/ISOFORM_LEGACY_README.md`
- `docs/LEGACY_PIPELINE.md`
- `docs/MLIP_QUICKSTART.md`
- `docs/POSE_SAMPLING.md`
- `docs/PREPARATION.md`
- `docs/REPOSITORY.md`
- `docs/SCIENTIFIC_SCOPE.md`
- `docs/SCREENING_FRAMEWORK.md`
- `docs/SELECTIVITY_SENTINEL.md`
- `docs/UMA_POCKETS.md`

## Scripts

Keep these current application, validation, artwork and media scripts. The two older recorders are optional presentation history, not runtime dependencies; archive them if keeping only the complete tour.

- `scripts/build_molio_logo.py`
- `scripts/build_molio_pipeline_cards.py`
- `scripts/build_whatif_dataset.py`
- `scripts/check_molea_studio.py`
- `scripts/check_whatif_browser.py`
- `scripts/check_whatif_compounds.py`
- `scripts/check_whatif_designs.py`
- `scripts/check_whatif_navigation.py`
- `scripts/check_whatif_prediction_results.py`
- `scripts/check_whatif_starter.py`
- `scripts/check_whatif_startup.py`
- `scripts/check_whatif_targets.py`
- `scripts/make_molio_tour_preview.py`
- `scripts/record_molio_complete_tour.py`
- `scripts/record_molio_pipeline.py`
- `scripts/record_molio_video.py`
- `scripts/render_molio_pipeline.py`

Other top-level scripts are predominantly the old CYP/UMA preparation, exchange, screening, benchmarking and demo tools. Archive them with that project after updating CI. `scripts/audit_repository.py` needs review/replacement against the new Molio layout rather than assuming its old repository checks still apply. `scripts/video/` belongs to the earlier presentation workflow. `check_molea_studio.py` is a current Molio browser check despite its name; rename it rather than remove it.

## Packaging and automation must change together

- `pyproject.toml` still names the package `cyp-selectivity-pilot`, describes IsoForm, installs both packages and exposes multiple legacy commands. Rename the distribution/description for Molio, restrict package discovery to the retained package, and expose a `molio` command. Keep `whatif-lab` temporarily as a compatibility alias because the usage docs use it. Remove CYP/IsoForm command entry points with the legacy package.
- The `test` extra currently contains `numpy` and `ase` for the older work. Reassess Molio's actual test dependencies rather than retaining those by habit; keep chemistry/browser/video extras used by Molio.
- `.github/workflows/ci.yml` currently builds and compares an IsoForm demo and runs old browser checks. Replace those jobs with Molio tests and relevant browser checks before deleting their fixtures.
- `Dockerfile` currently starts `cyp_pipeline.sentinel_server` on port 8000. Replace it with a documented Molio container or remove the unsupported recipe; merely deleting the old package leaves it broken.
- Review `.gitignore`, `.dockerignore` and `.gitattributes` for old demo exceptions and packaging assumptions; retain ignores for credentials, model weights, environments and `work/`.

## Rebuildable clutter and duplicate media

Safe rebuildable cleanup candidates: `build/`, `cyp_selectivity_pilot.egg-info/`, `__pycache__/`, `.pyc` files and any generated test caches. They provide little space compared with model weights; reinstall the package after changing its metadata.

The current README embeds **`docs/media/molio-complete-tour-preview.webp`**, not the original GIF. Keep that chosen preview, `molio-complete-tour.mp4`, the current gallery, pipeline artwork, captions and run/export metadata.

Presentation archive candidates:

- `molio-complete-tour.gif` (~94 MiB): superseded by the currently embedded WebP; not referenced in the inspected README/docs/scripts.
- `molio-complete-tour-HQ.webp` (~31 MiB): alternate export, likewise not referenced in the inspected README/docs/scripts. Retain externally if wanted as a master.
- Older `molio-walkthrough.mp4`, `molio-pipeline.mp4`, `molio-pipeline.gif` and their old screenshots/manifests: referenced by historical sections in `docs/media/README.md`; update that guide before removing them.
- `molio-complete-preview.gif` (~7.7 MiB) is still linked from the media guide and produced by its helper. Decide whether to retain a lightweight GIF alternative or standardize the guide on WebP before removal.

Do not delete by `whatif`, `boltz`, `data`, or `run` filename patterns: those match active features and valuable results.

## Space observed locally

Approximate on-disk usage at audit time:

| Item | Size | Meaning |
| --- | --- | --- |
| `work/whatif/boltz-cache/` | 7.6 GiB | Active model weights; deletion requires another download. |
| `.venv-boltz/` | 6.2 GiB | Configured inference environment. |
| `.venv-whatif/` | 302 MiB | Current chemistry environment. |
| `docs/media/` | 214 MiB | Multiple video/animation versions plus artwork. |
| `work/whatif/experiments/` | 55 MiB | Actual prediction records. |
| `work/whatif/workspaces/` | 22 MiB | User-created protein projects. |
| Legacy `prepared/` + `runs/` + `research/` + root `data/` | ~64 MiB | Old research material to archive. |
| `build/` | 1.9 MiB | Rebuildable packaging output. |

The main benefit is clarity and maintainability, not removing the runtime's largest files.

## Recommended order

1. Preserve the current Molio source and local research data; retain the old IsoForm project as a separately restorable archive/branch.
2. Move the sequence mapper into `molecular_lab/`, preserve its validation and provenance, verify the BRD4 sequence and imported-target path, and remove the cross-package import.
3. Update package metadata, entry points, CI, container/docs and dependency lists for Molio.
4. Remove the listed legacy code, tooling and fixtures from the active repository, keeping the archive outside that tree.
5. Consolidate media, remove abandoned brand concepts and clean rebuildable artifacts.
6. Run Molio tests and browser smoke checks, build/install the package in isolation, verify bundled assets and README links. Full GPU experiments need not be repeated solely for a layout cleanup.

Target top-level layout: `molecular_lab/`, `tests/`, Molio-only `scripts/`, `docs/`, `.github/`, `pyproject.toml`, README and license notices; local `work/` and environments remain ignored.
