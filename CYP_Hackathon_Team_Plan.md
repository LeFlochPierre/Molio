# CYP selectivity hackathon — team brief and planning request

## Instructions for Codex in VS Code

Read this brief, inspect our current environment using read-only commands, and propose a concrete implementation plan. **Do not start coding, installing packages, downloading models, provisioning services, or launching calculations yet.** Present your plan in chat and wait for our instruction to begin.

Use our resources and team structure below. Ask only the missing questions that materially affect the plan. Treat scientific assumptions as hypotheses to test, not conclusions to reproduce.

## Our team and resources

- We are a team of five and can divide the work into coordinated workstreams.
- We have access to good GPU compute. Verify the actual hardware, memory, availability, and budget before selecting workloads; do not assume this particular instance already has a GPU attached.
- We have access to BioNeMo.
- We have access to the Rosalind benchmark through OpenAI. Verify its actual tasks, data, interface, and scoring before deciding its role. Do not invent capabilities or assume it validates CYP selectivity.
- The hackathon deadline and remaining hours need to be confirmed.

## Project objective

Build a reproducible, agent-assisted workflow to investigate whether machine-learned interatomic potentials (MLIPs) add useful information when predicting inhibitor selectivity between CYP11B1 and CYP11B2.

Our central question is:

> Can fast ML-based atomistic energies add useful selectivity information beyond simple pocket geometry for CYP11B1/CYP11B2 inhibitors?

The hackathon deliverable is a working feasibility study and demonstration. We should not claim a generally validated lead-optimization predictor from a handful of compounds.

## Minimum scientific experiment

Start with R-fadrozole and S-fadrozole, each evaluated against CYP11B1 and CYP11B2. This gives four complexes and two ligand-wise isoform-preference predictions.

Experimental starting structures to verify:

- PDB 6M7X: CYP11B1 with S-fadrozole.
- PDB 4FDH: CYP11B2 with R-fadrozole.

The opposite enantiomer in each protein requires a modeled pose unless another suitable experimental structure is identified. Label experimental and modeled poses explicitly.

Osilodrostat and baxdrostat are stretch goals after the core workflow works. Baxdrostat is a retrospective holdout because its expected selectivity is already known; freeze the protocol before evaluating it rather than calling it a genuinely blind prediction.

## What we should do first

Spend the first team session agreeing on the experiment, the data contract, and the decision criteria. At the same time, inspect the available compute and services.

Agree on:

1. The minimum four-complex scope and the two preference predictions.
2. A primary exploratory descriptor, including its exact energy definition and sign convention.
3. A simple structural baseline.
4. Success and failure criteria fixed before seeing results.
5. Shared system identifiers, input metadata, output schema, and artifact locations.
6. What BioNeMo and Rosalind can actually contribute under the hackathon constraints.

The first shared milestone is **one reviewed complex, one successful calculation, one inspectable result**. Do not build separate pipelines that only meet at the end.

## Divide the work across five people

| Owner | Responsibility | First deliverable |
|---|---|---|
| 1 — Scientific benchmark | Audit structures and experimental selectivity evidence; define comparisons and labels | A sourced table of ligands, structures, assays, conditions, uncertainties, and missing information |
| 2 — Structure preparation | Inspect structures; define clusters, caps, protonation, charges, spins, and constraints | One reviewed, calculation-ready complex with preparation provenance |
| 3 — MLIP and compute | Select and establish a backend, GPU execution, logging, and reference checks | One successful energy/force calculation with measured runtime |
| 4 — Workflow and agent | Define reproducible orchestration, supported tool connections, and failure handling | A workflow that accepts a prepared system and returns traceable outputs |
| 5 — Evaluation and demonstration | Define baselines, sensitivity checks, result displays, and presentation | An evaluation specification and a simple structure/results interface |

These are ownership areas, not isolated projects. Owners 2 and 3 must review preparation and model compatibility together. Owner 1 supplies the evidence needed by owner 5. Owner 4 integrates an agreed workflow rather than independently choosing chemical assumptions.

Agree on file/module ownership before implementation to reduce merge conflicts. Use a common repository and review shared configuration changes together.

## Stage 1 — One complete computational path

Start with one experimentally observed fadrozole complex:

**Retrieve structure → inspect chemistry → prepare system → review preparation → calculate energy and forces → relax under defined constraints → inspect geometry → save results.**

This stage must answer:

- Does the selected model load and run on the available hardware?
- Does the system fit in memory?
- Are energies and forces finite, and are local perturbations and geometries chemically plausible?
- Does constrained relaxation converge without corrupting heme coordination?
- How long does each calculation take?
- Are the inputs, assumptions, model version, constraints, and results reproducible?

A successful model invocation is an engineering milestone, not proof of scientific accuracy.

## Stage 2 — Expand to the four-complex experiment

After the first complete path works, process both experimental complexes and prepare the two crossed combinations with a consistent pose-generation procedure.

Inspect ligand stereochemistry, donor atom identity, heme geometry, axial cysteine, missing atoms, alternate conformations, and residue mapping. Retain alternative plausible modeled poses where feasible.

Use the same preparation rules across comparisons. Do not hand-pick a different favorable setup for each known answer.

## Stage 3 — Define and calculate the descriptor

The initial concept includes two different quantities:

1. Deformation energy under pocket-imposed geometry.
2. Fixed-geometry interaction energy, E(complex) − E(pocket) − E(ligand).

Choose one primary descriptor before implementation and report others separately. A proposed first hypothesis is:

