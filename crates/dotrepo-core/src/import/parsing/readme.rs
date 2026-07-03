//! README title/description/name extraction: HTML/setext heading parsing,
//! description-paragraph detection, and universal post-extraction cleaners
//! (name/description normalization, generic-phrase rejection).
use super::super::types::ReadmeMetadata;
use super::markdown::{
    is_markdown_reference_definition, is_probable_docs_signal_line, is_probable_readme_nav_line,
    normalize_readme_text, parse_readme_docs_metadata, starts_with_ordered_list_item,
    strip_badge_run,
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
            if let Some(title) = parse_readme_logo_title(trimmed) {
                metadata.title = Some(title);
                idx += 1;
                continue;
            }
            if let Some((title, advance)) = try_parse_multiline_html_image_title(&lines, idx) {
                metadata.title = Some(title);
                idx += advance;
                continue;
            }
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

        if metadata.title.is_some() && metadata.description.is_none() {
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

    if metadata.title.is_none() && metadata.description.is_none() {
        metadata.description = parse_readme_description(&lines, 0).map(|(value, _)| value);
    }

    let docs = parse_readme_docs_metadata(&lines);
    metadata.docs_root = docs.root;
    metadata.docs_getting_started = docs.getting_started;

    metadata
}

fn parse_readme_logo_title(line: &str) -> Option<String> {
    let lower = line.to_ascii_lowercase();
    let image_start = lower.find("<img")?;
    let image = &line[image_start..];
    let image_lower = &lower[image_start..];
    let title = parse_html_attr(image, image_lower, "alt")?;
    credible_logo_alt_title(&title)
}

fn try_parse_multiline_html_image_title(lines: &[&str], idx: usize) -> Option<(String, usize)> {
    let line = lines.get(idx)?.trim();
    let lower = line.to_ascii_lowercase();
    if !lower.contains("<img") || lower.contains('>') {
        return None;
    }

    let mut accumulated = String::from(line);
    let mut scan = idx + 1;
    let mut lines_consumed = 1;
    while scan < lines.len() {
        let next = lines[scan].trim();
        lines_consumed += 1;
        if !next.is_empty() {
            accumulated.push(' ');
            accumulated.push_str(next);
        }
        if next.contains('>') {
            let lower_accumulated = accumulated.to_ascii_lowercase();
            let title = parse_html_attr(&accumulated, &lower_accumulated, "alt")?;
            return credible_logo_alt_title(&title).map(|value| (value, lines_consumed));
        }
        scan += 1;
    }
    None
}

pub(crate) fn parse_html_attr(image: &str, image_lower: &str, attr: &str) -> Option<String> {
    let attr_start = image_lower.find(&format!("{attr}="))? + attr.len() + 1;
    let quote = image.as_bytes().get(attr_start).copied()? as char;
    if quote != '"' && quote != '\'' {
        return None;
    }
    let value_start = attr_start + 1;
    let value_end = image[value_start..].find(quote)? + value_start;
    normalize_readme_text(&image[value_start..value_end])
}

fn credible_logo_alt_title(title: &str) -> Option<String> {
    let lowered = title.to_ascii_lowercase();
    let badge_words = [
        "badge", "build", "ci", "coverage", "docs", "image", "license", "logo", "package",
        "release", "status", "test", "version",
    ];
    if is_non_project_heading(title)
        || badge_words.iter().any(|word| {
            lowered
                .split(|ch: char| !ch.is_ascii_alphanumeric())
                .any(|part| part == *word)
        })
    {
        return None;
    }
    Some(title.to_string())
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
    "website",
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
        || is_promotional_copy(line)
    {
        return None;
    }

    let description = line.trim_start_matches('>').trim();
    normalize_readme_text(description)
        .filter(|value| value.chars().any(|ch| ch.is_alphanumeric()))
        .filter(|value| !is_non_project_heading(value))
        .filter(|value| !looks_like_artifact(value))
        .filter(|value| !is_quoted_tagline(value))
}

fn is_promotional_copy(line: &str) -> bool {
    let normalized = normalize_readme_text(line).unwrap_or_default();
    let lower = normalized.to_ascii_lowercase();
    [
        "announcing ",
        "new release",
        "now available",
        "program and tickets",
        "we are excited to announce",
        "we're excited to announce",
    ]
    .iter()
    .any(|phrase| lower.contains(phrase))
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
    [
        "src=\"",
        "alt=\"",
        "href=\"",
        "width=\"",
        "height=\"",
        "align=\"",
        "class=\"",
        "style=\"",
    ]
    .iter()
    .any(|attribute| lowered.contains(attribute))
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
pub(crate) fn clean_project_name(raw: &str, _repo_dir_fallback: &str) -> Option<String> {
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

    // Reject questions, release announcements, nav/link bars, badge spill, and
    // sentence/tagline-style headings. A README H1 like "## What is Redis?" or
    // "v2.15 is out!" is far worse than the honest dir-name fallback.
    if looks_like_sentence_or_non_name(&cleaned) {
        return None;
    }

    Some(cleaned)
}

/// Return true when an extracted candidate is clearly not a project identifier.
///
/// README titles frequently reuse sentence, announcement, or chrome patterns
/// (`## What is Redis?`, `# v2.15 is out!`, `# Website | Roadmap | Blog`,
/// `# pandas: A Powerful Python Data Analysis Toolkit`). Accepting any of them
/// yields a `repo.name` worse than the dir-name fallback, so reject and let the
/// caller fall back. The longest valid extracted name observed in the fixture
/// suite is four words, so a six-plus-word or 60-plus-char result is treated as
/// a leaked description or section heading.
fn looks_like_sentence_or_non_name(name: &str) -> bool {
    let trimmed = name.trim();
    let lowered = trimmed.to_ascii_lowercase();

    // No real project name ends with a question or exclamation mark.
    if trimmed.ends_with('?') || trimmed.ends_with('!') {
        return true;
    }
    // Markdown link / image alt-text spill: `Website](https://...) ![CI](...)`.
    if trimmed.contains("](") || trimmed.contains("![") {
        return true;
    }
    // Pipe-delimited nav/link bars: `Website | Roadmap | Blog | Docs`.
    if trimmed.contains(" | ") {
        return true;
    }
    // Question-style leads, with or without terminal punctuation.
    const QUESTION_LEADS: &[&str] = &[
        "what ", "why ", "how ", "when ", "where ", "who ", "whose ", "is ", "are ", "do ",
        "does ", "did ", "can ", "could ", "should ", "would ", "will ",
    ];
    if QUESTION_LEADS.iter().any(|lead| lowered.starts_with(lead)) {
        return true;
    }
    // Release/announcement leads.
    const ANNOUNCEMENT_LEADS: &[&str] = &[
        "introducing ",
        "announcing ",
        "welcome to ",
        "welcome back ",
        "we are ",
        "we're ",
        "new release ",
        "now available ",
    ];
    if ANNOUNCEMENT_LEADS
        .iter()
        .any(|lead| lowered.starts_with(lead))
    {
        return true;
    }
    if let Some(rest) = lowered.strip_prefix('v') {
        // Version-release announcements: "v2.15 is out", "v2 is out". The
        // version run is followed by whitespace. Genuine names like "V8" or
        // "v2rayN" have no such space and must survive.
        let ver_end = rest
            .find(|c: char| !c.is_ascii_digit() && c != '.')
            .unwrap_or(rest.len());
        let version = &rest[..ver_end];
        let has_digit = version.chars().any(|c| c.is_ascii_digit());
        if has_digit && rest[ver_end..].starts_with(' ') {
            return true;
        }
    }
    if let Some(rest) = lowered.strip_prefix("version ") {
        if rest.chars().next().is_some_and(|c| c.is_ascii_digit()) {
            return true;
        }
    }
    // Sentence/tagline length: real project names are short.
    let word_count = trimmed.split_whitespace().count();
    word_count >= 6 || trimmed.chars().count() >= 60
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
    if let Some(idx) = name.find(" – ") {
        let candidate = name[..idx].trim();
        if candidate.len() >= 2 {
            return candidate.to_string();
        }
    }
    if let Some(idx) = name.find(": ") {
        let candidate = name[..idx].trim();
        // "pandas: tagline" / "fp-go: tagline" → keep the single-token project
        // name and drop the tagline. Require a single token so we never split a
        // real multi-word name on a mid-sentence colon.
        if candidate.len() >= 2 && !candidate.contains(' ') {
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
