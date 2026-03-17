use crate::{SeedRepositoriesReport, SeedRepositoriesRequest};
use anyhow::{bail, Result};

pub(crate) fn seed_repositories_impl(
    request: &SeedRepositoriesRequest,
) -> Result<SeedRepositoriesReport> {
    if request.limit == 0 {
        return Ok(SeedRepositoriesReport {
            host: request.host.clone(),
            requested_limit: request.limit,
            exhausted_bands: false,
            discovered: Vec::new(),
        });
    }

    bail!("GitHub discovery is scaffolded but not implemented yet")
}
