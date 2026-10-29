# F-05 public response capture, 2026-10-29

This packet captures the public snapshot advertised by `dotrepo.org/v0/meta.json`
after the twelve-task source roster was frozen. Every enrolled identity was
queried, with case normalization against the snapshot inventory only. No task
was added, replaced, or excluded after consulting the index. Five requests
returned profiles and seven returned HTTP 404. These are response-presence
observations, not applicable-instruction counts or evidence of usefulness.

The immutable snapshot ID is
`bb01b134d0a2d7d913ccf3f0f54327a239d9bce24ac7735259a62bb5630cf976`;
its advertised source digest is
`e45b6ec2719c2b5d59d4acdfa1aa7e61e749810bbfdd3add2fcda1eb0bf97b33`.
`profile-capture/capture.json` binds the pre-existing task roster and source
freeze. `profile-capture/responses.json` has the internal runtime response
shape and binds the exact retained metadata bytes. Consumer policy, completion
oracles, model settings, environment, cost bounds, and launch qualification
remain separate, unfinished gates. No agent sessions ran during this capture.

The initial metadata request succeeded with the default urllib client. Its
headers and exact request timestamp were not retained. Three subsequent
immutable-path requests with that client returned Cloudflare HTTP 403/error
1010; the first raised before its headers/body could be saved. The next two
responses are retained in `initial-immutable-fetch.json`. An explicitly
identified `dotrepo-f05-snapshot/1.0` client then retrieved the file manifest,
inventory, and all twelve profile responses. Those request headers, response
headers, raw bodies, decoded sizes, and hashes are retained. Transport failures
are not counted as missing repositories or correct abstentions.

Each present profile and the inventory match the advertised manifest's hash
and length. Missing profiles have no inventory identity or advertised profile
leaf and returned HTTP 404. Retrieval used HTTPS at the advertised same-origin
immutable paths with redirects refused. Private `query-input/` files were not
fetched. The complete export identity was not recomputed from all public and
private payloads; these checks establish internal consistency with the public
manifest, not an independent authenticity attestation.

Preparation used 18 HTTP requests: one metadata request, three unsuccessful
manifest/inventory requests, two identified manifest/inventory requests, and
twelve profile requests. Known decoded byte counts exclude the body of the
first failed request and all transport overhead. Preparation and maintenance
monetary costs remain unknown. Cache and edge states are those recorded in the
receipts; this capture is not a cold-cache timing experiment.

`collect_profiles.py` preserves each response before checking it and refuses to
overwrite its output directory. A replay is a new observation; retain it in a
new dated packet rather than changing this freeze. All profile and response
bytes are access-arm artifacts: never copy them into the source-first prompt,
source bundle, environment, cache, or upstream tools. `FREEZE.json` binds the
retained files. Earlier source and evaluation packets are unchanged.
