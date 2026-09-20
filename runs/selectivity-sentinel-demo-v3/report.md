# Selectivity Sentinel report

This is decision support for a declared target-family panel. It does not establish that a candidate binds, is safe, or is clinically selective.

Target: **CYP11B2** — policy thresholds: 10× model screen and 10× paired-reference validation.

| Candidate | Decision | Boltz target/off-target | UMA local test | Paired reference |
|---|---|---:|---|---:|
| R-fadrozole | validated_selective | 1.49× | supported | 19.8× |
| S-fadrozole | validated_not_selective | 1.5× | not_supported | 0.231× |
| Osilodrostat (LCI699) | validated_not_selective | 6.28× | unassessed | 3.57× |
| Baxdrostat | validated_selective | 1.87× | unassessed | 101× |

## R-fadrozole

**Decision:** `validated_selective`. Retrospective paired-assay validation; this does not establish prospective model accuracy.

Boltz target advantage: **1.49×** (raw within-model IC50-like ranking; not an assay measurement).
Paired IC50 reference: **19.8×** target over CYP11B1 (policy 10×).

Alerts:
- Boltz execution manifest is unfinished; raw outputs must be reconciled before formal use.
- Model screen does not show the configured target margin over the mandatory close paralog.
- Experimental reference and model-screening gate disagree; do not calibrate from this single case.
- Expanded CYP off-target panel remains unassessed: CYP11A1, CYP17A1, CYP19A1.

Next action: Advance only with the declared paired assay and expanded counterscreen.

## S-fadrozole

**Decision:** `validated_not_selective`. Retrospective paired-assay validation; this does not establish prospective model accuracy.

Boltz target advantage: **1.5×** (raw within-model IC50-like ranking; not an assay measurement).
Paired IC50 reference: **0.231×** target over CYP11B1 (policy 10×).

Alerts:
- Boltz execution manifest is unfinished; raw outputs must be reconciled before formal use.
- Model screen does not show the configured target margin over the mandatory close paralog.
- UMA pose/boundary stress test does not support a robust target-preference call.
- Boltz geometry has a ligand-identity or chirality failure; affinity score is not interpretable for: CYP11B2.
- Expanded CYP off-target panel remains unassessed: CYP11A1, CYP17A1, CYP19A1.

Next action: Do not advance as selective; redesign or run a paired counterscreen before further optimization.

## Osilodrostat (LCI699)

**Decision:** `validated_not_selective`. Retrospective paired-assay validation; this does not establish prospective model accuracy.

Boltz target advantage: **6.28×** (raw within-model IC50-like ranking; not an assay measurement).
Paired IC50 reference: **3.57×** target over CYP11B1 (policy 10×).

Alerts:
- Boltz execution manifest is unfinished; raw outputs must be reconciled before formal use.
- Model screen does not show the configured target margin over the mandatory close paralog.
- Expanded CYP off-target panel remains unassessed: CYP11A1, CYP17A1, CYP19A1.

Next action: Do not advance as selective; redesign or run a paired counterscreen before further optimization.

## Baxdrostat

**Decision:** `validated_selective`. Retrospective paired-assay validation; this does not establish prospective model accuracy.

Boltz target advantage: **1.87×** (raw within-model IC50-like ranking; not an assay measurement).
Paired Ki reference: **101×** target over CYP11B1 (policy 10×).

Alerts:
- Boltz execution manifest is unfinished; raw outputs must be reconciled before formal use.
- Model screen does not show the configured target margin over the mandatory close paralog.
- Boltz geometry needs manual ligand identity/chirality review for: CYP11B2, CYP11B1.
- Experimental reference and model-screening gate disagree; do not calibrate from this single case.
- Expanded CYP off-target panel remains unassessed: CYP11A1, CYP17A1, CYP19A1.

Next action: Advance only with the declared paired assay and expanded counterscreen.
