# Molio: the complete workflow tour

**[Watch the 3-minute 44-second tour](molio-complete-tour.mp4)** · [Animated highlights](molio-complete-preview.gif) · [Capture metadata](molio-complete-tour-recording.json)

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

The README embeds a roughly **37-second, 720 px-wide, 6 fps** highlights GIF at **4× edited-video speed**, rather than the entire long tour. The inference section is already accelerated in the source video. Recreate the preview with:

```bash
python scripts/make_molio_tour_preview.py \
  --input docs/media/molio-complete-tour.mp4 \
  --output /tmp/molio-highlights.gif
```

 Open the MP4 to read scores and captions at full quality. Earlier recordings remain available below.

---

# Earlier recording: live BRD4 pipeline

**[Watch the complete pipeline](molio-pipeline.mp4)** · [Looping README demo](molio-pipeline.gif) · [Results screenshot](molio-pipeline-results.png) · [Predicted pose screenshot](molio-pipeline-pose.png)

The earlier **64-second, 1440 × 1000** video includes a visible moving cursor, click highlights, and chapter captions. It follows actual interactions with the local app, saves two generated designs, executes three new Boltz-2 predictions, inspects the results, and exports the record.

| Time | What happens |
| --- | --- |
| 0–4 s | Open Molio with Start |
| 4–9 s | Choose the BRD4 project |
| 9–15 s | Choose the parent molecule and open design exploration |
| 15–24 s | Inspect edits and select two designs |
| 24–30 s | Configure parent + two designs, one seed each |
| 30–34 s | Click Run local prediction |
| 34–44 s | Real inference progress; waiting time accelerated |
| 44–51 s | Compare the completed model scores |
| 51–60 s | Open and rotate an actual predicted complex |
| 60–64 s | Export the run record |

## Actual computation and timing

- Run ID: `7067a8ba-c421-4a4f-8586-34666c00a6a1`.
- Parent: `CHEMBL1828983`; designs: ethoxy → methoxy and ethyl ester → methyl ester.
- Three new Boltz-2 2.2.1 predictions, each using seed 42, on an NVIDIA RTX PRO 6000 Blackwell GPU.
- All three predictions completed. The job ran for about **3 minutes 16 seconds**.
- The captured waiting interval was **193.33 seconds**, condensed into **10 seconds** (about **19.3×**), explicitly labelled on screen.
- Other scenes use edited presentation pacing. Cursor, click halo, and captions are recording overlays; scientific values are not replaced or mocked.
- These single-seed results demonstrate the workflow, not independently validated affinity improvements. No automatic winner is selected.

[Native job record](molio-pipeline-job.json) · [Record exported through the app](molio-pipeline-export.json) · [Capture and timing metadata](molio-pipeline-recording.json)

The silent MP4 uses H.264, `yuv420p`, 30 fps output, and fast-start metadata. Source capture rates vary by scene; output frame rate is not a performance claim. The entire encoded MP4 was decoded to check integrity, and the browser reported no JavaScript errors.

## Record the real pipeline again

Start the app with RDKit and the configured Boltz executable, then use a Python environment with Playwright and imageio-ffmpeg:

```bash
python scripts/record_molio_pipeline.py --live \
  --url http://127.0.0.1:8001 \
  --out /tmp/molio-live-recording \
  --capture-dir /tmp/molio-live-frames
```

**`--live` saves two proposals and launches three actual GPU predictions.** It checks that the runtime is ready and no experiment is already active. Choose a new capture directory and an output directory without an existing `molio-pipeline.mp4`. The capture directory retains frames, clips, and progress metadata for recovery; the app keeps the scientific artifacts in its experiment directory. The current recorder does not automatically resume a failed capture; check for an active job before launching another recording.

The script uses installed Google Chrome when found, otherwise Playwright's Chromium. Install recording dependencies with the repository's `video` extra as shown below. For a read-only visual tour with no new calculations, use the earlier recorder instead.

## Animated README preview

The earlier `molio-pipeline.gif` is a 32-second loop, 960 px wide, 10 fps, approximately 7.8 MB. It plays the full video at 2× speed. Its six static screenshots remain available alongside the newer gallery above.

To reproduce the GIF with FFmpeg (choose a new filename if retaining the existing version):

```bash
ffmpeg -i docs/media/molio-pipeline.mp4 \
  -filter_complex "[0:v]setpts=0.5*PTS,fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" \
  -loop 0 docs/media/molio-pipeline.gif
```

The inference section is already time-compressed in the source video. For a shorter design-to-results GIF, add `-ss 15 -t 36` before `-i`. The MP4 remains the clearer, smaller format for reading results. Design and run-setup screenshots were extracted from the actual pipeline video at 20 and 28 seconds, respectively.

---

# Earlier visual walkthrough

[Watch the walkthrough](molio-walkthrough.mp4) · [Library poster](molio-library.png) · [Molecule screenshot](molio-molecule.png)

The silent 38-second walkthrough captures the actual local app at 1440 × 900:

| Time | View |
| --- | --- |
| 0–5 s | Animated Molio welcome screen |
| 5–9 s | Project library and moving molecular background |
| 9–12 s | Hovering over the BRD4 protein preview |
| 12–17 s | BRD4 workspace and molecule library |
| 17–23 s | A molecule's 3D conformer, properties, and SMILES |
| 23–29 s | Generated chemical variations |
| 29–35 s | Experimental protein-pocket viewer |
| 35–38 s | Closing welcome screen |

This is a UI walkthrough, not a new prediction run. It uses saved local projects and the bundled BRD4 example. No predictions or proposal saves are submitted, and no scientific results are mocked. The poster reflects the projects present on the recording machine; a fresh checkout has the bundled BRD4 project until more are created.

The MP4 uses H.264, `yuv420p`, 30 fps output, and fast-start metadata. Browser screenshots are captured at up to 15 fps and resampled to the scene durations. The full MP4 is decoded after encoding to check integrity. See [recording metadata](molio-recording.json) for frame counts and provenance.

## Record again

Start Molio with its chemistry environment, then use an environment containing Playwright and imageio-ffmpeg (the repository's `video` extra provides these):

```bash
python -m pip install -e '.[video]'
python -m playwright install chromium
python scripts/record_molio_video.py --out /tmp/molio-new-recording
```

The script connects to `http://127.0.0.1:8001` by default. Use `--url` to select another local server and `--browser /path/to/chrome` to use a particular browser. It uses installed Google Chrome when found, otherwise Playwright's Chromium. The output directory must not already contain `molio-walkthrough.mp4`. Raw frames and intermediate clips are temporary.

## Convert a short segment to GIF

With FFmpeg installed, this makes a 12-second GIF starting at the project library, at 960 px wide and 12 fps:

```bash
ffmpeg -ss 5 -t 12 -i docs/media/molio-walkthrough.mp4 \
  -vf "fps=12,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" \
  -loop 0 docs/media/molio-preview.gif
```

Use `-ss 0 -t 12` for the welcome-to-library segment, or reduce the width/frame rate for a smaller file. The MP4 is the higher-quality version and usually much smaller than an equivalent full-length GIF.

The current README uses the extended-tour highlights GIF. This shorter visual-tour GIF remains an optional alternative.
