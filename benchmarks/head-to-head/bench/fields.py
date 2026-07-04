"""The fixed question set.

`dotrepo_path` values are the dot-paths passed to /v0/batch/query. They follow
the `repo.*` convention shown in dotrepo's public-export examples
(repo.description, repo.test, ...). If the deployed schema names a path
differently, change it here in one place -- the arms don't hardcode paths.
"""
from .model import Field, FieldClass

FIELDS = [
    # --- GitHub-native: the baseline should nail these; dotrepo must at least tie ---
    Field("description", "One-line description of the project.",
          FieldClass.GITHUB_NATIVE, "categorical", "repo.description",
          "GET /repos/{o}/{r} -> .description"),
    Field("license", "SPDX license identifier.",
          FieldClass.GITHUB_NATIVE, "spdx", "repo.license",
          "GET /repos/{o}/{r} -> .license.spdx_id"),
    Field("language", "Primary implementation language.",
          FieldClass.GITHUB_NATIVE, "categorical", "repo.language",
          "GET /repos/{o}/{r} -> .language"),
    Field("homepage", "Canonical project homepage / docs URL.",
          FieldClass.GITHUB_NATIVE, "url", "repo.homepage",
          "GET /repos/{o}/{r} -> .homepage"),
    Field("archived", "Is the repository archived / unmaintained?",
          FieldClass.GITHUB_NATIVE, "bool", "repo.archived",
          "GET /repos/{o}/{r} -> .archived"),

    # --- Buried: the actual thesis. GitHub has no structured field for these; an
    #     agent must read README/SECURITY/CONTRIBUTING or guess. This is where a
    #     curated .repo should win -- or it isn't worth publishing. ---
    Field("build", "Exact command to build the project from a clean checkout.",
          FieldClass.BURIED, "command", "repo.build",
          "scrape README for build/install instructions"),
    Field("test", "Exact command to run the test suite.",
          FieldClass.BURIED, "command", "repo.test",
          "scrape README/CONTRIBUTING for test instructions"),
    Field("security_contact", "Where to report a security vulnerability.",
          FieldClass.BURIED, "categorical", "repo.security.contact",
          "scrape SECURITY.md"),
    Field("min_toolchain", "Minimum required toolchain / runtime version (MSRV, Node, Python).",
          FieldClass.BURIED, "categorical", "repo.toolchain.min",
          "scrape README/rust-toolchain/.nvmrc/pyproject"),
]

FIELDS_BY_ID = {f.id: f for f in FIELDS}
