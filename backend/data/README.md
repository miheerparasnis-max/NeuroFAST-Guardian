# Data acquisition and use

This repository intentionally contains **no patient media or downloadable clinical dataset**.

## Why no automatic download exists

Several useful sources require a signed agreement, credentialed account, institutional sponsor, or author approval. A script cannot lawfully bypass those gates. Even public files must be reviewed against their license before they are used.

Store authorized data in a protected directory outside this repository and configure its path locally. Never commit raw face video, audio, clinical labels, identifiers, or access tokens.

## Dataset roles

See `datasets.json` for the source, access state, permitted engineering purpose, and non-permitted clinical claim for each source.

No listed source validates acute-stroke detection. The immediate use of these sources is modality engineering:

- Face: landmark and expression measurement robustness.
- Speech: feature extraction and post-stroke speech processing.
- Arm: movement-quality feature extraction.
- Eye: gaze-task and capture-quality engineering.

## Clinical validation dataset that is still missing

A valid acute-stroke study must have prospectively collected, consented, imaging/clinician-confirmed labels; time-from-onset metadata; stroke mimics and healthy controls; diverse sites and devices; and an independent held-out test site. It requires institutional review and clinical partners.
