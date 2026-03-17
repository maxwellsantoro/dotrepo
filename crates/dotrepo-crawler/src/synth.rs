use crate::{SynthesizeRepositoryReport, SynthesizeRepositoryRequest};
use anyhow::{bail, Result};

pub(crate) fn synthesize_repository_impl(
    request: &SynthesizeRepositoryRequest,
) -> Result<SynthesizeRepositoryReport> {
    if request.model.trim().is_empty() {
        bail!("synthesis model must not be empty");
    }
    if request.provider.trim().is_empty() {
        bail!("synthesis provider must not be empty");
    }

    bail!("repository synthesis is scaffolded but not implemented yet")
}
