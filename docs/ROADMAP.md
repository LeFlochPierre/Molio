# Molio roadmap

Molio is a local workspace for exploring proteins, proposing molecular changes and comparing traceable computational predictions. It helps formulate research hypotheses; it does not establish experimental binding or design validated drugs.

## Available today

- A project library, interactive 3D proteins and compounds, and saved workspace data.
- Target discovery and sequence-first setup with available public records and AlphaFold DB models. Assay data are optional.
- Starting compounds entered as SMILES or imported from public chemistry sources.
- Custom proposals and rule-based design ideas with chemical checks.
- Optional local Boltz-2 comparisons across molecules and random seeds, with progress, cancellation, pose inspection and export.
- Separate presentation of native affinity, binder classifier probability, structural confidence and experimental evidence.
- A bundled BRD4 reference dataset for offline exploration and reproducible checks.

## Architecture

`molio/` contains the Python application and standard-library HTTP server. `molio/web/` contains plain JavaScript, CSS and the bundled 3Dmol.js viewer. RDKit is optional for chemistry operations; Boltz runs separately. Saved data and model caches live outside the source package.

See [the user guide](GUIDE.md), [backend setup](../README.md#enable-local-boltz-predictions) and [data provenance](DATA_PROVENANCE.md). Historical pilot reports document the protocols actually run, rather than promising broader validation.

## Next useful work

1. Improve target readiness summaries and provider failure recovery, so users know which inputs are available before starting a costly run.
2. Expand reference-based evaluation across diverse targets before interpreting model-score improvements as reliable design progress.
3. Improve comparison and filtering for larger design collections while preserving seed-level results and provenance.
4. Refine installation and browser coverage across supported platforms.

Automatic molecular optimization, experimental validation and molecular-dynamics trajectories are not implemented. New scientific backends should have explicit protocols, limitations and reproducible evaluation before they are exposed as design guidance.
