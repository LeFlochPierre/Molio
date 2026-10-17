# Third-party data and model notices

The MIT license covers original IsoForm project code, not third-party weights,
software, publications, or data that carry separate terms. No UMA, Boltz or
AlphaFold model weights, authentication credentials, downloaded package trees,
or model caches are distributed in this repository.

## Protein Data Bank coordinates

The reference library uses experimental entries from the PDB archive:

- CYP11B2: [4FDH](https://www.rcsb.org/structure/4FDH).
- CYP11B1: [6M7X](https://www.rcsb.org/structure/6M7X).
- CYP11A1: [3N9Y](https://www.rcsb.org/structure/3N9Y).
- CYP17A1: [3RUK](https://www.rcsb.org/structure/3RUK).
- CYP19A1: [3EQM](https://www.rcsb.org/structure/3EQM).

Additional research references include 7E7F, 7M8V and PDB chemical-component
records. PDB archive data are available under CC0; attribute the depositors and
associated publications when presenting the structures. See the
[RCSB PDB usage and citation policies](https://www.rcsb.org/pages/policies).
The original entry headers and existing source/hash sidecars are retained.
The earlier CYP app's molecular renderer is project code, not an embedded RCSB screenshot. The new What-If Lab viewer is attributed separately below.

## Assays and calculations

Small curated numerical assay records contain their primary-source URLs in
`data/benchmarks/`. No full research articles are redistributed. IC50 and Ki
endpoints are kept separate. The supplied prepared pockets are provisional
project-generated research artifacts, not claims of experimentally resolved
coordinates for every crossed drug/protein pair. Their provenance records
distinguish experimental and modeled components.

## Optional external models and software

- [UMA / FAIR Chemistry](https://huggingface.co/facebook/UMA): users must obtain
  model access and accept the upstream terms themselves. The project's MIT
  license does not grant access to or relicense UMA weights. Saved UMA outputs
  are explicitly labeled model-generated and retain model/checkpoint metadata.
- [FAIR Chemistry code](https://github.com/facebookresearch/fairchem): installed
  separately; follow its license and dependency notices.
- [Boltz](https://github.com/jwohlwend/boltz): optional external structure/model
  workflow; no model weights are included. New heme-containing input bundles
  deliberately do not request affinity predictions.
- AlphaFold-related preparation/import utilities do not include AlphaFold
  weights or a hosted prediction service.
- ASE, RDKit, OpenMM, PDBFixer, NumPy, SciPy, PyTorch, Playwright, Chromium and
  FFmpeg are optional runtime/tool dependencies with their own licenses.

## Video

The MP4 is a captioned capture of the actual IsoForm application, with original
HTML/CSS presentation graphics, no stock music and no third-party stock images.
It includes original model-output provenance and the same scientific limits
shown in the app. Recording tools and FFmpeg binaries are not redistributed.


## Molecular What-If Lab data and viewer

The new `molecular_lab/data/` fixture includes ChEMBL assay CHEMBL1832996,
compound records CHEMBL1828978–CHEMBL1828986, and document CHEMBL1828554.
ChEMBL-sourced records and derived datasets/depictions retain the **Creative
Commons Attribution-ShareAlike 3.0** terms, separately from the MIT application
code. Attribution: ChEMBL / EMBL-EBI and Hewings et al., *J. Med. Chem.* (2011),
[DOI 10.1021/jm200640v](https://doi.org/10.1021/jm200640v).
See [ChEMBL licensing](https://chembl.gitbook.io/chembl-interface-documentation/about)
and [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
Source URLs and hashes accompany the fixture; its experimental observations
are not new model results. The metadata snapshot is not a copy of the paper.

The bundled [3SVG](https://www.rcsb.org/structure/3SVG) PDB coordinates and ODR
chemical-component metadata come from the PDB archive (CC0), with original
headers retained. The crystal resolves a specified ligand stereoisomer while
the corresponding assay record leaves stereochemistry unspecified.

The new viewer bundles **3Dmol.js 2.5.5**, copyright University of Pittsburgh
and contributors, under BSD-3-Clause with incorporated dependency notices.
The full license is retained at `molecular_lab/web/vendor/3Dmol.LICENSE`;
package URL, pinned version, and bundle hash are in `provenance.json` beside it.
No external CDN is used at runtime. 2D images were generated using RDKit
2026.03.6 from the attributed chemical data.

Sequence-first workspaces download records from the **UniProt Consortium** and
precomputed protein models from **AlphaFold DB (Google DeepMind and EMBL-EBI)**.
These data use [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), separately
from the application code; see [UniProt terms](https://www.uniprot.org/help/license)
and [AlphaFold DB terms](https://alphafold.ebi.ac.uk/assets/License-Disclaimer.pdf).
Original provider records, model coordinates, URLs and hashes are retained in each
workspace. Models are displayed with confidence colours and optional region
highlights; their saved coordinates are not modified. Downloaded models remain
predictions, not experimental observations. These downloads are local project
artifacts, not additional bundled fixtures or AlphaFold inference weights.

Optional compound-name/CID lookups use **PubChem (NCBI/NLM)** and retain provider
responses, source URLs and hashes in the local workspace. See the
[PubChem data sources](https://pubchem.ncbi.nlm.nih.gov/sources) for contributing
organizations. Broader ChEMBL target-associated assay imports retain ChEMBL
attribution and CC BY-SA 3.0 terms; their raw source records are preserved without
combining measurements. Bundled example SMILES are labelled as general chemistry
examples and carry no claim of target-specific experimental activity.
