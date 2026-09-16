use crate::{
    CrawlStateRecord, RefreshCandidate, RefreshReason, ScheduleRefreshReport,
    ScheduleRefreshRequest, ScheduledRefresh, SkippedRefresh,
};
use anyhow::Result;

pub(crate) fn schedule_refresh_impl(
    request: &ScheduleRefreshRequest,
) -> Result<ScheduleRefreshReport> {
    let mut applicable = Vec::new();
    let mut scheduled = Vec::new();
    let mut skipped = Vec::new();

    for (index, candidate) in request.candidates.iter().enumerate() {
        let reason = refresh_reason(
            candidate,
            &request.state.repositories,
            request.synthesize,
            request.synthesis_model.as_deref(),
            request.now.as_deref(),
        );

        match reason {
            Some(reason) => applicable.push((index, candidate, reason)),
            None => skipped.push(SkippedRefresh {
                repository: candidate.repository.clone(),
                reason: "already fresh".into(),
            }),
        }
    }

    applicable.sort_by_key(|(index, _, reason)| (refresh_reason_rank(*reason), *index));

    for (position, (_, candidate, reason)) in applicable.into_iter().enumerate() {
        if position < request.limit {
            scheduled.push(ScheduledRefresh {
                repository: candidate.repository.clone(),
                default_branch: candidate.default_branch.clone(),
                head_sha: candidate.head_sha.clone(),
                reason,
                scheduled_at: request.now.clone(),
                synthesize: request.synthesize,
                synthesis_model: request.synthesis_model.clone(),
            });
        } else {
            skipped.push(SkippedRefresh {
                repository: candidate.repository.clone(),
                reason: format!("{} (limit reached)", refresh_reason_label(reason)),
            });
        }
    }

    Ok(ScheduleRefreshReport { scheduled, skipped })
}

fn refresh_reason(
    candidate: &RefreshCandidate,
    records: &[CrawlStateRecord],
    synthesize: bool,
    synthesis_model: Option<&str>,
    now: Option<&str>,
) -> Option<RefreshReason> {
    let Some(state) = records
        .iter()
        .find(|record| record.repository == candidate.repository)
    else {
        return Some(RefreshReason::MissingFactualCrawl);
    };

    if state.last_factual_crawl_at.is_none() {
        return Some(RefreshReason::MissingFactualCrawl);
    }

    // HEAD equality does not revalidate mutable host metadata or old parser decisions.
    use time::{format_description::well_known::Rfc3339, OffsetDateTime};
    let now = match now {
        Some(value) => OffsetDateTime::parse(value, &Rfc3339).ok(),
        None => Some(OffsetDateTime::now_utc()),
    };
    let checked = state
        .last_factual_crawl_at
        .as_deref()
        .and_then(|value| OffsetDateTime::parse(value, &Rfc3339).ok());
    if checked
        .zip(now)
        .is_none_or(|(checked, now)| checked > now || now - checked > time::Duration::days(30))
    {
        return Some(RefreshReason::StaleFactualCrawl);
    }

    if candidate.head_sha.is_some() && candidate.head_sha != state.head_sha {
        return Some(RefreshReason::HeadChanged);
    }

    if !synthesize {
        return None;
    }

    if state.last_synthesis_failure.is_some() {
        return Some(RefreshReason::PreviousSynthesisFailed);
    }

    if state.last_synthesis_success_at.is_none() {
        return Some(RefreshReason::MissingSynthesis);
    }

    if let Some(model) = synthesis_model {
        if state.synthesis_model.as_deref() != Some(model) {
            return Some(RefreshReason::SynthesisModelChanged);
        }
    }

    None
}

fn refresh_reason_label(reason: RefreshReason) -> &'static str {
    match reason {
        RefreshReason::StaleFactualCrawl => "stale factual crawl",
        RefreshReason::MissingFactualCrawl => "missing factual crawl",
        RefreshReason::HeadChanged => "head changed",
        RefreshReason::MissingSynthesis => "missing synthesis",
        RefreshReason::PreviousSynthesisFailed => "previous synthesis failed",
        RefreshReason::SynthesisModelChanged => "synthesis model changed",
    }
}

