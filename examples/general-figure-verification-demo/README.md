# General figure verification demonstration

Like opening one inspection hatch at a time, these folders keep one simple
Matplotlib plot fixed while exposing each distinct thing a recipient can
verify. The baseline and all nine formal ReproFig verification meanings have
their own visible figure, report and unpacked evidence folder.

Start with `verification-layers-overview/preview/verification-layers.png` for
the one-page map of what every layer establishes and what remains outside it.

The example starts with twelve synthetic observations typed into
`input/raw-observations.csv`. The producer uses only Python's standard library,
Matplotlib, and ReproFig; it does not need an application-specific plotting
package, pandas, a notebook, a saved analysis object, or prerequisite
statistical output.

- `00-traceable-carrier`: data, statistics, source hash and producer are
  recoverable, but no formal proof meaning is claimed.
- `01-internally-consistent`: carrier, record, evidence sections and evidence
  root agree.
- `02-statistics-reproduced`: the declared numbers rerun through the recorded
  producer-equivalent route.
- `03-statistics-independently-verified`: ReproFig's reference Welch test matches a
  separate Python-standard-library implementation.
- `04-figure-reproduced`: the trusted producer reruns and a separate matching
  Scalable Vector Graphics file is saved under `verification/reproduced/`.
- `05-display-verified`: bound dots, means, bracket and p-value text are
  unchanged.
- `06-source-linked`: an executable transformation reconstructs the plotted
  table from the copied raw CSV.
- `07-signature-valid`: an Ed25519 signature is mathematically valid for the
  evidence and visual binding.
- `08-signer-trusted`: that signature satisfies an explicit local trust-store
  policy.
- `09-attested`: a trusted signer approves the deterministic full-stack
  verification report.

Open a layer's `preview/raw-user-input-comparison.png`, then inspect
`verification/meaning-summary.csv` or the complete
`verification/report.json`. The `unpacked/` directory shows what ReproFig can
recover from the corresponding Scalable Vector Graphics file.

Install the runnable dependencies with:

```text
python -m pip install matplotlib "reprofig[proof]"
```

The data are intentionally synthetic and make no scientific claim. The signing
keys are temporary demonstration identities, not evidence of a real person's
identity. Their private halves are generated in temporary directories and
deleted; only public keys and, where needed, explicit local trust decisions are
retained.
