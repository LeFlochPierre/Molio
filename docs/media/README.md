# Molio: the complete workflow tour

**[Watch the 3-minute 44-second tour](molio-complete-tour.mp4)** · [Animated highlights](molio-complete-tour-preview.webp) · [Capture metadata](molio-complete-tour-recording.json)

The extended, silent **1440 × 1000** tour follows actual local-app interactions with a visible cursor, click highlights, chapter captions, and smooth digital close-ups. It starts with a new FKBP1A protein workspace and a user-entered molecule, creates proposals, executes **nine new Boltz-2 predictions across three seeds**, inspects the outputs, and finishes with public chemistry lookup and experimental evidence tools.

## Chapters

| Time | What you see |
| --- | --- |
| 0:00–0:11 | Molio welcome screen and project library |
| 0:11–0:25 | Search UniProt; create a workspace and download its sequence and available AlphaFold DB model |
| 0:25–0:42 | Rotate the protein; inspect sequence and prediction-region settings |
| 0:42–0:59 | Enter ethyl benzoate by SMILES and inspect its generated 3D conformer |
| 0:59–1:18 | Create a custom propyl-ester proposal, compare its chemistry, and save a hypothesis |
| 1:18–1:36 | Generate rule-based ideas, inspect changes, and select two designs |
| 1:36–1:52 | Configure the parent plus two designs with seeds 42, 43, and 44; launch the run |
| 1:52–2:04 | Real inference progress, with waiting time explicitly accelerated |
| 2:04–2:15 | Compare means, ranges, sample standard deviations, and paired differences |
| 2:15–2:26 | Read affinity, model binder probability, and structural confidence separately |
| 2:26–2:45 | Rotate a predicted complex; inspect geometry checks, nearby residues, and provenance |
| 2:45–2:52 | Export the completed prediction record |
| 2:52–3:10 | Search PubChem for caffeine, import the structure, explore offline examples, and export workspace data |
| 3:10–3:27 | Open BRD4's experimental series and measured activity map |
| 3:27–3:44 | Inspect the experimental pocket and molecular surface, then return to the library |

Chapter markers are embedded in the MP4 for players that support them; a [WebVTT caption file](molio-complete-tour.vtt) is also available. Times are approximate to the nearest second.

## What was actually run

- Target: human FKBP1A, UniProt `P62942`, in a new sequence-first workspace. The AlphaFold DB structure was downloaded for display; it was **not** folded locally or used as a Boltz template.
- Starting molecule: ethyl benzoate, `CCOC(=O)c1ccccc1`, entered through the app. This is an illustrative input, not a claimed FKBP1A binder.
- A separate propyl-benzoate hypothesis was saved manually. The comparison uses the starting molecule and two designs selected in the design explorer; the manual proposal is not part of that run.
- Three molecules × seeds 42, 43, and 44 = nine actual predictions, using Boltz-2 2.2.1 and the app's single-sequence protocol on an NVIDIA RTX PRO 6000 Blackwell GPU.
- All nine predictions completed. The actual job took **9 minutes 37 seconds**. The captured inference wait of **577.67 seconds** is shown in **12 seconds** (approximately **48.1×**) and labelled on screen.
- The selected designs were ethyl ester → methyl ester and one aromatic H → F substitution.
- Run ID: `d1a20c09-4f26-478e-921c-9ff2deb90c3a`. Workspace: `lab-c3ef2c78fa9c`.
- The PubChem caffeine import is a separate example of finding starting chemistry; it was not included in the nine predictions.

[Native job record](molio-complete-tour-job.json) · [Run exported through the UI](molio-complete-tour-export.json) · [Workspace exported through the UI](molio-tour-workspace.json)

**Interpretation:** affinity is the model's native log₁₀(µM) score; lower values predict stronger binding. Binder probability is the model's classifier output, not an experimentally established percentage chance of binding. Structural confidence is a separate output. Three random seeds show variation within one fixed protocol, not experimental replicates or calibrated uncertainty. No winning drug or validated affinity improvement is claimed. Imported-target pose checks cannot verify placement against a compatible experimental ligand reference.

## Editing and provenance

Scientific values are actual outputs, not mocked or substituted. Mouse and click overlays, captions, edited pacing, and selected 1.22× digital close-ups are presentation additions. Computation and download waits are shortened and labelled. The optional chemistry-lookup segment was captured separately during computation and inserted after the completed-run export; it did not change the submitted prediction inputs. The BRD4 chapter uses the bundled experimental dataset, separate from the new FKBP1A run.

The MP4 is H.264, `yuv420p`, with 30 fps output and fast-start metadata. Source screenshots have a variable capture rate; the output rate does not imply 30 distinct source frames per second. The final MP4 was fully decoded, the close-up framing was inspected, and the exported run matches the native job record. Retained frames and the metadata record support re-encoding without rerunning the GPU work.

## Record the extended tour

With the local app running and Boltz configured, use an environment containing Playwright and imageio-ffmpeg:

```bash
python scripts/record_molio_complete_tour.py --live \
  --url http://127.0.0.1:8001 \
  --out /tmp/molio-extended-video \
  --capture-dir /tmp/molio-extended-frames
```

**`--live` creates a project, adds molecules, saves proposals, performs public-data lookups, and launches nine GPU predictions.** Choose new output and capture directories. Actual computation takes longer than the edited video; downloads also depend on provider availability. No drawing editor, automatic chemical optimization, or molecular-dynamics trajectory is demonstrated: these are not implemented features.

To re-encode a completed capture without creating projects or running predictions:

```bash
python scripts/record_molio_complete_tour.py --encode-only \
  --capture-dir /tmp/molio-extended-frames \
  --out /tmp/molio-reencoded-video
```

Use a fresh output directory. A failed capture before completion is not automatically resumed; the app retains the real job, and recording metadata identifies it. Check that job before starting another `--live` recording.

The README embeds a roughly **37-second, 720 px-wide, 6 fps** highlights WebP at **4× edited-video speed**, rather than the entire long tour. The inference section is already accelerated in the source video. Recreate the preview with:

```bash
python scripts/make_molio_tour_preview.py \
  --input docs/media/molio-complete-tour.mp4 \
  --output /tmp/molio-highlights.webp
```

 Open the MP4 to read scores and captions at full quality.
