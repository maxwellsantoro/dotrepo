import fs from "node:fs";
import os from "node:os";
import path from "node:path";
export function compareTaskNames(a, b) {
    return compareStrings(a.options.name, b.options.name);
}
// oxlint-disable-next-line typescript/unbound-method
const compareStrings = new Intl.Collator(undefined, { numeric: true }).compare;
// Exported for testing.
export function simplifyPath(p) {
    const normalized = path.normalize(p);
    const homedir = path.normalize(os.homedir() + path.sep);
    return normalized.startsWith(homedir) ? `~${path.sep}${normalized.slice(homedir.length)}` : normalized;
}
export function findUp(dir, predicate) {
    const root = path.parse(dir).root;
    while (true) {
        const result = predicate(dir);
        if (result !== undefined)
            return result;
        if (dir === root)
            break;
        dir = path.dirname(dir);
    }
    return undefined;
}
export function prettyMilliseconds(ms) {
    if (ms < 1000)
        return `${Math.ceil(ms)}ms`;
    const seconds = (ms / 1000) % 60;
    const minutes = Math.floor(ms / 60000) % 60;
    const hours = Math.floor(ms / 3600000);
    // Round to one decimal, with an epsilon to avoid floating point errors (e.g. 5.0000001 -> 5).
    // Number formatting is already shortest-round-trip, so this prints as "5s" or "5.5s".
    const roundedSeconds = Math.floor(seconds * 10 + 1e-7) / 10;
    return [
        hours > 0 && `${hours}h`,
        minutes > 0 && `${minutes}m`,
        roundedSeconds > 0 && `${roundedSeconds}s`,
    ].filter(Boolean).join(" ");
}
/**
 * UserError is a special error that, when caught in the CLI will be printed
 * as a message only, without stacktrace. Use this instead of process.exit.
 */
export class UserError extends Error {
}
/**
 * Returns the candidate most similar to `target`, if any is close enough
 * to be a plausible typo correction.
 */
export function findSimilar(target, candidates) {
    let best;
    let bestDistance = Math.ceil(target.length * 0.4);
    for (const candidate of candidates) {
        const row = Array.from({ length: candidate.length + 1 }, (_, j) => j);
        for (let i = 1; i <= target.length; i++) {
            let diag = row[0];
            row[0] = i;
            for (let j = 1; j <= candidate.length; j++) {
                const tmp = row[j];
                row[j] = Math.min(row[j - 1] + 1, tmp + 1, diag + (target[i - 1] === candidate[j - 1] ? 0 : 1));
                diag = tmp;
            }
        }
        if (row[candidate.length] < bestDistance) {
            best = candidate;
            bestDistance = row[candidate.length];
        }
    }
    return best;
}
export function real() {
    /* oxlint-disable no-restricted-globals */
    return {
        columns: () => process.stdout.isTTY && process.stdout.columns || 80,
        log: console.log,
        error: console.error,
        // oxlint-disable-next-line typescript/unbound-method
        cwd: process.cwd,
        // oxlint-disable-next-line typescript/unbound-method
        chdir: process.chdir,
        simplifyPath,
        argv: process.argv,
        setExitCode: (code) => {
            process.exitCode = code;
        },
        version: () => {
            const packageJsonURL = new URL("../../package.json", import.meta.url);
            const packageJson = fs.readFileSync(packageJsonURL, "utf8");
            return JSON.parse(packageJson).version;
        },
    };
    /* oxlint-enable no-restricted-globals */
}
//# sourceMappingURL=utils.js.map