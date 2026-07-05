export const PUBLIC_API_VERSION = "v0";
export const PUBLIC_BATCH_MAX_IDENTITIES = 50;
export const PUBLIC_BATCH_MAX_PATHS = 25;
export const PUBLIC_BATCH_MAX_QUERY_RESULTS = 500;

export const PUBLIC_ERROR_CODES = {
  queryPathNotFound: "query_path_not_found",
  repositoryNotFound: "repository_not_found",
  invalidRepositoryIdentity: "invalid_repository_identity",
  internalError: "internal_error"
};

function normalizeHost(host) {
  return (host ?? "").trim().toLowerCase();
}

function maybeRedirectToCanonicalHost(request, env) {
  const canonicalHost = normalizeHost(env.CANONICAL_HOST);
  if (canonicalHost === "") {
    return null;
  }

  const url = new URL(request.url);
  if (normalizeHost(url.hostname) === canonicalHost) {
    return null;
  }

  url.hostname = canonicalHost;
  return Response.redirect(url.toString(), 308);
}

function normalizeBasePath(basePath) {
  const trimmed = (basePath ?? "/").trim();
  if (trimmed === "" || trimmed === "/") {
    return "/";
  }
  return `/${trimmed.replace(/^\/+|\/+$/g, "")}`;
}

function stripBasePath(pathname, basePath) {
  if (basePath === "/") {
    return pathname === "" ? "/" : pathname;
  }
  if (pathname === basePath) {
    return "/";
  }
  if (pathname.startsWith(`${basePath}/`)) {
    return pathname.slice(basePath.length) || "/";
  }
  return null;
}

function ensureSinglePathSegment(field, value) {
  const trimmed = typeof value === "string" ? value.trim() : "";
  if (trimmed === "") {
    throw new Error(`${field} must not be empty`);
  }
  if (trimmed === "." || trimmed === ".." || trimmed.includes("/")) {
    throw new Error(`${field} must be a single path segment`);
  }
}

function validateRepositoryIdentity(host, owner, repo) {
  for (const [field, value] of [
    ["host", host],
    ["owner", owner],
    ["repo", repo]
  ]) {
    try {
      ensureSinglePathSegment(field, value);
    } catch (error) {
      throw new Error(`invalid repository identity: ${error.message}`);
    }
  }
}

