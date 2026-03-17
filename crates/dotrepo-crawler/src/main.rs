use anyhow::{bail, Result};

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    bail!("dotrepo-crawler CLI wiring is not implemented yet; use the library entrypoints for now")
}
