# First-slice data audit — 2026-09-29

## Selected series

- Target: human BRD4, first bromodomain, UniProt **O60885**, ChEMBL **CHEMBL1163125**.
- Assay: **CHEMBL1832996**, displacement of H4Ac4 peptide from BRD4(1). ChEMBL target-assignment confidence score 9. This score concerns target assignment, not certainty of each measurement.
- Publication: Hewings et al. (2011), *3,5-Dimethylisoxazoles Act as Acetyl-lysine-mimetic Bromodomain Ligands*, DOI [10.1021/jm200640v](https://doi.org/10.1021/jm200640v).
- Imported records: nine distinct compounds, CHEMBL1828978–CHEMBL1828986. All have exact positive IC50 values in nM, the same assay/document/target, and no ChEMBL data-validity or potential-duplicate flag in the snapshot.
- Dataset intentionally remains smaller than the design's aspirational 50–200 compounds. A coherent assay with interpretable edits is preferable to mixing endpoint/construct/protocol contexts just to increase the count.

No independent replication or per-measurement uncertainty is present in the imported records. Stereochemistry is unspecified for some compounds. Preserve that uncertainty in all displays and exports.

## Comparisons

Seven manually selected related pairs are derived from the nine records. RDKit computes exact-bond maximum common substructures to align the drawings and highlight changed atoms. These are described as curated related comparisons, not a general validated single-cut matched-molecular-pair algorithm.

| Edit | A IC50 (nM) | B IC50 (nM) | B relative to A |
| --- | ---: | ---: | --- |
| Add ethoxy, 979 → 981 | 84,200 | 23,200 | 3.63× lower |
| Ketone to alcohol, 980 → 982 | 24,600 | 9,700 | 2.54× lower |
| Add acetyl, 981 → 985 | 23,200 | 7,500 | 3.09× lower |
| Ketone to alcohol with ethoxy, 985 → 986 | 7,500 | 4,800 | 1.56× lower |
| Ethyl ester to acid, 983 → 984 | 7,700 | 51,200 | 6.65× higher |
| Add ethoxy to alcohol series, 982 → 986 | 9,700 | 4,800 | 2.02× lower |
| Add acetyl to parent, 979 → 980 | 84,200 | 24,600 | 3.42× lower |

Compound suffixes refer to CHEMBL1828xxx. Ratios are recomputed from concentrations, not transcribed from a plotted figure. The selected edits are useful comparisons; the magnitude and uncertainty do not warrant automatically labelling them dramatic activity cliffs.

## Structural checks and exclusions

**Included: [3SVG](https://www.rcsb.org/structure/3SVG).** Experimental X-ray structure, 1.68 Å. DBREF maps chain A residues 44–168 to O60885; SEQADV records expression-tag residues. Ligand ODR is chain A residue 169, with 19 deposited heavy atoms. The builder checks target accession, chain, ligand ID, residue ID, and CCD connectivity.

ODR's graph matches CHEMBL1828986 after removing stereochemical specification. The CCD identifies a specific stereoisomer; the assay SMILES does not. Therefore 3SVG is **experimental pocket context**, not an exact stereochemically verified pose of the measured compound. The app never assigns the assay IC50 to the individually resolved stereoisomer.

**Excluded: 3SVH.** Although it is from the same publication and its KRG ligand matches the acid compound's graph, DBREF maps the structure to **Q92793 / CREBBP**, not BRD4. It cannot be displayed as a BRD4 pose.

**Excluded: 3SVF.** It is BRD4, but CCD ligand WDR has additional connectivity relative to the assay's dihydroquinazolinone compound. Sharing a paper or similar scaffold is not enough to assert an exact compound match.

No pair has two verified experimental bound poses in this fixture. Side-by-side molecular comparison is available as aligned 2D drawings and generated free-molecule 3D conformers. The protein pane remains the fixed, labelled experimental reference. Pair-specific poses are future prediction work.

## Provenance and terms

Raw ChEMBL activity/assay/document responses, the RCSB ODR component record, and original 3SVG PDB are stored under `molecular_lab/data/sources/`. Their public retrieval URLs and hashes appear in `dataset.json`. The corresponding derived records and drawings retain source IDs. ChEMBL-derived data are distributed under CC BY-SA 3.0; PDB archive data are CC0. See the repository's third-party notices for attribution and the viewer's separate software license.

## Acceptance boundary

The first slice provides at least five sourced comparisons, reproducible ratios, accurate structure identity, and offline inspection without GPU inference. It does **not** establish mechanistic explanations, new binding predictions, broad compound coverage, or chemist usability validation. The next user study should test whether the comparison/evidence layout helps a chemist formulate a concrete next experiment.
