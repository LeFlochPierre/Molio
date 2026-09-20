# IsoForm

IsoForm is an off-target **research workspace**, not a validated universal binding predictor. It connects a chosen molecule to a curated target/counter-screen panel, prepares starting inputs, exposes what has actually been calculated, and keeps model outputs separate from assay evidence.

## Use the app

Run from the project root, not the HTML folder:

```bash
cd IsoForm
python3 -m cyp_pipeline.sentinel_server
```

Open the forwarded port 8000 in your laptop browser, then `/demo.html`. Restart the previous server and hard-refresh after updating. `report.html` is the historical static report, not the app. Existing module names remain compatible with previous commands.

This default serves views, saved evidence and input preparation without model execution. For actual UMA, follow [the portable setup guide](GETTING_STARTED.md), then use `.venv-mlip/bin/python -m cyp_pipeline.sentinel_server --enable-uma --backend configs/uma-s-1p1-cpu.json`. Use `configs/uma-s-1p1-cuda.json` only with a working CUDA runtime. An alternate model environment can be selected with `--uma-python /path/to/environment/bin/python`.

This server is for a trusted local/Brev tunnel, not an unauthenticated public compute service.

## Default workflow: energy → fold preference

The app opens with the osilodrostat retrospective calibration. Click
**Calculate fold preference** to recompute its supplied UMA exchange terms and
3.23× fitted B2 preference; baxdrostat gives 103.36× with the selected fit or
5.86× with original minima. Metyrapone stops at failed B2 convergence. The
conversion, pose sensitivity, Boltz seeds, assay endpoints and provenance are
visible and exportable. No new UMA inference or GPU is required here.
See [method and limitations](CALIBRATED_SELECTIVITY.md). Reference structures
are not the selected relaxed drug poses. The fitted ratios are not independent
predictions, and pose robustness remains unresolved.

## Live paired screen

Choose **Compare pair · live UMA** to see R-fadrozole and the prepared CYP11B2/CYP11B1 pair side by side. Switching to S-fadrozole loads that candidate's actual prepared coordinates in both views. These are provisional prepared pockets, not new docking predictions. Geometric coordination guides show distances in the supplied coordinates; they do not prove chemical bonds or binding strength.

Use **Compare pair · live UMA → Run UMA** to launch eight real frozen-coordinate energy evaluations. The displayed progress comes from completed energy components, not a simulated progress timer. Once submitted, the views are tied to the job's immutable input snapshot. A result card reports energy direction and the hypothetical energy-fold proxy described below. Changing an unprepared candidate to a known reference molecule opens saved evidence instead; a new molecule opens the input builder.

## More proteins: Build inputs

1. Choose **Prepare more targets**, then select a molecule and intended target. The default counter-screen panel contains five steroidogenic P450 proteins.
2. Click **Build inputs**. Existing reference PDBs are checked; missing curated files are fetched from RCSB. Protein chain/UniProt accession, PDB ID, sequence records, heme and reference ligand are checked before accepting a download.
3. The app saves a downloadable input bundle and displays separate readiness columns. Changing the target changes the actual coordinate view. A custom sequence without a mapped structure shows an empty state, never a different protein.

