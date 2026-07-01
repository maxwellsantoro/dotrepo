//! Shared, ecosystem-agnostic markdown/text normalization: HTML entity and
//! tag stripping, markdown link/reference-link extraction, and README
//! docs-signal (docs root / getting-started) detection.
use super::super::types::ReadmeDocsMetadata;
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

pub(crate) fn parse_readme_docs_metadata(lines: &[&str]) -> ReadmeDocsMetadata {
    let mut docs = ReadmeDocsMetadata::default();
    let reference_definitions = markdown_reference_definitions(lines);
    let mut in_code_block = false;

    for line in lines {
        let trimmed = line.trim();
        if trimmed.starts_with("```") {
            in_code_block = !in_code_block;
            continue;
        }
        if in_code_block {
            continue;
        }

        let signal = parse_readme_docs_signal_with_references(trimmed, &reference_definitions);
        if docs.root.is_none() {
            docs.root = signal.root;
        }
        if docs.getting_started.is_none() {
            docs.getting_started = signal.getting_started;
        }

        if docs.root.is_some() && docs.getting_started.is_some() {
            break;
        }
    }

    docs
}

#[allow(dead_code)]
pub(crate) fn parse_readme_docs_signal(line: &str) -> ReadmeDocsMetadata {
    parse_readme_docs_signal_with_references(line, &HashMap::new())
}

fn parse_readme_docs_signal_with_references(
    line: &str,
    reference_definitions: &HashMap<String, String>,
) -> ReadmeDocsMetadata {
    let mut docs = ReadmeDocsMetadata::default();
    let lower_line = strip_html_tags(line).to_ascii_lowercase();

    let mut links = extract_markdown_links(line);
    links.extend(extract_markdown_reference_links(
        line,
        reference_definitions,
    ));
    links.extend(extract_html_links(line));

    for (label, url) in links {
        let lower_label = label.to_ascii_lowercase();
        let lower_url = url.to_ascii_lowercase();

        let is_getting_started = lower_label.contains("getting started")
            || lower_label.contains("quickstart")
            || lower_label == "installation"
            || lower_line.starts_with("getting started:")
            || lower_line.starts_with("quickstart:")
            || lower_url.contains("getting-started")
            || lower_url.contains("/installation")
            || lower_url.contains("quickstart");

        if is_badge_asset_url(&url) {
            continue;
        }

        if docs.getting_started.is_none() && is_getting_started {
            docs.getting_started = Some(url.clone());
        }

        let is_docs_root = !is_getting_started
            && (lower_label == "docs"
                || lower_label == "documentation"
                || lower_label == "configuration"
                || lower_label.contains("reference")
                || lower_line.starts_with("docs:")
                || lower_line.starts_with("documentation:")
                || lower_line.starts_with("documentation ")
                || lower_url.contains("/config/")
                || lower_url.contains("/configuration/")
                || lower_url == "./docs/"
                || lower_url == "docs/"
                || lower_url.ends_with("/docs/")
                || lower_url.ends_with("/docs")
                || lower_url.contains("readthedocs.io")
                || lower_url.contains("readthedocs.org"));

        if docs.root.is_none() && is_docs_root {
            docs.root = Some(url);
        }
    }

    docs
}

fn is_badge_asset_url(url: &str) -> bool {
    let lower = url.to_ascii_lowercase();
    lower.contains("badge")
        || lower.contains("shields.io")
        || lower.ends_with(".svg")
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
