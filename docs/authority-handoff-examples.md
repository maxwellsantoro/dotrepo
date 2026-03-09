# Authority handoff examples

These examples are non-normative. They illustrate the claim, supersede, and conflict
rules from [`RFC 0004`](../rfcs/0004-index-and-trust-model.md).

## 1. Overlay only

```toml
# index overlay
[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/acme/widget"
```

Outcome:
- the overlay is the preferred record because no higher-authority record exists
- its `record.source`, `record.status`, `record.trust`, and evidence remain the active
  context for consumers
- no claim or supersede relationship is implied yet

## 2. Canonical only

```toml
# maintainer-controlled .repo
[record]
mode = "native"
status = "canonical"
```

Outcome:
- the canonical `.repo` is the preferred record for that repository
- if the index later publishes a canonical mirror, the mirror inherits canonical
  authority for index consumers without outranking the source `.repo`
- no overlay is inferred automatically

## 3. Canonical record supersedes an existing overlay

```toml
# existing index overlay
[record]
mode = "overlay"
status = "verified"
source = "https://github.com/acme/widget"
```

```toml
# later maintainer-controlled .repo
[record]
mode = "native"
status = "canonical"
```

Outcome:
- the canonical record claims the same repository identity and becomes the preferred
  record by default
- the overlay remains inspectable as historical evidence and third-party curation
- consumers should preserve the overlay's trust metadata and evidence trail as visible
  context
- if the canonical record leaves a field missing or intentionally `unknown`, consumers
  should not silently backfill that field from the overlay

## 4. Higher-status overlay supersedes a lower-status overlay

```toml
# imported overlay
[record]
mode = "overlay"
status = "imported"
source = "https://github.com/acme/widget"
```

```toml
# later reviewed overlay
[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/acme/widget"
```

Outcome:
- the reviewed overlay is the preferred record because it has higher authority than the
  imported overlay
- the imported overlay remains visible as lower-authority context
- this is still not canonical authority; it is only the best available overlay

## 5. Equal-status overlays conflict without a canonical record

```toml
# curator A
[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/acme/widget"
```

```toml
# curator B
[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/acme/widget"
```

Outcome:
- consumers should not invent a resolved fact from the disagreement
- both overlays remain parallel claims with visible `record.source`, `record.status`,
  `record.trust`, and evidence
- tools may sort the records deterministically for presentation, but that sort order is
  not itself a claim or supersede decision