```text
E_deform = E_fragment(pocket-imposed geometry)
           - E_fragment(relaxed reference geometry)
```

A candidate fragment is ligand + heme + axial thiolate. Both energy terms must use identical atoms, charge, electronic-state convention, and model. Specify a chemically meaningful reference coordination state. Do not silently allow dissociation or a spin-state change to redefine the reference.

Explain how the pocket imposes the geometry and how the fragment energy is evaluated afterwards. Exclude artificial restraint penalties from the physical score. Never subtract a small free-fragment energy from a larger pocket-cluster energy.

Deformation and interaction energies are exploratory descriptors, not binding free energies. Solvation, entropy, protein reorganization, and coordination-state changes can alter selectivity.

## Preparation and interpretation requirements

- Preserve the chemical groups that create the pocket's steric environment. Specify exact capping bonds and fixed boundary atoms.
- Review protonation, total charge, oxidation state, and spin multiplicity explicitly; do not guess them from residue names alone.
- A neutral thiol and an anionic thiolate are not interchangeable.
- Do not claim that identical active-site residue identities imply identical geometry.
- Enantiomers control for formula and simple physicochemical properties, but a chiral pocket can distinguish them through shape.
- OMol25-based MLIPs approximate DFT reference data; they do not automatically solve multireference electronic-structure problems.
- Agreement between models sharing training data is useful but not independent validation.
- Crystal occupancy is structural evidence, not quantitative experimental selectivity ground truth.
- Record assay species, conditions, and endpoints. Do not silently combine IC50, Ki, Kd, or cellular effects.

## Stage 4 — Challenge the result

Build the baseline alongside the MLIP workflow so it is ready when results arrive. Candidate baseline descriptors include clashes, coordination geometry, and ligand-only strain, with definitions fixed in advance.

Ask:

1. Does the MLIP add information beyond the baseline?
2. Does the preference survive plausible alternative poses?
3. Does it survive reasonable changes in restraints or cluster boundaries?
4. Does relaxation preserve valid chemistry?
5. Do selected quantum reference calculations support the relevant energy differences, if feasible?

Budget reference calculations explicitly and assess their feasibility. Good GPU availability does not guarantee an appropriate quantum-chemistry backend, license, or reference accuracy.

Report **unresolved** when preparation choices reverse the result, chemistry becomes invalid, or uncertainty is comparable to the signal. Baselines do not need to fail. Two correct preferences are an encouraging pilot, not statistical validation.

Prioritize stronger validation over adding more compounds. Add a second MLIP or a stretch ligand only after the core calculation is reproducible and interpretable.

## Stage 5 — Integrate the demo and agent evaluation

The demonstration should allow someone to select a ligand–isoform pair, inspect its preparation, launch or replay a clearly identified calculation, and inspect:

- Experimental versus modeled pose provenance.
- Before/after geometry and coordination measurements.
- The primary descriptor and its sign convention.
- Baseline comparison.
- Runtime, convergence, and sensitivity checks.
- Limitations and unresolved cases.

Use BioNeMo for the model or service that is actually available and suitable. Give Rosalind a role only after checking its documented scope. Scientific validation and agent evaluation are separate questions.

The agent can coordinate validated steps, submit jobs, check outputs, and produce evidence-linked reports. Keep chemical rules explicit and reviewable. Record tool failures, human interventions, reproducibility, runtime, costs, and token use where available.

Keep the scientific calculation independently runnable so a service integration problem does not stop the entire experiment.

## Remote environment context

Our laptop uses Windows. Brev runs inside WSL Ubuntu-22.04. The instance alias is `sixies`, and the remote folder is `/home/ubuntu/HackProject`.

Previously working PowerShell commands:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc 'source ~/.bashrc && brev open sixies code'
wsl -d Ubuntu-22.04 -- bash -lc 'source ~/.bashrc && brev shell sixies'
```

After entering the remote shell:

```bash
cd /home/ubuntu/HackProject
hostname
pwd
```

Important: a previous agent/terminal context reported `C:\Users\plefl` even though VS Code displayed an SSH project. Verify the agent's actual command execution context. Opening an SSH terminal does not automatically relocate the agent backend.

Do not print API keys, inspect authentication secrets, or disable SSH host verification. Verify access using non-secret status information.

A small starter was created in a separate Windows desktop session but has not been confirmed on the remote instance. Inspect actual files before assuming any code exists. No scientific calculations or selectivity results have been confirmed.

## What Codex should return now

After read-only inspection, provide a plan covering:

1. Verified machine, working directory, hardware, software, and access; distinguish facts from unknowns.
2. The first shared milestone and an ordered sequence of tasks.
3. Five workstreams with dependencies, ownership, and integration checkpoints.
4. Proposed repository layout and shared input/output schema.
5. A recommended model backend and precise primary descriptor, with preparation-review requirements.
6. Baseline, validation, and failure criteria.
7. A schedule adjusted to our actual remaining hackathon time, with stretch goals and a fallback.
8. A few essential questions, including deadline, available chemistry expertise, compute budget, and mandatory sponsor technology.

**Stop after the plan. Wait for our instruction before implementation.**

## References to verify during planning

- Structural study: https://pmc.ncbi.nlm.nih.gov/articles/PMC6333875/
- CYP11B1 starting structure: https://www.rcsb.org/structure/6M7X
- CYP11B2 starting structure: https://www.rcsb.org/structure/4FDH
- OMol25: https://fair-chem.github.io/omol25/
- MACE: https://github.com/ACEsuit/mace
- FAIR Chemistry: https://github.com/facebookresearch/fairchem