function parseRepositoryParam(value) {
  const trimmed = (value ?? "").trim();
  const withoutScheme = trimmed.replace(/^https?:\/\//, "");
  const withoutGit = withoutScheme.endsWith(".git")
    ? withoutScheme.slice(0, -4)
    : withoutScheme;
  const parts = withoutGit.split("/").filter((part) => part !== "");
  if (parts.length !== 3) {
    return {
      identity: {
        host: trimmed,
        owner: "",
        repo: ""
      },
      error: {
        code: PUBLIC_ERROR_CODES.invalidRepositoryIdentity,
        message: `invalid repository identity: repository must be host/owner/repo or https://host/owner/repo: ${value}`
      }
    };
  }

  const identity = {
    host: parts[0],
    owner: parts[1],
    repo: parts[2]
  };
  try {
    validateRepositoryIdentity(identity.host, identity.owner, identity.repo);
  } catch (error) {
    return {
      identity,
      error: {
        code: PUBLIC_ERROR_CODES.invalidRepositoryIdentity,
        message: error.message
      }
    };
  }

  return { identity, error: null };
}

function decodeRepositoryIdentity(route) {
  try {
    return {
      host: decodeURIComponent(route.host),
      owner: decodeURIComponent(route.owner),
      repo: decodeURIComponent(route.repo)
    };
  } catch {
    throw new Error("invalid repository identity: malformed percent-encoding");
  }
}

export function normalizeQueryPath(path) {
  if (path === "" || path === ".") {
    return ".";
  }
  if (path === "trust") {
    return "record.trust";
  }
  if (path.startsWith("trust.")) {
    return `record.${path}`;
  }
  if (path === "repo.language") {
    return "repo.languages.0";
  }
  if (path === "repo.archived") {
    return "x.github.archived";
  }
  return path;
}

export function queryValue(value, path) {
  if (path === "" || path === ".") {
    return value;
  }

  let current = value;
  for (const segment of path.split(".")) {
    if (Array.isArray(current)) {
      const index = Number.parseInt(segment, 10);
      if (!Number.isInteger(index) || `${index}` !== segment || index < 0 || index >= current.length) {
        throw new Error(`query path not found: ${path}`);
      }
      current = current[index];
      continue;
    }
    if (current && typeof current === "object" && !Array.isArray(current)) {
      if (!Object.hasOwn(current, segment)) {
        throw new Error(`query path not found: ${path}`);
      }
      current = current[segment];
      continue;
    }
    throw new Error(`query path not found: ${path}`);
  }

  return current;
}

function buildRepositoryRoot(host, owner, repo, basePath) {
  const normalized = normalizeBasePath(basePath);
  const prefix = normalized === "/" ? "" : normalized;
  return `${prefix}/v0/repos/${host}/${owner}/${repo}`;
}

function buildQueryLinks(host, owner, repo, path, basePath) {
  const repositoryRoot = buildRepositoryRoot(host, owner, repo, basePath);
  return {
    self: `${repositoryRoot}/query?path=${path}`,
    repository: `${repositoryRoot}/index.json`,
    trust: `${repositoryRoot}/trust.json`,
    profile: `${repositoryRoot}/profile.json`,
    queryTemplate: `${repositoryRoot}/query?path={dot_path}`,
    indexPath: `repos/${host}/${owner}/${repo}/`
  };
}

function buildFreshnessFromMeta(meta) {
  return {
    generatedAt: meta.generatedAt,
    snapshotDigest: meta.snapshotDigest,
    ...(meta.staleAfter ? { staleAfter: meta.staleAfter } : {})
  };
}

async function fetchInternalAsset(env, request, pathname) {
  const assetUrl = new URL(pathname, request.url);
  return env.ASSETS.fetch(assetUrl);
}

async function fetchArchivedSnapshot(env, pathname) {
  if (!pathname.startsWith("/v0/snapshots/") || env.SNAPSHOT_ARCHIVE === undefined) {
    return null;
  }
  const key = pathname.replace(/^\/+/, "");
  const object = await env.SNAPSHOT_ARCHIVE.get(key);
  if (object === null) {
    return null;
  }
  const headers = new Headers();
  headers.set("content-type", pathname.endsWith(".json") ? "application/json; charset=utf-8" : "application/octet-stream");
  headers.set("cache-control", "public, max-age=31536000, immutable");
  headers.set("x-dotrepo-snapshot-source", "archive");
  if (object.httpEtag) {
    headers.set("etag", object.httpEtag);
  }
  return new Response(object.body, { status: 200, headers });
}

async function fetchSnapshotAssetOrArchive(env, request, pathname) {
  const response = await fetchInternalAsset(env, request, pathname);
  if (response.status !== 404) {
    return response;
  }
  return (await fetchArchivedSnapshot(env, pathname)) ?? response;
}

async function loadMeta(env, request) {
  const response = await fetchInternalAsset(env, request, "/v0/meta.json");
  if (!response.ok) {
    throw new Error(`failed to load /v0/meta.json: ${response.status}`);
  }
  return response.json();
}

function snapshotAssetPath(meta, suffix, legacyPath) {
  const root = meta?.paths?.root;
  if (typeof root !== "string" || root === "") {
    return legacyPath;
  }
  const basePath = normalizeBasePath(meta?.paths?.root?.split("/v0/snapshots/")[0] ?? "/");
  const internalRoot = stripBasePath(root, basePath);
  return `${internalRoot}${suffix}`;
}

async function currentSnapshotAssetPath(env, request, suffix, legacyPath) {
  const meta = await loadMeta(env, request);
  return snapshotAssetPath(meta, suffix, legacyPath);
}

async function loadQueryInputSnapshot(env, request, host, owner, repo) {
  const pathname = await currentSnapshotAssetPath(
    env,
    request,
    `/query-input/${host}/${owner}/${repo}.json`,
    `/query-input/${host}/${owner}/${repo}.json`
  );
  const response = await fetchInternalAsset(
    env,
    request,
    pathname
  );
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(
      `failed to load /query-input/${host}/${owner}/${repo}.json: ${response.status}`
    );
  }
  return response.json();
}

async function loadProfileSnapshot(env, request, host, owner, repo) {
  const pathname = await currentSnapshotAssetPath(
    env,
    request,
    `/repos/${host}/${owner}/${repo}/profile.json`,
    `/v0/repos/${host}/${owner}/${repo}/profile.json`
  );
  const response = await fetchInternalAsset(
    env,
    request,
    pathname
  );
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(
      `failed to load /v0/repos/${host}/${owner}/${repo}/profile.json: ${response.status}`
    );
  }
  return response.json();
}

async function loadRelationsSnapshot(env, request, host, owner, repo) {
  const pathname = await currentSnapshotAssetPath(
    env,
    request,
    `/repos/${host}/${owner}/${repo}/relations.json`,
    `/v0/repos/${host}/${owner}/${repo}/relations.json`
  );
  const response = await fetchInternalAsset(
    env,
    request,
    pathname
  );
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(
      `failed to load /v0/repos/${host}/${owner}/${repo}/relations.json: ${response.status}`
    );
  }
  return response.json();
}

