use std::path::Path;

use super::*;

fn classify_public_error(message: &str) -> PublicErrorCode {
    if message.starts_with("query path not found: ") {
        PublicErrorCode::QueryPathNotFound
    } else if message.starts_with("repository not found in index: ") {
        PublicErrorCode::RepositoryNotFound
    } else if message.starts_with("invalid repository identity: ") {
        PublicErrorCode::InvalidRepositoryIdentity
    } else {
        PublicErrorCode::InternalError
    }
}

pub fn public_error_response(
    host: &str,
    owner: &str,
    repo: &str,
    path: Option<&str>,
    freshness: PublicFreshness,
    error: &anyhow::Error,
) -> PublicErrorResponse {
    let message = error.to_string();
    PublicErrorResponse {
        api_version: PUBLIC_API_VERSION,
        freshness: Box::new(freshness),
        identity: Box::new(PublicRepositoryIdentity {
            host: host.to_string(),
            owner: owner.to_string(),
            repo: repo.to_string(),
            source: None,
        }),
        path: path.map(ToOwned::to_owned),
        error: Box::new(PublicErrorDetail {
            code: classify_public_error(&message),
            message,
        }),
    }
}

pub fn public_repository_summary_or_error(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> std::result::Result<PublicRepositorySummaryResponse, PublicErrorResponse> {
    public_repository_summary_or_error_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_summary_or_error_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicRepositorySummaryResponse, PublicErrorResponse> {
    public_repository_summary_with_base(index_root, host, owner, repo, freshness.clone(), base_path)
        .map_err(|error| public_error_response(host, owner, repo, None, freshness, &error))
}

pub fn public_repository_trust_or_error(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> std::result::Result<PublicTrustResponse, PublicErrorResponse> {
    public_repository_trust_or_error_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_trust_or_error_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicTrustResponse, PublicErrorResponse> {
    public_repository_trust_with_base(index_root, host, owner, repo, freshness.clone(), base_path)
        .map_err(|error| public_error_response(host, owner, repo, None, freshness, &error))
}

pub fn public_repository_profile_or_error(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> std::result::Result<PublicResearchProfileResponse, PublicErrorResponse> {
    public_repository_profile_or_error_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_profile_or_error_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicResearchProfileResponse, PublicErrorResponse> {
    public_repository_profile_or_error_with_base_ref(
        index_root, host, owner, repo, &freshness, base_path,
    )
}

pub fn public_repository_profile_or_error_with_base_ref(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: &PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicResearchProfileResponse, PublicErrorResponse> {
    public_repository_profile_with_base(index_root, host, owner, repo, freshness.clone(), base_path)
        .map_err(|error| public_error_response(host, owner, repo, None, freshness.clone(), &error))
}

pub fn public_repository_query_or_error(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: PublicFreshness,
) -> std::result::Result<PublicQueryResponse, PublicErrorResponse> {
    public_repository_query_or_error_with_base(index_root, host, owner, repo, path, freshness, "/")
}

pub fn public_repository_query_or_error_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicQueryResponse, PublicErrorResponse> {
    public_repository_query_or_error_with_base_ref(
        index_root, host, owner, repo, path, &freshness, base_path,
    )
}

pub fn public_repository_query_or_error_with_base_ref(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: &PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicQueryResponse, PublicErrorResponse> {
    public_repository_query_with_base(
        index_root,
        host,
        owner,
        repo,
        path,
        freshness.clone(),
        base_path,
    )
    .map_err(|error| {
        public_error_response(host, owner, repo, Some(path), freshness.clone(), &error)
    })
}

pub fn public_repository_query_from_input_or_error_with_base(
    snapshot: &PublicQueryInputSnapshot,
    path: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicQueryResponse, PublicErrorResponse> {
    let identity = &snapshot.identity;
    public_repository_query_from_input_with_base(snapshot, path, freshness.clone(), base_path)
        .map_err(|error| {
            public_error_response(
                &identity.host,
                &identity.owner,
                &identity.repo,
                Some(path),
                freshness,
                &error,
            )
        })
}
