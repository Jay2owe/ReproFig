# Signed identity registry and recovery

Editors and upload services can strip metadata while leaving a recognizable
figure. A registry is an index card pointing from a public visual/carrier
identity to a trusted recovery artifact; it never makes private masters public.

Registry entries contain figure ID, evidence root, public or minimal-public
profile, exact carrier hashes, a normalized visual fingerprint, HTTPS or safe
relative recovery locations, lifecycle metadata and an Ed25519 signature.
Master-profile entries, absolute paths, parent traversal and non-HTTPS remote
locations are rejected.

```console
reprofig registry entry Figure.public.png --registry registry.json \
  --recovery companions/Figure.public.reprofig.zip \
  --key registry-signing.pem --password-env REPROFIG_REGISTRY_KEY_PASSWORD

reprofig registry recover downloaded.png --registry registry.json \
  --trust-store trust.json --output recovered.reprofig.zip
```

Resolution first tries exact carrier SHA-256. If that fails, it may return a
visual-fingerprint candidate. Only mathematically valid, unrevoked entries
signed by a key trusted for the `registry` scope are eligible. Recovery then
validates the downloaded/local companion and requires its embedded figure ID
and evidence root to match the signed entry before atomic promotion.

A visual match is a candidate, not proof of identity. Average-hash collision,
substantial redesign or platform recompression can produce false matches or
misses. Exact carrier identity is stronger. Host remote registries and recovery
files over authenticated HTTPS, preserve historical signed entries, and use
`supersedes`/revocation instead of silently rewriting identity history.
