use crate::{CrawlRepositoryReport, CrawlRepositoryRequest};
use anyhow::{bail, Result};

pub(crate) fn crawl_repository_impl(
    request: &CrawlRepositoryRequest,
) -> Result<CrawlRepositoryReport> {
    if request.repository.host.trim().is_empty()
        || request.repository.owner.trim().is_empty()
        || request.repository.repo.trim().is_empty()
    {
        bail!("repository identity must include host, owner, and repo");
    }

    bail!("repository crawl is scaffolded but not implemented yet")
}
