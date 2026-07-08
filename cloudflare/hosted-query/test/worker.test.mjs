import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { handleRequest, logLookupMiss } from "../src/worker.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..", "..");

function fixturePath(...parts) {
  return path.join(repoRoot, ...parts);
}

async function readJson(...parts) {
  return JSON.parse(await readFile(fixturePath(...parts), "utf8"));
}

function makeAssets(files) {
  return {
    async fetch(input) {
      const url =
        input instanceof Request ? new URL(input.url) : new URL(input.toString());
      let body = files.get(url.pathname);
      if (body === undefined) {
        const snapshotMatch = url.pathname.match(/^\/v0\/snapshots\/[^/]+(\/.*)$/);
        if (snapshotMatch !== null) {
          const suffix = snapshotMatch[1];
          const legacyPath = suffix.startsWith("/repos/")
            ? `/v0${suffix}`
            : suffix === "/files.json"
              ? "/v0/files.json"
              : suffix;
          body = files.get(legacyPath);
        }
      }
      if (body === undefined) {
        return new Response("not found", { status: 404 });
      }
      return new Response(body, {
        status: 200,
        headers: {
          "content-type": url.pathname.endsWith(".json")
            ? "application/json; charset=utf-8"
            : "text/plain; charset=utf-8"
        }
      });
    }
  };
}

function makeR2Archive(files) {
  return {
    async get(key) {
      const body = files.get(key);
      if (body === undefined) {
        return null;
      }
      return {
        body,
        httpEtag: `"${key.length.toString(16)}"`
      };
    }
  };
}

test("serves query responses from exported query-input fixtures", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "v0",
          "meta.json"
        ),
        "utf8"
      )
    ],
    [
      "/query-input/github.com/example/orbit.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "query-input",
          "github.com",
          "example",
          "orbit.json"
        ),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };
  const response = await handleRequest(
    new Request(
      "https://example.test/v0/repos/github.com/example/orbit/query?path=repo.description"
    ),
    env
  );

  assert.equal(response.status, 200);
  assert.deepEqual(
    await response.json(),
    await readJson(
      "crates",
      "dotrepo-core",
      "tests",
      "fixtures",
      "public-query",
      "expected",
      "orbit-description.json"
    )
  );
});

test("serves hosted batch profile responses with item errors", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "v0",
          "meta.json"
        ),
        "utf8"
      )
    ],
    [
      "/v0/repos/github.com/example/orbit/profile.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "v0",
          "repos",
          "github.com",
          "example",
          "orbit",
          "profile.json"
        ),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };
  const response = await handleRequest(
    new Request(
      "https://example.test/v0/batch/profiles?repo=github.com/example/orbit&repo=github.com/missing/repo"
    ),
    env
  );
  const json = await response.json();

  assert.equal(response.status, 200);
  assert.equal(json.apiVersion, "v0");
  assert.equal(json.resultCount, 2);
  assert.equal(json.results[0].profile.purpose, "Reviewed orbital tooling metadata.");
  assert.equal(json.results[1].identity.host, "github.com");
  assert.equal(json.results[1].error.code, "repository_not_found");
});

test("serves hosted batch query responses with path-level item errors", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "v0",
          "meta.json"
        ),
        "utf8"
      )
    ],
    [
      "/query-input/github.com/example/orbit.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "query-input",
          "github.com",
          "example",
          "orbit.json"
        ),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/dotrepo" };
  const response = await handleRequest(
    new Request(
      "https://example.test/dotrepo/v0/batch/query?repo=https%3A%2F%2Fgithub.com%2Fexample%2Forbit&path=repo.description&path=repo.missing_field"
    ),
    env
  );
  const json = await response.json();

  assert.equal(response.status, 200);
  assert.equal(json.repositoryCount, 1);
  assert.equal(json.pathCount, 2);
  assert.equal(json.resultCount, 2);
  assert.equal(json.results[0].query.value, "Reviewed orbital tooling metadata.");
  assert.equal(
    json.results[0].query.links.self,
    "/dotrepo/v0/repos/github.com/example/orbit/query?path=repo.description"
  );
  assert.equal(json.results[1].error.code, "query_path_not_found");
});

