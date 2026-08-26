# Proof-carrying, independently verifiable scientific figures

## End goal

Users who explicitly opt into proof features can add machine-checkable evidence connecting source data, transformations, statistics and visible marks to individual figures or the canonical publication workbook built by `docs/publication-workbook/`. A verifier can independently reconstruct supported calculations, confirm that the output displays those results correctly, identify who signed the evidence, and decrypt only protected sections for which the user has a key. Ordinary ReproFig saving, inspection and CSV extraction remain the unchanged default; only an explicitly activated strict policy prevents an artificial-intelligence agent or plotting script from placing an unverified output in a controlled publication directory.

## Why we're doing this

ReproFig 0.2 already keeps figures attached to exact plotted tables, structured statistics, source fingerprints, producer information and privacy profiles across sixteen carriers. It currently proves record integrity and publication safety, but it does not prove that the recorded statistics follow from the source data, that the pixels show those results, or that a claimed author signed the record with a trusted key. This work turns embedded provenance into independently testable evidence and makes common plotting errors or invented annotations detectable before a figure is published.

## Existing foundation — do not rebuild

The following are already implemented and are excluded from this plan except where an extension must remain compatible:

- the package-neutral `reprofig/1` figure record;
- exact embedded comma-separated value tables and SHA-256 content hashes;
- structured but currently opaque statistics records and deterministic statistics tables;
- source references, file fingerprints and source-change detection;
- master, public and minimal-public one-way privacy profiles;
- save, embed, extract, inspect, validate, scan, publish and bundle operations;
- direct support for eight vector or raster carriers and eight document or scientific containers;
- deterministic ZIP and Research Object Crate bundles with member checksums;
- dots-per-inch presets, physical dimensions and format-specific encoder options;
- atomic carrier writes, carrier integrity checks and tested metadata-survival documentation;
- current PyFLASH, PyMicroglia and `plot-that` integrations, plus the completed canonical publication-workbook pipeline.

The existing multi-format design remains documented in `docs/multiformat_embedding_plan.md`, and `docs/publication-workbook/` must be completed first so this plan can extend its stable publication, table and test identities. Both are implemented foundations for this new work, not duplicate scope.

## Architecture overview

```text
source data -> declared transformations -> plotted table -> declared statistics
     |                  |                       |                 |
     +------------- canonical evidence graph and hashes --------+
                                        |
                                        v
                              semantic render manifest
                              /                      \
                    vector comparison          raster comparison
                              \                      /
                               verification report
                                        |
                 signed evidence root + selectively encrypted sections
                                        |
                         agent/output enforcement gate
```

The public manifest remains readable and identifies the figure, evidence sections, algorithms, verification grade and signer. Sensitive tables, source locations, reproduction material or other selected sections may be encrypted separately. A signature covers the canonical public manifest and every plaintext or ciphertext section hash, so adding, removing, replacing or reordering evidence invalidates the signature.

A bundled public key does **not** establish trust by itself: anyone can create a new key and sign their own record. Verification therefore separates `signature_valid` from `signer_trusted`. Trust comes from a key fingerprint already present in a local trust store, an approved laboratory or organization registry, or another independently verified identity route. A modified record signed with an unknown key is reported as a valid signature from an untrusted signer, never as the original author.