async function loadInventorySnapshot(env, request) {
  const pathname = await currentSnapshotAssetPath(
    env,
    request,
    "/repos/index.json",
    "/v0/repos/index.json"
  );
  const response = await fetchInternalAsset(env, request, pathname);
  if (!response.ok) {
    throw new Error(`failed to load /v0/repos/index.json: ${response.status}`);
  }
  return response.json();
}

function repositoryNotFoundMessage(identity) {
  return `repository not found in index: repos/${identity.host}/${identity.owner}/${identity.repo}/record.toml`;
}

function buildPublicErrorDetail(code, message) {
  return {
    code,
    message
  };
}

function buildPublicErrorResponse(identity, path, freshness, code, message) {
  return {
    apiVersion: PUBLIC_API_VERSION,
    freshness,
    identity,
    ...(path === undefined ? {} : { path }),
    error: {
      code,
      message
    }
  };
}

function classifyErrorCode(message) {
  if (message.startsWith("query path not found: ")) {
    return PUBLIC_ERROR_CODES.queryPathNotFound;
  }
  if (message.startsWith("repository not found in index: ")) {
    return PUBLIC_ERROR_CODES.repositoryNotFound;
  }
  if (message.startsWith("invalid repository identity: ")) {
    return PUBLIC_ERROR_CODES.invalidRepositoryIdentity;
  }
  return PUBLIC_ERROR_CODES.internalError;
}

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8"
    }
  });
}

function textResponse(status, body) {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/plain; charset=utf-8"
    }
  });
}

function parseQueryRoute(pathname) {
  const segments = pathname.split("/");
  if (
    segments.length !== 7 ||
    segments[1] !== "v0" ||
    segments[2] !== "repos" ||
    segments[6] !== "query"
  ) {
    return null;
  }

  return {
    host: segments[3],
    owner: segments[4],
    repo: segments[5]
  };
}

function parseRelationsRoute(pathname) {
  const segments = pathname.split("/");
  if (
    segments.length !== 7 ||
    segments[1] !== "v0" ||
    segments[2] !== "repos" ||
    segments[6] !== "relations"
  ) {
    return null;
  }

  return {
    host: segments[3],
    owner: segments[4],
    repo: segments[5]
  };
}

function parseBatchRoute(pathname) {
  if (pathname === "/v0/batch/profiles") {
    return "profiles";
  }
  if (pathname === "/v0/batch/query") {
    return "query";
  }
  return null;
}

function validateBatchRepos(repoParams) {
  if (repoParams.length === 0) {
    throw new Error("batch request requires at least one repository identity");
  }
  if (repoParams.length > PUBLIC_BATCH_MAX_IDENTITIES) {
    throw new Error(
      `batch request exceeds the maximum of ${PUBLIC_BATCH_MAX_IDENTITIES} repositories`
    );
  }
}

function validateBatchQuery(repoParams, paths) {
  validateBatchRepos(repoParams);
  if (paths.length === 0) {
    throw new Error("batch query requires at least one path");
  }
  if (paths.length > PUBLIC_BATCH_MAX_PATHS) {
    throw new Error(`batch query exceeds the maximum of ${PUBLIC_BATCH_MAX_PATHS} paths`);
  }
  const resultCount = repoParams.length * paths.length;
  if (resultCount > PUBLIC_BATCH_MAX_QUERY_RESULTS) {
    throw new Error(
      `batch query exceeds the maximum of ${PUBLIC_BATCH_MAX_QUERY_RESULTS} results`
    );
  }
}

function normalizeSearchValue(value) {
  return `${value ?? ""}`.trim().toLowerCase();
}

function containsNormalized(values, expected) {
  const normalized = normalizeSearchValue(expected);
  return (values ?? []).some((value) => normalizeSearchValue(value) === normalized);
}

function optionMatchesFilter(actual, filters) {
  return filters.length === 0 || filters.some((filter) => normalizeSearchValue(actual) === normalizeSearchValue(filter));
}

function profileMatchesFilters(profile, options) {
  if (!options.languages.every((language) => containsNormalized(profile.languages ?? [], language))) {
    return false;
  }
  if (!options.topics.every((topic) => containsNormalized(profile.topics ?? [], topic))) {
    return false;
  }
  if (!optionMatchesFilter(profile.trust?.selectedStatus, options.statuses)) {
    return false;
  }
  if (!optionMatchesFilter(profile.trust?.confidence, options.confidences)) {
    return false;
  }
  const completeness = profile.completeness ?? {};
  if (options.requireBuild && !completeness.hasBuild) return false;
  if (options.requireTest && !completeness.hasTest) return false;
  if (options.requireDocs && !completeness.hasDocs) return false;
  if (options.requireSecurityContact && !completeness.hasSecurityContact) return false;
  if (options.requireLicense && !completeness.hasLicense) return false;
  return true;
}

