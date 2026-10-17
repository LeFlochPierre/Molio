# First generated-design trial

Run: `b75952b7-2d9b-49ad-bdbd-44ef287336ff`. Three fresh Boltz-2 predictions at seed 42: the measured
CHEMBL1828983 parent and two generated side-chain variants. The variants have no
experimental activity assigned; both are absent from the nine-compound local library.

| Molecule | Native affinity | Difference from parent | Pose screen |
| --- | ---: | ---: | --- |
| CHEMBL1828983 | -0.0731 | +0.0000 | screen_clear |
| Ethoxy → methoxy · 0da435 | -0.0294 | +0.0437 | screen_clear |
| Ethyl ester → methyl ester · 355cc3 | -0.2068 | -0.1337 | screen_clear |

Native affinity is log10(IC50 in micromolar), lower is stronger predicted binding.
Positive differences mean a worse model score than the parent. Small single-seed
differences do not establish reliable ranking or experimental improvement.

The ether edit replaces O–CH2–CH3 with O–CH3. The ester edit replaces
C(=O)O–CH2–CH3 with C(=O)O–CH3. Each retains the ring scaffold and reduces molecular
weight by one CH2 unit. These are structural hypotheses, not synthesis routes.

The full design workflow generated these candidates, saved them as proposals,
selected the parent as baseline, and ran identical prediction settings. Original
SMILES, native outputs, coordinates and hashes are in the local experiment directory.
Pose-screen success is limited geometry evidence, not chemical or affinity validation.

Next decision: inspect poses and consider matched repeats before treating any small
score difference as a useful improvement. The app does not automatically select a winner.
