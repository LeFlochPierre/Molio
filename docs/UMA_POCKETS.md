# Run prepared pockets beyond the original CYP pair

The new **Run prepared pockets · UMA** mode can evaluate pockets with arbitrary
protein identifiers. It accepts up to eight prepared systems per batch, with
at most 1,000 atoms each (or a smaller limit from the backend config).

This is a **single-point total-energy / force calculation**, not the four-term
CYP ligand–water exchange cycle. It does not calculate binding affinity, rank
unrelated proteins or establish selectivity. The existing **Run CYP pair · UMA**
mode remains available for that separate exchange descriptor.

## What is still missing for the additional CYP proteins?

The repository has no calculation-ready CYP11A1/CYP17A1/CYP19A1 drug pockets.
The catalog lists reasons to investigate them, not coordinates or poses.
For each candidate and protein we still need:

1. The appropriate 3D protein structure and drug pose, with source provenance.
2. Ligand identity/stereochemistry and protonation states; all hydrogens.
3. A chemically complete local pocket, with documented cut bonds/caps,
   relevant cofactors, waters and metal coordination.
4. Explicit total charge and spin multiplicity, with rationale.
5. Geometry checks and a review declaration (or an explicitly provisional run).
6. A matched comparison protocol and experimental benchmarking before making
   any binding/selectivity claim. Independent pocket totals are insufficient.

The runner does not guess these choices, generate a drug pose from a sequence,
automatically protonate a raw PDB, or validate a model's applicability to every
protein. A GPU accelerates computation; it does not supply missing preparation.

## Try the real prepared example

Start the usual Sentinel server with `--enable-uma` and the appropriate
`--uma-python` / `--backend` settings. Default backend is CPU:

```bash
cd /home/ubuntu/HackProject
python3 -m cyp_pipeline.sentinel_server \
  --site runs/selectivity-sentinel-demo-v3/demo.html \
  --port 8000 --bind 0.0.0.0 --enable-uma
```

On a new machine where the runtime was installed into `.venv-mlip`, add
`--uma-python /home/ubuntu/HackProject/.venv-mlip/bin/python`.
For configured GPU execution add `--backend configs/uma-s-1p1-a100.json`.

After restarting the server and hard-refreshing `/demo.html`:

1. Select **Run prepared pockets · UMA**.
2. Click **Try prepared example**.
3. Check the two pocket summaries and their uploaded coordinates in 3D.
4. Acknowledge the provisional input declaration.
5. Click **Run UMA · 2 pockets**.

The example copies the existing R-fadrozole B1/B2 cluster-ligand inputs without
altering atoms, charge/spin, geometry bounds or review declarations. It is not
new experimental evidence or a preparation for the three additional proteins.
The model calculates fresh energies and forces; the result JSON retains the
input hash, backend/checkpoint metadata and provisional status. Per-system
forces and the complete input snapshot are saved in the job directory.

## Supply another protein

Use `examples/uma-pocket-batch.template.json` or **Template ↓** in the app.
The template is intentionally incomplete and must fail checks until filled.
Each system requires:

- A unique simple `id`, a `protein_id` label, and a ligand label.
- `source` and `preparation` statements documenting the actual input chemistry.
- Explicit atoms (`id`, chemical `element`, `position` in Å).
- `ligand_atom_ids`: a proper, nonempty subset of those atoms.
- `state`: integer `charge`, positive integer `multiplicity`, and a convention.
- `review`: either approval with a reviewer or `provisional: true`.
- Explicit `coordination`, `covalent_bounds` and `chirality_checks` arrays.
  Empty arrays are allowed when not applicable; missing stereo checks are
  reported, and emptiness does not establish chemical correctness.

Checks reject invalid elements/coordinates, duplicate IDs, absent hydrogens,
coincident atoms, impossible electron-count/spin parity, failed supplied
geometry/chirality bounds, oversize inputs and undeclared preparation.
These are input checks, **not** independent validation of the claimed protein
identity, chemical completeness, oxidation state, or model domain.

Coordinates are immutable during a run. Protein labels do not authorize reuse
of other proteins' chemistry. Renaming B1 coordinates to another protein is
not a valid preparation and must never be reported as such.

## CLI

Export the existing example to a new file:

```bash
python3 -m cyp_pipeline.uma_batch export-exchange \
  prepared/exchange-R-pilot-v1/manifest.json \
  --out runs/my-prepared-pockets.json
python3 -m cyp_pipeline.uma_batch check runs/my-prepared-pockets.json
```

Run with an installed UMA interpreter (use a new output directory):

```bash
.venv-mlip/bin/python -m cyp_pipeline.uma_batch run \
  runs/my-prepared-pockets.json \
  --backend configs/uma-s-1p1-a100.json \
  --out runs/my-pocket-energies --allow-provisional
```

Do not add `--allow-provisional` to hide a failed review. It explicitly records
that the prepared chemistry is an assumption-based research input.

## API and operating limits

- `GET /api/prepared-example`: the existing R-fadrozole pocket inputs.
- `POST /api/prepared-check`: batch JSON; no model loading or execution.
- `POST /api/prepared-jobs`: `{"batch": ..., "confirm_provisional": true}`.
- `GET /api/jobs/<id>`: actual progress and results, shared with preset jobs.

Execution requires `--enable-uma`; at most one model job runs per server.
Inputs are limited to 4 MiB and snapshotted under server-generated IDs. Uploads
cannot choose model, command or filesystem paths. Failed systems remain failed
with no usable energy. Other successfully evaluated systems are preserved, but
the batch is marked failed if any system failed. Polling JSON writes are atomic.
The demonstration server is intended for a controlled local/Brev tunnel, not
as a public multi-user compute service.

## Verification

```bash
python3 -m unittest tests.test_uma_batch -v
# In an optional Playwright environment:
python scripts/check_sentinel_browser.py
# Explicitly starts a real two-pocket CPU job:
python scripts/check_sentinel_browser.py --live-batch
```

The 3D view uses actual uploaded heavy-atom coordinates after input checks;
all atoms, including hydrogens, remain in the calculation. Visual bonds are
distance-based display aids, not inferred/validated chemical bond orders.
