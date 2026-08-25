# Decision: section encryption uses authenticated hybrid envelopes

Status: accepted for ReproFig 0.3.0.

Each selected evidence section receives a random 256-bit AES-GCM content key
and 96-bit nonce. Password access wraps the content key with an Argon2id-derived
AES-GCM key. Named-recipient access wraps the same content key independently
for X25519 public keys through HKDF-SHA-256 and AES-GCM.

Authenticated data binds figure ID, record schema, section identity, section
schema and the public encryption descriptor. Plaintext SHA-256 and size remain
public to support stable evidence identity and authorized validation; this is a
documented equality/dictionary-guessing leak. Private keys and passwords never
enter the figure record.

Algorithms and bounds are closed under `reprofig-encrypted-section/1`. A future
algorithm requires a new version rather than reinterpretation of this envelope.
