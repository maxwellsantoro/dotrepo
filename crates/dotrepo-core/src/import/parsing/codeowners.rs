//! CODEOWNERS parsing: maintainer/team extraction and note synthesis for
//! ambiguous or repo-wide-only ownership rules.
use super::super::push_unique;
use super::super::types::{CodeownersMetadata, CodeownersRule};
use super::security::{is_team_handle, looks_like_email, trim_contact_token};

pub(crate) fn parse_codeowners_metadata(contents: &str) -> CodeownersMetadata {
    let mut owners = Vec::new();
    let mut rules = Vec::new();

    for line in contents.lines() {
        let trimmed = line.split('#').next().unwrap_or("").trim();
        if trimmed.is_empty() {
            continue;
        }

        let mut tokens = trimmed.split_whitespace();
        let Some(pattern) = tokens.next() else {
            continue;
        };
        let mut rule_owners = Vec::new();
        let mut rule_teams = Vec::new();
        for token in tokens {
            let cleaned = trim_contact_token(token);
            if cleaned.starts_with('@') || looks_like_email(cleaned) {
                push_unique(&mut owners, cleaned.to_string());
                push_unique(&mut rule_owners, cleaned.to_string());
            }
            if is_team_handle(cleaned) {
                push_unique(&mut rule_teams, cleaned.to_string());
            }
        }

        if !rule_owners.is_empty() {
            rules.push(CodeownersRule {
                pattern: pattern.to_string(),
                owners: rule_owners,
                teams: rule_teams,
            });
        }
    }

    let all_teams = collect_codeowners_teams(&rules);
    let repo_wide_rules = rules
        .iter()
        .filter(|rule| is_repo_wide_codeowners_pattern(&rule.pattern))
        .cloned()
        .collect::<Vec<_>>();
    let repo_wide_teams = collect_codeowners_teams(&repo_wide_rules);
    let team = if repo_wide_teams.len() == 1 {
        Some(repo_wide_teams[0].clone())
    } else {
        match all_teams.as_slice() {
            [only] => Some(only.clone()),
            _ => None,
        }
    };

    CodeownersMetadata {
        owners,
        team: team.clone(),
        note: codeowners_import_note(&rules, team.as_deref()),
    }
}

fn collect_codeowners_teams(rules: &[CodeownersRule]) -> Vec<String> {
    let mut teams = Vec::new();
    for rule in rules {
        for team in &rule.teams {
            push_unique(&mut teams, team.clone());
        }
    }
    teams
}

fn is_repo_wide_codeowners_pattern(pattern: &str) -> bool {
    matches!(pattern.trim(), "*" | "/*" | "**" | "/**" | "**/*" | "/**/*")
}

fn codeowners_import_note(rules: &[CodeownersRule], selected_team: Option<&str>) -> Option<String> {
    if rules.len() <= 1 {
        return None;
    }

    let repo_wide_rules = rules
        .iter()
        .filter(|rule| is_repo_wide_codeowners_pattern(&rule.pattern))
        .cloned()
        .collect::<Vec<_>>();
    let repo_wide_teams = collect_codeowners_teams(&repo_wide_rules);
    let all_teams = collect_codeowners_teams(rules);

    if let Some(team) = selected_team {
        if repo_wide_teams.len() == 1 && all_teams.len() > 1 {
            return Some(format!(
                "Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `{}` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.",
                team
            ));
        }

        if rules
            .iter()
            .any(|rule| !is_repo_wide_codeowners_pattern(&rule.pattern) && !rule.owners.is_empty())
        {
            return Some(format!(
                "Maintainer information was imported from CODEOWNERS; `owners.team` is `{}` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.",
                team
            ));
        }
    }

    if all_teams.len() > 1 {
        return Some(
            "Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates."
                .to_string(),
        );
    }

    None
}
