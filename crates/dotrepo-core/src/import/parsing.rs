use super::{
    push_unique, CodeownersMetadata, CodeownersRule, ReadmeDocsMetadata, ReadmeMetadata,
    SecurityImportMetadata,
};

pub(crate) fn try_parse_multiline_html_heading(
    lines: &[&str],
    idx: usize,
) -> Option<(String, usize)> {
    let line = lines.get(idx)?.trim();
    let lower = line.to_ascii_lowercase();
    let tag_level = ["<h1", "<h2", "<h3", "<h4", "<h5", "<h6"]
        .iter()
        .find(|needle| lower.starts_with(**needle))?;
    let close_tag = tag_level.replace('<', "</");
    if line.contains(&close_tag) {
        return None;
    }
    let mut accumulated = String::new();
    let mut scan = idx + 1;
    let mut lines_consumed = 1;
    while scan < lines.len() {
        let next = lines[scan].trim();
        lines_consumed += 1;
        if next.contains(&close_tag) {
            if !accumulated.is_empty() {
                if let Some(normalized) = normalize_readme_text(&accumulated) {
                    if !is_non_project_heading(&normalized) {
                        return Some((normalized, lines_consumed));
                    }
                }
            }
            return None;
        }
        if !next.is_empty() {
            if !accumulated.is_empty() {
                accumulated.push(' ');
            }
            accumulated.push_str(next);
        }
        scan += 1;
    }
    None
}

pub(crate) fn parse_readme_metadata(contents: &str) -> ReadmeMetadata {
    let mut metadata = ReadmeMetadata::default();
    let lines = contents.lines().collect::<Vec<_>>();
    let mut in_code_block = false;
    let mut idx = 0;

    while idx < lines.len() {
        let trimmed = lines[idx].trim();
        if trimmed.starts_with("```") {
            in_code_block = !in_code_block;
            idx += 1;
            continue;
        }
        if in_code_block {
            idx += 1;
            continue;
        }

        if metadata.title.is_none() {
            if let Some((title, advance)) = try_parse_multiline_html_heading(&lines, idx) {
                metadata.title = Some(title);
                idx += advance;
                continue;
            }
            if let Some(title) = parse_readme_title_line(trimmed) {
                metadata.title = Some(title);
                idx += 1;
                continue;
            }
            if let Some(title) = parse_setext_heading(&lines, idx) {
                metadata.title = Some(title);
                idx += 2;
                continue;
            }
        }

        if metadata.description.is_none() {
            if let Some((description, next_idx)) = parse_readme_description(&lines, idx) {
                metadata.description = Some(description);
                idx = next_idx;
                if metadata.title.is_some() {
                    break;
                }
                continue;
            }
        }

        if metadata.title.is_some() && metadata.description.is_some() {
            break;
        }

        idx += 1;
    }

    let docs = parse_readme_docs_metadata(&lines);
    metadata.docs_root = docs.root;
    metadata.docs_getting_started = docs.getting_started;

    metadata
}

pub(crate) fn parse_readme_title_line(line: &str) -> Option<String> {
    if line.starts_with('#') {
        let title = strip_badge_run(line.trim_start_matches('#').trim());
        if is_promo_link_heading(title) {
            return None;
        }
        if let Some(normalized) = normalize_readme_text(title) {
            if !is_non_project_heading(&normalized) {
                return Some(normalized);
            }
        }
        return None;
    }

    parse_html_heading(line).filter(|h| !is_non_project_heading(h))
}

fn is_promo_link_heading(text: &str) -> bool {
    let trimmed = text.trim();
    if !trimmed.starts_with('[') {
        return false;
    }
    if let Some(close_bracket) = trimmed.find("](") {
        let after_link = trimmed[close_bracket + 2..].trim();
        after_link.ends_with(')')
            && after_link
                .rfind(')')
                .is_some_and(|pos| pos == after_link.len() - 1)
    } else {
        false
    }
}

pub(crate) fn is_non_project_heading(heading: &str) -> bool {
    let lowered = heading.to_ascii_lowercase();
    let trimmed = lowered.trim();
    if NON_PROJECT_HEADINGS.contains(&trimmed) {
        return true;
    }
    NON_PROJECT_HEADING_KEYWORDS
        .iter()
        .any(|keyword| trimmed.contains(keyword))
}