| Protein | Experimental reference | Deposited ligand |
| --- | --- | --- |
| CYP11B2 | [4FDH](https://www.rcsb.org/structure/4FDH) | R-fadrozole |
| CYP11B1 | [6M7X](https://www.rcsb.org/structure/6M7X) | S-fadrozole |
| CYP11A1 | [3N9Y](https://www.rcsb.org/structure/3N9Y) | Cholesterol |
| CYP17A1 | [3RUK](https://www.rcsb.org/structure/3RUK) | Abiraterone |
| CYP19A1 | [3EQM](https://www.rcsb.org/structure/3EQM) | Androstenedione |

The ligand in a crystal view is **not replaced** with the selected candidate. These references locate known sites; they do not demonstrate binding of your molecule. Experimental constructs can have tags, mutations or missing coordinates; SEQRES, DBREF and SEQADV provenance accompanies the exported sequences. Sequences are not silently relabeled as canonical full-length proteins.

Each bundle in `runs/isoform-inputs/<content-id>/` contains:

- `references/`: original downloaded PDB files.
- `sequences/`: FASTA experimental construct sequences (or an explicitly supplied custom sequence).
- `boltz/`: JSON-compatible YAML describing protein + selected candidate + heme for the curated P450s. These are **structure prediction inputs**, not predictions or UMA inputs.
- `reference-pockets/`: unapproved heavy-atom coordinate drafts around the *deposited* ligand. These cannot pass the UMA input validator.
- `uma/prepared-pockets.json`, only when applicable: a copy of the existing provisional R/S-fadrozole B1/B2 preparations, with their review status preserved.
- `manifest.json`: source mappings, SHA-256 hashes, readiness and scientific limitations.

The same request and source files reuse the same bundle. Edited artifacts are never overwritten. Arbitrary URLs, commands, output paths and backend configurations are not accepted from the browser.

CLI equivalents:

```bash
python3 -m cyp_pipeline.structure_library --download
python3 -m cyp_pipeline.auto_inputs --candidate r_fadrozole --target CYP11B2
```

For offline input building, add `--offline` after downloading references. Custom molecules need RDKit SMILES syntax validation in the **server interpreter** before prediction files are exported; syntax validation is still not chemistry approval.

## What is automatic, and what remains?

**Automatic now:** curated reference retrieval, identity checks, sequence extraction, model-input generation, reference-pocket extraction, provenance, available UMA input reuse, 3D views and input auditing.

**Not yet automatic:** running and auditing a new Boltz pose, complete chemical preparation of that pose (hydrogens, capped boundaries, protonation, charge and metal/spin state), or a validated binding/selectivity calculation for the expanded panel. No new CYP11A1/17A1/19A1 UMA calculation is claimed.

The generated command can launch Boltz separately after reviewing the inputs and installing its runtime/weights. Generation itself never launches a GPU job or transmits sequences to an MSA service. Files default to `msa: empty`, a lower-accuracy single-sequence baseline. Opt into a public MSA server only deliberately, or supply local MSAs for private sequences. The downloaded references are context; the exported Boltz files currently co-fold from sequence and do not apply a structural template.

Affinity prediction is deliberately **disabled** in these new inputs: the [Boltz documentation](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md) warns that its affinity output is unreliable with cofactor-containing targets. A heme-containing pose also does not declare the charge/spin state needed by [UMA's OMol task](https://fair-chem.github.io/core/uma.html). After pose and chemistry review, use **Upload UMA pockets** to evaluate a complete prepared batch.

## Interpreting energy and fold preference

For the original matched ligand/water exchange protocol, `delta = exchange(B2) - exchange(B1)`:

- Negative: **UMA exchange favors CYP11B2** in this calculation.
- Positive: **UMA exchange favors CYP11B1** in this calculation.
- Exactly zero: no difference in this descriptor; not proof of equal binding affinity.

The UI reports the direction and energy gap alongside an **exploratory fold preference** explicitly labeled **Boltzmann energy proxy · 298.15 K · not binding selectivity**. JSON exports preserve `fold_selectivity: null` and put the mathematical proxy in a separate `energy_fold_proxy` object. Failed, synthetic, nonfinite, incomplete, inconsistent or non-exchange results receive no proxy.

The displayed proxy is `exp(abs(delta_eV)/(kB_eV_per_K * T))`. It transforms the matched exchange-energy difference into a hypothetical ratio of energy weights. It is **not** a calibrated predictor of affinity, population, confidence, safety or experimental selectivity. The [Boltzmann constant](https://physics.nist.gov/cuu/Constants/Table/allascii.txt) is obtained from the exact SI constants in eV/K. Temperature is an explicit assumed scale (298.15 K by default); no thermal sampling was run.

The calculation stays in log space for large values, with approximately three significant figures displayed in scientific notation. At or above 10^6 the UI adds an extreme/unvalidated-magnitude warning; that is a display warning, **not a selectivity acceptance threshold**. For example, the previously saved R-fadrozole frozen-coordinate difference of −9.584489 eV maps mathematically to approximately `1.03 × 10^162`. Such an enormous proxy is not evidence of enormous biological selectivity. We do not clip it into an attractive confidence percentage or apply the assay's 10× threshold to it.

For an actual standard binding free-energy difference, the association-constant ratio would be `Ka(B2)/Ka(B1) = exp(-(Gbind(B2) - Gbind(B1))/(R*T))` in consistent molar units. This follows the [IUPAC equilibrium relation](https://goldbook.iupac.org/terms/view/S05915). Our frozen-coordinate UMA exchange **potential energies are not those binding free energies**. The exploratory proxy does not provide the missing solvent, entropy or thermodynamic sampling contributions. Binding fold selectivity remains **not determined**; experimental cross-checks alone would not make this mathematical conversion thermodynamically valid.

The **Explore assay examples** workspace shows fold preference from existing paired experimental endpoints, including the inverse ratio when B1 is favored. IC50 and Ki ratios remain separately labeled; they are not interchangeable with each other or with a predicted thermodynamic affinity ratio. Generic prepared-pocket total energies cannot rank different proteins and deliberately have no preference label.
