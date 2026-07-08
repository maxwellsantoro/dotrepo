//! URL quality gates: structural validity checks for general repository URLs
//! and stricter checks for actionable security-reporting destinations.

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
    if trimmed.is_empty() {
        return false;
    }

    let lower = trimmed.to_ascii_lowercase();

    // Reject channels that are not security-reporting surfaces.
    if lower.contains("discord.gg/")
        || lower.contains("discord.com/invite")
        || lower.starts_with("https://x.com/")
        || lower.starts_with("https://twitter.com/")
        || lower.contains("/issues/new")
        || lower.ends_with("/issues")
    {
        return false;
    }

    // GitHub vulnerability disclosure and repository security surfaces.
    if lower.contains("/security/advisories/new")
        || is_github_security_surface(&lower)
        || lower.contains("docs.github.com/")
            && lower.contains("privately-reporting-a-security-vulnerability")
    {
        return true;
    }

    // Microsoft Security Response Center report forms.
    if lower.contains("msrc.microsoft.com/create-report")
        || lower.contains("msrc.microsoft.com/report/vulnerability")
        || lower.contains("aka.ms/security")
    {
        return true;
    }

    // Coordinated disclosure platforms.
    if lower.contains("hackerone.com/")
        || lower.contains("bugcrowd.com/")
        || lower.contains("bughunters.google.com/")
        || lower.contains("tidelift.com/security")
        || lower.contains("g.co/vulnz")
        || lower.contains("synack.com/")
        || lower.contains("intigriti.com/")
    {
        return true;
    }

    // Vendor security pages with clear first-party reporting instructions.
    if lower.contains("djangoproject.com/security")
        || lower.contains("go.dev/security")
        || lower.contains("kubernetes.io/")
            && (lower.contains("/security") || lower.contains("report-a-vulnerability"))
        || lower.contains("cypress.io/security")
        || lower.contains("kotlinlang.org/docs/security")
        || lower.contains("prometheus.io/") && lower.contains("security")
        || lower.contains("postgresql.org/support/security")
        || lower.contains("chromium.org/") && lower.contains("security")
        || lower.contains("notion.site/") && lower.contains("vulnerability")
        || lower.contains("contribute.freecodecamp.org/") && lower.contains("security")
        // Meta / Facebook coordinated disclosure.
        || lower.contains("facebook.com/whitehat")
        || lower.contains("www.facebook.com/whitehat")
        // Historical Node security reporting portal.
        || lower.contains("nodesecurity.io/")
        // Project books/docs with a dedicated security page (stem match).
        || lower.contains("/security.html")
        || lower.ends_with("security.html")
    {
        return true;
    }

    // Generic first-party policy URLs with an explicit security path segment.
    if let Some(host) = security_url_host(&lower) {
        if !is_generic_issue_or_homepage_path(&lower, host)
            && security_path_segments(&lower).any(|segment| is_security_path_token(segment))
        {
            return true;
        }
    }

    false
}

fn is_github_security_surface(lower: &str) -> bool {
    if !lower.contains("github.com/") {
        return false;
    }

    if lower.contains("/security/advisories")
        || lower.contains("/security/policy")
        || lower.ends_with("/security")
    {
        return true;
    }

    lower.contains("security.md")
        || lower.contains("/security/readme")
        || lower.contains("/security#")
        || lower.contains("early-disclosure")
}

fn security_url_host(lower: &str) -> Option<&str> {
    lower
        .strip_prefix("https://")
        .or_else(|| lower.strip_prefix("http://"))
        .and_then(|rest| rest.split('/').next())
        .filter(|host| !host.is_empty())
}

fn security_path_segments(lower: &str) -> impl Iterator<Item = &str> {
    // Keep bare path tokens and file stems such as `security.html` (the old
    // filter dropped any segment containing `.`, which silently rejected real
    // first-party security doc URLs like rust-analyzer's security.html page).
    lower
        .split(['/', '?', '#'])
        .filter(|segment| !segment.is_empty())
        .filter(|segment| !segment.contains(':')) // drop scheme leftovers
}

fn is_security_path_token(segment: &str) -> bool {
    let token = segment
        .rsplit_once('.')
        .map(|(stem, _ext)| stem)
        .unwrap_or(segment);
    matches!(
        token,
        "security" | "vulnerability" | "vulnerabilities" | "responsible-disclosure" | "whitehat"
    )
}

fn is_generic_issue_or_homepage_path(lower: &str, host: &str) -> bool {
    if host == "github.com" {
        let path = lower
            .split_once("github.com/")
            .map(|(_, rest)| rest)
            .unwrap_or("");
        let segments: Vec<_> = path.split('/').filter(|s| !s.is_empty()).collect();
        // Bare repo homepages like github.com/owner/repo are not reporting surfaces.
        return segments.len() <= 2 && !lower.contains("security");
    }

    lower.contains("/about") && !lower.contains("security")
}
