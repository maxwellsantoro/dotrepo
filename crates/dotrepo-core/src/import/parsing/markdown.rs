//! Shared, ecosystem-agnostic markdown/text normalization: HTML entity and
//! tag stripping, markdown link/reference-link extraction, and README
//! docs-signal (docs root / getting-started) detection.
use super::super::types::{ReadmeDocEvidence, ReadmeDocsMetadata};
use super::readme::parse_html_attr;
use super::security::extract_link_destination;
use std::collections::HashMap;

pub(crate) fn normalize_readme_text(line: &str) -> Option<String> {
    let linked = rewrite_markdown_links(line);
    let stripped = replace_common_html_entities(&strip_html_tags(&linked));
    let collapsed = stripped.split_whitespace().collect::<Vec<_>>().join(" ");
    let cleaned = strip_wrapping_emphasis(collapsed.trim().trim_matches('`').trim());
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned.to_string())
    }
}

pub(crate) fn strip_badge_run(line: &str) -> &str {
    line.find("[![")
        .map(|idx| line[..idx].trim_end())
        .unwrap_or(line)
}

pub(crate) fn is_markdown_reference_definition(line: &str) -> bool {
    let trimmed = line.trim();
    trimmed.starts_with('[') && trimmed.contains("]:")
}

fn replace_common_html_entities(line: &str) -> String {
    line.replace("&emsp;", " ")
        .replace("&ensp;", " ")
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
}

fn strip_wrapping_emphasis(mut line: &str) -> &str {
    loop {
        let trimmed = line.trim();
        if let Some(inner) = trimmed
            .strip_prefix("**")
            .and_then(|s| s.strip_suffix("**"))
            .or_else(|| {
                trimmed
                    .strip_prefix("__")
                    .and_then(|s| s.strip_suffix("__"))
            })
        {
            line = inner;
            continue;
        }
        if let Some(inner) = trimmed
            .strip_prefix('*')
            .and_then(|s| s.strip_suffix('*'))
            .or_else(|| trimmed.strip_prefix('_').and_then(|s| s.strip_suffix('_')))
        {
            line = inner;
            continue;
        }
        return trimmed;
    }
}

fn strip_html_tags(line: &str) -> String {
    let mut out = String::new();
    let mut in_tag = false;

    for ch in line.chars() {
        match ch {
            '<' => in_tag = true,
            '>' => in_tag = false,
            _ if !in_tag => out.push(ch),
            _ => {}
        }
    }

    out
}

// Rank declarations, not URL shapes: a dependency can use any docs host.
struct DocsCandidate {
    url: String,
    rank: u8,
    evidence: ReadmeDocEvidence,
}

fn select_docs_candidate(candidates: Vec<DocsCandidate>) -> (Option<DocsCandidate>, bool) {
    let Some(rank) = candidates.iter().map(|candidate| candidate.rank).max() else {
        return (None, false);
    };
    let mut strongest = candidates
        .into_iter()
        .filter(|candidate| candidate.rank == rank);
    let Some(selected) = strongest.next() else {
        return (None, false);
    };
    // Equally explicit declarations of different targets require resolution;
    // source order is not evidence that the first target belongs to this repo.
    if strongest.all(|candidate| candidate.url == selected.url) {
        (Some(selected), false)
    } else {
        (None, true)
    }
}

