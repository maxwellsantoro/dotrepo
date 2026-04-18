use crate::github::{GitHubDiscoveryClient, HttpGitHubClient};
use crate::{DiscoveredRepository, SeedRepositoriesReport, SeedRepositoriesRequest, StarBand};
use anyhow::{bail, Result};
use std::collections::HashSet;

const DEFAULT_MIN_STARS: u64 = 1;
const SEARCH_PAGE_SIZE: usize = 100;
const MAX_SEARCH_PAGES_PER_BAND: usize = 10;
pub(crate) const MAX_SEED_LIMIT: usize = 1_000;

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

    let client = HttpGitHubClient::new()?;
    seed_repositories_with_client(request, &client)
}

pub(crate) fn seed_repositories_with_client<C: GitHubDiscoveryClient>(
    request: &SeedRepositoriesRequest,
    client: &C,
) -> Result<SeedRepositoriesReport> {
    validate_seed_request(request)?;

    let star_bands = effective_star_bands(request);
    let mut discovered = Vec::new();
    let mut seen = HashSet::new();
    let mut exhausted_bands = request.limit > 0;

    'bands: for star_band in &star_bands {
        for page in 1..=MAX_SEARCH_PAGES_PER_BAND {
            let page_results = client.search_repositories(
                &request.host,
                star_band,
                page,
                SEARCH_PAGE_SIZE,
                request.include_archived,
                request.include_forks,
            )?;

            if page_results.is_empty() {
                break;
            }

            for entry in page_results
                .iter()
                .filter(|entry| matches_request(entry, request))
            {
                let identity = &entry.repository;
                let key = format!("{}/{}/{}", identity.host, identity.owner, identity.repo);
                if seen.insert(key) {
                    discovered.push(entry.clone());
                    if discovered.len() >= request.limit {
                        exhausted_bands = false;
                        break 'bands;
                    }
                }
            }

            if page_results.len() < SEARCH_PAGE_SIZE {
                break;
            }

            if page == MAX_SEARCH_PAGES_PER_BAND {
                exhausted_bands = false;
                break 'bands;
            }
        }
    }

    if discovered.len() >= request.limit {
        exhausted_bands = false;
    }

    Ok(SeedRepositoriesReport {
        host: request.host.clone(),
        requested_limit: request.limit,
        exhausted_bands,
        discovered,
    })
}

fn validate_seed_request(request: &SeedRepositoriesRequest) -> Result<()> {
    if request.host.trim().is_empty() {
        bail!("seed_repositories requires a non-empty host");
    }
    if request.host.trim() != "github.com" {
        bail!("seed_repositories currently supports github.com only");
    }
    if request.limit > MAX_SEED_LIMIT {
        bail!(
            "seed_repositories limit {} exceeds max {}",
            request.limit,
            MAX_SEED_LIMIT
        );
    }

    for band in &request.star_bands {
        if let Some(max_stars) = band.max_stars {
            if max_stars < band.min_stars {
                bail!(
                    "star band max_stars ({}) must be >= min_stars ({})",
                    max_stars,
                    band.min_stars
                );
            }
        }
    }

    Ok(())
}

fn effective_star_bands(request: &SeedRepositoriesRequest) -> Vec<StarBand> {
    if request.star_bands.is_empty() {
        return vec![StarBand {
            min_stars: DEFAULT_MIN_STARS,
            max_stars: None,
        }];
    }
    request.star_bands.clone()
}

