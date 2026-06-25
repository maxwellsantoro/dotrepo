import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { normalizeQueryPath, queryValue } from "../src/worker.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..", "..");

test("query path helpers match the shared parity fixture", async () => {
  const fixturePath = path.join(
    repoRoot,
    "crates",
    "dotrepo-core",
    "tests",
    "fixtures",
    "query-path-cases.json"
  );
  const cases = JSON.parse(await readFile(fixturePath, "utf8"));

  for (const entry of cases) {
    const canonical = normalizeQueryPath(entry.path);
    const actual = queryValue(entry.manifest, canonical);
    assert.deepEqual(actual, entry.expected, `path ${entry.path} drifted`);
  }
});