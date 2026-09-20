# Historical MLIP setup notes

For the current reproducible setup, use [Getting started](GETTING_STARTED.md).
The notes below preserve the initial environment bring-up, including early
missing-checkpoint failures. They are not the current project status: real
UMA demo runs have subsequently completed and are included with the video.

The UMA adapter is implemented and the CPU dependencies are installed in `.venv-mlip`.
The model weights are **not downloaded**: Hugging Face denied access to the gated UMA repository.
No real UMA energy has been calculated. Sixteen tests pass in the MLIP environment, including actual ASE integration with an analytic test calculator. Those tests do not validate pretrained UMA predictions.

## What is ready

- Python 3.12 environment, FAIR Chemistry 2.22.0, CPU PyTorch 2.13.0, ASE.
- Local checkpoint loading; the model stays in memory across energy/force evaluations.
- Explicit OMol charge and multiplicity mapping, electron-count parity check, finite coordinates, atom budget.
- SHA-256 checkpoint provenance, package versions, device and inference settings in results.
- CPU and GPU configs using the same checkpoint and physical-energy convention.
- Water smoke test with one energy finite-difference check against a predicted force.
- Real prepared-system runs use the same workflow, comparison checks and reporting as before.

## The one account step needed

1. Open https://huggingface.co/facebook/UMA in your browser and obtain access under its terms.
2. On this machine, from the project directory, authenticate interactively:

```bash
.venv-mlip/bin/hf auth login
```

Enter your token only in the terminal prompt. Do not put it in chat, configuration files or source control.

Then download the small checkpoint:

```bash
.venv-mlip/bin/python -m cyp_pipeline.mlip download
```

The checkpoint and provenance sidecar are written to `models/`. The downloader also maintains a project-local cache; allow disk space for both the cached file and the copied checkpoint. A local checkpoint already supplied by the team can instead be referenced in a copied backend config. Load only a checkpoint from a trusted source. If `checkpoint_sha256` is supplied in the config, the adapter verifies it before loading.

## Run a small real-model check on CPU

```bash
.venv-mlip/bin/python -m cyp_pipeline.mlip preflight
.venv-mlip/bin/python -m cyp_pipeline.mlip smoke --out runs/uma-water-01
```

Read `runs/uma-water-01/result.json`. `passed` means finite energy/forces and agreement within 0.1 eV/Å for the tested coordinate. This tolerance is an integration threshold, not chemical accuracy. It is a water test, not a heme or selectivity benchmark. The check evaluates three water geometries and records runtime. A failed test still saves a result artifact. Use a new output directory each time.

The earlier attempt is in `runs/uma-cpu-smoke-01/result.json`; it records the missing-checkpoint failure, not a computed energy.

## Run a reviewed CYP complex

```bash
.venv-mlip/bin/python -m cyp_pipeline validate prepared/system.json
.venv-mlip/bin/python -m cyp_pipeline run prepared/system.json \
  --backend configs/uma-cpu.json --out runs/cyp-cpu-01
```

`prepared/system.json` is a path for your future reviewed input, not an existing prepared file. Follow `docs/PREPARATION.md`. The CLI validates preparation before loading the model. CPU config limits systems to 256 atoms to avoid unexpectedly large jobs; this is an operational limit, not a recommended cluster boundary. Do not cut chemistry to fit it. Set an appropriate budget after inspecting the preparation and available compute.

Raw local-checkpoint energies are used consistently for both identical-fragment terms. The adapter does not download optional isolated-atom reference-energy tables or apply formation-energy corrections. Do not compare these absolute energies to outputs using different reference conventions.

## Move to the GPU instance later

Copy the source, configs, prepared inputs and (if available) trusted checkpoint/provenance files. Recreate the Python environment there; do not copy `.venv-mlip` between machines.

```bash
nvidia-smi
bash scripts/setup_mlip.sh cuda
.venv-mlip/bin/python -m cyp_pipeline.mlip preflight --backend configs/uma-gpu.json
.venv-mlip/bin/python -m cyp_pipeline.mlip smoke \
  --backend configs/uma-gpu.json --out runs/uma-gpu-water-01
.venv-mlip/bin/python -m cyp_pipeline run prepared/system.json \
  --backend configs/uma-gpu.json --out runs/cyp-gpu-01
```

GPU setup selects PyTorch for the available driver. The adapter refuses a silent CPU fallback when CUDA was requested. The 5,000-atom GPU cap is a job limit, not a promise the system fits in GPU memory. Profile the first reviewed cluster before expanding. Use a job timeout for long runs; the in-process adapter does not enforce a wall-clock limit.

## Recreate the CPU environment

```bash
bash scripts/setup_mlip.sh cpu
```

The script pins FAIR Chemistry and writes an installed-package inventory. To reproduce the recorded CPU package versions in an existing Python 3.12 virtual environment:

```bash
uv pip install --python .venv-mlip/bin/python --torch-backend cpu -r requirements-mlip-cpu.lock.txt
```

The lock is a version inventory, not a hash-verified wheel lock. The independent core remains runnable using system Python without optional ML packages.

## Verified upstream interfaces

- [FAIR Chemistry installation](https://github.com/facebookresearch/fairchem/blob/main/docs/core/install.md)
- [UMA model access and checkpoint](https://huggingface.co/facebook/UMA)
- [ASE calculator: charge and spin metadata](https://github.com/facebookresearch/fairchem/blob/main/src/fairchem/core/calculate/ase_calculator.py)

The installed 2.22.0 package imports successfully, and its local loading API was checked directly. `batch` inference settings avoid assumptions of fixed atom composition/state while switching between cluster and fragment. Compatibility with iron-containing CYP clusters must still be tested; a water smoke test cannot establish that.
