# Third-party notices

The MIT license covers original Molio code. Third-party data, software and weights retain their own terms. No model weights or credentials are distributed.

## Molio data and viewer

The `molio/data/` fixture includes ChEMBL assay CHEMBL1832996,
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

The viewer bundles **3Dmol.js 2.5.5**, copyright University of Pittsburgh
and contributors, under BSD-3-Clause with incorporated dependency notices.
The full license is retained at `molio/web/vendor/3Dmol.LICENSE`;
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

## Optional software and demo media

Boltz, RDKit, PyTorch, Playwright, Chromium and FFmpeg are separate dependencies with their own licenses. Installing Molio does not install Boltz or download its weights.

The Molio tour captures the local application and actual prediction outputs. Captions, cursor effects and pacing are presentation additions. Pipeline illustrations are illustrative generated artwork, not scientific structures or results. See `docs/media/README.md` for recording provenance.
