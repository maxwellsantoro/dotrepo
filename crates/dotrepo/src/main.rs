// Installable alias for `dotrepo-cli`. Dispatch lives in `dotrepo_cli::run` /
// `dotrepo_cli::main` so this binary cannot drift from the workspace CLI.

fn main() {
    dotrepo_cli::main();
}
