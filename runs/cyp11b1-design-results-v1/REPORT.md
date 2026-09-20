# CYP11B1 design iteration results

Current provisional lead: **S-fadrozole**.

| Molecule | Evidence | B1 exchange (eV) | B2−B1 selectivity (eV) | Decision |
|---|---|---:|---:|---|
| S-fadrozole | 3 expanded-pocket poses | −2.321695 to −2.321683 | +0.282165 to +0.398223 | provisional CYP11B1 lead |
| S para-carboxamide | 1 baseline pose | −2.532183 | +0.050992 | borderline; no improvement and needs pose range |
| S meta-fluoro para-carboxamide | 1 baseline pose | −2.523384 | −0.009626 | nonselective within signal floor |
| S meta-hydroxy | geometry failure | unresolved | unresolved | excluded; conserved C03–C02 bond opened |

Positive B2−B1 values favor CYP11B1. Lead eligibility requires at least three accepted poses, favorable B1 exchange in every pose, and a complete selectivity range above +0.05 eV.

The first analogs show a potency/selectivity tradeoff. Replacing the nitrile with carboxamide made modeled B1 exchange about 0.21 eV more favorable than S-fadrozole, but reduced the selectivity signal from a robust minimum of +0.282 eV to a single-pose +0.051 eV. Adding meta fluorine to that carboxamide eliminated the direction entirely. The current model therefore favors retaining the S-fadrozole nitrile while exploring smaller ring substitutions and alternative orientations.

The next campaign queue is generated in `design/cyp11b1-selectivity-v1/next_batch.json`. Every new candidate must use the expanded pocket containing residues 109, 112, 320, and 404 and must pass the same bond, chirality, convergence, and three-pose gates.