const NON_PROJECT_HEADINGS: &[&str] = &[
    "about",
    "acknowledgments",
    "api reference",
    "badges",
    "changelog",
    "commands",
    "code of conduct",
    "communication",
    "concepts",
    "configuration",
    "contributing",
    "credits",
    "documentation",
    "donate",
    "example",
    "examples",
    "faq",
    "features",
    "flags",
    "getting started",
    "installation",
    "installing",
    "introduction",
    "license",
    "links",
    "motivation",
    "overview",
    "quick links",
    "quick start",
    "quickstart",
    "readme",
    "resources",
    "roadmap",
    "security",
    "security and privacy",
    "sponsors",
    "support",
    "table of contents",
    "usage",
];

const NON_PROJECT_HEADING_KEYWORDS: &[&str] = &["sponsors", "sponsor", "backed by", "supported by"];

fn parse_setext_heading(lines: &[&str], idx: usize) -> Option<String> {
    let line = lines.get(idx)?.trim();
    let underline = lines.get(idx + 1)?.trim();
    if line.is_empty() || !is_setext_underline(underline) {
        return None;
    }

    normalize_readme_text(line)
}

fn is_setext_underline(line: &str) -> bool {
    line.len() >= 3 && line.chars().all(|ch| ch == '=' || ch == '-')
}

fn parse_html_heading(line: &str) -> Option<String> {
    let trimmed = line.trim();
    let lower = trimmed.to_ascii_lowercase();
    if !["<h1", "<h2", "<h3", "<h4", "<h5", "<h6"]
        .iter()
        .any(|needle| lower.contains(needle))
    {
        return None;
    }

    normalize_readme_text(trimmed)
}

/// A GitHub alert / admonition blockquote, e.g. `> [!NOTE]`, `> [!IMPORTANT]`.
/// These are presentation chrome, not project descriptions.
fn is_github_admonition_line(trimmed: &str) -> bool {
    let Some(rest) = trimmed.strip_prefix('>') else {
        return false;
    };
    let inner = rest.trim();
    let Some(tag_body) = inner.strip_prefix("[!") else {
        return false;
    };
    match tag_body.find(']') {
        Some(end) => {
            let tag = &tag_body[..end];
            !tag.is_empty() && tag.chars().all(|c| c.is_ascii_alphanumeric())
        }
        None => false,
    }
}

/// Advance past a contiguous blockquote block (lines whose text begins with `>`).
fn skip_blockquote_block(lines: &[&str], start: usize) -> usize {
    let mut idx = start;
    while idx < lines.len() && lines[idx].trim_start().starts_with('>') {
        idx += 1;
    }
    idx
}

fn parse_readme_description(lines: &[&str], start: usize) -> Option<(String, usize)> {
    let mut parts = Vec::new();
    let mut idx = start;

    while idx < lines.len() {
        let trimmed = lines[idx].trim();
        if trimmed.starts_with("```") {
            break;
        }
        if trimmed.is_empty() {
            if parts.is_empty() {
                idx += 1;
                continue;
            }
            break;
        }
        // GitHub admonition blockquotes (> [!NOTE], > [!IMPORTANT], ...) are
        // presentation chrome. Skip a leading admonition block entirely so it is
        // never mistaken for the description; an admonition after description
        // text ends the description like any other non-description content.
        if is_github_admonition_line(trimmed) {
            if parts.is_empty() {
                idx = skip_blockquote_block(lines, idx);
                continue;
            }
            break;
        }
        if parse_readme_title_line(trimmed).is_some() || parse_setext_heading(lines, idx).is_some()
        {
            if parts.is_empty() {
                return None;
            }
            break;
        }

        let normalized = match normalize_description_line(trimmed) {
            Some(normalized) => normalized,
            None => {
                if parts.is_empty() {
                    idx += 1;
                    continue;
                }
                break;
            }
        };

        parts.push(normalized);
        idx += 1;
    }

    if parts.is_empty() {
        None
    } else {
        let joined = parts.join(" ");
        if looks_like_artifact(&joined) {
            return None;
        }
        if joined.len() < 15 || !joined.contains(' ') {
            return None;
        }
        Some((joined, idx))
    }
}

pub(crate) fn normalize_description_line(line: &str) -> Option<String> {
    if line.is_empty()
        || line.starts_with('#')
        || line.starts_with("![")
        || line.starts_with("[![")
        || is_markdown_reference_definition(line)
        || line.starts_with("<!--")
        || line == "---"
        || line.starts_with("- ")
        || line.starts_with("* ")
        || starts_with_ordered_list_item(line)
        || is_probable_readme_nav_line(line)
        || is_probable_docs_signal_line(line)
        || is_pipe_delimited_nav_line(line)
        || is_nav_link_item(line)
    {
        return None;
    }

    let description = line.trim_start_matches('>').trim();
    normalize_readme_text(description)
        .filter(|value| value.chars().any(|ch| ch.is_alphanumeric()))
        .filter(|value| !looks_like_artifact(value))
        .filter(|value| !is_quoted_tagline(value))
}

