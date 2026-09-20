# Sharing, release contents and provenance

The public repository is intended for `LeFlochPierre/IsoForm`, using the MIT
license for original project code. It contains the runnable application,
research source, prepared input manifests, reference data, tests, setup and
selected reproducible presentation artifacts.

## Included

- Python source, browser assets, documentation, benchmark and design utilities.
- All supplied `prepared/` research inputs and their existing audit metadata.
- A small `research/source-preparation/` snapshot for historical preparation helpers.
- Public PDB/CCD references and small curated assay records.
- The v3 IsoForm app, static report, saved evidence and example pockets.
- The final 54-second MP4, poster and real-run/result provenance.
- Selected benchmark, pose-sensitivity and design summary reports.

## Intentionally not published

- More than 20 GB of downloaded model/package caches.
- Python environments, gated model weights, access tokens and private settings.
- Large intermediate trajectories, AF3/Boltz inference directories, temporary
  recording frames, interrupted video clips and in-progress research jobs.

These files are **excluded, not deleted** from the original machine. Some
historical reports refer to large original-host runs that are not bundled.
The recording metadata retains original paths as provenance; replaying its
video requires only the MP4. Fresh model jobs create new local run IDs.

The supported demo has self-contained prepared manifests, so replaying it
does not require the original host's parent directories. Some historical
preparation utilities have additional chemistry dependencies and source
artifacts; consult their contracts rather than treating them as a universal
automatic preparation service.

## Setup and build checks

- Default serving is localhost-only, without model execution.
- CPU/CUDA checkpoint paths are project-relative.
- An optional git-ignored local runtime override preserves existing hosts.
- Core tests, browser checks and regeneration of the HTML are available.
- CI is configured without GPU credentials, UMA weights or inference jobs.

## Publishing

After authenticating GitHub locally and confirming the intended account,
create a new public repository and push the reviewed initial commit:

```bash
gh auth login
gh repo create LeFlochPierre/IsoForm --public --source=. --remote=origin --push \
  --description 'IsoForm: exploratory molecular counter-screening with 3D pockets, UMA and evidence checks'
```

Authenticate only through GitHub's normal browser/device flow. Do not paste
tokens into chat. If the repository already exists, inspect its contents and
history before adding a remote or pushing; never force-push over someone
else's work. A prepared local Git repository is not public until the remote
creation/push succeeds. Static hosting, if added later, cannot execute UMA;
collaborators run the backend on their own trusted machine.
