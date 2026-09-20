"""Backend contract: physical energies (eV), forces (eV/Å), no restraint penalties."""
import importlib
import json
import subprocess
from .core import require


class HarmonicDemo:
    """Synthetic fixture ONLY. Not a chemical potential or a selectivity model."""
    metadata = {'name': 'synthetic-harmonic', 'version': '1', 'synthetic': True}

    def evaluate(self, atoms, state):
        delta = [[x-y for x, y in zip(a['position'], a['demo_target'])] for a in atoms]
        return sum(x*x/2 for d in delta for x in d), [[-x for x in d] for d in delta]


class CommandBackend:
    """Launch an explicitly configured executable, without a shell, for each call.

    stdin: JSON {atoms, state, units}; stdout: JSON {energy_eV, forces_eV_A}.
    The worker owns model loading, device selection and electronic-state handling.
    """
    def __init__(self, config):
        self.command = config['command']
        require(isinstance(self.command, list) and self.command and
                all(isinstance(x, str) for x in self.command), 'command must be an argv list')
        self.timeout = config.get('timeout_seconds', 120)
        require(isinstance(self.timeout, (int, float)) and 0 < self.timeout <= 86400,
                'Invalid backend timeout')
        self.metadata = config['metadata']
        for key in ('name', 'version', 'checkpoint_sha256', 'state_handling', 'supported_elements'):
            require(bool(self.metadata.get(key)), f'Backend metadata missing {key}')
        require(self.metadata.get('physical_energy_only') is True, 'Physical energy declaration required')
        require(self.metadata.get('synthetic') is False, 'Real backend must declare synthetic=false')

    def evaluate(self, atoms, state):
        require({a['element'] for a in atoms} <= set(self.metadata['supported_elements']),
                'Model does not support all system elements')
        request = {'atoms': atoms, 'state': state, 'units': {'energy': 'eV', 'length': 'angstrom'}}
        result = subprocess.run(self.command, input=json.dumps(request), text=True,
                                capture_output=True, timeout=self.timeout, check=False)
        # Avoid propagating environment-dependent stderr that could contain credentials.
        require(result.returncode == 0, f'Backend exited {result.returncode}; check worker locally')
        output = json.loads(result.stdout)
        return output['energy_eV'], output['forces_eV_A']


class FactoryBackend:
    """Load local module:function returning an evaluate(atoms, state) backend.

    This keeps large models resident. The factory receives the entire config and
    must explicitly map charge and multiplicity to its model's documented API.
    """
    def __init__(self, config):
        # Reuse metadata validation; factory config includes a placeholder argv.
        checked = CommandBackend({**config, 'command': ['unused']})
        self.metadata = checked.metadata
        module, name = config['factory'].split(':', 1)
        self.worker = getattr(importlib.import_module(module), name)(config)

    def evaluate(self, atoms, state):
        require({a['element'] for a in atoms} <= set(self.metadata['supported_elements']),
                'Model does not support all system elements')
        return self.worker.evaluate(atoms, state)


def load_backend(config):
    kind = config.get('kind')
    if kind == 'uma':
        from .mlip import UMABackend
        return UMABackend(config)
    require(kind in ('command', 'factory'), 'Unknown backend kind')
    return CommandBackend(config) if kind == 'command' else FactoryBackend(config)
