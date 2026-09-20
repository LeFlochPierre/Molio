# Excluded R-fadrozole sensitivity attempts

The CYP11B1/R −10° starting-pose run in `runs/exchange-R-pose-minus10-01/` reached the optimizer force threshold but failed the independent final retained-bond audit: the Ala313 CB–HB3 distance was 2.22469 Å, outside its 0.7–1.4 Å hydrogen-bonded range. Its energy and apparent −4.62619 eV B2−B1 value are excluded from the sensitivity range and candidate ranking.

The −15° starting pose was rejected before GPU evaluation because its minimum initial atom-pair distance was 0.634 Å, below the 0.65 Å catastrophic-overlap threshold.

The valid sensitivity set consists of baseline, −5°, +5°, and +10° runs. Each converged and passed the full final bond/fixed-boundary audit.
