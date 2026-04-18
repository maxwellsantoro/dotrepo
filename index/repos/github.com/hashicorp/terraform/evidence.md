# Evidence

- Imported the repository name, description, homepage, docs root, and getting-started entry points from README.md.
- Imported `repo.build = "go install ."` and `repo.test = "go test ./..."` from the documented Terraform CLI/Core development environment in `.github/CONTRIBUTING.md`.
- Cross-checked the build-from-source guidance in BUILDING.md. That document also provides `go build -o bin/ .` variants with `ldflags`, but the default record keeps the simpler contributor workflow from CONTRIBUTING.md.
- Imported `license = "BUSL-1.1"` from the upstream LICENSE file and README license section.
- Imported `owners.team = "@hashicorp/terraform-core"` from the repo-wide `* @hashicorp/terraform-core` CODEOWNERS rule. Narrower subtree owners exist, but they are intentionally not expanded into top-level maintainers.
- Imported `owners.security_contact = "security@hashicorp.com"` from the GitHub security overview. No repository SECURITY.md was present in the crawled snapshot.
- Imported `.go-version = "1.25.7"` as supporting evidence for the documented toolchain baseline, but dotrepo does not yet expose a dedicated environment/toolchain field on the public surface.
- Acceptance tests are documented separately behind `TF_ACC=1` and depend on external services, so they are not the default `repo.test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