fn looks_like_artifact(value: &str) -> bool {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return true;
    }
    if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        return true;
    }
    if looks_like_html_attribute_spill(trimmed) {
        return true;
    }
    if looks_like_file_path(trimmed) {
        return true;
    }
    if has_unbalanced_brackets(trimmed) {
        return true;
    }
    if is_pipe_delimited_nav_text(trimmed) {
        return true;
    }
    false
}

fn looks_like_html_attribute_spill(value: &str) -> bool {
    let lowered = value.to_ascii_lowercase();
    lowered.contains("src=\"") || lowered.contains("alt=\"") || lowered.contains("href=\"")
}

fn is_pipe_delimited_nav_line(line: &str) -> bool {
    is_pipe_delimited_nav_text(line.trim())
}

fn is_pipe_delimited_nav_text(value: &str) -> bool {
    let pipe_count = value.chars().filter(|ch| *ch == '|').count();
    if pipe_count < 2 {
        return false;
    }
    let segments = value.split('|').collect::<Vec<_>>();
    segments.len() >= 3 && segments.iter().all(|s| s.trim().len() <= 40)
}

fn is_nav_link_item(line: &str) -> bool {
    let trimmed = line.trim();
    if trimmed.starts_with('|') && trimmed.contains('|') {
        return true;
    }
    if trimmed.contains('|') && trimmed.ends_with('|') {
        return true;
    }
    let normalized = normalize_readme_text(trimmed);
    normalized
        .as_ref()
        .is_some_and(|text| text.ends_with('|') || text.trim().ends_with('|'))
}

fn looks_like_file_path(value: &str) -> bool {
    let has_extension = value.rsplit_once('.').is_some_and(|(_, ext)| {
        ext.len() <= 10
            && ext
                .chars()
                .all(|ch| ch.is_ascii_alphanumeric() || ch == '-')
    });
    if !has_extension {
        return false;
    }
    let sep_count = value.chars().filter(|ch| *ch == '/').count();
    sep_count >= 1
}

fn has_unbalanced_brackets(value: &str) -> bool {
    let mut depth_paren = 0i32;
    let mut depth_bracket = 0i32;
    for ch in value.chars() {
        match ch {
            '(' => depth_paren += 1,
            ')' => depth_paren -= 1,
            '[' => depth_bracket += 1,
            ']' => depth_bracket -= 1,
            _ => {}
        }
    }
    depth_paren != 0 || depth_bracket != 0
}

// ---------------------------------------------------------------------------
// Universal post-extraction cleaners
// ---------------------------------------------------------------------------
// These operate on the *result* of README/GitHub parsing and apply
// language-agnostic quality rules that work for any repo at scale.

/// Strip emoji prefix, parenthetical aliases, and trailing punctuation from
/// an extracted project name. Returns `None` when the cleaned result is
/// clearly not a project name (generic phrase, too short, etc.).
pub(super) fn clean_project_name(raw: &str, _repo_dir_fallback: &str) -> Option<String> {
    let trimmed = raw.trim();

    // Strip leading emoji / non-ASCII symbols.
    let name = trim_leading_emoji(trimmed);

    // Strip parenthetical alias: "ripgrep (rg)" → "ripgrep"
    let name = strip_parenthetical_suffix(&name);

    // Strip trailing colon or dash patterns: "npm - a JavaScript package manager"
    let name = strip_name_trailer(&name);

    let cleaned = name.trim().to_string();
    if cleaned.is_empty() {
        return None;
    }

    // Reject generic phrases that somehow passed the heading skip-list.
    if is_generic_phrase(&cleaned) {
        return None;
    }

    Some(cleaned)
}

fn trim_leading_emoji(s: &str) -> String {
    s.chars()
        .skip_while(|ch| !ch.is_ascii_alphabetic() && !ch.is_ascii_digit())
        .collect()
}

fn strip_parenthetical_suffix(name: &str) -> String {
    if let Some(open) = name.rfind(" (") {
        if name.ends_with(')') {
            return name[..open].to_string();
        }
    }
    name.to_string()
}

