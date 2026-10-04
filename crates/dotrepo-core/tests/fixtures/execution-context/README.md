# Execution context fixture

The repository build runs `cargo build --workspace` from the root after
installing the Rust toolchain.

The UI component tests run `npm test` in `packages/ui` after installing
Node.js and running `npm ci` in that directory. They are component tests and
are not the repository's scalar default test command.
