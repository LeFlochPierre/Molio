# IsoFit / IsoForm: running ALCHEMI agent integration

Installed and tested on 20 September 2026 in `/home/ubuntu/HackProject` on the existing Brev machine.

The existing demo UI is served by an additional loopback service on port 8001. Its energy calculations now use ALCHEMI 0.2.0's native UMA wrapper, the existing UMA s1.1 checkpoint, OMol, explicit charge/spin, and the A100 GPU. The original port 8000 service and source modules were not replaced.

An existing coding agent controls the workflow through seven MCP tools or the equivalent CLI. A project skill and project MCP configuration were installed. This is a custom companion integration compatible with BioNeMo Agent Toolkit's skill approach, not a standalone BioNeMo LLM server. No additional LLM API key is required when using the existing Codex agent.

## Use it now

In the VS Code agent opened on HackProject, ask:

> Use $isoform-alchemi to inspect the completed R- and S-fadrozole runs, compare their CYP11B1/CYP11B2 exchange-energy scores, and suggest the next experiments. Clearly distinguish computed evidence from untested hypotheses.

The installed skill is `.agents/skills/isoform-alchemi/SKILL.md`. The MCP entry is `isoform_alchemi` in `.codex/config.toml`; an existing extension session may need to reload its MCP configuration. The skill's CLI works without MCP discovery.

```bash
cd /home/ubuntu/HackProject
.venv-alchemi-agent/bin/python scripts/start_isoform_agent.py
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools capabilities
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools jobs
.venv-alchemi-agent/bin/python -m cyp_pipeline.agent_tools compare f4a8ce69bfc8 1dc01667e06a
```

Open the forwarded port 8001 in VS Code, or forward it from your Mac:

```bash
ssh -N -L 18001:127.0.0.1:8001 ubuntu@smoggy-orange-ant
```

Then open http://127.0.0.1:18001/ . A tunnel is already open for this session. The remote service is a background process, not a boot-time system service. It persists after the SSH command ends, but must be started again after a machine reboot. Job tracking lasts for the server lifetime; input snapshots and numerical results persist on disk. Do not restart during a job.

## Verified results

Both jobs completed all eight exchange components, with real model energies and no failed components:

| Candidate | Job ID | B2 minus B1 exchange energy (eV) | Direction in this prepared energy model |
|---|---|---:|---|
| R-fadrozole | f4a8ce69bfc8 | -9.5844923074 | CYP11B2 |
| S-fadrozole | 1dc01667e06a | +0.6029305710 | CYP11B1 |

These are frozen-coordinate calculations with provisional pocket chemistry and different pose sources. They are not binding free energies or validated biological selectivity predictions. Both ligands contain three nitrogen atoms, so this pair does not establish a nitrogen-count SAR. Baxdrostat is registered in the catalog but still requires prepared pocket inputs for execution.

The numerical regression compared water, a 450-atom heme-containing pocket, and free ligand against the original fairchem/ASE backend. Maximum energy difference was 4.06e-7 eV; maximum force difference was 2.15e-6 eV/angstrom. See `parity.json`. The adapter preserves fairchem's double-precision reference-restored energy because the default ALCHEMI output cast loses precision before exchange subtraction.

Agent boundary tests passed, and the real MCP stdio transport listed all seven tools and successfully submitted and compared both jobs. Result evidence is included alongside this file.

## Live and next

- Live: preparation-aware planning, allow-listed real UMA runs through ALCHEMI, job monitoring, matched-recipe comparison, descriptive ligand counts, and retrieval of existing unscored analog hypotheses.
- Agent controller: your existing Codex/VS Code agent, using the installed skill or MCP tools. The service does not contain an embedded LLM or a chat UI.
- Next: prepare baxdrostat and other candidates, establish a matched dataset and experimental validation, fit and evaluate QSAR, then connect a configured generator and rescore prepared analogs.
- The analog library was written for CYP11B1 hypotheses; its members are not claimed to improve CYP11B2 selectivity. This integration returns them unranked, without invented QSAR predictions.

## Suggested pitch placement

Add a slide after PDF page 8, “What can research scientists do with IsoFit?”, before the team.

Title: **Where IsoFit connects: an agent-callable molecular workflow**

Main flow: **Research agent → IsoFit preparation and comparison → ALCHEMI + UMA s1.1 → Results and evidence**

Under the agent: **Custom skill + MCP, compatible with the BioNeMo Agent Toolkit approach**

Solid line / live: **Submit • monitor • compare — two candidate workflows tested**

Dashed loop / next: **Validated data → QSAR → new candidate generation → prepare and rescore**

Speaker line: “IsoFit turns our pocket-comparison workflow into a tool an agent can operate. ALCHEMI runs UMA s1.1, and the agent launches calculations, checks results, and compares the target pair. Our next step is to validate those scores and close the loop with QSAR and candidate generation.”

On PDF page 4, replace the outdated blanket statement that the connection is planned with “ALCHEMI + UMA connected; agent tools live.” Keep Rosalind marked planned unless it is independently connected. On PDF page 10, align the sign convention with the demo: the demo uses B2 minus B1, with negative values favoring B2 in this energy model. The current slide has the opposite subtraction.

References: [ALCHEMI model wrappers](https://nvidia.github.io/nvalchemi-toolkit/userguide/models.html), [BioNeMo Agent Toolkit](https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit), [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp).
