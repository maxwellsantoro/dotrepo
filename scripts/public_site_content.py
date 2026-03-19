ARTICLES = [
    {
        "slug": "what-the-ais-think-about-dotrepo",
        "title": "What the AIs Think About dotrepo",
        "dek": "12 models. 10 questions each. One protocol built for them.",
        "published": "March 18, 2026",
        "summary": (
            "A dotrepo-side synthesis of a 12-model interview round about repository "
            "metadata, trust, adoption, and what AI coding tools actually need."
        ),
        "kicker": "AI interview experiment",
        "tags": ["dotrepo", "ai", "metadata", "protocol", "mcp"],
        "companion_url": (
            "https://maxwellsantoro.com/writing/"
            "i-asked-12-ai-models-what-they-want-from-a-repository-metadata-protocol/"
        ),
        "body_html": """
<div class="article-callout">
  <p>This is the dotrepo-side synthesis of the interview round. The companion essay on MaxwellSantoro.com covers the broader framing and why this experiment was worth running at all.</p>
  <p><a href="https://maxwellsantoro.com/writing/i-asked-12-ai-models-what-they-want-from-a-repository-metadata-protocol/">Read the sister article</a></p>
</div>

<h2>The Experiment</h2>
<p>dotrepo is an open metadata protocol for software repositories. It is designed for three audiences: maintainers, human users, and AI agents. Since AI agents are a first-class consumer of the protocol, it made sense to ask them directly what they want from it.</p>
<p>I sent the same 10-question prompt to 12 different AI models across 8 providers. Fresh conversations, no priming, no pep talk. The goal was not affirmation. The goal was pressure testing: what feels obviously useful, what is missing, what looks risky, and what would actually make an agent check dotrepo first.</p>
<p>The answers converged much harder than expected. That convergence is the signal.</p>

<h2>Models Interviewed</h2>
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Model</th>
        <th>Provider</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>ChatGPT 5.4 Thinking</td><td>OpenAI</td><td>Logged-in session</td></tr>
      <tr><td>ChatGPT 5.4 Thinking</td><td>OpenAI</td><td>Incognito session</td></tr>
      <tr><td>Claude Opus 4.6 Extended</td><td>Anthropic</td><td>Logged-in session</td></tr>
      <tr><td>Claude Opus 4.6 Extended</td><td>Anthropic</td><td>Incognito session</td></tr>
      <tr><td>Gemini Pro 3.1</td><td>Google</td><td>Fresh conversation</td></tr>
      <tr><td>Gemini Thinking 3.1</td><td>Google</td><td>Fresh conversation</td></tr>
      <tr><td>Grok Expert 4.20</td><td>xAI</td><td>Logged-in session</td></tr>
      <tr><td>Grok Expert 4.20</td><td>xAI</td><td>Incognito session</td></tr>
      <tr><td>GLM-5</td><td>Zhipu AI</td><td>Fresh conversation</td></tr>
      <tr><td>Hunter Alpha</td><td>OpenRouter</td><td>Fresh conversation</td></tr>
      <tr><td>MiniMax M2.5</td><td>MiniMax</td><td>Fresh conversation</td></tr>
      <tr><td>Nemotron 3 Super</td><td>NVIDIA</td><td>Fresh conversation</td></tr>
    </tbody>
  </table>
</div>
<p>Where possible, ChatGPT and Grok were grounded against the live repo and public site, and both ChatGPT, Claude, and Grok were tested in more than one session shape to check whether the takeaways were stable.</p>

<h2>Consensus Findings</h2>

<h3>1. Build and test commands are the sharpest pain point</h3>
<p>This was unanimous. Every model described “how do I actually build and test this repo?” as the most expensive reasoning step in unfamiliar codebases. The hard part is not inferring the language. It is getting from the presence of build files to the exact, correct command with the right flags, prerequisites, and side effects.</p>
<blockquote>
  <p>The gap between “I see a build file” and “I know the correct command including flags and prerequisites” is where most wasted effort lives.</p>
</blockquote>
<p>The implication for dotrepo is direct: structured build and test metadata is not ornamental. It is the highest-value field family in the protocol.</p>

<h3>2. The overlay index is the wedge</h3>
<p>All 12 models independently identified the public overlay index as dotrepo’s smartest near-term design move. It breaks the adoption trap that kills most metadata standards by making the protocol useful before maintainers opt in.</p>
<p>That view was not abstract. Several models gave concrete coverage thresholds for when dotrepo would flip from “nice to check” to “I check this first.” The shared theme: the protocol is already coherent; the missing ingredient is enough reviewed data that checking dotrepo is usually cheaper than not checking it.</p>

<h3>3. Trust and provenance is the moat</h3>
<p>The distinction between maintainer-declared facts, imported facts, and inferred facts was universally praised as the genuinely differentiated part of the project. Models described using that metadata to change both language and behavior:</p>
<ul>
  <li><strong>Declared or verified</strong>: act confidently and cite it directly.</li>
  <li><strong>Imported</strong>: treat it as a strong default but mention the source.</li>
  <li><strong>Inferred</strong>: use it as a hypothesis and verify before execution.</li>
  <li><strong>Low confidence</strong>: warn the user and avoid silent action.</li>
</ul>
<p>That is exactly the behavior dotrepo is trying to induce, and it is already visible on the live public surface at <a href="/v0/repos/index.json">/v0/repos/index.json</a> and in trust-aware queries such as <a href="/v0/repos/github.com/BurntSushi/ripgrep/query?path=repo.description">this repository field query</a>.</p>

<h3>4. Stale metadata is the most dangerous failure mode</h3>
<p>This was also unanimous. Every model made some version of the same argument: stale trusted metadata is worse than no metadata, because it suppresses the skepticism that would otherwise push an agent back toward the source materials.</p>
<p>That is why freshness is first-class on dotrepo’s public surface. Every response carries snapshot freshness and digest metadata, and the top-level meta document at <a href="/v0/meta.json">/v0/meta.json</a> exists specifically so agents and operators can reason about staleness instead of pretending it away.</p>

<h3>5. Keep the core schema brutally small</h3>
<p>Every model warned against schema bloat. The useful framing was not “small is elegant.” It was “small is how this survives.” The winning version of dotrepo answers a short list of high-value questions reliably: what this repo is, how it builds, how it tests, where the real docs are, who owns it, and what trust level attaches to each answer.</p>

<h2>Strongest Criticisms</h2>
<ol>
  <li><strong>The project scope is still very ambitious for one repo.</strong> The protocol, toolchain, public API, claim workflows, and deployment story are all real now. That is impressive, but it also means the ratio of infrastructure to adoption is something to watch closely.</li>
  <li><strong>Plain-string build commands are not enough.</strong> Multiple models wanted prerequisites, environment requirements, platform constraints, and an explicit “safe for agent execution?” shape.</li>
  <li><strong>Monorepo and workspace semantics remain an obvious gap.</strong> The repos where metadata is most painful are often exactly the repos where workspace structure matters most.</li>
  <li><strong>Record-level trust is not always granular enough.</strong> Several models argued that identity may be maintainer-declared while build commands are imported and docs topology is inferred. That pressure toward field-level provenance is real even if it does not need to land immediately.</li>
  <li><strong>The MCP server still lacks remote lookup.</strong> The hosted HTTP surface already supports predictable repo-first lookup, but the MCP layer still requires local context for most workflows.</li>
  <li><strong>The index is still too small to change behavior by default.</strong> Five reviewed overlays proves the architecture. It does not yet create the habit loop where an agent expects dotrepo coverage on arbitrary open-source repos.</li>
</ol>

<h2>Missing MCP Operations</h2>
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Operation</th>
        <th>Description</th>
        <th>Models Requesting</th>
      </tr>
    </thead>
    <tbody>
      <tr><td><code>dotrepo.lookup</code></td><td>Remote query by repository URL without a local clone</td><td>6 / 12</td></tr>
      <tr><td><code>dotrepo.diff</code> / <code>dotrepo.staleness</code></td><td>Compare overlay expectations against current repo state</td><td>6 / 12</td></tr>
      <tr><td><code>dotrepo.batch_query</code></td><td>Resolve multiple fields or repositories in one call</td><td>5 / 12</td></tr>
      <tr><td><code>dotrepo.suggest</code></td><td>Propose fields for incomplete or newly imported records</td><td>4 / 12</td></tr>
      <tr><td><code>dotrepo.evidence</code></td><td>Show why a specific field has the value it has</td><td>3 / 12</td></tr>
    </tbody>
  </table>
</div>
<p>The clear front-runner is remote lookup. The public origin already supports the lookup pattern structurally. What is missing is the MCP operation that makes that path zero-friction inside agent tooling.</p>

<h2>Risk Warnings</h2>
<ul>
  <li><strong>Stale metadata becomes trusted metadata.</strong> This was the most cited risk by a wide margin.</li>
  <li><strong>Supply-chain risk through executable commands.</strong> Several models explicitly warned that agents may auto-run commands unless trust and execution safety are clearly surfaced.</li>
  <li><strong>Index curation becomes a bottleneck.</strong> The overlay strategy is the wedge, but it also creates a review burden that has to stay credible as volume rises.</li>
  <li><strong>Schema bloat erodes the core value proposition.</strong> The more dotrepo tries to describe everything, the harder it becomes to keep the important fields boringly reliable.</li>
  <li><strong>The project quietly collapses into one ecosystem.</strong> Early index growth needs to stay visibly cross-language, or the public signal becomes “Rust plus GitHub” regardless of the stated ambition.</li>
</ul>

<h2>Synthesis: The Three Things That Matter Most</h2>
<p><strong>1. Seed the index.</strong> The protocol and hosting surface are ahead of the data. The near-term job is not more architecture. It is more reviewed overlays covering the repos agents actually encounter.</p>
<p><strong>2. Build remote lookup.</strong> The hosted HTTP layer already proves the contract. The MCP gap is now the highest-leverage toolchain gap.</p>
<p><strong>3. Protect the minimal core.</strong> dotrepo should answer a short list of essential repo questions with explicit provenance and freshness. Everything else should face a very high bar for inclusion.</p>
<p>The trust model is the moat. The overlay index is the wedge. The small schema is the survival constraint.</p>

<h2>Methodology Notes</h2>
<ul>
  <li>All interviews were conducted on March 17, 2026.</li>
  <li>The same 10-question prompt was sent to every model.</li>
  <li>Fresh conversations were used for each interview.</li>
  <li>Where possible, both logged-in and incognito variants were used to check for consistency.</li>
  <li>This write-up is a synthesis, not a verbatim archive.</li>
</ul>

<h2>Where This Feeds Back Into dotrepo</h2>
<p>The repo-side synthesis and backlog changes live in <a href="https://github.com/maxwellsantoro/dotrepo/blob/main/docs/ai-tool-interviews.md">docs/ai-tool-interviews.md</a> and the post-v1 backlog. The public site now carries this write-up because it is not just internal planning context. It is one of the clearest pieces of product evidence behind the current roadmap.</p>
<p>If you are building an AI coding tool and want to integrate dotrepo, or if you maintain a popular open-source project and want to correct or replace your overlay record, start at <a href="https://github.com/maxwellsantoro/dotrepo">github.com/maxwellsantoro/dotrepo</a>.</p>
""",
    }
]
