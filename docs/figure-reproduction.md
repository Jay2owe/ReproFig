# Figure reproduction

Think of this as a sealed rehearsal: ReproFig reruns a trusted figure producer
in a temporary workspace, keeps the new figure beside the verification report,
and compares it with the master without replacing the master.

Ordinary `validate`, `inspect`, `extract`, and `verify` calls never execute
embedded code. Complete figure reproduction is a separate, explicit operation
because producer scripts have the same authority as any other code you run.

```python
from reprofig import reproduce_figure, verify_proof

run = reproduce_figure(
    "bundle/fig/Figure-1.svg",
    bundle_root="bundle",
    output_dir="bundle/verification/reproduced",
    report_path="bundle/verification/reproduction-report.json",
    execute_trusted_producer=True,
)
assert run.valid

proof = verify_proof(
    "bundle/fig/Figure-1.svg",
    required=["figure_reproduced"],
    reproduction_report="bundle/verification/reproduction-report.json",
)
assert proof.valid
```

The runner copies declared input data into a temporary directory, materializes
embedded tables, writes the embedded producer script, and invokes only an
allowlisted Python executable without a shell. Time, input, output, and log
sizes are bounded. Network isolation is reported as `not_enforced`; use an
operating-system sandbox or isolated continuous-integration worker when that
boundary matters.

A passing `figure_reproduced` check means:

- the trusted producer exited successfully and created a valid ReproFig carrier;
- the reproduced carrier is saved separately as
  `<name>.reproduced.<extension>`;
- embedded data-table identities and normalized statistics match;
- semantic marks, annotations, and carrier-specific visual bindings match; and
- the saved carrier and report still match their recorded hashes.

The report binds to the stable evidence root, so adding a valid signature or
attestation later does not invalidate it. It also records the master file hash
at reproduction time for audit history. A pass does not establish that the
input observations are true, that the analysis choice is suitable, or that the
producer is safe to run.

The command-line equivalent is:

```console
reprofig reproduce bundle/fig/Figure-1.svg \
  --bundle-root bundle \
  --output-dir bundle/verification/reproduced \
  --report bundle/verification/reproduction-report.json \
  --execute-trusted-producer

reprofig verify bundle/fig/Figure-1.svg \
  --require figure_reproduced \
  --reproduction-report bundle/verification/reproduction-report.json
```

Legacy verification inputs remain accepted: `reproduced` maps to
`statistics_reproduced`, and `independently_verified` maps to
`statistics_independently_verified`.
