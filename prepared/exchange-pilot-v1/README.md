# Provisional capped-pocket exchange pilot v1

Inputs are `manifest.json`; initial checks are `preparation_audit.json`. Reproduction script: `scripts/prepare_exchange_pilot.py`. The manifest additionally records ligand covalent-distance/chirality guards and bound-water O-H guards. The run snapshots the complete manifest.

This rebuild uses mapped whole-domain preparations, selected complete residues 110,113,116,130,231,310,313-316,318,378-383,450,487-488, and full heme. Cut peptide N-C bonds receive neutral H caps along the removed bond direction (N-H 1.01 A; C-H 1.09 A). Backbone N/CA/C/O and cap H positions are fixed; other atoms relax. It is an isolated cluster without retained crystallographic waters, solvent or embedding. This is a new 450-atom model, not the old 462-atom numerical cross-check.

Selected residue identities match between enzymes; the pilot probes local geometry differences and excludes sequence/environment differences outside the selected pocket. Source preparation protonation is inherited; caps add no formal charge. The explicit charge ledger gives -3 for both ligand/water states. All metal clusters assume ferric doublet, including water-bound states; this is a provisional shared spin convention, not an established spin ground state. Alternative protonation/spin/boundary/pose choices remain necessary sensitivity studies.

B1/S uses the experimental ligand heavy-atom pose. B2/S is a proper-rotation heme-aligned transfer of B1/S, with no stereochemical inversion and no docking validation. Replacement water oxygen is placed 2.2 A from Fe toward the removed ligand donor. Water bond lengths/angle come from the relaxed isolated-water reference; 72 rotations are sampled to choose H orientation with greatest minimum separation from non-Fe scaffold heavy atoms. Its hydrogens initially point away from Fe. Both water and ligand clusters share identical scaffold and fixed atom positions within each enzyme.

Provisional geometry acceptance bounds are Fe-donor 1.8-2.8 A and Fe-S 2.0-2.9 A, set before energies. Ligand bonds must remain between 0.85 and 1.85 A and chiral volume must preserve sign. Bound water O-H distances must remain 0.7-1.3 A. These engineering checks do not validate chemical accuracy.

Use UMA v1.1 OMol and ASE BFGS, 0.02 eV/A force tolerance, 0.05 A maximum step, at most 400 steps. Failed convergence or geometry checks withhold the selectivity difference. The complete cycle is running in `runs/exchange-pilot-v1-01/`.