test("serves hosted profile search from staged profiles", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "meta.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/index.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "index.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/github.com/example/orbit/profile.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "github.com", "example", "orbit", "profile.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/github.com/example/nova/profile.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "github.com", "example", "nova", "profile.json"),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/dotrepo" };
  const response = await handleRequest(
    new Request(
      "https://example.test/dotrepo/v0/search?q=orbit&status=reviewed&require-docs&require-security-contact"
    ),
    env
  );
  const json = await response.json();

  assert.equal(response.status, 200);
  assert.equal(json.query, "orbit");
  assert.equal(json.matchedCount, 1);
  assert.equal(json.returnedCount, 1);
  assert.equal(json.results[0].identity.repo, "orbit");
  assert.equal(json.filters.requireDocs, true);
});

test("serves simple hosted profile search from inventory without profile fan-out", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "meta.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/index.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "index.json"),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/dotrepo" };
  const response = await handleRequest(
    new Request("https://example.test/dotrepo/v0/search?q=orbit"),
    env
  );
  const json = await response.json();

  assert.equal(response.status, 200);
  assert.equal(json.matchedCount, 1);
  assert.equal(json.returnedCount, 1);
  assert.equal(json.results[0].identity.repo, "orbit");
  assert.equal(json.results[0].purpose, "Reviewed orbital tooling metadata.");
});

test("serves hosted factual compare from staged profiles", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "meta.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/github.com/example/orbit/profile.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "github.com", "example", "orbit", "profile.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/github.com/example/nova/profile.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "github.com", "example", "nova", "profile.json"),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/dotrepo" };
  const response = await handleRequest(
    new Request(
      "https://example.test/dotrepo/v0/compare?repo=github.com/example/orbit&repo=github.com/example/nova"
    ),
    env
  );
  const json = await response.json();

  assert.equal(response.status, 200);
  assert.equal(json.repositoryCount, 2);
  assert.equal(json.results[0].identity.repo, "orbit");
  assert.equal(json.results[0].links.self, "/v0/repos/github.com/example/orbit/profile.json");
  assert.equal(json.signals.hasDocs[0].value, true);
  assert.equal(json.signals.hasDocs[1].value, false);
});

test("serves hosted relation traversal from query-input snapshots", async () => {
  const orbitSnapshot = await readJson(
    "crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public",
    "query-input", "github.com", "example", "orbit.json"
  );
  orbitSnapshot.selection.manifest.relations.links = [
    {
      kind: "dependency",
      target: "github.com/example/nova",
      notes: "Runtime integration.",
      trust: { confidence: "high", provenance: ["declared"] }
    }
  ];
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "meta.json"),
        "utf8"
      )
    ],
    [
      "/query-input/github.com/example/orbit.json",
      JSON.stringify(orbitSnapshot)
    ],
    [
      "/query-input/github.com/example/nova.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "query-input", "github.com", "example", "nova.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/index.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "index.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/github.com/example/nova/profile.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "github.com", "example", "nova", "profile.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/github.com/example/orbit/profile.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "repos", "github.com", "example", "orbit", "profile.json"),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/dotrepo" };
  const response = await handleRequest(
    new Request("https://example.test/dotrepo/v0/repos/github.com/example/orbit/relations"),
    env
  );
  const json = await response.json();

  assert.equal(response.status, 200);
  assert.equal(json.relationCount, 2);
  assert.equal(json.references[0].relationship, "dependency");
  assert.equal(json.references[0].direction, "outgoing");
  assert.equal(json.references[0].trust.confidence, "high");
  assert.equal(json.references[0].target, "github.com/example/nova");
  assert.equal(json.references[0].profile.identity.repo, "nova");
  assert.equal(json.links.self, "/dotrepo/v0/repos/github.com/example/orbit/relations");
  assert.equal(json.links.profile, "/dotrepo/v0/repos/github.com/example/orbit/profile.json");

  const reverseResponse = await handleRequest(
    new Request("https://example.test/dotrepo/v0/repos/github.com/example/nova/relations"),
    env
  );
  const reverse = await reverseResponse.json();
  assert.equal(reverseResponse.status, 200);
  assert.equal(reverse.relationCount, 2);
  assert.equal(reverse.references[0].relationship, "depended_on_by");
  assert.equal(reverse.references[0].direction, "incoming");
  assert.equal(reverse.references[1].relationship, "referenced_by");
  assert.equal(reverse.references[0].profile.identity.repo, "orbit");
});

