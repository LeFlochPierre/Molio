# Preparation and evidence contract

A chemical reviewer must supply a chemically complete cluster. No automatic residue-name-to-charge or spin inference occurs. Start with one chain/pose from 6M7X and explicitly resolve alternate locations, missing atoms, protonation, stereochemistry, waters, heme connectivity and axial cysteine treatment.

The real-system template is intentionally empty. Required atom objects:

```json
{"id":"stable-atom-label","element":"N","role":"ligand","position":[0.0,0.0,0.0]}
```

Coordinates are Å. Roles: ligand, heme, axial, pocket, cap. IDs are unique and remain stable across fragment extraction and comparable isoforms. Supply all hydrogens/caps explicitly. `fragment_ids` selects exact atoms already in the full cluster; no cap is synthesized during extraction. Review every cut bond. If a chemically closed fragment cannot be represented as this subset, prepare a suitable capped cluster or extend the contract before calculation. Never silently evaluate a broken-bond fragment.

`fixed_ids` fixes full-cluster boundary atoms. `cluster_state` and `fragment_state` each require an integer charge, positive integer multiplicity and a description of the model's electronic-state convention. These states can differ between full cluster and fragment, but the fragment state is identical in both descriptor terms.

`coordination` contains at least the Fe–ligand donor and Fe–axial S pairs. Each entry has `ids` (two atom IDs), `min_A`, `max_A`. A reviewer sets physically motivated bounds before calculation; there are no real-chemistry defaults. Add other coordination checks as appropriate. Distance checks alone do not validate oxidation state, bonding, stereochemistry or spin; inspect XYZ outputs and validate against chemical expertise.

Every preparation entry is a required explanation: protonation, oxidation_state, caps (exact cut/capping bonds), boundary, stereochemistry, reference_coordination, fragment_definition, pocket_geometry. Record source structure hash, chosen chain, atom/residue mapping, preparation software/version and modeling method in additional fields. The complete input is snapshotted.

`review.approved=true` and a reviewer name are attestations entered by the team, not a claim the software has independently verified chemistry. `comparison_group` identifies a shared reviewed preparation protocol. Comparison checks matching fragment ID/element/role sets, state, and selected preparation definitions. It cannot infer equivalent chemistry from coordinates or prose. Keep comparable definitions identical and document pose/boundary variants separately.

# Evidence and interpretation

Verified starting structure sources:

- [6M7X](https://www.rcsb.org/structure/6M7X): human CYP11B1, S-fadrozole (JD7).
- [4FDH](https://www.rcsb.org/structure/4FDH): human CYP11B2, fadrozole; the comparative structural study assigns R-fadrozole.
- [Structural study linked from RCSB](https://doi.org/10.1074/jbc.RA118.006214): structural comparison supports these starting poses. Crystal occupancy is not quantitative selectivity ground truth.

Curate a separate assay table with ligand stereochemistry, species, enzyme, endpoint, units, conditions, source, uncertainty and comparability. Do not mix IC50, Ki, Kd and cellular effects. No quantitative experimental labels are currently included.

Failure criteria: nonfinite energy/forces, model unsupported elements, absent review, invalid mapping, coordination failure, nonconvergence, inconsistent protocols/models, missing isoform or sensitivity ranges reaching zero/signal threshold. Results with a numeric descriptor remain exploratory; additional preparation uncertainties can require manual unresolved classification.

Before claiming MLIP adds information, compare against geometry baselines using compatible assays; test alternative poses, boundaries and reference assumptions; inspect local perturbation responses; budget and perform suitable quantum references where possible. Two ligand preferences cannot support statistical validation. Baxdrostat is a retrospective holdout after protocol freeze, not a blind prediction.
