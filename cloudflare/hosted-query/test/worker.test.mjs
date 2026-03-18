import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { handleRequest } from "../src/worker.mjs";

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
      const body = files.get(url.pathname);
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

test("falls through to static assets after stripping the configured base path", async () => {
  const files = new Map([
    ["/index.html", "<html>dotrepo</html>"],
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