Selective encryption uses authenticated encryption: decryption succeeds only when both the key and integrity tag are correct. Each protected section receives a random content key; the content key is then wrapped for named recipients or derived from a password through a memory-hard key derivation function. The signed public manifest covers the ciphertext, encryption parameters and recipient envelopes. Initial algorithm choices are proposed, not final: Ed25519 signatures follow [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032), password-derived keys use Argon2id as specified by [RFC 9106](https://www.rfc-editor.org/rfc/rfc9106), and section encryption uses a maintained authenticated-encryption implementation rather than new cryptographic code; Advanced Encryption Standard Galois/Counter Mode is specified by [NIST Special Publication 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final).

## Verification meanings

ReproFig must report separate achievements rather than one ambiguous “verified” badge:

- **display verified** — the visible label and graphical object match the embedded result;
- **internally consistent** — carrier, tables, statistics and render manifest agree;
- **statistics reproduced** — the declared statistical implementation obtains the recorded result;
- **statistics independently verified** — a separate reference implementation obtains the same result;
- **figure reproduced** — an explicitly trusted producer rerun saves a separate matching carrier;
- **source-linked** — the evidence matches identified source content;
- **signature valid** — the signed bytes have not changed;
- **signer trusted** — the signing key is independently trusted under the active policy;
- **attested** — a trusted signer approved a stated verification result.

Encryption changes visibility, not truth. A verifier without a decryption key can check ciphertext integrity, signature coverage and public claims, but must report protected calculations as inaccessible rather than verified.

## Stage map

| NN | name | one-line goal | rough size | depends on |
|---:|---|---|---|---|
| 01 | evidence schema | Add typed claims, transformations, statistical specifications, render manifests and cryptographic envelopes without breaking `reprofig/1` readers | 2 days | publication-workbook 01–08 |
| 02 | evidence graph and canonical hashes | Give every evidence section a stable identity, deterministic byte representation and tamper-evident dependency graph | 2 days | 01 |
| 03 | verification grades and reports | Create one extensible verifier result model and command-line contract for every later check | 1 day | 01, 02 |
| 04 | source and transformation reconstruction | Canonicalize source tables, apply declared filters and transformations, and prove the plotted table can be reconstructed | 2 days | 02, 03 |
| 05 | statistical specification registry | Define versioned, declarative test specifications with all choices needed for independent calculation | 2 days | 01, 03 |
| 06 | independent descriptive and t-test engine | Independently verify counts, summaries, confidence intervals and common independent or paired t-tests | 2 days | 04, 05 |
| 07 | rank, analysis-of-variance and correction engine | Add rank tests, one-way analysis of variance and complete multiple-comparison families | 2 days | 05, 06 |
| 08 | regression and resampling verification | Add ordinary least-squares regression and deterministic bootstrap/permutation verification while defining honest limits for complex models | 2 days | 05, 06 |
| 09 | semantic render manifest | Define links from points, lines, bars, intervals, brackets and text to data rows or statistical result identities | 2 days | 01, 02, 03 |
| 10 | Matplotlib semantic capture | Capture those semantic links and deterministic render facts from Python figures before they are saved | 2 days | 09 |
| 11 | vector visual verifier | Normalize and compare vector geometry, text, group brackets and statistical annotations against the render manifest | 2 days | 09, 10 |
| 12 | raster visual verifier | Rerender a canonical reference and compare pixels, regions and annotation maps with documented tolerances | 2 days | 09, 10, 11 |
| 13 | signature envelope and key commands | Sign the canonical evidence root, verify tampering, and safely create/import/export signing keys | 2 days | 02, 03 |
| 14 | trust policies and signer lifecycle | Distinguish valid from trusted signatures through trust stores, key rotation, revocation and organization policies | 2 days | 13 |
| 15 | selective evidence encryption | Encrypt individual evidence sections for passwords or named recipients without hiding public verification facts | 2 days | 02, 13 |
| 16 | profiles with signatures and encryption | Define safe master-to-public derivation, re-signing, encrypted-field removal and disclosure behavior | 2 days | 13, 14, 15 |
| 17 | Python save interception | Intercept supported Python plotting save routes and require a passing ReproFig policy | 2 days | 03, 10 |
| 18 | controlled output broker | Make ReproFig the only process allowed to promote files from a temporary workspace into a publication directory | 2 days | 03, 17 |
| 19 | other-language adapters | Add contract-tested adapter templates for R, Julia, JavaScript and MATLAB plotting environments | 2 days | 03, 05, 09, 18 |
| 20 | identity registry and stripped-metadata recovery | Recover evidence by stable identity after an upload or editor strips embedded metadata | 2 days | 13, 14, 16 |
| 21 | PyFLASH integration | Upgrade PyFLASH plots and its agent runner from embedded provenance to declared statistics, semantic marks and enforced verification | 2 days | 06–18 |
| 22 | PyMicroglia integration | Upgrade every PyMicroglia figure action and its generated catalogue to the proof-carrying contract | 2 days | 06–18 |
| 23 | plot-that integration | Make the general plotting skill request, validate and report the strongest available proof grade | 1 day | 17, 18, 21, 22 |
| 24 | adversarial and carrier hardening | Test tampering, forged keys, corrupted ciphertext, metadata stripping and proof survival across all carriers | 2 days | 01–23 |
| 25 | documentation and release | Publish the schemas, threat model, migration guide, examples and verified package release | 2 days | 01–24 |

Stages 05 and 09 may begin in parallel after the core report model exists. Stages 13 and 17 may also proceed in parallel with the statistical and visual engines because they share only the canonical evidence and report contracts. Stage 19 should implement adapter contracts and one thin route per language; exhaustive support for every plotting library remains separate follow-on work.

## House rules

- Preserve all existing `reprofig/1` read and write behavior unless a caller explicitly requests the new evidence features.
- Keep carrier handling format-neutral: scientific meaning belongs in the evidence schema, not in Portable Document Format-, image- or Office-specific records.
- Keep the base install and beginner path unchanged. Statistical, visual and cryptographic implementations belong behind separate optional extras and capability discovery; no ordinary save or extraction call gains a new required argument.
- Never execute embedded producer scripts during inspection, extraction or ordinary validation.
- Independent verification must use declarative specifications and a separate reference implementation; the same statistical route is `statistics_reproduced`, while a saved producer rerun is `figure_reproduced`.
- Every statistical algorithm is versioned and records missing-data, pairing, tail, tie, correction, convergence, tolerance and randomization choices that affect its answer.
- Every displayed statistical annotation links to one result identity; optical character recognition alone is never accepted as strong display verification.
- Verification fails closed when required evidence is unavailable, unsupported or encrypted without a key. It reports `inaccessible` or `unsupported`, never an inferred pass.
- Never implement cryptographic primitives in ReproFig. Use maintained libraries, published algorithms and official test vectors.
- A signature proves control of a private key and integrity of signed bytes. Only an independent trust policy may call the signer trusted.
- Sign canonical section hashes, encryption envelopes and ciphertext. Do not sign a mutable carrier byte stream whose metadata contains the signature itself.
- Never reuse a content-encryption nonce or content key. Never store plaintext private keys or passwords in figure records, logs or command history.
- Public and minimal-public derivation remains one-way. Encryption is not a substitute for the current privacy audit.
- Adding evidence must not alter visible content. Visual verification may compare a normalized rerender, but embedding stays metadata-only where the carrier permits it.
- Preserve atomic writes, size limits, decompression limits, safe archive extraction and no-silent-downgrade behavior.
- Keep machine-readable verification output deterministic and suitable for automated gates.
- Treat verification, interception, signatures and encryption as explicitly activated capabilities: artifacts without them remain readable, current saves remain non-blocking, and only a caller-supplied proof policy may require a grade or key.

## Progressive activation contract

The rigorous system is layered around the existing workflow rather than replacing it:

| user path | activation | behavior |
|---|---|---|
| basic provenance | base `pip install reprofig` | Current save, inspect, extract, publish and bundle behavior with no new prompts or required fields. |
| publication workbook | explicit `reprofig[excel]` install and workbook call | Combines existing evidence into Excel; it is never created during ordinary figure saving. |
| rigorous proof | explicit `reprofig[proof]` install and verification, signing or encryption call | Includes workbook, scientific, visual and cryptographic capabilities, loads them lazily and reports the strongest evidence available. |
| enforced output | explicit guard or broker policy | Blocks only the scoped run or controlled destination named by that policy. |

Installing an extra enables commands but activates no hooks, network access, key prompts, strict grades or output blocking. Missing optional evidence leaves current artifacts valid and produces `unsupported`, `unavailable` or a lower grade unless the user explicitly requires more.

## Known open questions

These decisions were not fixed in the conversational source and must be resolved in their owning stages before implementation:

1. Whether the typed evidence model becomes `reprofig/2` or a versioned extension carried by `reprofig/1`.
2. Which identities can be trusted initially: individual researcher keys, laboratory keys, automated release keys, or all three under separate policies.
3. Whether the first trust mechanism is a local allowlist, a repository-backed public-key registry, or integration with an external identity-attestation service.
4. Whether password encryption and named-recipient encryption ship together or password encryption lands first.
5. Which common statistical tests form the first independently verified compatibility set.
6. Whether the first strong visual verifier targets Matplotlib-generated Scalable Vector Graphics only or also Portable Document Format in the same release.
7. Which non-Python language is the first fully enforced adapter after the shared adapter contract exists.
8. Where a public identity-and-recovery registry would be hosted and who may publish or revoke entries.
9. How trusted-key compromise and historical signature validity are represented without requiring a continuously available network service.

## How to run a stage

After the numbered stage files are approved and written, run `/do-step docs/proof-carrying-figures/` to execute the first incomplete stage.
