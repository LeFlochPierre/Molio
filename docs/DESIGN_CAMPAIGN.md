# CYP11B1-selective molecular design loop

The design campaign uses the completed relaxed ligand/water exchange cycles as
training observations. Its target is CYP11B1 over CYP11B2.

For every accepted pose:

`exchange = E(cluster+ligand) + E(free water) - E(cluster+water) - E(free ligand)`

`delta = exchange(CYP11B2) - exchange(CYP11B1)`

A provisional CYP11B1 lead must satisfy both rules across the complete accepted
pose set:

- every CYP11B1 exchange energy is below 0 eV;
- the minimum delta is above +0.05 eV.

The gates keep target binding and isoform discrimination separate. The scores
are UMA potential-energy descriptors. They are not binding free energies,
affinities, or experimental selectivity ratios.

## Current campaign

The machine-readable registry is
`design/cyp11b1-selectivity-v1/campaign.json`. Expanded-pocket S-fadrozole is
the current provisional CYP11B1 lead. The earlier R-fadrozole result remains a
small-pocket CYP11B2-directed reference and is excluded from expanded-pocket
model training.

The original capped pocket omitted the closest useful sequence differences.
New analog calculations use an expanded pocket containing residues 109, 112,
320, and 404 in addition to the original pocket. This exposes these
hypotheses:

- B1 Arg404 versus B2 Gln404: stronger neutral acceptor/donor groups on the
  nitrile-facing end;
- B1 Ser112/His109 versus B2 Ile112/Cys109: compact polar ring substituents;
- B1 Val320 versus B2 Ala320: small steric probes.

## Commands

Create or refresh the campaign with RDKit descriptors:

```bash
/home/ubuntu/whole-protein-pilot-niv20260919/.venv-prep/bin/python \
  -m cyp_pipeline.design init \
  --out design/cyp11b1-selectivity-v1 \
  --target CYP11B1
```

Prepare one candidate by constrained embedding into both seed poses:

```bash
/home/ubuntu/whole-protein-pilot-niv20260919/.venv-prep/bin/python \
  scripts/prepare_design_candidate.py \
  design/cyp11b1-selectivity-v1/campaign.json \
  S-para-carboxamide \
  --seed-manifest prepared/exchange-design-pocket-S-v1-converged.json \
  --out prepared/design-S-para-carboxamide-v2
```

Validate and run the candidate:

```bash
/home/ubuntu/uma-crosscheck-niv-462/.venv-uma-s11/bin/python \
  -m cyp_pipeline.exchange \
  prepared/design-S-para-carboxamide-v2/manifest.json \
  --check-only

/home/ubuntu/uma-crosscheck-niv-462/.venv-uma-s11/bin/python \
  -m cyp_pipeline.exchange \
  prepared/design-S-para-carboxamide-v2/manifest.json \
  --backend configs/uma-s-1p1-a100.json \
  --out runs/design-S-para-carboxamide-v2-01
```

After pose sensitivity is summarized, ingest it and refresh the next batch:

```bash
/home/ubuntu/whole-protein-pilot-niv20260919/.venv-prep/bin/python \
  -m cyp_pipeline.design ingest \
  design/cyp11b1-selectivity-v1/campaign.json \
  S-para-carboxamide \
  runs/design-S-para-carboxamide-pose-sensitivity-v1/summary.json
```

With fewer than four distinct calculated analogs, ranking emphasizes chemistry
hypotheses and structural diversity. At four observations it switches to a
chiral Morgan-fingerprint kernel surrogate. The acquisition score combines the
predicted robust CYP11B1 selectivity, distance from already calculated
molecules, and the declared pocket-interaction hypothesis. Each round retains
failed and wrong-direction molecules as training evidence.

Before a molecule is promoted, repeat local pose perturbations, audit source
bonds and fixed boundaries, and challenge pocket boundary, protonation, spin,
and solvation choices. Experimental CYP11B1/CYP11B2 measurements remain the
final selection criterion.

## September 19, 2026 result

Expanded-pocket S-fadrozole passed three local pose cycles with B2-minus-B1
from +0.282165 to +0.398223 eV and is the current provisional CYP11B1 lead.
The first two completed analog baselines show a potency/selectivity tradeoff:
para-carboxamide gives B1 exchange -2.532183 eV but only +0.050992 eV
single-pose selectivity, while meta-fluoro para-carboxamide gives -0.009626 eV.
Meta-hydroxy is excluded because the conserved C03-C02 ligand bond opened
during CYP11B1 relaxation. See `runs/cyp11b1-design-results-v1/REPORT.md`.
