# Language-neutral adapters

The broker contract separates rendering from evidence verification. A producer
creates three files inside one controlled workspace:

1. the candidate figure in `candidates/`;
2. a package-neutral `reprofig/1` JSON record;
3. optionally a `reprofig-render-manifest/1` JSON file with semantic bindings.

The broker embeds the record, attaches carrier-specific visual references,
applies the common output policy and promotes only after verification.

Reference wrappers are supplied in `adapters/` for R, Julia, JavaScript and
MATLAB. They invoke:

```console
reprofig broker promote CANDIDATE --workspace WORKSPACE \
  --destination DESTINATION --policy POLICY --record RECORD \
  --semantic-bindings BINDINGS
```

The semantic manifest is language-neutral. Axes declare scale, limits and
normalized figure bounding box. Marks declare stable ID, kind, geometry,
coordinate system and optional table rows/columns. Annotations declare exact
text, position, optional statistic ID and formatter ID.

An adapter is not allowed to promote directly. It should propagate the broker
exit code and receipt, avoid secrets in command arguments, and write only below
the workspace. Passwords remain in environment variables explicitly named by
the policy. A wrapper can omit semantic bindings; the result can still pass
integrity, source/statistics and signature checks, but `display_verified` is
unavailable.
