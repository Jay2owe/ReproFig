# Decision: proof remains an optional `reprofig/1` extension

Status: accepted for ReproFig 0.3.0.

Proof evidence is additive under `extensions.proof`; the top-level figure
schema remains `reprofig/1`. Existing base records and readers stay compatible,
while every proof component has its own closed versioned schema and algorithm
identity. Unknown proof algorithms are retained but cannot receive a passing
verification meaning.

This decision avoids forcing proof dependencies or migration on ordinary users.
A future incompatible change to top-level identity/data semantics would require
`reprofig/2`; adding a new optional verifier does not.
