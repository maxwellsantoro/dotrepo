// Exercise generated links through the production Worker, backed by a local export.
import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { handleRequest } from "../cloudflare/hosted-query/src/worker.mjs";

export async function checkPublicLinks(root) {
  root = path.resolve(root);
  const meta = JSON.parse(await readFile(path.join(root, "v0/meta.json"), "utf8"));
  const snapshotRoot = meta.paths.root;
  const basePath = snapshotRoot.slice(0, snapshotRoot.indexOf("/v0/"));
  const origin = "https://dotrepo.org";
  const links = new Set([`${basePath}/sitemap.xml`, `${basePath}/robots.txt`]);
  const errors = [];
  async function pages(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (["v0", "query-input", "sitemaps"].includes(entry.name)) continue;
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) { await pages(file); continue; }
      if (!entry.name.endsWith(".html")) continue;
      const html = await readFile(file, "utf8");
      const pageUrl = `${origin}${basePath}/${path.relative(root, file).split(path.sep).join("/").replace(/index\.html$/, "")}`;
      for (const match of html.matchAll(/\bhref=["']([^"']+)["']/g)) {
        const value = match[1].replaceAll("&amp;", "&");
        if (value.startsWith("#")) continue;
        const url = new URL(value, pageUrl);
        if (url.origin === origin) links.add(url.pathname + url.search);
      }
      if (html.includes("/query-input/")) errors.push(`${file}: exposes internal query-input URL`);
      if (html.includes("function repositoryQueryHref(item)")) {
        const source = html.slice(html.indexOf("function pathSegment(value)"), html.indexOf("function makeLink(href"));
        const context = vm.createContext({});
        vm.runInContext(source + ";this.buildHref = repositoryQueryHref;", context, { timeout: 1000 });
        const inventory = JSON.parse(await readFile(path.join(root, "v0/repos/index.json"), "utf8"));
        for (const entry of inventory.repositories) {
          links.add(context.buildHref({ identity: entry.identity, links: entry.links ?? {} }));
          // Exercise the fallback used when older inventories omit templates too.
          links.add(context.buildHref({ identity: entry.identity, links: {} }));
        }
      }
    }
  }
  await pages(root);
  const env = {
    BASE_PATH: basePath,
    ASSETS: { async fetch(input) {
      const url = new URL(input instanceof Request ? input.url : input.toString());
      let relative = decodeURIComponent(url.pathname);
      if (basePath && relative.startsWith(basePath + "/")) relative = relative.slice(basePath.length);
      let file = path.resolve(root, "." + relative);
      if (file !== root && !file.startsWith(root + path.sep)) return new Response("not found", { status: 404 });
      try {
        if ((await stat(file)).isDirectory()) file = path.join(file, "index.html");
        return new Response(await readFile(file), { headers: { "content-type": file.endsWith(".json") ? "application/json" : "text/plain" } });
      } catch { return new Response("not found", { status: 404 }); }
    } }
  };
  for (const link of links) {
    const response = await handleRequest(new Request(new URL(link, origin)), env);
    if (!response.ok) errors.push(`${link}: ${response.status}`);
  }
  // Internal backing artifacts must remain private, including immutable copies.
  const inventory = JSON.parse(await readFile(path.join(root, "v0/repos/index.json"), "utf8"));
  const identity = inventory.repositories[0]?.identity;
  if (identity) {
    const input = `/query-input/${identity.host}/${identity.owner}/${identity.repo}.json`;
    for (const route of [`${basePath}${input}`, `${meta.paths.root}${input}`]) {
      const response = await handleRequest(new Request(origin + route), env);
      if (response.status !== 404) errors.push(`${route}: internal input became public`);
    }
  }
  return { checked: links.size, errors };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = await checkPublicLinks(process.argv[2]);
  console.log(JSON.stringify(report, null, 2));
  process.exitCode = report.errors.length ? 1 : 0;
}
