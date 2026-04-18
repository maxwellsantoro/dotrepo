#!/usr/bin/env bash

set -euo pipefail

if command -v node >/dev/null 2>&1; then
  current_node_version="$(node -p 'process.versions.node' 2>/dev/null || true)"
  if [[ "$current_node_version" == 20.* ]]; then
    echo "Using Node.js ${current_node_version} already on PATH"
    node -v
    npm -v
    exit 0
  fi
fi

toolcache_root="${RUNNER_TOOL_CACHE:-/opt/hostedtoolcache}"
shopt -s nullglob
candidates=("$toolcache_root"/node/20.*/x64/bin)
shopt -u nullglob

if [ "${#candidates[@]}" -eq 0 ]; then
  echo "Failed to find preinstalled Node.js 20.x on PATH or under ${toolcache_root}/node" >&2
  exit 1
fi

mapfile -t sorted_candidates < <(printf '%s\n' "${candidates[@]}" | sort -V)
node_bin_dir="${sorted_candidates[-1]}"
export PATH="${node_bin_dir}:$PATH"

if [ -n "${GITHUB_PATH:-}" ]; then
  echo "${node_bin_dir}" >> "${GITHUB_PATH}"
fi

selected_node_version="$(node -p 'process.versions.node')"
if [[ "$selected_node_version" != 20.* ]]; then
  echo "Expected Node.js 20.x after selecting runner toolcache, found ${selected_node_version}" >&2
  exit 1
fi

echo "Using Node.js ${selected_node_version} from ${node_bin_dir}"
node -v
npm -v
