# Stage 03 — Establish verification grades, reports and command-line behavior

## Why this stage exists

Later stages will add very different checks: source reconstruction, statistics, visual comparison, signatures, trust and decryption. They need one stable result model so tools and agents cannot mistake “not checked” for “passed.” This stage creates that common contract before individual verifiers are implemented.

## Prerequisites

- Stages 01 and 02 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 01 and Stage 02 files
- `docs/publication-workbook/05_embedded-evidence-and-validation_COMPLETED.md:1-end`
- `src/reprofig/workbook/validation.py:1-end`
- `src/reprofig/validation.py:1-246`
- `src/reprofig/artifacts.py:322-483`
- `src/reprofig/api.py:1-428`
- `src/reprofig/cli.py:1-214`
- `tests/test_sources_cli.py:1-54`

## Scope

- Define check outcomes: pass, fail, unavailable, inaccessible, unsupported and not-requested.
- Define the separate verification meanings approved in the overview.
- Keep integrity/privacy validation distinct from proof verification while allowing one combined report.
- Add stable issue codes, evidence identities, expected/actual values and numerical tolerances.
- Add deterministic machine-readable serialization.
- Add `reprofig verify` with selectable required grade and optional decryption/trust inputs reserved for later stages.
- Define process exit codes suitable for automated gates.
- Return lower honest grades for old records rather than treating absent proof fields as errors unless the caller requires them.
- Add proof results to publication-workbook validation without changing its basic integrity result or requiring proof extras.

## Out of scope

- Source, statistical, visual, cryptographic and trust checks are later stages.
- No save interception or output blocking is introduced until Stages 17 and 18.
- This stage does not infer a test or annotation from free text.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/verification.py` | NEW | Common proof-check, grade and report model. |
| `src/reprofig/validation.py` | MODIFY | Compose existing validation with proof reports without conflating them. |
| `src/reprofig/workbook/validation.py` | MODIFY | Append optional proof checks to the workbook's existing integrity report. |
| `src/reprofig/api.py` | MODIFY | Export `verify_artifact` and report types. |
| `src/reprofig/__init__.py` | MODIFY | Publish the stable verification interface. |
| `src/reprofig/cli.py` | MODIFY | Add the `verify` command and deterministic exit behavior. |
| `tests/test_verification_reports.py` | NEW | Freeze statuses, grades, serialization and command exit codes. |
| `README.md` | MODIFY | Explain validation versus proof verification. |

## Implementation sketch

```python
class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    INACCESSIBLE = "inaccessible"
    UNSUPPORTED = "unsupported"
    NOT_REQUESTED = "not_requested"

class VerificationGrade(str, Enum):
    DISPLAY_VERIFIED = "display_verified"
    INTERNALLY_CONSISTENT = "internally_consistent"
    STATISTICS_REPRODUCED = "statistics_reproduced"
    STATISTICS_INDEPENDENTLY_VERIFIED = "statistics_independently_verified"
    FIGURE_REPRODUCED = "figure_reproduced"
    SOURCE_LINKED = "source_linked"
    SIGNATURE_VALID = "signature_valid"
    SIGNER_TRUSTED = "signer_trusted"
    ATTESTED = "attested"

@dataclass
class VerificationCheck:
    check_id: str
    status: CheckStatus
    evidence_ids: list[str]
    message: str
    expected: Any = None
    actual: Any = None
    tolerance: dict[str, Any] | None = None

@dataclass
class VerificationReport:
    artifact: str
    figure_id: str
    checks: list[VerificationCheck]
    achieved_grades: list[VerificationGrade]
    required_grade: VerificationGrade | None
```

Command contract:

```text
reprofig verify FIGURE [--require GRADE] [--json]

exit 0: all requested checks pass and required grade is achieved
exit 1: a requested check fails or required grade is not achieved
exit 2: usage/configuration error or unreadable artifact
```

`unavailable`, `inaccessible` and `unsupported` do not count as passes. They may still allow exit 0 when the caller did not require the affected grade, but the report must retain them.

## Exit gate

1. Reports serialize deterministically and contain no Python-specific object representations.
2. A version-1 artifact receives honest absent/unsupported proof checks without losing its existing integrity result.
3. Requiring an unavailable grade exits with code 1 and identifies the missing evidence.
4. Corrupt or unreadable input exits with code 2 in both human and machine-readable modes.
5. No combination of statuses promotes an unavailable check to a passing grade.
6. `reprofig validate` retains its existing behavior.
7. `pytest tests/test_verification_reports.py tests/test_sources_cli.py -q` passes.
8. Ordinary `validate`, `inspect`, `extract` and save operations do not invoke proof verification or fail because proof evidence is absent.

## Known risks

- A single Boolean `valid` would erase essential distinctions. Keep validity, availability and trust separate.
- Grade ordering is not strictly linear: source linkage and signature trust answer different questions. Store achieved grades as a set, not a numeric score.
- Command exit semantics become an integration contract; freeze them with tests before agents depend on them.
