# Model integration

The UMA adapter and CPU dependencies are installed; model weights remain unavailable because Hugging Face access was denied. See [MLIP quickstart](MLIP_QUICKSTART.md). No model is chemically validated for this project. The machine currently has no working NVIDIA driver. A suitable candidate must support all prepared elements (including Fe), charge and electronic state, molecular clusters, and the intended coordination chemistry. Confirm licensing, checkpoint access, memory, cost and training-domain limitations first. OMol25-trained potentials may be candidates for evaluation; their applicability here is unverified. The brief's OMol25 web link returned 404 during inspection.

## Command worker

Copy `configs/backend.example.json`; replace every placeholder with verified metadata. `command` is an argv list, executed without a shell. Each invocation receives one JSON object on stdin:

```json
{"atoms":[{"id":"a","element":"H","role":"cap","position":[0,0,0]}],"state":{"charge":0,"multiplicity":2,"convention":"documented mapping"},"units":{"energy":"eV","length":"angstrom"}}
```

Return only this JSON shape on stdout (model diagnostics go to stderr):

```json
{"energy_eV":-1.0,"forces_eV_A":[[0.0,0.0,0.0]]}
```

Preserve atom order; forces are negative Cartesian energy gradients. Return **physical model energy only**, without optimizer penalties. Both fragment evaluations must use identical model/checkpoint/state handling. A worker must reject unsupported states rather than ignoring charge/spin. Metadata is a reviewer declaration; the orchestrator cannot prove checkpoint identity or state support from an arbitrary executable.

The command adapter has a per-call timeout and finite-output checks. It starts a process each evaluation, so a large-model worker should call a persistent local service. Credentials belong in that worker's environment, never command arguments or committed config. Captured stderr is not copied to result artifacts.

## Resident factory

For efficient in-process loading, set `kind` to `factory`, replace `command` with `factory: "your_module:create_backend"`, and retain the same metadata. The local module must be importable in the Python environment running this pipeline:

```python
def create_backend(config):
    return YourBackend(config)

class YourBackend:
    def evaluate(self, atoms, state):
        # Convert atom list into the model's native representation.
        # Explicitly map state['charge'] and state['multiplicity'].
        # Return a float and list-of-list forces, in eV and eV/Å.
        ...
```

ASE calculators can be wrapped here after their installed version and charge/spin conventions are verified. Factory plugins execute trusted local Python code and have no per-call timeout; use a scheduler/job timeout for production GPU workloads. Restart the run with a new output directory after failures.

Validate a backend using finite differences of energies versus forces, known structures, state changes, small displacements, and element coverage before interpreting the pilot. No fairchem/MACE/BioNeMo API is guessed by this repository. Rosalind integration awaits a documented task/interface; agent performance would be evaluated separately from chemical accuracy.