/// Strip " - description" or ": description" trailers that leak into names
/// when README titles use the pattern "Name — A description of the project".
fn strip_name_trailer(name: &str) -> String {
    if let Some(idx) = name.find(" - ") {
        let candidate = name[..idx].trim();
        if candidate.len() >= 2 {
            return candidate.to_string();
        }
    }
    if let Some(idx) = name.find(" — ") {
        let candidate = name[..idx].trim();
        if candidate.len() >= 2 {
            return candidate.to_string();
        }
    }
    if let Some(idx) = name.find(": ") {
        let candidate = name[..idx].trim();
        if candidate.len() >= 2 && candidate.chars().next().is_some_and(|c| c.is_uppercase()) {
            return candidate.to_string();
        }
    }
    name.to_string()
}

/// Reject names that are clearly not project identifiers.
fn is_generic_phrase(name: &str) -> bool {
    let lowered = name.to_ascii_lowercase();
    let trimmed = lowered.trim();

    // Exact-match against known generic names that slip through heading checks.
    GENERIC_NAME_REJECTS.contains(&trimmed)
}

const GENERIC_NAME_REJECTS: &[&str] = &[
    "a project",
    "the project",
    "this project",
    "project",
    "a tool",
    "a library",
    "a framework",
    "welcome",
    "overview",
    "introduction",
];

/// Clean a description extracted from a README: fix backtick artifacts,
/// truncate at the first sentence boundary, and reject fragments.
pub(crate) fn clean_project_description(raw: &str) -> Option<String> {
    let trimmed = raw.trim();

    // Strip orphaned backtick artifacts: "gh` is..." → "gh is..."
    let cleaned = strip_orphan_backticks(trimmed);

    // Truncate at first sentence boundary.
    let cleaned = truncate_at_first_sentence(&cleaned);

    let cleaned = cleaned.trim().to_string();

    // Reject fragments: starts with lowercase (likely mid-sentence).
    if cleaned
        .chars()
        .next()
        .is_some_and(|ch| ch.is_ascii_lowercase())
    {
        return None;
    }

    // Reject very short results or language names.
    if cleaned.len() < 20 || !cleaned.contains(' ') {
        return None;
    }

    // Reject meta-descriptions about the repo itself.
    if is_meta_description(&cleaned) {
        return None;
    }

    // Reject quoted taglines: "Any color you like."
    if is_quoted_tagline(&cleaned) {
        return None;
    }

    Some(cleaned)
}