fn refresh_reason_rank(reason: RefreshReason) -> u8 {
    match reason {
        RefreshReason::StaleFactualCrawl => 0,
        RefreshReason::MissingFactualCrawl => 0,
        RefreshReason::HeadChanged => 1,
        RefreshReason::PreviousSynthesisFailed => 2,
        RefreshReason::MissingSynthesis => 3,
        RefreshReason::SynthesisModelChanged => 4,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        CrawlStateRecord, CrawlerStateSnapshot, RepositoryRef, ScheduleRefreshRequest,
        SynthesisFailureClass, SynthesisFailureMetadata,
    };

    fn repository(repo: &str) -> RepositoryRef {
        RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: repo.into(),
        }
    }

    #[test]
    fn unchanged_head_still_refreshes_expired_or_invalid_factual_records() {
        let candidate = RefreshCandidate {
            repository: repository("old"),
            default_branch: None,
            head_sha: Some("same".into()),
        };
        for checked in ["2026-07-01T00:00:00Z", "invalid", "2026-09-17T00:00:00Z"] {
            let state = CrawlStateRecord {
                repository: repository("old"),
                default_branch: None,
                head_sha: Some("same".into()),
                last_factual_crawl_at: Some(checked.into()),
                last_synthesis_success_at: None,
                last_synthesis_failure: None,
                synthesis_model: None,
            };
            assert_eq!(
                refresh_reason(
                    &candidate,
                    &[state],
                    false,
                    None,
                    Some("2026-09-16T00:00:00Z")
                ),
                Some(RefreshReason::StaleFactualCrawl)
            );
        }
    }

    #[test]
    fn schedule_refresh_picks_missing_factual_and_head_change() {
        let request = ScheduleRefreshRequest {
            now: Some("2026-03-17T12:00:00Z".into()),
            limit: 10,
            synthesize: false,
            synthesis_model: None,
            state: CrawlerStateSnapshot {
                repositories: vec![CrawlStateRecord {
                    repository: repository("orbit"),
                    default_branch: Some("main".into()),
                    head_sha: Some("abc123".into()),
                    last_factual_crawl_at: Some("2026-03-16T12:00:00Z".into()),
                    last_synthesis_success_at: None,
                    last_synthesis_failure: None,
                    synthesis_model: None,
                }],
            },
            candidates: vec![
                RefreshCandidate {
                    repository: repository("nova"),
                    default_branch: Some("main".into()),
                    head_sha: Some("seed000".into()),
                },
                RefreshCandidate {
                    repository: repository("orbit"),
                    default_branch: Some("main".into()),
                    head_sha: Some("def456".into()),
                },
            ],
        };

        let report = schedule_refresh_impl(&request).expect("schedule builds");
        let reasons: Vec<_> = report.scheduled.iter().map(|entry| entry.reason).collect();

        assert_eq!(
            reasons,
            vec![
                RefreshReason::MissingFactualCrawl,
                RefreshReason::HeadChanged
            ]
        );
    }

    #[test]
    fn schedule_refresh_requests_synthesis_after_failure_or_model_change() {
        let request = ScheduleRefreshRequest {
            now: Some("2026-03-17T12:00:00Z".into()),
            limit: 10,
            synthesize: true,
            synthesis_model: Some("gpt-5.4".into()),
            state: CrawlerStateSnapshot {
                repositories: vec![
                    CrawlStateRecord {
                        repository: repository("orbit"),
                        default_branch: Some("main".into()),
                        head_sha: Some("abc123".into()),
                        last_factual_crawl_at: Some("2026-03-16T12:00:00Z".into()),
                        last_synthesis_success_at: Some("2026-03-16T12:10:00Z".into()),
                        last_synthesis_failure: Some(SynthesisFailureMetadata {
                            class: SynthesisFailureClass::RateLimited,
                            message: "secondary rate limit".into(),
                            occurred_at: Some("2026-03-16T12:15:00Z".into()),
                            model: Some("gpt-5.3".into()),
                            provider: Some("openai".into()),
                        }),
                        synthesis_model: Some("gpt-5.3".into()),
                    },
                    CrawlStateRecord {
                        repository: repository("nova"),
                        default_branch: Some("main".into()),
                        head_sha: Some("seed000".into()),
                        last_factual_crawl_at: Some("2026-03-16T12:00:00Z".into()),
                        last_synthesis_success_at: Some("2026-03-16T12:10:00Z".into()),
                        last_synthesis_failure: None,
                        synthesis_model: Some("gpt-5.3".into()),
                    },
                ],
            },
            candidates: vec![
                RefreshCandidate {
                    repository: repository("orbit"),
                    default_branch: Some("main".into()),
                    head_sha: Some("abc123".into()),
                },
                RefreshCandidate {
                    repository: repository("nova"),
                    default_branch: Some("main".into()),
                    head_sha: Some("seed000".into()),
                },
            ],
        };

        let report = schedule_refresh_impl(&request).expect("schedule builds");
        let reasons: Vec<_> = report.scheduled.iter().map(|entry| entry.reason).collect();

        assert_eq!(
            reasons,
            vec![
                RefreshReason::PreviousSynthesisFailed,
                RefreshReason::SynthesisModelChanged
            ]
        );
    }

    #[test]
    fn schedule_refresh_prioritizes_factual_work_when_limit_is_tight() {
        let request = ScheduleRefreshRequest {
            now: Some("2026-03-17T12:00:00Z".into()),
            limit: 1,
            synthesize: true,
            synthesis_model: Some("gpt-5.4".into()),
            state: CrawlerStateSnapshot {
                repositories: vec![
                    CrawlStateRecord {
                        repository: repository("alpha"),
                        default_branch: Some("main".into()),
                        head_sha: Some("aaa111".into()),
                        last_factual_crawl_at: Some("2026-03-16T12:00:00Z".into()),
                        last_synthesis_success_at: None,
                        last_synthesis_failure: None,
                        synthesis_model: None,
                    },
                    CrawlStateRecord {
                        repository: repository("zeta"),
                        default_branch: Some("main".into()),
                        head_sha: Some("bbb111".into()),
                        last_factual_crawl_at: Some("2026-03-16T12:00:00Z".into()),
                        last_synthesis_success_at: Some("2026-03-16T12:10:00Z".into()),
                        last_synthesis_failure: None,
                        synthesis_model: Some("gpt-5.4".into()),
                    },
                ],
            },
            candidates: vec![
                RefreshCandidate {
                    repository: repository("alpha"),
                    default_branch: Some("main".into()),
                    head_sha: Some("aaa111".into()),
                },
                RefreshCandidate {
                    repository: repository("zeta"),
                    default_branch: Some("main".into()),
                    head_sha: Some("bbb222".into()),
                },
            ],
        };

        let report = schedule_refresh_impl(&request).expect("schedule builds");

        assert_eq!(report.scheduled.len(), 1);
        assert_eq!(report.scheduled[0].repository.repo, "zeta");
        assert_eq!(report.scheduled[0].reason, RefreshReason::HeadChanged);
        assert_eq!(report.skipped.len(), 1);
        assert_eq!(report.skipped[0].repository.repo, "alpha");
        assert_eq!(
            report.skipped[0].reason,
            "missing synthesis (limit reached)"
        );
    }
}
