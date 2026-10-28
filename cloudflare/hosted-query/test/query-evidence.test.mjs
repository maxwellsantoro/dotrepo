import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { queryFieldEvidence, queryValue, normalizeQueryPath, handleRequest } from "../src/worker.mjs";

const cases = JSON.parse(await readFile(new URL("../../../crates/dotrepo-core/tests/fixtures/query-evidence-cases.json", import.meta.url), "utf8"));
for (const item of cases) {
  test(`value-bound field evidence: ${item.name}`, () => {
    assert.deepEqual(queryFieldEvidence(item.manifest, item.path, queryValue(item.manifest, normalizeQueryPath(item.path))) ?? null, item.expectedEvidence);
  });
}

test("numeric evidence fails closed on unsafe or rounded JSON number tokens", () => {
  const template = cases.find(item => item.name === "maximum-safe-integer");
  for (const [value, valueJson] of [
    [9007199254740992, "9007199254740992"],
    [-9007199254740992, "-9007199254740992"],
    [1, "1.0000000000000001"],
    [0, "1e-400"],
    [Infinity, "1e400"],
    [{ nested: [0.1] }, '{"nested":[0.10000000000000001]}'],
  ]) {
    const manifest = structuredClone(template.manifest);
    manifest.x.example.value = value;
    manifest.x.dotrepo.field_evidence[template.path].valueJson = valueJson;
    assert.equal(queryFieldEvidence(manifest, template.path, value), undefined, valueJson);
  }
});

test("single and batch query wrappers withhold rounded integer assessments", async () => {
  const item = cases.find(item => item.name === "large-integer-rounding-collision");
  const fixture = JSON.parse(await readFile(new URL("../../../crates/dotrepo-core/tests/fixtures/public-export/expected/public/query-input/github.com/example/orbit.json", import.meta.url), "utf8"));
  fixture.selection.manifest = item.manifest;
  const root = "/v0/snapshots/numeric-fixture";
  const files = new Map([
    ["/v0/meta.json", JSON.stringify({ paths: { root } })],
    [`${root}/query-input/github.com/example/orbit.json`, JSON.stringify(fixture)]
  ]);
  const env = { ASSETS: { async fetch(input) {
    const pathname = new URL(input instanceof Request ? input.url : input).pathname;
    return files.has(pathname) ? new Response(files.get(pathname)) : new Response("missing", { status: 404 });
  } } };
  for (const route of ["repos/github.com/example/orbit/query?path=x.example.value", "batch/query?repo=github.com/example/orbit&path=x.example.value"]) {
    const response = await handleRequest(new Request(`https://example.test/v0/${route}`), env);
    assert.equal(response.status, 200);
    const payload = await response.json();
    const query = payload.results ? payload.results[0].query : payload;
    assert.equal(query.value, 9007199254740992);
    assert.equal(Object.hasOwn(query, "fieldEvidence"), false);
  }
});

test("single and batch query wrappers expose only the requested assessment", async () => {
  const root = "/v0/snapshots/fixture";
  const fixture = JSON.parse(await readFile(new URL("../../../crates/dotrepo-core/tests/fixtures/public-export/expected/public/query-input/github.com/example/orbit.json", import.meta.url), "utf8"));
  fixture.selection.manifest = cases[0].manifest;
  const files = new Map([
    ["/v0/meta.json", JSON.stringify({ paths: { root } })],
    [`${root}/query-input/github.com/example/orbit.json`, JSON.stringify(fixture)]
  ]);
  const env = { ASSETS: { async fetch(input) {
    const pathname = new URL(input instanceof Request ? input.url : input).pathname;
    return files.has(pathname) ? new Response(files.get(pathname)) : new Response("missing", { status: 404 });
  } } };
  for (const route of ["repos/github.com/example/orbit/query?path=repo.test", "batch/query?repo=github.com/example/orbit&path=repo.test"]) {
    const response = await handleRequest(new Request(`https://example.test/v0/${route}`), env);
    assert.equal(response.status, 200);
    const payload = await response.json();
    const query = payload.results ? payload.results[0].query : payload;
    assert.deepEqual(query.fieldEvidence, cases[0].expectedEvidence);
    assert.equal(query.value, "cargo test --all");
    assert.equal(query.fieldEvidence.valueJson, undefined);
  }
  delete fixture.selection.manifest.x;
  files.set(`${root}/query-input/github.com/example/orbit.json`, JSON.stringify(fixture));
  // A new env avoids the intentional per-binding immutable snapshot cache.
  const response = await handleRequest(new Request("https://example.test/v0/repos/github.com/example/orbit/query?path=repo.test"), { ASSETS: { fetch: env.ASSETS.fetch } });
  assert.equal(Object.hasOwn(await response.json(), "fieldEvidence"), false);
});
