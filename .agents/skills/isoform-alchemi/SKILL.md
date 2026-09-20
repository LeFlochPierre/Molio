---
name: isoform-alchemi
description: Run the local IsoForm CYP11B1/CYP11B2 comparison through ALCHEMI and UMA s1.1, inspect job evidence, and propose follow-up analog hypotheses. Use for this project's selectivity demo and agent-driven screening.
---

Work from the HackProject directory. This is a custom companion skill to the
BioNeMo Agent Toolkit: the current coding agent supplies reasoning, and the
local IsoForm service supplies bounded simulation tools. There is no embedded
LLM service or automatic QSAR/generative model.

Use the `isoform_*` MCP tools when configured. The equivalent CLI is:

```bash
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools capabilities
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools plan '{"candidate_id":"r_fadrozole","target_id":"CYP11B2"}'
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools start r_fadrozole
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools status JOB_ID
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools compare JOB_ID_1 JOB_ID_2
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools suggest CYP11B2
```

1. Inspect capabilities and plan the requested candidates. Only the R- and
   S-fadrozole exchange presets are currently prepared. Baxdrostat and new
   analogs must first pass the project's structure, charge, spin and pocket
   preparation checks; a SMILES or name is not a scoreable pocket.
2. When running an authorized comparison, submit one preset, poll until it
   completes, inspect its result, then submit the next. Poll around every
   10–20 seconds while keeping the user informed. On a busy response, inspect
   jobs and wait; do not duplicate submissions after an uncertain timeout.
3. Compare only successful real jobs with matching protocols. Report job IDs,
   input hashes, checkpoint identity, energy difference and unresolved inputs.
   Negative delta (B2 minus B1) favors B2 in this potential-energy model.
4. Preserve the distinction between a frozen-coordinate exchange-energy
   descriptor and binding free energy or biological selectivity. The existing
   fold display is only an uncalibrated energy transform. Two stereoisomers
   cannot establish a nitrogen-count SAR; report counts descriptively.
5. For follow-up suggestions, use the existing analog hypotheses and name their
   unscored status. Training QSAR requires a defined, sufficiently populated,
   matched-protocol dataset and held-out validation. Generation requires an
   explicitly configured generator and preparation before scoring. Neither is
   enabled by installing this skill.

Service startup (only if capabilities cannot connect and no server is running):

```bash
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_server
```

It binds to loopback port 8001 and serves the current demo HTML. The original
port 8000 server is separate. Job tracking lasts for the service lifetime;
input snapshots and result files persist under `runs/selectivity-sentinel-web-*`.
Do not restart the service during a running job. A terminal or supervisor must
keep the server alive.
