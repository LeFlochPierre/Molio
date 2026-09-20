# Run IsoForm on your own machine

## 1. Open the app without ML dependencies

Install Python 3.10+ and Git, then:

```bash
git clone https://github.com/LeFlochPierre/IsoForm.git
cd IsoForm
python3 -m cyp_pipeline.sentinel_server
```

Browse to **http://localhost:8000/demo.html**. This works without a GPU, model
weights or an account. Start with **Explore assay examples** or **Prepare more
targets**. The R/S paired views are supplied prepared coordinates, not new
predictions. Core input generation needs no ML installation; custom SMILES
export additionally requires RDKit syntax validation.

On Windows, replace `python3` with `python`. For remote development, forward
the server port and open it on your laptop. `xdg-open` on a headless remote
machine does not open your laptop's browser. The default binds only localhost.

## 2. Optional actual UMA execution (tested on Linux, Python 3.12)

Use Linux or WSL for the tested model workflow. Install `uv` if needed using
your normal Python/package-management process, then from the repository root:

```bash
bash scripts/setup_mlip.sh cpu
.venv-mlip/bin/hf auth login
```

First request access to [facebook/UMA](https://huggingface.co/facebook/UMA)
and accept its terms. Authenticate only through the local terminal prompt.
Never paste an access token into an issue, chat, tracked file or command line.

Download the **same checkpoint used by the demo**, not the downloader's newer
default model:

```bash
.venv-mlip/bin/python -m cyp_pipeline.mlip download \
  --filename checkpoints/uma-s-1p1.pt --out models/uma-s-1p1.pt

.venv-mlip/bin/python -m cyp_pipeline.mlip preflight \
  --backend configs/uma-s-1p1-cpu.json

.venv-mlip/bin/python -m cyp_pipeline.mlip smoke \
  --backend configs/uma-s-1p1-cpu.json --out runs/my-water-smoke

.venv-mlip/bin/python -m cyp_pipeline.sentinel_server \
  --enable-uma --backend configs/uma-s-1p1-cpu.json
```

Use a fresh output directory for each smoke test. `ready_to_load` checks runtime
and checkpoint presence; loading also verifies the configured SHA-256. A water
smoke test is an integration check, not chemical or selectivity validation.
Select **R-fadrozole → Compare pair · live UMA → Run UMA** in the app.

The CPU config limits the job to 1,000 atoms per component and four threads.
The supported preset computes eight frozen-coordinate energies. It is not a
relaxation, pose search, binding free-energy calculation or GPU requirement.
The setup pins fairchem-core 2.22.0 and records installed versions under
`runs/setup/`. The existing `requirements-mlip-cpu.lock.txt` is a historical
version inventory, not a hash-verified cross-platform wheel lock.

### GPU host

Verify your host's driver with `nvidia-smi`, then:

```bash
bash scripts/setup_mlip.sh cuda
.venv-mlip/bin/python -m cyp_pipeline.mlip preflight \
  --backend configs/uma-s-1p1-cuda.json
.venv-mlip/bin/python -m cyp_pipeline.sentinel_server \
  --enable-uma --backend configs/uma-s-1p1-cuda.json
```

Use the same `models/uma-s-1p1.pt` checkpoint. The adapter refuses a silent CPU
fallback when CUDA was requested. Do not copy virtual environments between
machines. Installations and model downloads require network access and disk
space; source-only demo serving does not.

### Existing model environment or checkpoint

Pass `--uma-python /path/to/environment/bin/python` explicitly, or set
`ISOFORM_UMA_PYTHON`. The server otherwise checks a git-ignored
`configs/runtime.local.json`, then `.venv-mlip`, then its own Python interpreter.
The virtual-environment executable is not resolved through its symlink.

Copy a portable config to `configs/my-backend.local.json`, change `checkpoint`
to your trusted local file, and pass `--backend configs/my-backend.local.json`.
Do not change or remove the hash to disguise a different model as UMA-s-1.1.
The original host's private config/interpreter settings are not published.

## Tests

```bash
python3 -m unittest discover -s tests
```

Optional NumPy/ASE/RDKit/gemmi tests may skip when dependencies are absent. Use
`python -m pip install -e '.[test]'` for the NumPy/ASE checks. Browser
checks additionally use Playwright:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[browser]'
python -m playwright install chromium
python scripts/check_sentinel_browser.py
python scripts/check_isoform_preview_races.py
```

On a minimal Linux machine, `python -m playwright install --with-deps chromium`
can also install required system libraries; that may need administrator
approval. CI uses this in its isolated runner. Default checks do not run UMA;
add `--live` deliberately and configure the model environment to exercise it.

## Video

The included [54-second MP4](../runs/isoform-video/powerpoint-demo-v2/IsoForm-demo-1080p.mp4)
plays without any model environment. To record a new real run:

```bash
python -m pip install -e '.[video]'
python -m playwright install chromium
python scripts/record_isoform_video.py
```

Install the optional video packages in your active environment; keep UMA in
`.venv-mlip` or select it with `ISOFORM_UMA_PYTHON`. See the
[recording guide](../scripts/video/README.md). Recording without `--preview`
launches one real CPU model job.

## Docker: no-GPU demo only

```bash
docker build -t isoform-demo .
docker run --rm -p 127.0.0.1:8000:8000 isoform-demo
```

Open the same browser URL. The image does not include model weights or ML
dependencies and does not enable UMA. Generated jobs/input bundles inside this
ephemeral container disappear when it is removed; use the source checkout if
you want persistent local research artifacts. The normal Python path above is
the primary tested setup.

## Security

The app runs arbitrary supported local calculations only when explicitly
enabled, validates uploaded pockets and uses allow-listed presets. It does
not supply login, multi-user isolation, rate limiting or TLS. Do not expose
an enabled model server directly to the public internet. Source publication
does not require publishing your running compute endpoint.
