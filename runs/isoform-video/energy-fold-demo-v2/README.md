# IsoForm: from eV to fold preference

`IsoForm-demo-1080p.mp4` is a **53-second, 1920 × 1080, 30 fps H.264 MP4**,
with burned-in captions and no audio, ready to insert into PowerPoint.

This is a capture of the real updated local application and API—not mocked
results. It recomputes the component energies supplied in the team's
20 September 2026 handoff. **No new UMA inference is performed in this video.**

| Time | Scene |
| --- | --- |
| 00–03 | From eV to fold preference |
| 03–08 | Candidate and pose-policy selection |
| 08–12 | Interactive protein references (not selected relaxed drug poses) |
| 12–17 | Actual backend recomputation |
| 17–23 | Exchange-energy difference and empirical conversion |
| 23–28 | Osilodrostat: 3.23× fitted B2 preference, below illustrative 10× screen |
| 28–35 | Baxdrostat: 103.36× fitted B2 preference and export |
| 35–40 | Supplied Boltz seeds versus the fitted UMA signal and Ki reference |
| 40–46 | Original baxdrostat minima: 5.86× with the same coefficient |
| 46–49 | Metyrapone: missing B2 convergence, no fold reported |
| 49–53 | Next experiments and scope |

The two-compound coefficient and selected poses were fitted retrospectively.
These are training fits, not independent predictions or validated transferable
selectivity. Both fitted compounds remain unresolved under the supplied
pose-spread rule. Fitted UMA versus uncalibrated Boltz does not establish model
superiority. Ki and IC50 remain distinct endpoints.

`recording.json` contains the actual API responses, source hashes, scene
durations and capture frame counts. `baxdrostat-selected-fit.json` is the
export downloaded through the app. `encoding-check.txt` records the final
media format; the encoder decodes the whole MP4 to check integrity.

Reproduce from the project root with `python scripts/record_calibrated_video.py`.
See `docs/CALIBRATED_SELECTIVITY.md` for setup, equations and provenance.
Capture playback is editorially paced to the scene durations, not a compute
runtime benchmark; original counts remain in the provenance.
