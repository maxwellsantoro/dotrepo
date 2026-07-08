//! Security-contact extraction: SECURITY.md / CONTRIBUTING.md / issue-template
//! parsing for mailto addresses, bare emails, and scored security-reporting URLs.
use super::super::push_unique;
use super::super::types::SecurityImportMetadata;
use super::markdown::{extract_markdown_links, rewrite_markdown_links};
use super::urls::is_actionable_security_url;

pub(crate) fn parse_security_contact(contents: &str) -> Option<String> {
    match find_mailto_or_email(contents) {
        Some(email) => {
            if email_in_reporting_context(contents, &email) {
                return Some(email);
            }
            // The only email in the document is incidental: SECURITY.md files
            // routinely list downstream packagers, credits, or moderation
            // contacts far from the actual reporting instruction. A scored
            // security-reporting URL is the actionable channel in that case.
            // Non-actionable URLs must not win over a real mailbox.
            match find_best_security_url(contents).filter(|url| is_actionable_security_url(url)) {
                Some(url) => Some(url),
                None => Some(email),
            }
        }
        None => find_first_url(contents).filter(|url| is_actionable_security_url(url)),
    }
}

fn email_in_reporting_context(contents: &str, email: &str) -> bool {
    let email_lower = email.to_ascii_lowercase();
    let mut current_heading = String::new();
    for line in contents.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        if let Some(heading) = markdown_heading_text(trimmed) {
            current_heading = heading;
            continue;
        }
        let line_lower = trimmed.to_ascii_lowercase();
        if !line_lower.contains(&email_lower) {
            continue;
        }
        if line_lower.contains("mailto:") {
            return true;
        }
        let heading_lower = current_heading.to_ascii_lowercase();
        if ["report", "disclos", "security", "contact"]
            .iter()
            .any(|needle| heading_lower.contains(needle))
        {
            return true;
        }
        if ["report", "email", "contact", "disclos", "send", "write to"]
            .iter()
            .any(|needle| line_lower.contains(needle))
        {
            return true;
        }
    }
    false
}

pub(crate) fn parse_security_import_metadata(contents: &str) -> SecurityImportMetadata {
    match parse_security_contact(contents) {
        Some(contact) if looks_like_email(&contact) => SecurityImportMetadata {
            contact: Some(contact),
            note: None,
        },
        Some(contact) if is_actionable_security_url(&contact) => SecurityImportMetadata {
            contact: Some(contact),
            note: Some(
                "SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL."
                    .to_string(),
            ),
        },
        // Non-actionable URLs (Discord, bare repo homepages, issue forms,
        // personal sites) are not security reporting channels. Leave contact
        // unset so the importer can record honest `unknown` when SECURITY.md
        // exists, rather than storing medium-confidence junk that blocks
        // promotion forever.
        Some(_) | None => SecurityImportMetadata::default(),
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

pub(crate) fn extract_link_destination(raw: &str) -> Option<String> {
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

pub(crate) fn is_team_handle(token: &str) -> bool {
    token
        .strip_prefix('@')
        .is_some_and(|rest| rest.contains('/'))
}

pub(crate) fn trim_contact_token(token: &str) -> &str {
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

pub(crate) fn looks_like_email(token: &str) -> bool {
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

#[cfg(test)]
mod security_contact_tests {
    use super::parse_security_contact;

    #[test]
    fn reporting_url_beats_incidental_downstream_packager_email() {
        // Shaped like psf/requests: the reporting instruction is an advisory
        // URL in the opening section, and the only email in the document is a
        // downstream packager notified ahead of releases.
        let contents = r#"# Vulnerability Disclosure

If you think you have found a potential security vulnerability, please
open a [draft Security Advisory](https://github.com/example/project/security/advisories/new)
via GitHub.

## Process

### Timeline

Currently the list of people we actively contact ahead of a public release is:

-   Python Maintenance Team, Red Hat (python-maint@redhat.com)
-   Daniele Tricoli, Debian (@eriol)
"#;
        assert_eq!(
            parse_security_contact(contents).as_deref(),
            Some("https://github.com/example/project/security/advisories/new"),
        );
    }

    #[test]
    fn reporting_context_email_still_beats_policy_url() {
        let contents = r#"# Security Policy

## Reporting a Vulnerability

Please email security@example.com with details.
See https://example.com/security/policy for scope.
"#;
        assert_eq!(
            parse_security_contact(contents).as_deref(),
            Some("security@example.com"),
        );
    }

    #[test]
    fn lone_email_without_context_is_kept_when_no_url_exists() {
        let contents = "# Notes\n\nMaintained by team@example.com.\n";
        assert_eq!(
            parse_security_contact(contents).as_deref(),
            Some("team@example.com"),
        );
    }
}

#[cfg(test)]
mod security_url_tests {
    use super::super::urls::is_actionable_security_url;

    #[test]
    fn recognizes_common_security_reporting_surfaces() {
        for url in [
            "https://github.com/axios/axios/security",
            "https://github.com/ShareX/ShareX/security",
            "https://github.com/eslint/.github/blob/master/SECURITY.md",
            "https://github.com/containerd/project/blob/main/SECURITY.md#reporting-a-vulnerability",
            "https://hackerone.com/ibm",
            "https://bugcrowd.com/engagements/openai",
            "https://tidelift.com/security",
            "https://bughunters.google.com/report",
            "https://g.co/vulnz",
            "https://go.dev/security/policy",
            "https://kubernetes.io/docs/reference/issues-security/security/#report-a-vulnerability",
            "https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability",
            "https://rust-analyzer.github.io/book/security.html",
            "https://www.facebook.com/whitehat",
            "https://nodesecurity.io/report",
            "https://github.com/grpc/proposal/blob/master/P4-grpc-cve-process.md",
        ] {
            assert!(is_actionable_security_url(url), "expected actionable: {url}");
        }
    }

    #[test]
    fn non_actionable_security_md_urls_do_not_become_contacts() {
        // SECURITY.md that only links a Discord / homepage / issue form must
        // not produce a medium-confidence security_contact value.
        let discord_only = "# Security\n\nJoin us on https://discord.gg/NtAbbGn\n";
        assert_eq!(super::parse_security_contact(discord_only), None);
        assert!(super::parse_security_import_metadata(discord_only)
            .contact
            .is_none());

        let bare_repo = "# Security\n\nSee https://github.com/junegunn/fzf for details.\n";
        assert_eq!(super::parse_security_contact(bare_repo), None);

        let actionable = "# Security\n\nReport at https://github.com/axios/axios/security\n";
        assert_eq!(
            super::parse_security_contact(actionable).as_deref(),
            Some("https://github.com/axios/axios/security"),
        );
    }

    #[test]
    fn rejects_non_reporting_channels() {
        for url in [
            "https://blog.burntsushi.net/about/",
            "https://github.com/junegunn/fzf",
            "https://github.com/dani-garcia/vaultwarden/issues",
            "https://github.com/LadybirdBrowser/ladybird/issues/new?template=bug_report.yml",
            "https://discord.gg/NtAbbGn",
            "https://x.com/openai",
            "https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=traefik",
            "https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck",
            "https://bitwarden.com/contact",
        ] {
            assert!(!is_actionable_security_url(url), "expected rejected: {url}");
        }
    }
}
