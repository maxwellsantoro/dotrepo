export const PUBLIC_API_VERSION = "v0";

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

function normalizeQueryPath(path) {
  if (path === "" || path === ".") {
    return ".";
  }
  if (path === "trust") {
    return "record.trust";
  }
  if (path.startsWith("trust.")) {
    return `record.${path}`;
  }
  return path;
}

function queryValue(value, path) {
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

async function loadMeta(env, request) {
  const response = await fetchInternalAsset(env, request, "/v0/meta.json");
  if (!response.ok) {
    throw new Error(`failed to load /v0/meta.json: ${response.status}`);
  }
  return response.json();
}

async function loadQueryInputSnapshot(env, request, host, owner, repo) {
  const response = await fetchInternalAsset(
    env,
    request,
    `/query-input/${host}/${owner}/${repo}.json`
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

async function serveStaticAsset(request, env, strippedPath) {
  const assetPath = strippedPath === "/" ? "/" : strippedPath;
  const assetRequest = new Request(new URL(assetPath, request.url), request);
  return env.ASSETS.fetch(assetRequest);
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
  if (strippedPath.startsWith("/query-input/")) {
    return textResponse(404, "not found");
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