function profileQueryMatches(profile, query) {
  const normalized = normalizeSearchValue(query);
  if (normalized === "") {
    return ["all"];
  }
  const fields = [
    ["identity", `${profile.identity?.host}/${profile.identity?.owner}/${profile.identity?.repo}`],
    ["name", profile.name],
    ["purpose", profile.purpose],
    ["homepage", profile.homepage],
    ["license", profile.license]
  ];
  const matched = [];
  for (const [field, value] of fields) {
    if (normalizeSearchValue(value).includes(normalized)) {
      matched.push(field);
    }
  }
  if ((profile.languages ?? []).some((language) => normalizeSearchValue(language).includes(normalized))) {
    matched.push("languages");
  }
  if ((profile.topics ?? []).some((topic) => normalizeSearchValue(topic).includes(normalized))) {
    matched.push("topics");
  }
  return matched;
}

function searchProfileFromInventoryEntry(entry) {
  return {
    identity: entry.identity,
    name: entry.name,
    purpose: entry.description,
    links: entry.links
  };
}

function searchItemFromProfile(profile, matched = ["relation"]) {
  return {
    identity: profile.identity,
    name: profile.name,
    purpose: profile.purpose,
    ...((profile.languages ?? []).length === 0 ? {} : { languages: profile.languages }),
    ...((profile.topics ?? []).length === 0 ? {} : { topics: profile.topics }),
    completeness: profile.completeness,
    trust: profile.trust,
    matched,
    links: profile.links
  };
}

function parseSearchOptions(url) {
  return {
    query: url.searchParams.get("q"),
    languages: url.searchParams.getAll("language").filter((value) => value.trim() !== ""),
    topics: url.searchParams.getAll("topic").filter((value) => value.trim() !== ""),
    statuses: url.searchParams.getAll("status").filter((value) => value.trim() !== ""),
    confidences: url.searchParams.getAll("confidence").filter((value) => value.trim() !== ""),
    requireBuild: url.searchParams.has("requireBuild") || url.searchParams.has("require-build"),
    requireTest: url.searchParams.has("requireTest") || url.searchParams.has("require-test"),
    requireDocs: url.searchParams.has("requireDocs") || url.searchParams.has("require-docs"),
    requireSecurityContact: url.searchParams.has("requireSecurityContact") || url.searchParams.has("require-security-contact"),
    requireLicense: url.searchParams.has("requireLicense") || url.searchParams.has("require-license"),
    limit: url.searchParams.has("limit") ? Number.parseInt(url.searchParams.get("limit"), 10) : null
  };
}

function searchRequiresProfileSnapshots(options) {
  return (
    options.languages.length > 0 ||
    options.topics.length > 0 ||
    options.statuses.length > 0 ||
    options.confidences.length > 0 ||
    options.requireBuild ||
    options.requireTest ||
    options.requireDocs ||
    options.requireSecurityContact ||
    options.requireLicense
  );
}

async function loadInventoryProfiles(env, request) {
  const inventory = await loadInventorySnapshot(env, request);
  const repositories = Array.isArray(inventory.repositories) ? inventory.repositories : [];
  const profiles = [];
  for (const entry of repositories) {
    const identity = entry.identity ?? {};
    const profile = await loadProfileSnapshot(env, request, identity.host, identity.owner, identity.repo);
    if (profile !== null) {
      profiles.push(profile);
    }
  }
  return { inventory, profiles };
}

async function buildSearchResponse(env, request, url, freshness) {
  const options = parseSearchOptions(url);
  const inventory = await loadInventorySnapshot(env, request);
  const repositories = Array.isArray(inventory.repositories) ? inventory.repositories : [];
  const profiles = searchRequiresProfileSnapshots(options)
    ? (await loadInventoryProfiles(env, request)).profiles
    : repositories.map(searchProfileFromInventoryEntry);
  let results = [];
  for (const profile of profiles) {
    if (!profileMatchesFilters(profile, options)) {
      continue;
    }
    const matched = options.query === null ? ["filters"] : profileQueryMatches(profile, options.query);
    if (matched.length === 0) {
      continue;
    }
    results.push(searchItemFromProfile(profile, matched));
  }
  results.sort((left, right) => {
    const matched = right.matched.length - left.matched.length;
    if (matched !== 0) return matched;
    return `${left.identity.host}/${left.identity.owner}/${left.identity.repo}`.localeCompare(
      `${right.identity.host}/${right.identity.owner}/${right.identity.repo}`
    );
  });
  const matchedCount = results.length;
  if (Number.isInteger(options.limit) && options.limit >= 0) {
    results = results.slice(0, options.limit);
  }
  return {
    apiVersion: PUBLIC_API_VERSION,
    freshness,
    query: options.query,
    filters: {
      languages: options.languages,
      topics: options.topics,
      statuses: options.statuses,
      confidences: options.confidences,
      requireBuild: options.requireBuild,
      requireTest: options.requireTest,
      requireDocs: options.requireDocs,
      requireSecurityContact: options.requireSecurityContact,
      requireLicense: options.requireLicense,
      ...(options.limit === null ? {} : { limit: options.limit })
    },
    totalRepositoryCount: inventory.repositoryCount ?? profiles.length,
    matchedCount,
    returnedCount: results.length,
    results
  };
}