pub(crate) fn parse_readme_docs_metadata(
    lines: &[&str],
    project_name: Option<&str>,
) -> ReadmeDocsMetadata {
    let definitions = markdown_reference_definitions(lines);
    let mut roots = Vec::new();
    let mut getting_started = Vec::new();
    let mut fence: Option<char> = None;
    let mut docs_intro = false;

    for (index, line) in lines.iter().enumerate() {
        let line = line.trim();
        if line.starts_with("```") || line.starts_with("~~~") {
            let marker = line.chars().next();
            if fence.is_none() {
                fence = marker;
            } else if fence == marker {
                fence = None;
            }
            continue;
        }
        if fence.is_some() || line.is_empty() {
            continue;
        }
        if line.starts_with('#') {
            let heading = line.trim_matches('#').trim().to_ascii_lowercase();
            docs_intro = matches!(heading.as_str(), "docs" | "documentation" | "document");
            continue;
        }
        if is_markdown_reference_definition(line) {
            continue;
        }
        let mut links = extract_markdown_links(line);
        links.extend(extract_markdown_reference_links(line, &definitions));
        links.extend(extract_html_links(line));
        let lower_line = strip_html_tags(line)
            .replace("**", "")
            .replace("__", "")
            .to_ascii_lowercase();
        let prefix = lower_line.starts_with("docs:") || lower_line.starts_with("documentation:");
        if links.is_empty() && (docs_intro || prefix) {
            for word in line.split_whitespace() {
                let url = word.trim_matches(|ch| matches!(ch, '<' | '>' | '`'));
                if url.starts_with("https://") || url.starts_with("http://") {
                    links.push(("Documentation".into(), url.into()));
                }
            }
        }
        let single_link = links.len() == 1;
        let mut remainder = strip_html_tags(&rewrite_markdown_links(line));
        for (label, _) in &links {
            remainder = remainder.replace(label, "");
        }
        // Reference-style navigation may include unresolved neighbours such
        // as [Website][]. Ignore their bracketed labels, not surrounding prose.
        let mut bracket_depth = 0usize;
        let navigation = remainder.chars().all(|ch| match ch {
            '[' => {
                bracket_depth += 1;
                true
            }
            ']' if bracket_depth > 0 => {
                bracket_depth -= 1;
                true
            }
            _ if bracket_depth > 0 => true,
            _ => ch.is_whitespace() || "|·•:/-()*".contains(ch),
        }) && bracket_depth == 0;
        let declaration = single_link
            && (docs_intro || prefix || lower_line.contains("documentation is available at"));
        docs_intro = docs_intro
            && links.is_empty()
            && lower_line.contains("docs")
            && lower_line.ends_with(':');

        for (label, url) in links {
            if is_badge_asset_url(&url) {
                continue;
            }
            // Generic labels in a dependency catalogue or prose with several
            // project links do not identify this repository's documentation.
            if !single_link && !navigation {
                continue;
            }
            let label = label.to_ascii_lowercase();
            let is_start = label.contains("getting started")
                || label.contains("quickstart")
                || label == "installation"
                || label == "installation guide"
                || label == "installation documentation"
                || (single_link
                    && (lower_line.starts_with("getting started:")
                        || lower_line.starts_with("quickstart:")));
            let rank = if declaration {
                3
            } else if matches!(label.as_str(), "docs" | "documentation")
                || project_name.is_some_and(|name| {
                    label == format!("{} documentation", name.to_ascii_lowercase())
                })
            {
                2
            } else if matches!(
                label.as_str(),
                "configuration" | "reference" | "api reference"
            ) {
                1
            } else {
                0
            };
            let candidate = DocsCandidate {
                url,
                rank,
                evidence: ReadmeDocEvidence {
                    line: index + 1,
                    context: line.to_string(),
                },
            };
            if is_start {
                getting_started.push(candidate);
            } else if rank > 0 {
                roots.push(candidate);
            }
        }
    }
    let (root, root_ambiguous) = select_docs_candidate(roots);
    let (start, getting_started_ambiguous) = select_docs_candidate(getting_started);
    ReadmeDocsMetadata {
        root: root.as_ref().map(|candidate| candidate.url.clone()),
        getting_started: start.as_ref().map(|candidate| candidate.url.clone()),
        root_evidence: root.map(|candidate| candidate.evidence),
        getting_started_evidence: start.map(|candidate| candidate.evidence),
        root_ambiguous,
        getting_started_ambiguous,
    }
}

#[allow(dead_code)]
pub(crate) fn parse_readme_docs_signal(line: &str) -> ReadmeDocsMetadata {
    parse_readme_docs_metadata(&[line], None)
}

fn is_badge_asset_url(url: &str) -> bool {
    let lower = url.to_ascii_lowercase();
    let path = lower.split(['?', '#']).next().unwrap_or(&lower);
    lower.contains("badge")
        || lower.contains("shields.io")
        || [".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"]
            .iter()
            .any(|extension| path.ends_with(extension))
        || lower.contains("status.svg")
}

fn markdown_reference_definitions(lines: &[&str]) -> HashMap<String, String> {
    let mut definitions = HashMap::new();
    for line in lines {
        let trimmed = line.trim();
        if !trimmed.starts_with('[') {
            continue;
        }
        let Some(split_idx) = trimmed.find("]:") else {
            continue;
        };
        let label = trimmed[1..split_idx].trim();
        if label.is_empty() {
            continue;
        }
        if let Some(destination) = extract_link_destination(&trimmed[split_idx + 2..]) {
            definitions.insert(label.to_ascii_lowercase(), destination);
        }
    }
    definitions
}

fn extract_markdown_reference_links(
    line: &str,
    definitions: &HashMap<String, String>,
) -> Vec<(String, String)> {
    let mut links = Vec::new();
    let mut idx = 0;
    while idx < line.len() {
        let Some(rel) = line[idx..].find('[') else {
            break;
        };
        let label_start = idx + rel;
        if label_start > 0 && line.as_bytes().get(label_start - 1) == Some(&b'!') {
            idx = label_start + 1;
            continue;
        }
        let Some(label_end_rel) = line[label_start + 1..].find(']') else {
            break;
        };
        let label_end = label_start + 1 + label_end_rel;
        let raw_label = &line[label_start + 1..label_end];
        let remainder = &line[label_end + 1..];
        let Some((reference_key, advance)) = parse_reference_suffix(remainder, raw_label) else {
            idx = label_end + 1;
            continue;
        };
        if let Some(url) = definitions.get(&reference_key) {
            if let Some(label) = normalize_readme_text(raw_label) {
                links.push((label, url.clone()));
            }
        }
        idx = label_end + 1 + advance;
    }
    links
}

