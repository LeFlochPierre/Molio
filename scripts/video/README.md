# IsoForm presentation recording

## New: energy-to-fold demo

Use `python scripts/record_calibrated_video.py` for the **53-second** updated
workflow: supplied relaxed UMA energies → exchange difference → empirical fold
preference → Boltz/assay comparison → original-minima sensitivity → failed-
convergence gate. This records actual API recalculation, **not new UMA inference**.
No GPU/checkpoint is needed. It retains the full responses in `recording.json`.
See [method and scope](../../docs/CALIBRATED_SELECTIVITY.md).

The completed video is
`runs/isoform-video/energy-fold-demo-v2/IsoForm-demo-1080p.mp4`.

## Earlier: fresh frozen-pocket UMA recording

`scripts/record_isoform_video.py` records the actual local web application and
one fresh eight-component UMA CPU exchange run. It exports a **54-second,
1920 × 1080, 30 fps H.264 MP4** with burned-in captions. There is no audio, so
the presenter can speak over the video. The encoder uses `yuv420p` and moves
MP4 metadata to the front of the file for playback compatibility.

## Record

Run from the project root with the optional browser/video environment:

```bash
python scripts/record_isoform_video.py
```

Dependencies: Playwright, its Chromium installation, and `imageio-ffmpeg`.
The existing configured UMA interpreter and CPU checkpoint are also needed.
The script starts an isolated loopback server on a free port; it does not
restart an existing demo server or touch a GPU job. Recording launches one
CPU model calculation. `--preview` checks the layout without launching UMA.

Files go to `runs/isoform-video/<UTC timestamp>/`, or a **new** directory
supplied with `--out`. Existing directories are not overwritten.

If encoding fails after capture, resume without rerunning the model:

```bash
python scripts/record_isoform_video.py \
  --encode-only runs/isoform-video/RECORDING_DIRECTORY
```

## Storyboard

| Time | On screen |
| --- | --- |
| 00:00–00:03 | Branded introduction |
| 00:03–00:08 | Molecule selection and B2/B1 target pair |
| 00:08–00:14 | Rotating actual prepared pockets |
| 00:14–00:17 | Browser launches the real UMA job |
| 00:17–00:25 | Real model progress, with waiting accelerated |
| 00:25–00:33 | Actual exchange-energy result, hypothetical fold proxy, JSON export |
| 00:33–00:38 | Saved osilodrostat IC50 evidence below the assay threshold |
| 00:38–00:43 | Saved baxdrostat Ki evidence above the threshold, with model disagreement |
| 00:43–00:50 | CYP19A1 reference and five-protein input-bundle generation |
| 00:50–00:54 | Closing research-use message |

The app's own numerical results, source labels and scientific warnings are
not replaced or mocked. A separate recording stage adds editorial titles,
captions, a pointer, and a compact browser-only layout. Compute waiting is
captured at about one frame per second and uniformly condensed to eight
seconds. Other scenes are paced for presentation; the video is not a runtime
benchmark. Capture is capped at 12 fps (actual rate depends on machine load)
and encoded at 30 fps. Original frame counts are retained in the provenance.

The hypothetical UMA energy-fold proxy is **not binding selectivity**. The
saved paired-assay examples are clearly separated from the live calculation;
Ki and IC50 ratios are not interchangeable. The expanded panel segment
builds inputs, not new poses or UMA predictions for all five proteins.

## Deliverables and traceability

- `IsoForm-demo-1080p.mp4`: presentation video.
- `poster.png`: app overview image for a video poster or slide.
- `uma-result.png`, `structure-comparison.png`, `assay-alert.png`,
  `assay-contrast.png`, `expanded-panel.png`, `closing-slide.png`: stills.
- `actual-uma-job.json`: the fresh completed job, including its real run path.
- `downloaded-results.json`: the result exported through the actual app.
- `downloaded-input-bundle.zip`: the expanded inputs downloaded in the video.
- `recording.json`: scene timing, capture frame counts, runtime, and provenance.
- `encoding-check.txt`: final media format and duration report.
- `frames/` and `clips/`: original captured frames and encoded scene clips.

The script decodes the entire final MP4 as an integrity check. To use it in
PowerPoint, download the MP4 from the remote machine and insert it as a video
from your computer. The PNGs are optional; no accompanying files are needed
for the MP4 to play.