function compareItemFromProfile(profile) {
  return {
    identity: profile.identity,
    name: profile.name,
    purpose: profile.purpose,
    ...(profile.homepage ? { homepage: profile.homepage } : {}),
    ...(profile.license ? { license: profile.license } : {}),
    ...((profile.languages ?? []).length === 0 ? {} : { languages: profile.languages }),
    ...((profile.topics ?? []).length === 0 ? {} : { topics: profile.topics }),
    execution: profile.execution ?? {},
    docs: profile.docs ?? {},
    ownership: profile.ownership ?? {},
    completeness: profile.completeness,
    trust: profile.trust,
    links: profile.links
  };
}

function sharedValues(items, key) {
  if (items.length === 0) return [];
  let shared = new Set((items[0][key] ?? []).map(normalizeSearchValue));
  for (const item of items.slice(1)) {
    const values = new Set((item[key] ?? []).map(normalizeSearchValue));
    shared = new Set([...shared].filter((value) => values.has(value)));
  }
  return (items[0][key] ?? []).filter((value) => shared.has(normalizeSearchValue(value)));
}

function textSignals(items, select) {
  return items.map((item) => {
    const value = select(item);
    return {
      identity: item.identity,
      ...(value === undefined || value === null ? {} : { value })
    };
  });
}

function boolSignals(items, select) {
  return items.map((item) => ({
    identity: item.identity,
    value: Boolean(select(item))
  }));
}

function compareSignals(items) {
  return {
    sharedLanguages: sharedValues(items, "languages"),
    sharedTopics: sharedValues(items, "topics"),
    licenses: textSignals(items, (item) => item.license),
    selectedStatuses: textSignals(items, (item) => item.trust?.selectedStatus),
    confidences: textSignals(items, (item) => item.trust?.confidence),
    hasBuild: boolSignals(items, (item) => item.completeness?.hasBuild),
    hasTest: boolSignals(items, (item) => item.completeness?.hasTest),
    hasDocs: boolSignals(items, (item) => item.completeness?.hasDocs),
    hasSecurityContact: boolSignals(items, (item) => item.completeness?.hasSecurityContact),
    hasLicense: boolSignals(items, (item) => item.completeness?.hasLicense)
  };
}

async function buildCompareResponse(env, request, repoParams, freshness) {
  const results = [];
  for (const repoParam of repoParams) {
    const parsed = parseRepositoryParam(repoParam);
    if (parsed.error) {
      throw new Error(parsed.error.message);
    }
    const profile = await loadProfileSnapshot(
      env,
      request,
      parsed.identity.host,
      parsed.identity.owner,
      parsed.identity.repo
    );
    if (profile === null) {
      throw new Error(repositoryNotFoundMessage(parsed.identity));
    }
    results.push(compareItemFromProfile(profile));
  }
  return {
    apiVersion: PUBLIC_API_VERSION,
    freshness,
    repositoryCount: results.length,
    results,
    signals: compareSignals(results)
  };
}

