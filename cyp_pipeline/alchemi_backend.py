"""Native ALCHEMI UMA execution, preserving the existing UMA input checks."""
from importlib.metadata import version
from pathlib import Path

from .core import require
from .mlip import UMABackend, configure_cache, file_hash, package_versions


class AlchemiUMABackend(UMABackend):
    """Use the validated ASE boundary with ALCHEMI AtomicData/UMAWrapper inside."""

    def __init__(self, config):
        require(config.get('engine') == 'alchemi', 'Explicit alchemi engine required')
        require(config.get('device') in ('cpu', 'cuda'), 'UMA device must be cpu or cuda')
        require(config.get('task', 'omol') == 'omol', 'CYP requires the OMol task')
        require(config.get('inference_settings', 'batch') == 'batch',
                'Changing compositions require batch inference settings')
        checkpoint = Path(config['checkpoint'])
        require(checkpoint.is_file(), 'UMA checkpoint is missing')
        actual_hash = file_hash(checkpoint)
        require(bool(config.get('checkpoint_sha256')), 'Pinned checkpoint SHA256 required')
        require(actual_hash == config['checkpoint_sha256'], 'Checkpoint SHA-256 mismatch')
        self.max_atoms = config.get('max_atoms', 1000)
        threads = config.get('threads', 4)
        require(type(self.max_atoms) is int and self.max_atoms > 0, 'Invalid atom budget')
        require(type(threads) is int and threads > 0, 'Invalid thread budget')
        configure_cache()
        import torch
        from ase.calculators.calculator import Calculator, all_changes
        from nvalchemi.data import AtomicData, Batch
        from nvalchemi.models.uma import UMAWrapper

        device = torch.device(config['device'])
        require(device.type != 'cuda' or torch.cuda.is_available(), 'CUDA unavailable')
        torch.set_num_threads(threads)
        class ExchangeUMAWrapper(UMAWrapper):
            def adapt_output(self, raw, data=None):
                result = super().adapt_output(raw, data=data)
                # ALCHEMI 0.2.0 casts the reference-restored fp64 energy to
                # fp32. Cluster totals are ~hundreds of keV; that rounding
                # corrupts small exchange differences. Keep fairchem's fp64
                # energy while using the native wrapper for graph/inference.
                if 'energy' in result:
                    result['energy'] = raw['energy'].reshape(-1, 1)
                return result

        model = ExchangeUMAWrapper.from_checkpoint(str(checkpoint), task_name='omol',
                                                   device=device, inference_settings='batch', train=False)

        class AlchemiCalculator(Calculator):
            implemented_properties = ['energy', 'forces']

            def calculate(self, atoms=None, properties=None, system_changes=all_changes):
                super().calculate(atoms, properties, system_changes)
                data = AtomicData(
                    positions=torch.tensor(atoms.positions, dtype=torch.float32, device=device),
                    atomic_numbers=torch.tensor(atoms.numbers, dtype=torch.long, device=device),
                    charge=torch.tensor([[atoms.info['charge']]], dtype=torch.float32, device=device),
                    spin=torch.tensor([[atoms.info['spin']]], dtype=torch.float32, device=device),
                )
                batch = Batch.from_data_list([data], device=device)
                # UMAWrapper builds the fairchem graph on the fly. Autograd must
                # remain enabled because this checkpoint has conservative forces.
                with torch.enable_grad():
                    result = model(batch)
                self.results = {
                    'energy': float(result['energy'].detach().cpu().reshape(-1)[0]),
                    'forces': result['forces'].detach().cpu().numpy(),
                }

        self.calculator = AlchemiCalculator()
        self.metadata = {
            'name': config.get('model_name', 'uma-s-1p1'), 'version': version('fairchem-core'),
            'engine': 'alchemi', 'alchemi_version': version('nvalchemi-toolkit'),
            'packages': package_versions(), 'checkpoint_sha256': actual_hash,
            'task': 'omol', 'inference_settings': 'batch', 'device': device.type,
            'threads': threads, 'synthetic': False, 'physical_energy_only': True,
            'energy_output_precision': 'Preserve fairchem fp64 reference-restored totals for exchange subtraction',
            'state_handling': 'Explicit AtomicData charge and spin multiplicity; inherited electron parity validation',
            'energy_convention': 'Raw UMA OMol total energies in eV; forces in eV/angstrom',
        }