test("serves pre-exported relations snapshots without scanning the inventory", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath("crates", "dotrepo-core", "tests", "fixtures", "public-export", "expected", "public", "v0", "meta.json"),
        "utf8"
      )
    ],
    [
      "/v0/repos/github.com/example/orbit/relations.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "v0",
          "repos",
          "github.com",
          "example",
          "orbit",
          "relations.json"
        ),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/dotrepo" };
  const response = await handleRequest(
    new Request("https://example.test/dotrepo/v0/repos/github.com/example/orbit/relations"),
    env
  );
  const json = await response.json();

  assert.equal(response.status, 200);
  assert.equal(json.identity.repo, "orbit");
  assert.ok(Array.isArray(json.references));
});

test("returns the public error contract for invalid identities", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "v0",
          "meta.json"
        ),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };
  const response = await handleRequest(
    new Request(
      "https://example.test/v0/repos/github.com/example%2Fnested/orbit/query?path=repo.description"
    ),
    env
  );

  assert.equal(response.status, 400);
  assert.deepEqual(
    await response.json(),
    await readJson(
      "crates",
      "dotrepo-core",
      "tests",
      "fixtures",
      "public-query",
      "expected",
      "invalid-identity.json"
    )
  );
});

test("returns invalid_repository_identity for malformed percent-encoding", async () => {
  const meta = await readJson(
    "crates",
    "dotrepo-core",
    "tests",
    "fixtures",
    "public-export",
    "expected",
    "public",
    "v0",
    "meta.json"
  );
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "v0",
          "meta.json"
        ),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };
  const response = await handleRequest(
    new Request(
      "https://example.test/v0/repos/github.com/%E0%A4%A/orbit/query?path=repo.description"
    ),
    env
  );

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), {
    apiVersion: "v0",
    freshness: {
      generatedAt: meta.generatedAt,
      snapshotDigest: meta.snapshotDigest,
      staleAfter: meta.staleAfter
    },
    identity: {
      host: "github.com",
      owner: "%E0%A4%A",
      repo: "orbit"
    },
    path: "repo.description",
    error: {
      code: "invalid_repository_identity",
      message: "invalid repository identity: malformed percent-encoding"
    }
  });
});

test("returns repository_not_found when query-input is absent", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      await readFile(
        fixturePath(
          "crates",
          "dotrepo-core",
          "tests",
          "fixtures",
          "public-export",
          "expected",
          "public",
          "v0",
          "meta.json"
        ),
        "utf8"
      )
    ]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };
  const response = await handleRequest(
    new Request(
      "https://example.test/v0/repos/github.com/missing/repo/query?path=repo.description"
    ),
    env
  );

  assert.equal(response.status, 404);
  assert.deepEqual(
    await response.json(),
    await readJson(
      "crates",
      "dotrepo-core",
      "tests",
      "fixtures",
      "public-query",
      "expected",
      "missing-repo.json"
    )
  );
});

test("rejects inherited properties in query paths", async () => {
  const snapshot = {
    apiVersion: "v0",
    freshness: {
      generatedAt: "2026-03-10T18:30:00Z",
      snapshotDigest: "fixture"
    },
    identity: {
      host: "github.com",
      owner: "example",
      repo: "orbit",
      source: "https://github.com/example/orbit"
    },
    selection: {
      reason: "only_matching_record",
      record: {
        manifestPath: "repos/github.com/example/orbit/record.toml",
        record: {
          mode: "overlay",
          status: "reviewed",
          source: "https://github.com/example/orbit"
        }
      },
      manifest: {
        schema: "dotrepo/v0.1",
        record: {
          mode: "overlay",
          status: "reviewed",
          source: "https://github.com/example/orbit"
        },
        repo: {
          name: "orbit",
          description: "Selected description"
        }
      }
    },
    conflicts: []
  };
  const files = new Map([
    [
      "/v0/meta.json",
      JSON.stringify({
        apiVersion: "v0",
        generatedAt: "2026-03-10T18:30:00Z",
        snapshotDigest: "fixture"
      })
    ],
    ["/query-input/github.com/example/orbit.json", JSON.stringify(snapshot)]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };
  const response = await handleRequest(
    new Request(
      "https://example.test/v0/repos/github.com/example/orbit/query?path=repo.__proto__"
    ),
    env
  );

  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), {
    apiVersion: "v0",
    freshness: {
      generatedAt: "2026-03-10T18:30:00Z",
      snapshotDigest: "fixture"
    },
    identity: {
      host: "github.com",
      owner: "example",
      repo: "orbit"
    },
    path: "repo.__proto__",
    error: {
      code: "query_path_not_found",
      message: "query path not found: repo.__proto__"
    }
  });
});