async function buildRelationsResponse(env, request, identity, freshness, basePath) {
  const exported = await loadRelationsSnapshot(
    env,
    request,
    identity.host,
    identity.owner,
    identity.repo
  );
  if (exported !== null) {
    return exported;
  }

  const snapshot = await loadQueryInputSnapshot(env, request, identity.host, identity.owner, identity.repo);
  if (snapshot === null) {
    throw new Error(repositoryNotFoundMessage(identity));
  }
  const relationNames = {
    reference: ["reference", "referenced_by"],
    alternative: ["alternative", "alternative"],
    dependency: ["dependency", "depended_on_by"],
    predecessor: ["predecessor", "successor"],
    fork: ["fork", "forked_by"],
    related: ["related", "related"]
  };
  const manifestRelations = snapshot.selection?.manifest?.relations ?? {};
  const relations = (manifestRelations.references ?? []).map((target) => ({
    relationship: "reference",
    inverseRelationship: "referenced_by",
    target
  }));
  for (const link of manifestRelations.links ?? []) {
    const names = relationNames[link.kind];
    if (!names) continue;
    relations.push({
      relationship: names[0],
      inverseRelationship: names[1],
      target: link.target,
      ...(link.notes ? { notes: link.notes } : {}),
      ...(link.trust ? { trust: link.trust } : {})
    });
  }
  const items = [];
  async function appendItem(relation, target, direction) {
    const parsed = parseRepositoryParam(target);
    const item = {
      relationship: relation.relationship,
      direction,
      target,
      ...(relation.notes ? { notes: relation.notes } : {}),
      ...(relation.trust ? { trust: relation.trust } : {})
    };
    if (parsed.error) {
      items.push(item);
      return;
    }
    item.identity = parsed.identity;
    const profile = await loadProfileSnapshot(
      env,
      request,
      parsed.identity.host,
      parsed.identity.owner,
      parsed.identity.repo
    );
    if (profile === null) {
      item.error = buildPublicErrorDetail(
        PUBLIC_ERROR_CODES.repositoryNotFound,
        repositoryNotFoundMessage(parsed.identity)
      );
    } else {
      item.identity = profile.identity;
      item.profile = searchItemFromProfile(profile, ["relation"]);
    }
    items.push(item);
  }
  for (const relation of relations) {
    await appendItem(relation, relation.target, "outgoing");
  }

  const selectedKey = `${identity.host}/${identity.owner}/${identity.repo}`;
  const inventory = await loadInventorySnapshot(env, request);
  for (const entry of inventory.repositories ?? []) {
    const candidate = entry.identity ?? {};
    const candidateKey = `${candidate.host}/${candidate.owner}/${candidate.repo}`;
    if (candidateKey === selectedKey) continue;
    const candidateSnapshot = await loadQueryInputSnapshot(
      env,
      request,
      candidate.host,
      candidate.owner,
      candidate.repo
    );
    if (candidateSnapshot === null) continue;
    const candidateRelations = candidateSnapshot.selection?.manifest?.relations ?? {};
    const links = (candidateRelations.references ?? []).map((target) => ({
      relationship: "reference",
      inverseRelationship: "referenced_by",
      target
    }));
    for (const link of candidateRelations.links ?? []) {
      const names = relationNames[link.kind];
      if (!names) continue;
      links.push({
        relationship: names[0],
        inverseRelationship: names[1],
        target: link.target,
        ...(link.notes ? { notes: link.notes } : {}),
        ...(link.trust ? { trust: link.trust } : {})
      });
    }
    for (const link of links) {
      const parsed = parseRepositoryParam(link.target);
      if (parsed.error) continue;
      const targetKey = `${parsed.identity.host}/${parsed.identity.owner}/${parsed.identity.repo}`;
      if (targetKey !== selectedKey) continue;
      await appendItem(
        { ...link, relationship: link.inverseRelationship },
        candidateKey,
        "incoming"
      );
    }
  }
  items.sort((left, right) =>
    left.direction.localeCompare(right.direction) ||
    left.relationship.localeCompare(right.relationship) ||
    left.target.localeCompare(right.target)
  );
  return {
    apiVersion: PUBLIC_API_VERSION,
    freshness,
    identity: snapshot.identity,
    relationCount: items.length,
    references: items,
    links: {
      self: `${buildRepositoryRoot(identity.host, identity.owner, identity.repo, basePath)}/relations`,
      repository: `${buildRepositoryRoot(identity.host, identity.owner, identity.repo, basePath)}/index.json`,
      profile: `${buildRepositoryRoot(identity.host, identity.owner, identity.repo, basePath)}/profile.json`,
      trust: `${buildRepositoryRoot(identity.host, identity.owner, identity.repo, basePath)}/trust.json`,
      queryTemplate: `${buildRepositoryRoot(identity.host, identity.owner, identity.repo, basePath)}/query?path={dot_path}`,
      indexPath: `repos/${identity.host}/${identity.owner}/${identity.repo}/`
    }
  };
}

function buildQueryResponse(snapshot, path, basePath) {
  if (snapshot.apiVersion !== PUBLIC_API_VERSION) {
    throw new Error(`unsupported public query input apiVersion: ${snapshot.apiVersion}`);
  }

  const normalizedPath = normalizeQueryPath(path);
  const value = queryValue(snapshot.selection.manifest, normalizedPath);
  const conflicts = snapshot.conflicts.map((conflict) => {
    let competingValue;
    try {
      competingValue = queryValue(conflict.manifest, normalizedPath);
    } catch {
      competingValue = undefined;
    }
    return {
      relationship: conflict.relationship,
      reason: conflict.reason,
      ...(competingValue === undefined ? {} : { value: competingValue }),
      record: conflict.record
    };
  });

  return {
    apiVersion: PUBLIC_API_VERSION,
    freshness: snapshot.freshness,
    identity: snapshot.identity,
    path,
    value,
    selection: {
      reason: snapshot.selection.reason,
      record: snapshot.selection.record
    },
    conflicts,
    links: buildQueryLinks(
      snapshot.identity.host,
      snapshot.identity.owner,
      snapshot.identity.repo,
      path,
      basePath
    )
  };
}