fn parse_reference_suffix(remainder: &str, raw_label: &str) -> Option<(String, usize)> {
    if let Some(rest) = remainder.strip_prefix("[]") {
        return Some((
            raw_label.trim().to_ascii_lowercase(),
            remainder.len() - rest.len(),
        ));
    }
    let rest = remainder.strip_prefix('[')?;
    let close = rest.find(']')?;
    let reference = rest[..close].trim();
    if reference.is_empty() {
        return None;
    }
    Some((reference.to_ascii_lowercase(), close + 2))
}

fn extract_html_links(line: &str) -> Vec<(String, String)> {
    let mut links = Vec::new();
    let lower = line.to_ascii_lowercase();
    let mut idx = 0;
    while let Some(rel) = lower[idx..].find("<a") {
        let anchor_start = idx + rel;
        let Some(tag_end_rel) = lower[anchor_start..].find('>') else {
            break;
        };
        let tag_end = anchor_start + tag_end_rel;
        let tag = &line[anchor_start..=tag_end];
        let tag_lower = tag.to_ascii_lowercase();
        let Some(url) = parse_html_attr(tag, &tag_lower, "href") else {
            idx = tag_end + 1;
            continue;
        };
        let Some(close_rel) = lower[tag_end + 1..].find("</a>") else {
            idx = tag_end + 1;
            continue;
        };
        let label_raw = &line[tag_end + 1..tag_end + 1 + close_rel];
        if let Some(label) = normalize_readme_text(label_raw) {
            links.push((label, url));
        }
        idx = tag_end + 1 + close_rel + "</a>".len();
    }
    links
}

pub(crate) fn extract_markdown_links(line: &str) -> Vec<(String, String)> {
    let mut links = Vec::new();
    let mut idx = 0;

    while idx < line.len() {
        let next_idx = match line[idx..].find(['[', '!']) {
            Some(rel) => idx + rel,
            None => break,
        };
        let is_image = line[next_idx..].starts_with("![");
        let link_start = if is_image { next_idx + 1 } else { next_idx };

        if let Some((end, label, url)) = parse_markdown_link_at(line, link_start) {
            if !is_image {
                if let Some(label) = normalize_readme_text(&label).filter(|_| !url.is_empty()) {
                    links.push((label, url));
                }
            }
            idx = end;
            continue;
        }

        idx = next_idx + 1;
    }

    links
}

pub(crate) fn rewrite_markdown_links(line: &str) -> String {
    let mut out = String::new();
    let mut idx = 0;

    while idx < line.len() {
        let remainder = &line[idx..];

        if remainder.starts_with("![") {
            if let Some((end, _, _)) = parse_markdown_link_at(line, idx + 1) {
                idx = end;
                continue;
            }
        }

        if remainder.starts_with('[') {
            if let Some((end, label, _)) = parse_markdown_link_at(line, idx) {
                out.push_str(&label);
                idx = end;
                continue;
            }
        }

        let Some(ch) = remainder.chars().next() else {
            break;
        };
        out.push(ch);
        idx += ch.len_utf8();
    }

    out
}

fn parse_markdown_link_at(line: &str, start: usize) -> Option<(usize, String, String)> {
    let bytes = line.as_bytes();
    if bytes.get(start).copied()? != b'[' {
        return None;
    }

    let close_label_rel = line[start + 1..].find(']')?;
    let close_label = start + 1 + close_label_rel;
    if bytes.get(close_label + 1).copied()? != b'(' {
        return None;
    }

    let url_start = close_label + 2;
    let mut idx = url_start;
    let mut depth = 1usize;
    while idx < bytes.len() {
        match bytes[idx] {
            b'(' => depth += 1,
            b')' => {
                depth -= 1;
                if depth == 0 {
                    let label = line[start + 1..close_label].to_string();
                    let url = line[url_start..idx].trim().to_string();
                    return Some((idx + 1, label, url));
                }
            }
            _ => {}
        }
        idx += 1;
    }

    None
}

pub(crate) fn is_probable_readme_nav_line(line: &str) -> bool {
    if extract_markdown_links(line).len() < 2 {
        return false;
    }

    let lowered = strip_html_tags(line).to_ascii_lowercase();
    lowered.contains("docs")
        || lowered.contains("getting started")
        || lowered.contains("quickstart")
        || lowered.contains("api")
        || lowered.contains("guide")
        || lowered.contains("reference")
}

pub(crate) fn is_probable_docs_signal_line(line: &str) -> bool {
    let lowered = strip_html_tags(line)
        .trim_start_matches('*')
        .trim_start_matches('_')
        .trim()
        .to_ascii_lowercase();
    lowered.starts_with("docs:")
        || lowered.starts_with("documentation:")
        || lowered.starts_with("getting started:")
        || lowered.starts_with("quickstart:")
}

pub(crate) fn starts_with_ordered_list_item(line: &str) -> bool {
    let digits = line.chars().take_while(|ch| ch.is_ascii_digit()).count();
    digits > 0
        && line
            .chars()
            .nth(digits)
            .is_some_and(|ch| matches!(ch, '.' | ')'))
}
