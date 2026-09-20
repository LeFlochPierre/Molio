# Energy → fold preference

The default IsoForm workflow recomputes the **supplied relaxed UMA exchange
energies** from the 20 September 2026 team handoff. This is a real Python-backed
analysis, not a mock result animation. It does **not** execute new UMA inference
or independently reproduce the selected poses.

## Run

From the project root:

```bash
python3 -m cyp_pipeline.sentinel_server --port 8000
```

Open `http://localhost:8000/` (forward port 8000 if the machine is remote).
Choose **Energy → fold preference**, a candidate, a pose-selection policy,
then **Calculate fold preference**. No GPU or checkpoint is required for this
reanalysis. Restart an old server after updating the code and refresh the
browser. Live UMA, pocket upload and planning remain in the workflow menu.

CLI:

```bash
python3 -m cyp_pipeline.calibrated_selectivity osilodrostat
python3 -m cyp_pipeline.calibrated_selectivity baxdrostat --pose-policy original_minima
```

Or `POST /api/calibrated-selectivity`:

```json
{"candidate_id":"baxdrostat","pose_policy":"selected_fit"}
```

IDs: `osilodrostat`, `baxdrostat`, or the unresolved `metyrapone` example.
Policies: `selected_fit` or `original_minima`. Arbitrary candidates,
coefficients, command strings and extra fields are rejected. This calibration
is not attached to the frozen R/S-fadrozole jobs.

## Calculation and provenance

For each enzyme, in eV:

```text
X = E(cluster + ligand) + E(free water)
    − E(cluster + water) − E(free ligand)
B2 advantage = X_B1 − X_B2
log10(S) = 2.13893364745 × B2 advantage
S = potency concentration B1 / potency concentration B2
```

Positive advantage / S > 1 favors B2 **within this empirical model**. Full
decimal component energies are subtracted before converting to JSON floats;
the exchange score is checked against the handoff. Total energies are never
divided to produce selectivity.

| Compound | Selected-fit S | Original-minima S, same coefficient | Training endpoint |
| --- | ---: | ---: | --- |
| Osilodrostat | 3.23× B2 | 3.13× B2 | O01 IC50, 3.5714× |
| Baxdrostat | 103.36× B2 | 5.86× B2 | B01 Ki, 100.7692× |
| Metyrapone | Not reported | Not reported | Not a training compound |

This is a **two-compound retrospective fit**, after searching 360 pose/assay
combinations. Selected poses are not the original minima. The coefficient is
supplied, not re-estimated here, and is neither a physical constant nor
validated for new compounds or targets. A 10× screen is an illustrative rule,
not a validated development gate. Both usable compounds remain **unresolved
under the supplied pose-spread rule**, even when a fitted ratio exceeds 10×.

The source is `cyp_pipeline/data/selectivity_handoff.json`; exports include
its SHA-256 and that of the original attachment. Pose bundles and convergence
logs were not supplied. Arithmetic is independently checked; geometry,
atom balance, convergence and experimental citations are not independently
re-audited. The supplied text ends at a Sources heading without references.

Osilodrostat O02 (33.93× IC50, original human V79 reference) stays visible
alongside O01. Ki and IC50 are distinct endpoints. The handoff's H295R
hormone-output ratio is not used as an isolated-enzyme calibration target.

Boltz ratios use `10^(y_B1 − y_B2)` from rounded supplied y values, under the
**handoff's stated output convention**. Geometry flags are supplied audit
flags. Invalid rows retain raw values only for audit, without a usable ratio.
Fitted UMA vs uncalibrated Boltz is not a fair accuracy comparison; two seeds
do not define confidence intervals.

The 3D panels show existing crystal reference complexes, clearly labeled;
they are **not** the selected relaxed osilodrostat/baxdrostat poses.

## Video and tests

The new recorder captures the real app/API without mocked endpoints or model
jobs. It produces a 53-second captioned, silent 1080p MP4; earlier recordings
are retained.

```bash
python -m pip install -e '.[video]'
python -m playwright install chromium
python scripts/check_calibrated_browser.py
python scripts/record_calibrated_video.py
```

`--preview` creates stills; `--out NEW_DIRECTORY` chooses a fresh output
folder; `--encode-only RECORDING_DIRECTORY` resumes encoding. `recording.json`
retains actual API responses and scene frame counts.

Next scientific steps: obtain the source pose/convergence bundles, validate
chemistry and atom balance, prespecify pose selection, and evaluate a frozen
calibration on held-out compounds with matched assay endpoints.