async function buildBatchProfileItem(env, request, repoParam) {
  const parsed = parseRepositoryParam(repoParam);
  if (parsed.error) {
    return {
      identity: parsed.identity,
      error: parsed.error
    };
  }

  const profile = await loadProfileSnapshot(
    env,
    request,
    parsed.identity.host,
    parsed.identity.owner,
    parsed.identity.repo
  );
  if (profile === null) {
    return {
      identity: parsed.identity,
      error: buildPublicErrorDetail(
        PUBLIC_ERROR_CODES.repositoryNotFound,
        repositoryNotFoundMessage(parsed.identity)
      )
    };
  }

  return {
    identity: profile.identity,
    profile
  };
}

async function buildBatchQueryItem(env, request, repoParam, path, basePath) {
  const parsed = parseRepositoryParam(repoParam);
  if (parsed.error) {
    return {
      identity: parsed.identity,
      path,
      error: parsed.error
    };
  }

  const snapshot = await loadQueryInputSnapshot(
    env,
    request,
    parsed.identity.host,
    parsed.identity.owner,
    parsed.identity.repo
  );
  if (snapshot === null) {
    return {
      identity: parsed.identity,
      path,
      error: buildPublicErrorDetail(
        PUBLIC_ERROR_CODES.repositoryNotFound,
        repositoryNotFoundMessage(parsed.identity)
      )
    };
  }

  try {
    return {
      identity: snapshot.identity,
      path,
      query: buildQueryResponse(snapshot, path, basePath)
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      identity: parsed.identity,
      path,
      error: buildPublicErrorDetail(classifyErrorCode(message), message)
    };
  }
}

async function buildBatchProfileResponse(env, request, repoParams, freshness) {
  const results = [];
  for (const repoParam of repoParams) {
    results.push(await buildBatchProfileItem(env, request, repoParam));
  }
  return {
    apiVersion: PUBLIC_API_VERSION,
    freshness,
    resultCount: results.length,
    results
  };
}

async function buildBatchQueryResponse(env, request, repoParams, paths, freshness, basePath) {
  const results = [];
  for (const repoParam of repoParams) {
    for (const path of paths) {
      results.push(await buildBatchQueryItem(env, request, repoParam, path, basePath));
    }
  }
  return {
    apiVersion: PUBLIC_API_VERSION,
    freshness,
    repositoryCount: repoParams.length,
    pathCount: paths.length,
    resultCount: results.length,
    results
  };
}

