# Saved figure reproduction and explicit statistical verification grades

## End goal

ReproFig will distinguish internal evidence integrity, reproduced statistics,
independently verified statistics, and complete figure reproduction. An
explicit reproduction operation will run the recorded producer in an isolated
workspace, preserve a separate reproduced figure, and report whether its data,
statistics and visible content match the master. Existing records that use the
old verification names will remain readable.

## Why we're doing this

The current `reproduced` grade only recalculates a statistical specification;
it does not run the producer or save another figure. That name overstates what
was checked. Users need the saved reproduced carrier itself so they can inspect
and compare the result rather than trusting a numerical badge.

## Architecture overview

```text
master carrier + bundle inputs
             |
             v
 explicit isolated producer run
             |
             +--> reproduced carrier (never overwrites master)
             |
             v
 data + statistics + visual comparison
             |
             v
 figure_reproduced verification report
```

Statistical grades remain declarative checks inside `verify_proof`. Complete
figure reproduction is an explicit operation because embedded scripts are
arbitrary code and must never run during inspection or ordinary verification.

## Stage map

| NN | name | one-line goal | rough size | depends on |
|---|---|---|---|---|
| 01 | verification terminology | Introduce explicit statistical grade names with legacy aliases. | medium | none |
| 02 | isolated reproduction runner | Materialize inputs and run the producer without overwriting the master. | large | 01 |
| 03 | reproduced-figure comparison | Compare the new carrier and issue `figure_reproduced`. | large | 02 |
| 04 | public API and command line | Expose safe Python and command-line reproduction workflows. | medium | 03 |
| 05 | integrations and examples | Update plot-that guidance and regenerate every demonstration layer. | large | 04 |
| 06 | release and publication | Audit, version, build, publish and verify every public surface. | medium | 05 |

## House rules

- `internally_consistent` only means carrier, record, sections and evidence-root hashes agree.
- Use `statistics_reproduced` for the same declared statistical implementation.
- Use `statistics_independently_verified` only for a separate reference implementation.
- `figure_reproduced` requires a saved second carrier plus successful comparisons.
- Never execute embedded code during inspect, extract, validate or ordinary `verify`.
- Reproduction is explicit, bounded, shell-free and performed in an isolated temporary workspace.
- Never overwrite the master carrier; save under `verification/reproduced/` by default.
- Preserve old `reproduced` and `independently_verified` inputs as deprecated aliases.
- Every saved example figure goes through plot-that and retains exact comma-separated value files beside it.
- Run the full test suite and rebuild `graphify-out` after code changes.
- No upload occurs before publication audit, artifact audit and push-guard pass.

## Known open questions

None. The user preapproved the terminology, split and implementation direction.

## How to run a stage

Run `/do-step docs/figure-reproduction-verification/` to execute the first incomplete stage.