fn matches_request(entry: &DiscoveredRepository, request: &SeedRepositoriesRequest) -> bool {
    entry.repository.host == request.host
        && (request.include_archived || !entry.archived)
        && (request.include_forks || !entry.fork)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::RepositoryRef;
    use std::collections::BTreeMap;

    struct FakeDiscoveryClient {
        pages: BTreeMap<(u64, Option<u64>, usize), Vec<DiscoveredRepository>>,
    }

    impl FakeDiscoveryClient {
        fn new(pages: BTreeMap<(u64, Option<u64>, usize), Vec<DiscoveredRepository>>) -> Self {
            Self { pages }
        }
    }

    impl GitHubDiscoveryClient for FakeDiscoveryClient {
        fn search_repositories(
            &self,
            _host: &str,
            star_band: &StarBand,
            page: usize,
            _per_page: usize,
            _include_archived: bool,
            _include_forks: bool,
        ) -> Result<Vec<DiscoveredRepository>> {
            Ok(self
                .pages
                .get(&(star_band.min_stars, star_band.max_stars, page))
                .cloned()
                .unwrap_or_default())
        }
    }

    fn discovered(
        owner: &str,
        repo: &str,
        stars: u64,
        default_branch: &str,
    ) -> DiscoveredRepository {
        DiscoveredRepository {
            repository: RepositoryRef {
                host: "github.com".into(),
                owner: owner.into(),
                repo: repo.into(),
            },
            stars,
            default_branch: Some(default_branch.into()),
            archived: false,
            fork: false,
        }
    }

    #[test]
    fn seed_repositories_uses_default_star_band_and_stops_at_limit() {
        let mut pages = BTreeMap::new();
        pages.insert(
            (1, None, 1),
            vec![
                discovered("tokio-rs", "tokio", 30000, "master"),
                discovered("vitejs", "vite", 70000, "main"),
                discovered("fastapi", "fastapi", 85000, "master"),
            ],
        );
        let client = FakeDiscoveryClient::new(pages);
        let report = seed_repositories_with_client(
            &SeedRepositoriesRequest {
                host: "github.com".into(),
                limit: 2,
                star_bands: Vec::new(),
                include_archived: false,
                include_forks: false,
            },
            &client,
        )
        .expect("discovery succeeds");

        assert_eq!(report.discovered.len(), 2);
        assert!(!report.exhausted_bands);
        assert_eq!(report.discovered[0].repository.repo, "tokio");
        assert_eq!(report.discovered[1].repository.repo, "vite");
    }

    #[test]
    fn seed_repositories_dedupes_across_star_bands() {
        let mut pages = BTreeMap::new();
        pages.insert(
            (1000, Some(10000), 1),
            vec![
                discovered("astral-sh", "uv", 10000, "main"),
                discovered("tokio-rs", "tokio", 30000, "master"),
            ],
        );
        pages.insert(
            (10000, None, 1),
            vec![
                discovered("tokio-rs", "tokio", 30000, "master"),
                discovered("fastapi", "fastapi", 85000, "master"),
            ],
        );
        let client = FakeDiscoveryClient::new(pages);
        let report = seed_repositories_with_client(
            &SeedRepositoriesRequest {
                host: "github.com".into(),
                limit: 5,
                star_bands: vec![
                    StarBand {
                        min_stars: 1000,
                        max_stars: Some(10000),
                    },
                    StarBand {
                        min_stars: 10000,
                        max_stars: None,
                    },
                ],
                include_archived: false,
                include_forks: false,
            },
            &client,
        )
        .expect("discovery succeeds");

        assert_eq!(report.discovered.len(), 3);
        assert!(report.exhausted_bands);
        assert_eq!(report.discovered[0].repository.repo, "uv");
        assert_eq!(report.discovered[1].repository.repo, "tokio");
        assert_eq!(report.discovered[2].repository.repo, "fastapi");
    }

    #[test]
    fn seed_repositories_filters_archived_and_forks_defensively() {
        let mut archived = discovered("example", "old", 1000, "main");
        archived.archived = true;
        let mut fork = discovered("example", "forked", 900, "main");
        fork.fork = true;

        let mut pages = BTreeMap::new();
        pages.insert(
            (1, None, 1),
            vec![archived, fork, discovered("example", "fresh", 1200, "main")],
        );
        let client = FakeDiscoveryClient::new(pages);
        let report = seed_repositories_with_client(
            &SeedRepositoriesRequest {
                host: "github.com".into(),
                limit: 5,
                star_bands: Vec::new(),
                include_archived: false,
                include_forks: false,
            },
            &client,
        )
        .expect("discovery succeeds");

        assert_eq!(report.discovered.len(), 1);
        assert_eq!(report.discovered[0].repository.repo, "fresh");
    }

    #[test]
    fn seed_repositories_rejects_limits_above_maximum() {
        let client = FakeDiscoveryClient::new(BTreeMap::new());
        let err = seed_repositories_with_client(
            &SeedRepositoriesRequest {
                host: "github.com".into(),
                limit: MAX_SEED_LIMIT + 1,
                star_bands: Vec::new(),
                include_archived: false,
                include_forks: false,
            },
            &client,
        )
        .expect_err("oversized limit rejected");

        assert!(err.to_string().contains("exceeds max"));
    }
}