function withCacheControl(response, cacheControl) {
  const headers = new Headers(response.headers);
  headers.set("cache-control", cacheControl);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

async function serveStaticAsset(request, env, strippedPath) {
  let assetPath = strippedPath === "/" ? "/" : strippedPath;
  let cacheControl = null;
  if (strippedPath === "/v0/meta.json") {
    cacheControl = "public, max-age=60, must-revalidate";
  } else if (strippedPath === "/v0/stats.json" || strippedPath === "/v0/snapshots/log.json") {
    cacheControl = "no-cache";
  } else if (strippedPath === "/v0/files.json" || strippedPath.startsWith("/v0/repos/")) {
    try {
      const meta = await loadMeta(env, request);
      assetPath = snapshotAssetPath(
        meta,
        strippedPath === "/v0/files.json"
          ? "/files.json"
          : strippedPath.slice("/v0".length),
        strippedPath
      );
    } catch {
      // Legacy and local fixture exports may not yet have a pointer. Serving
      // their thin mutable copy preserves compatibility during migration.
      assetPath = strippedPath;
    }
    cacheControl = "no-cache";
  } else if (strippedPath.startsWith("/v0/snapshots/")) {
    cacheControl = "public, max-age=31536000, immutable";
  }
  const assetRequest = new Request(new URL(assetPath, request.url), request);
  const response = assetPath.startsWith("/v0/snapshots/")
    ? await fetchSnapshotAssetOrArchive(env, assetRequest, assetPath)
    : await env.ASSETS.fetch(assetRequest);
  return cacheControl === null ? response : withCacheControl(response, cacheControl);
}

export async function handleRequest(request, env) {
  const redirect = maybeRedirectToCanonicalHost(request, env);
  if (redirect) {
    return redirect;
  }

  const basePath = normalizeBasePath(env.BASE_PATH);
  const url = new URL(request.url);

  if (url.pathname === "/healthz") {
    return textResponse(200, "ok");
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    return textResponse(405, "method not allowed");
  }

  const strippedPath = stripBasePath(url.pathname, basePath);
  if (strippedPath === null) {
    return textResponse(404, "not found");
  }
  if (strippedPath.startsWith("/query-input/") || strippedPath.includes("/query-input/")) {
    return textResponse(404, "not found");
  }

  if (strippedPath === "/v0/search") {
    const meta = await loadMeta(env, request);
    const freshness = buildFreshnessFromMeta(meta);
    return jsonResponse(200, await buildSearchResponse(env, request, url, freshness));
  }

  if (strippedPath === "/v0/compare") {
    const repoParams = url.searchParams.getAll("repo").filter((value) => value.trim() !== "");
    if (repoParams.length === 0) {
      return textResponse(400, "missing query parameter `repo`");
    }
    const meta = await loadMeta(env, request);
    const freshness = buildFreshnessFromMeta(meta);
    try {
      return jsonResponse(200, await buildCompareResponse(env, request, repoParams, freshness));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return jsonResponse(
        classifyErrorCode(message) === PUBLIC_ERROR_CODES.invalidRepositoryIdentity ? 400 : 404,
        {
          apiVersion: PUBLIC_API_VERSION,
          freshness,
          error: buildPublicErrorDetail(classifyErrorCode(message), message)
        }
      );
    }
  }

  const relationsRoute = parseRelationsRoute(strippedPath);
  if (relationsRoute !== null) {
    const meta = await loadMeta(env, request);
    const freshness = buildFreshnessFromMeta(meta);
    let identity = relationsRoute;
    try {
      identity = decodeRepositoryIdentity(relationsRoute);
      validateRepositoryIdentity(identity.host, identity.owner, identity.repo);
      return jsonResponse(200, await buildRelationsResponse(env, request, identity, freshness, basePath));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const code = classifyErrorCode(message);
      return jsonResponse(
        code === PUBLIC_ERROR_CODES.invalidRepositoryIdentity ? 400 : 404,
        buildPublicErrorResponse(identity, undefined, freshness, code, message)
      );
    }
  }

  const batchRoute = parseBatchRoute(strippedPath);
  if (batchRoute !== null) {
    if (request.method !== "GET") {
      return textResponse(405, "method not allowed");
    }
    const repoParams = url.searchParams.getAll("repo").filter((value) => value.trim() !== "");
    if (repoParams.length === 0) {
      return textResponse(400, "missing query parameter `repo`");
    }
    try {
      if (batchRoute === "profiles") {
        validateBatchRepos(repoParams);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return textResponse(400, message);
    }
    const meta = await loadMeta(env, request);
    const freshness = buildFreshnessFromMeta(meta);
    if (batchRoute === "profiles") {
      return jsonResponse(
        200,
        await buildBatchProfileResponse(env, request, repoParams, freshness)
      );
    }

    const paths = url.searchParams.getAll("path").filter((value) => value.trim() !== "");
    if (paths.length === 0) {
      return textResponse(400, "missing query parameter `path`");
    }
    try {
      validateBatchQuery(repoParams, paths);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return textResponse(400, message);
    }
    return jsonResponse(
      200,
      await buildBatchQueryResponse(env, request, repoParams, paths, freshness, basePath)
    );
  }

  const route = parseQueryRoute(strippedPath);
  if (route === null) {
    return serveStaticAsset(request, env, strippedPath);
  }

  if (request.method !== "GET") {
    return textResponse(405, "method not allowed");
  }

  const requestedPath = url.searchParams.get("path");
  if (requestedPath === null || requestedPath.trim() === "") {
    return textResponse(400, "missing query parameter `path`");
  }

  const meta = await loadMeta(env, request);
  const fallbackFreshness = buildFreshnessFromMeta(meta);
  const rawIdentity = {
    host: route.host,
    owner: route.owner,
    repo: route.repo
  };
  let identity = rawIdentity;

  try {
    identity = decodeRepositoryIdentity(route);
    validateRepositoryIdentity(identity.host, identity.owner, identity.repo);
  } catch (error) {
    return jsonResponse(
      400,
      buildPublicErrorResponse(
        identity,
        requestedPath,
        fallbackFreshness,
        PUBLIC_ERROR_CODES.invalidRepositoryIdentity,
        error.message
      )
    );
  }

  try {
    const snapshot = await loadQueryInputSnapshot(
      env,
      request,
      identity.host,
      identity.owner,
      identity.repo
    );
    if (snapshot === null) {
      return jsonResponse(
        404,
        buildPublicErrorResponse(
          identity,
          requestedPath,
          fallbackFreshness,
          PUBLIC_ERROR_CODES.repositoryNotFound,
          `repository not found in index: repos/${identity.host}/${identity.owner}/${identity.repo}/record.toml`
        )
      );
    }

    return jsonResponse(200, buildQueryResponse(snapshot, requestedPath, basePath));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const code = classifyErrorCode(message);
    const status =
      code === PUBLIC_ERROR_CODES.invalidRepositoryIdentity
        ? 400
        : code === PUBLIC_ERROR_CODES.internalError
          ? 500
          : 404;
    return jsonResponse(
      status,
      buildPublicErrorResponse(
        identity,
        requestedPath,
        fallbackFreshness,
        code,
        message
      )
    );
  }
}

const worker = {
  async fetch(request, env) {
    return handleRequest(request, env);
  }
};

export default worker;
