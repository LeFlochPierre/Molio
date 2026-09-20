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
The app's molecular renderer is project code, not an embedded RCSB screenshot.

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
