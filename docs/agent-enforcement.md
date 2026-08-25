# Agent and automated-output enforcement

Prompt instructions are useful policy, not a security boundary. An agent can
forget them, call another writer, or launch another process. ReproFig provides
three progressively stronger options.

## Cooperative wrapper

Call `save_figure(..., proof=True, proof_policy=policy)` directly. This is the
simplest integration for plotting libraries and agents that already use a
known save helper. Policy application is atomic: encryption, signing and
required verification finish before the destination is replaced.

## Scoped Python interception

```python
from reprofig.guard import OutputPolicy, guarded_python

policy = OutputPolicy(
    permitted_formats=["svg", "pdf", "png"],
    profile="master",
    required_meanings=["internally_consistent", "display_verified"],
    destination="figures",
)
with guarded_python(policy):
    run_agent_plotting_code()
```

The context intercepts common Matplotlib save routes, checks format and
destination, routes the output through ReproFig, records an audit row and
deletes a strict output that misses required meanings. Importing the module
patches nothing; functions are restored even after exceptions.

This remains bypassable by direct file writers, cached original methods,
subprocesses or native libraries.

## Controlled-output broker

For a stronger arrangement, give the agent write access only to the broker's
candidate workspace. Keep the real publication destination outside that write
scope. The broker rejects outside files, links, traversal names, wrong formats,
wrong profiles, invalid carriers and missing proof meanings. It hashes before
and after copying and atomically promotes only identical bytes.

```console
reprofig broker promote workspace/candidates/Figure.svg \
  --workspace workspace --destination publication \
  --policy reprofig-output-policy.json \
  --record workspace/scratch/figure-record.json \
  --semantic-bindings workspace/scratch/render-manifest.json
```

`mode="hard"` labels the intended deployment but does not create an operating-
system sandbox itself. Hard enforcement requires filesystem permissions,
container mounts or a service account that cannot write to the destination.
The broker then becomes the only authorized promotion process.

Every language and agent must still supply truthful data, statistics and
semantic bindings. Enforcement guarantees that declared evidence accompanies
the promoted file; it cannot prevent internally consistent fabricated inputs.