/// Replace backtick-space patterns like "gh` is" with "gh is".
fn strip_orphan_backticks(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '`' {
            let next_is_continuation = chars
                .get(i + 1)
                .is_some_and(|ch| *ch == ' ' || ch.is_ascii_lowercase());
            let prev_is_alphanum = i > 0 && chars[i - 1].is_ascii_alphanumeric();
            if prev_is_alphanum && next_is_continuation {
                i += 1;
                continue;
            }
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

/// Truncate text at the first sentence boundary (period + space).
/// Keeps the first sentence only, which is the core description.
fn truncate_at_first_sentence(s: &str) -> String {
    // Look for ". " (period followed by space) — standard sentence boundary.
    if let Some(idx) = s.find(". ") {
        let first = &s[..idx + 1];
        if first.len() >= 20 {
            return first.to_string();
        }
    }
    // Also truncate at ".\n" boundary.
    if let Some(idx) = s.find(".\n") {
        let first = &s[..idx + 1];
        if first.len() >= 20 {
            return first.to_string();
        }
    }
    s.to_string()
}

/// Detect descriptions that are about the repository rather than the project.
fn is_meta_description(s: &str) -> bool {
    let lowered = s.to_ascii_lowercase();
    lowered.starts_with("this repository is")
        || lowered.starts_with("this repo is")
        || lowered.starts_with("this is the")
        || lowered.starts_with("this is a repo")
}

fn is_quoted_tagline(s: &str) -> bool {
    let trimmed = s.trim();
    let openers = ['"', '\u{201c}', '\u{201e}'];
    let closers = ['"', '\u{201d}', '\u{201e}'];
    if trimmed.len() <= 2 {
        return false;
    }
    let Some(first) = trimmed.chars().next() else {
        return false;
    };
    if !openers.contains(&first) {
        return false;
    }
    let Some(last) = trimmed.chars().last() else {
        return false;
    };
    if !closers.contains(&last) {
        return false;
    }
    let start = first.len_utf8();
    let end = trimmed.len().saturating_sub(last.len_utf8());
    if start >= end {
        return false;
    }
    !trimmed[start..end].contains(". ")
}

/// Validate that a URL is structurally sound for use in the index.
/// Rejects localhost, anchor-only, and bare domains without scheme.
pub(crate) fn is_quality_url(url: &str) -> bool {
    let trimmed = url.trim();

    // Reject empty.
    if trimmed.is_empty() {
        return false;
    }

    // Reject anchor-only: "#documentation", "#getting-started"
    if trimmed.starts_with('#') {
        return false;
    }

    // Reject localhost / private IPs.
    if trimmed.starts_with("http://127.0")
        || trimmed.starts_with("http://localhost")
        || trimmed.starts_with("https://localhost")
        || trimmed.starts_with("http://0.0.0")
        || trimmed.starts_with("http://[::1]")
    {
        return false;
    }

    // Require http:// or https:// scheme for absolute URLs.
    // Allow relative paths like "docs/" but reject bare domains like "docs.rs/clap".
    if !trimmed.starts_with("http://")
        && !trimmed.starts_with("https://")
        && !trimmed.starts_with('/')
        && !trimmed.starts_with("./")
        && !trimmed.contains(char::is_whitespace)
    {
        // If it looks like a domain (contains dots and slashes but no scheme), reject.
        if trimmed.contains('.') && trimmed.contains('/') && !trimmed.starts_with('#') {
            return false;
        }
        // If it looks like a bare domain without any path, reject.
        if trimmed.contains('.') && !trimmed.contains('/') {
            return false;
        }
    }

    true
}

pub(crate) fn is_actionable_security_url(url: &str) -> bool {
    let trimmed = url.trim();

    // GitHub's built-in vulnerability disclosure form per repo.
    if trimmed.contains("/security/advisories/new") {
        return true;
    }

    // Microsoft Security Response Center report form.
    if trimmed.contains("msrc.microsoft.com/create-report") {
        return true;
    }

    // Vendor security pages with clear first-party reporting instructions.
    if trimmed.contains("djangoproject.com/security") {
        return true;
    }

    false
}

fn normalize_readme_text(line: &str) -> Option<String> {
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

fn strip_badge_run(line: &str) -> &str {
    line.find("[![")
        .map(|idx| line[..idx].trim_end())
        .unwrap_or(line)
}

fn is_markdown_reference_definition(line: &str) -> bool {
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

fn parse_readme_docs_metadata(lines: &[&str]) -> ReadmeDocsMetadata {
    let mut docs = ReadmeDocsMetadata::default();
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

        let signal = parse_readme_docs_signal(trimmed);
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

pub(crate) fn parse_readme_docs_signal(line: &str) -> ReadmeDocsMetadata {
    let mut docs = ReadmeDocsMetadata::default();
    let lower_line = strip_html_tags(line).to_ascii_lowercase();

    for (label, url) in extract_markdown_links(line) {
        let lower_label = label.to_ascii_lowercase();
        let lower_url = url.to_ascii_lowercase();

        let is_getting_started = lower_label.contains("getting started")
            || lower_label.contains("quickstart")
            || lower_line.starts_with("getting started:")
            || lower_line.starts_with("quickstart:")
            || lower_url.contains("getting-started")
            || lower_url.contains("quickstart");

        if docs.getting_started.is_none() && is_getting_started {
            docs.getting_started = Some(url.clone());
        }

        let is_docs_root = !is_getting_started
            && (lower_label == "docs"
                || lower_label == "documentation"
                || lower_label.contains("reference")
                || lower_line.starts_with("docs:")
                || lower_line.starts_with("documentation:")
                || lower_line.starts_with("documentation ")
                || lower_url == "./docs/"
                || lower_url == "docs/"
                || lower_url.ends_with("/docs/")
                || lower_url.ends_with("/docs"));

        if docs.root.is_none() && is_docs_root {
            docs.root = Some(url);
        }
    }

    docs
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

fn rewrite_markdown_links(line: &str) -> String {
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

fn is_probable_readme_nav_line(line: &str) -> bool {
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

fn is_probable_docs_signal_line(line: &str) -> bool {
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

fn starts_with_ordered_list_item(line: &str) -> bool {
    let digits = line.chars().take_while(|ch| ch.is_ascii_digit()).count();
    digits > 0
        && line
            .chars()
            .nth(digits)
            .is_some_and(|ch| matches!(ch, '.' | ')'))
}

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

pub(crate) fn parse_security_contact(contents: &str) -> Option<String> {
    find_mailto_or_email(contents).or_else(|| find_first_url(contents))
}

pub(crate) fn parse_security_import_metadata(contents: &str) -> SecurityImportMetadata {
    match parse_security_contact(contents) {
        Some(contact) if looks_like_email(&contact) => SecurityImportMetadata {
            contact: Some(contact),
            note: None,
        },
        Some(contact) => SecurityImportMetadata {
            contact: Some(contact),
            note: Some(
                "SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL."
                    .to_string(),
            ),
        },
        None => SecurityImportMetadata::default(),
    }
}

pub(crate) fn parse_readme_security(contents: &str) -> Option<String> {
    parse_security_section_from_markdown(contents)
}

pub(crate) fn parse_contributing_security(contents: &str) -> Option<String> {
    parse_security_section_from_markdown(contents)
}

fn parse_security_section_from_markdown(contents: &str) -> Option<String> {
    // Extract the security reporting section from CONTRIBUTING.md.
    // Only look under headings that mention "security", "vulnerability",
    // or "responsible disclosure".
    let mut in_security_section = false;
    let mut section_depth = 0;
    let mut security_text = String::new();

    for line in contents.lines() {
        let trimmed = line.trim();
        let heading_depth = trimmed.chars().take_while(|c| *c == '#').count();
        let is_heading = heading_depth > 0 && trimmed.starts_with('#');

        if is_heading {
            let heading_text = trimmed.trim_start_matches('#').trim().to_lowercase();

            if in_security_section {
                // Same or higher-level heading ends the security section
                if heading_depth <= section_depth {
                    in_security_section = false;
                }
            }

            if !in_security_section
                && (heading_text.contains("security")
                    || heading_text.contains("vulnerability")
                    || heading_text.contains("responsible disclosure"))
            {
                in_security_section = true;
                section_depth = heading_depth;
                continue;
            }
        }

        if in_security_section {
            security_text.push_str(line);
            security_text.push('\n');
        }
    }

    if security_text.trim().is_empty() {
        return None;
    }

    parse_security_contact(&security_text)
}

pub(crate) fn parse_issue_template_security(contents: &str) -> Option<String> {
    // Look for security reporting links or emails in issue templates.
    // YAML front matter or plain markdown.
    parse_security_contact(contents)
}

fn find_mailto_or_email(contents: &str) -> Option<String> {
    let rewritten = rewrite_markdown_links(contents);

    for destination in security_link_destinations(contents) {
        if let Some(email) = extract_email_candidate(&destination) {
            return Some(email);
        }
    }

    for token in rewritten.split_whitespace() {
        if let Some(email) = extract_email_candidate(token) {
            return Some(email);
        }
    }

    // Additional pass: scan for bare emails anywhere (e.g. "contact security@foo.com")
    // This helps when punctuation or surrounding text interferes with simple split.
    if let Some(email) = find_bare_email_anywhere(contents) {
        return Some(email);
    }

    None
}

fn find_bare_email_anywhere(text: &str) -> Option<String> {
    let lower = text.to_ascii_lowercase();
    // Look for common security email patterns
    for prefix in [
        "security@",
        "vuln@",
        "security-response@",
        "cve@",
        "disclosure@",
    ] {
        if let Some(pos) = lower.find(prefix) {
            // extract until whitespace or common terminators
            let start = pos;
            let mut end = start;
            for (i, ch) in text[start..].char_indices() {
                if ch.is_whitespace() || matches!(ch, ')' | ']' | '>' | ',' | ';' | '"' | '\'') {
                    end = start + i;
                    break;
                }
                end = start + i + ch.len_utf8();
            }
            if end > start {
                let candidate = &text[start..end];
                let cleaned = trim_contact_token(candidate);
                if looks_like_email(cleaned) {
                    return Some(cleaned.to_string());
                }
            }
        }
    }
    None
}

fn find_first_url(contents: &str) -> Option<String> {
    if let Some(url) = find_best_security_url(contents) {
        return Some(url);
    }

    // Fall back to the first URL that looks semantically related to security reporting.
    // This catches cases where the URL contains "security" in its path but the surrounding
    // text triggers a negative score (e.g., "policy" in the line penalizes the URL).
    let rewritten = rewrite_markdown_links(contents);

    for destination in security_link_destinations(contents) {
        if let Some(url) = extract_url_candidate(&destination) {
            if looks_like_security_url(&url) {
                return Some(url);
            }
        }
    }

    for token in rewritten.split_whitespace() {
        if let Some(url) = extract_url_candidate(token) {
            if looks_like_security_url(&url) {
                return Some(url);
            }
        }
    }

    None
}

fn find_best_security_url(contents: &str) -> Option<String> {
    let mut current_heading = String::new();
    let mut best: Option<(i32, String)> = None;

    for line in contents.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if let Some(heading) = markdown_heading_text(trimmed) {
            current_heading = heading;
            continue;
        }

        for url in security_urls_in_line(trimmed) {
            let score = security_reporting_score(&current_heading, trimmed, &url);
            if score <= 0 {
                continue;
            }
            match &best {
                Some((best_score, _)) if *best_score >= score => {}
                _ => best = Some((score, url)),
            }
        }
    }

    best.map(|(_, url)| url)
}

fn looks_like_security_url(url: &str) -> bool {
    let lowered = url.to_ascii_lowercase();

    // Reject known non-security URL patterns.
    let non_security_path_keywords = [
        "blog", "docs/", "tutorial", "guide/", "wiki/", "example", "demo",
    ];
    for keyword in &non_security_path_keywords {
        if lowered.contains(keyword) {
            return false;
        }
    }

    // Accept URLs that contain security-related keywords in their path.
    let security_path_keywords = [
        "security",
        "vulnerability",
        "disclosure",
        "advisories",
        "report",
        "contact",
        "issue",
    ];
    for keyword in &security_path_keywords {
        if lowered.contains(keyword) {
            return true;
        }
    }

    false
}

fn markdown_heading_text(line: &str) -> Option<String> {
    let trimmed = line.trim_start();
    let hashes = trimmed.chars().take_while(|ch| *ch == '#').count();
    if hashes == 0 {
        return None;
    }

    let text = trimmed[hashes..].trim();
    (!text.is_empty()).then(|| text.to_ascii_lowercase())
}

fn security_urls_in_line(line: &str) -> Vec<String> {
    let rewritten = rewrite_markdown_links(line);
    let mut urls = Vec::new();

    for (label, destination) in extract_markdown_links(line) {
        if let Some(url) = extract_url_candidate(&label) {
            push_unique(&mut urls, url);
        }
        if let Some(url) = extract_url_candidate(&destination) {
            push_unique(&mut urls, url);
        }
    }

    for destination in markdown_reference_destinations(line) {
        if let Some(url) = extract_url_candidate(&destination) {
            push_unique(&mut urls, url);
        }
    }

    for destination in html_href_destinations(line) {
        if let Some(url) = extract_url_candidate(&destination) {
            push_unique(&mut urls, url);
        }
    }

    for token in rewritten.split_whitespace() {
        if let Some(url) = extract_url_candidate(token) {
            push_unique(&mut urls, url);
        }
    }

    urls
}

fn security_reporting_score(heading: &str, line: &str, url: &str) -> i32 {
    let heading_lower = heading.to_ascii_lowercase();
    let line_lower = line.to_ascii_lowercase();
    let url_lower = url.to_ascii_lowercase();
    let mut score = 0;

    if heading_lower.contains("security") {
        score += 3;
    }
    if heading_lower.contains("report") || heading_lower.contains("disclosure") {
        score += 6;
    }
    if [
        "report",
        "contact",
        "disclosure",
        "response center",
        "vulnerability",
    ]
    .iter()
    .any(|needle| line_lower.contains(needle))
    {
        score += 4;
    }
    if ["report", "create-report", "contact", "submit"]
        .iter()
        .any(|needle| url_lower.contains(needle))
    {
        score += 3;
    }

    // Lighter penalty for "policy" (common in legitimate SECURITY.md titles)
    // only apply full penalty if no strong positive signals in line/url.
    let has_policy = heading_lower.contains("policy") || line_lower.contains("policy");
    let has_strong_positive = heading_lower.contains("report")
        || heading_lower.contains("disclosure")
        || line_lower.contains("report")
        || line_lower.contains("vulnerability")
        || url_lower.contains("security")
        || url_lower.contains("report");
    if has_policy && !has_strong_positive {
        score -= 3;
    } else if has_policy {
        score -= 1;
    }

    if ["definition", "faq", "bounty", "preferred languages"]
        .iter()
        .any(|needle| heading_lower.contains(needle) || line_lower.contains(needle))
    {
        score -= 4;
    }
    if ["definition", "faq", "bounty"]
        .iter()
        .any(|needle| url_lower.contains(needle))
    {
        score -= 3;
    }
    if ["aka.ms/", "bit.ly/", "t.co/", "goo.gl/", "tinyurl.com/"]
        .iter()
        .any(|needle| url_lower.contains(needle))
    {
        score -= 2;
    }

    score
}

fn extract_email_candidate(token: &str) -> Option<String> {
    if let Some(address) = extract_mailto_address(token) {
        return Some(address);
    }

    let cleaned = trim_contact_token(token);
    looks_like_email(cleaned).then(|| cleaned.to_string())
}

fn extract_mailto_address(token: &str) -> Option<String> {
    let cleaned = trim_contact_token(token);
    let prefix = cleaned.get(..7)?;
    if !prefix.eq_ignore_ascii_case("mailto:") {
        return None;
    }

    let value = cleaned
        .get(7..)
        .unwrap_or("")
        .split(['?', '#'])
        .next()
        .map(trim_contact_token)
        .unwrap_or("");
    looks_like_email(value).then(|| value.to_string())
}

fn extract_url_candidate(token: &str) -> Option<String> {
    let cleaned = trim_contact_token(token);
    if cleaned.starts_with("https://") || cleaned.starts_with("http://") {
        Some(cleaned.to_string())
    } else {
        None
    }
}

fn security_link_destinations(contents: &str) -> Vec<String> {
    let mut destinations = Vec::new();

    for destination in markdown_link_destinations(contents) {
        push_unique(&mut destinations, destination);
    }
    for destination in markdown_reference_destinations(contents) {
        push_unique(&mut destinations, destination);
    }
    for destination in html_href_destinations(contents) {
        push_unique(&mut destinations, destination);
    }

    destinations
}

fn markdown_link_destinations(contents: &str) -> Vec<String> {
    extract_markdown_links(contents)
        .into_iter()
        .map(|(_, url)| url)
        .collect()
}

fn markdown_reference_destinations(contents: &str) -> Vec<String> {
    let mut destinations = Vec::new();

    for line in contents.lines() {
        let trimmed = line.trim();
        if !trimmed.starts_with('[') {
            continue;
        }
        let Some(split_idx) = trimmed.find("]:") else {
            continue;
        };
        if let Some(destination) = extract_link_destination(&trimmed[split_idx + 2..]) {
            destinations.push(destination);
        }
    }

    destinations
}

fn html_href_destinations(contents: &str) -> Vec<String> {
    let mut destinations = Vec::new();
    let lower = contents.to_ascii_lowercase();
    let bytes = contents.as_bytes();
    let mut idx = 0;

    while let Some(rel) = lower[idx..].find("href=") {
        let mut start = idx + rel + 5;
        while start < bytes.len() && bytes[start].is_ascii_whitespace() {
            start += 1;
        }
        if start >= bytes.len() {
            break;
        }

        let (raw_start, raw_end) = match bytes[start] {
            b'"' | b'\'' => {
                let quote = bytes[start] as char;
                let raw_start = start + 1;
                let Some(rel_end) = contents[raw_start..].find(quote) else {
                    break;
                };
                (raw_start, raw_start + rel_end)
            }
            _ => {
                let raw_start = start;
                let raw_end = contents[raw_start..]
                    .find(|ch: char| ch.is_whitespace() || ch == '>')
                    .map(|rel_end| raw_start + rel_end)
                    .unwrap_or(contents.len());
                (raw_start, raw_end)
            }
        };

        if let Some(destination) = extract_link_destination(&contents[raw_start..raw_end]) {
            destinations.push(destination);
        }

        idx = raw_end;
    }

    destinations
}

fn extract_link_destination(raw: &str) -> Option<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return None;
    }

    let destination = if let Some(stripped) = trimmed.strip_prefix('<') {
        stripped.split('>').next().unwrap_or("")
    } else {
        trimmed.split_whitespace().next().unwrap_or("")
    };
    let cleaned = trim_contact_token(destination);
    (!cleaned.is_empty()).then(|| cleaned.to_string())
}

fn is_team_handle(token: &str) -> bool {
    token
        .strip_prefix('@')
        .map_or(false, |rest| rest.contains('/'))
}

fn trim_contact_token(token: &str) -> &str {
    token.trim_matches(|ch: char| {
        matches!(
            ch,
            '<' | '>'
                | '('
                | ')'
                | '['
                | ']'
                | '{'
                | '}'
                | ','
                | ';'
                | ':'
                | '.'
                | '"'
                | '\''
                | '`'
        )
    })
}

fn looks_like_email(token: &str) -> bool {
    let mut parts = token.split('@');
    let local = parts.next().unwrap_or("");
    let domain = parts.next().unwrap_or("");
    !local.is_empty()
        && !domain.is_empty()
        && parts.next().is_none()
        && token
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '.' | '_' | '%' | '+' | '-' | '@'))
        && domain.contains('.')
        && !token.starts_with("http://")
        && !token.starts_with("https://")
}
