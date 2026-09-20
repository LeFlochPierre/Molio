"""ASE BFGS using the existing physical-energy backend contract."""
import copy
import math
from .core import checked_evaluate, require


def relax_bfgs(backend, atoms, state, fixed_ids, protocol, output):
    from ase import Atoms
    from ase.calculators.calculator import Calculator, all_changes
    from ase.constraints import FixAtoms
    from ase.optimize import BFGS
    from .workflow import save
    class Adapter(Calculator):
        implemented_properties = ['energy', 'forces']
        def calculate(self, molecule=None, properties=None, system_changes=all_changes):
            import numpy as np
            super().calculate(molecule, properties, system_changes)
            current=copy.deepcopy(atoms)
            for a,p in zip(current,self.atoms.positions.tolist()):a['position']=p
            energy,forces=checked_evaluate(backend,current,state)
            self.results={'energy':energy,'forces':np.array(forces)}
    molecule=Atoms(symbols=[a['element'] for a in atoms],positions=[a['position'] for a in atoms],pbc=False)
    fixed=[i for i,a in enumerate(atoms) if a['id'] in fixed_ids]
    free=[i for i in range(len(atoms)) if i not in fixed]
    require(bool(free),'No movable atoms')
    molecule.set_constraint(FixAtoms(indices=fixed));molecule.calc=Adapter()
    optimizer=BFGS(molecule,maxstep=protocol['max_step_A'],logfile=str(output/'optimization.log'),trajectory=str(output/'optimization.traj'))
    history=[]
    def record():
        forces=molecule.get_forces();fmax=max(math.sqrt(sum(x*x for x in forces[i])) for i in free)
        history.append({'step':optimizer.nsteps,'energy_eV':float(molecule.get_potential_energy()),'free_fmax_eV_A':fmax})
        save(output/'progress.json',history[-1])
    optimizer.attach(record,interval=1)
    converged=bool(optimizer.run(fmax=protocol['force_tolerance_eV_A'],steps=protocol['max_steps']))
    final=copy.deepcopy(atoms)
    for a,p in zip(final,molecule.positions.tolist()):a['position']=p
    return {'atoms':final,'energy_eV':float(molecule.get_potential_energy()),'converged':converged,'history':history,'optimizer':'ASE BFGS'}