test("falls through to static assets after stripping the configured base path", async () => {
  const files = new Map([
    ["/", "<html>dotrepo</html>"],
    ["/v0/repos/index.json", "{\"ok\":true}"]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/dotrepo" };

  const rootResponse = await handleRequest(
    new Request("https://example.test/dotrepo"),
    env
  );
  assert.equal(rootResponse.status, 200);
  assert.equal(await rootResponse.text(), "<html>dotrepo</html>");

  const inventoryResponse = await handleRequest(
    new Request("https://example.test/dotrepo/v0/repos/index.json"),
    env
  );
  assert.equal(inventoryResponse.status, 200);
  assert.equal(await inventoryResponse.text(), "{\"ok\":true}");
});

test("resolves mutable inventory through the immutable snapshot pointer", async () => {
  const files = new Map([
    [
      "/v0/meta.json",
      JSON.stringify({
        snapshotDigest: "abc123",
        paths: { root: "/v0/snapshots/abc123" }
      })
    ],
    ["/v0/repos/index.json", "{\"snapshot\":\"stale\"}"],
    ["/v0/snapshots/abc123/repos/index.json", "{\"snapshot\":\"abc123\"}"]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };

  const response = await handleRequest(
    new Request("https://example.test/v0/repos/index.json"),
    env
  );

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { snapshot: "abc123" });
  assert.equal(response.headers.get("cache-control"), "no-cache");
});

test("marks pointer and immutable snapshot responses with distinct cache policies", async () => {
  const files = new Map([
    ["/v0/meta.json", "{\"snapshotDigest\":\"abc123\"}"],
    ["/v0/snapshots/abc123/repos/index.json", "{\"ok\":true}"]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };

  const pointer = await handleRequest(
    new Request("https://example.test/v0/meta.json"),
    env
  );
  const snapshot = await handleRequest(
    new Request("https://example.test/v0/snapshots/abc123/repos/index.json"),
    env
  );

  assert.equal(pointer.headers.get("cache-control"), "public, max-age=60, must-revalidate");
  assert.equal(snapshot.headers.get("cache-control"), "public, max-age=31536000, immutable");
});

test("falls through to R2 archive for older immutable snapshots", async () => {
  const files = new Map([
    ["/v0/meta.json", "{\"snapshotDigest\":\"current\"}"]
  ]);
  const archive = new Map([
    ["v0/snapshots/old123/repos/index.json", "{\"snapshot\":\"old123\"}"]
  ]);
  const env = {
    ASSETS: makeAssets(files),
    BASE_PATH: "/",
    SNAPSHOT_ARCHIVE: makeR2Archive(archive)
  };

  const response = await handleRequest(
    new Request("https://example.test/v0/snapshots/old123/repos/index.json"),
    env
  );

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { snapshot: "old123" });
  assert.equal(response.headers.get("cache-control"), "public, max-age=31536000, immutable");
  assert.equal(response.headers.get("x-dotrepo-snapshot-source"), "archive");
});

test("keeps returning 404 for missing archived snapshots", async () => {
  const env = {
    ASSETS: makeAssets(new Map()),
    BASE_PATH: "/",
    SNAPSHOT_ARCHIVE: makeR2Archive(new Map())
  };

  const response = await handleRequest(
    new Request("https://example.test/v0/snapshots/missing/repos/index.json"),
    env
  );

  assert.equal(response.status, 404);
});

test("serves the root document without redirecting through /index.html", async () => {
  const files = new Map([["/", "<html>home</html>"]]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };

  const response = await handleRequest(
    new Request("https://dotrepo.org/"),
    env
  );

  assert.equal(response.status, 200);
  assert.equal(await response.text(), "<html>home</html>");
});

test("does not expose query-input artifacts on the public origin", async () => {
  const files = new Map([
    ["/query-input/github.com/example/orbit.json", "{\"hidden\":true}"]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/" };

  const response = await handleRequest(
    new Request("https://example.test/query-input/github.com/example/orbit.json"),
    env
  );
  assert.equal(response.status, 404);
  assert.equal(await response.text(), "not found");
});

test("redirects non-canonical hosts to the configured apex host", async () => {
  const env = {
    ASSETS: makeAssets(new Map()),
    BASE_PATH: "/",
    CANONICAL_HOST: "dotrepo.org"
  };

  const response = await handleRequest(
    new Request("https://www.dotrepo.org/v0/repos/index.json?x=1"),
    env
  );

  assert.equal(response.status, 308);
  assert.equal(
    response.headers.get("location"),
    "https://dotrepo.org/v0/repos/index.json?x=1"
  );
});

test("preserves equal-authority conflict values from the snapshot", async () => {
  const snapshot = {
    apiVersion: "v0",
    freshness: {
      generatedAt: "2026-03-10T18:30:00Z",
      snapshotDigest: "fixture",
      staleAfter: "2026-03-11T18:30:00Z"
    },
    identity: {
      host: "github.com",
      owner: "example",
      repo: "orbit",
      source: "https://github.com/example/orbit"
    },
    selection: {
      reason: "equal_authority_conflict",
      record: {
        manifestPath: "repos/github.com/example/orbit/record.toml",
        record: {
          mode: "overlay",
          status: "reviewed",
          source: "https://github.com/example/orbit"
        }
      },
      manifest: {
        schema: "dotrepo/v0.1",
        record: {
          mode: "overlay",
          status: "reviewed",
          source: "https://github.com/example/orbit"
        },
        repo: {
          name: "orbit",
          description: "Selected description"
        }
      }
    },
    conflicts: [
      {
        relationship: "parallel",
        reason: "equal_authority_conflict",
        record: {
          manifestPath: "repos/github.com/example/orbit/alt/record.toml",
          record: {
            mode: "overlay",
            status: "reviewed",
            source: "https://github.com/example/orbit"
          }
        },
        manifest: {
          schema: "dotrepo/v0.1",
          record: {
            mode: "overlay",
            status: "reviewed",
            source: "https://github.com/example/orbit"
          },
          repo: {
            name: "orbit",
            description: "Competing description"
          }
        }
      }
    ]
  };

  const files = new Map([
    [
      "/v0/meta.json",
      JSON.stringify({
        apiVersion: "v0",
        generatedAt: "2026-03-10T18:30:00Z",
        snapshotDigest: "fixture",
        staleAfter: "2026-03-11T18:30:00Z"
      })
    ],
    ["/query-input/github.com/example/orbit.json", JSON.stringify(snapshot)]
  ]);
  const env = { ASSETS: makeAssets(files), BASE_PATH: "/dotrepo" };
  const response = await handleRequest(
    new Request(
      "https://example.test/dotrepo/v0/repos/github.com/example/orbit/query?path=repo.description"
    ),
    env
  );
  const json = await response.json();

  assert.equal(response.status, 200);
  assert.equal(json.selection.reason, "equal_authority_conflict");
  assert.equal(json.conflicts[0].relationship, "parallel");
  assert.equal(json.conflicts[0].value, "Competing description");
  assert.equal(
    json.links.self,
    "/dotrepo/v0/repos/github.com/example/orbit/query?path=repo.description"
  );
});

test("logLookupMiss emits structured DOTREPO_LOOKUP_MISS lines", () => {
  const lines = [];
  const original = console.log;
  console.log = (...args) => {
    lines.push(args.join(" "));
  };
  try {
    logLookupMiss(
      { host: "github.com", owner: "acme", repo: "widgets" },
      "query"
    );
  } finally {
    console.log = original;
  }
  assert.equal(lines.length, 1);
  assert.match(lines[0], /^DOTREPO_LOOKUP_MISS \{/);
  const payload = JSON.parse(lines[0].slice("DOTREPO_LOOKUP_MISS ".length));
  assert.equal(payload.host, "github.com");
  assert.equal(payload.owner, "acme");
  assert.equal(payload.repo, "widgets");
  assert.equal(payload.route, "query");
  assert.ok(payload.ts);
});
