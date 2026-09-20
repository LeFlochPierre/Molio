"""Real-checkpoint regression against the original ASE path, including a heme cluster."""
import json
from pathlib import Path
import sys
import numpy as np

from cyp_pipeline.mlip import UMABackend
from cyp_pipeline.alchemi_backend import AlchemiUMABackend

config = json.loads(Path(sys.argv[1]).read_text())
manifest = json.loads(Path('prepared/exchange-R-pilot-v1/manifest.json').read_text())
cases = {name: manifest['enzymes']['CYP11B1'][name]
         for name in ('free_water', 'cluster_ligand', 'free_ligand')}
reference = UMABackend(config)
expected = {name: reference.evaluate(row['atoms'], row['state']) for name, row in cases.items()}
del reference
import gc
gc.collect()
backend = AlchemiUMABackend(config)
rows = []
for name, row in cases.items():
    energy, forces = backend.evaluate(row['atoms'], row['state'])
    e, f = expected[name]
    ediff, fdiff = abs(energy - e), float(np.max(np.abs(np.array(forces) - f)))
    rows.append({'component': name, 'atoms': len(row['atoms']), 'state': row['state'],
                 'reference_energy_eV': e, 'alchemi_energy_eV': energy,
                 'absolute_energy_error_eV': ediff, 'max_force_error_eV_A': fdiff,
                 'passed': ediff <= 0.001 and fdiff <= 0.001})
result = {'passed': all(row['passed'] for row in rows), 'cases': rows,
          'tolerance': {'energy_eV': 0.001, 'force_eV_A': 0.001}, 'backend': backend.metadata}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['passed'] else 1)
