# CYP11B1 selectivity design campaign

Target: **CYP11B1** over **CYP11B2**.

A molecule is lead-eligible only when every accepted pose has favorable target exchange and the complete selectivity range clears the 0.05 eV engineering floor. These are UMA potential-energy screening criteria, not affinity or free-energy predictions.

## Preparation gate

Status: **expanded_seed_pose_gate_passed**. The current pocket omits B1/B2 differences at residues 109, 112, 320, and 404; analog design must include them before comparing chemistry hypotheses.

Required added residues: 109, 112, 320, 404

## Existing observations

| Candidate | Poses | Robust target selectivity (eV) | Expanded pocket | Lead eligible |
|---|---:|---:|---|---|
| S-fadrozole | 3 | +0.282165 | yes | yes |
| R-fadrozole | 4 | -0.675412 | no | no |
| S-fadrozole para-carboxamide | 1 | +0.050992 | yes | no |
| S-fadrozole meta-fluoro para-carboxamide | 1 | -0.009626 | yes | no |

## Excluded preparations or runs

| Candidate | Stage | Reason |
|---|---|---|
| S-meta-hydroxy | relaxed_cluster_geometry | CYP11B1 conserved ligand C03-C02 bond opened to 3.688 A; cycle unresolved and excluded. |

## Next proposed batch

| Rank | Candidate | Acquisition | Predicted robust selectivity (eV) | Uncertainty | Hypothesis |
|---:|---|---:|---:|---:|---|
| 1 | S-fadrozole pyridyl nitrile | +0.3438 | +0.2483 | 0.295 | Adds a directional acceptor while retaining the nitrile and approximate size. |
| 2 | S-fadrozole meta-methoxy | +0.3287 | +0.2431 | 0.380 | Separates hydrogen-bond acceptance and steric effects near residues 109/112. |
| 3 | S-fadrozole para-sulfonamide | +0.3045 | +0.1928 | 0.348 | Provides two neutral acceptors and one donor near the B1 Arg404 region. |
| 4 | S-fadrozole meta-fluoro | +0.3017 | +0.2109 | 0.340 | Low-size steric/electronic probe for the B1 Val320 versus B2 Ala320 difference. |
| 5 | S-fadrozole para-methylsulfone | +0.3010 | +0.2050 | 0.383 | Tests a neutral, strongly polarized Arg404-facing group without a donor. |

The ranking currently uses 3 expanded-pocket observations, including 1 full pose set(s). Single-pose observations receive lower model weight. At four or more distinct calculated candidates, the campaign switches to the fingerprint kernel surrogate and balances predicted selectivity with uncertainty.
