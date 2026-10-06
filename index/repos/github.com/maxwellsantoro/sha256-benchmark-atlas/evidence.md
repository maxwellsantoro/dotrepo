# Source inspection, October 5, 2026

Checked at `2026-10-06T01:15:26.806051Z` against upstream revision `71eda5d6480e0b9e39f914f3641d91f98402e943`.

- Imported repository name/description from the pinned README and license from the license files/Cargo declaration. Homepage is the inspected repository identity.
- Build/test selection: README quick start explicitly names full registry build and correctness commands, uv sync and the full compiler/toolchain cohort. Registry and workflow were inspected to check that the commands cover all admitted implementations. Operator-specific SDK selection is preparation, not record environment metadata. Commands are retained as candidates rather than claiming a single universal default correctness configuration.
- No docs.root is asserted: this bounded refresh did not inspect a complete documentation-root contract. No unknown placeholder is used for absent ownership/security fields.
- Whole command candidates have exact JSON value and check-time bindings. Prerequisites are descriptions, not shell commands or execution authorization.

- [README.md](https://github.com/maxwellsantoro/sha256-benchmark-atlas/blob/71eda5d6480e0b9e39f914f3641d91f98402e943/README.md) SHA-256 `363e25b27f99f2138209bedc89ab0d3e48cc6debc5976d74e8627efd8b14d249`.
- [LICENSE](https://github.com/maxwellsantoro/sha256-benchmark-atlas/blob/71eda5d6480e0b9e39f914f3641d91f98402e943/LICENSE) SHA-256 `de106531e84e6fe7d5e0f8c61a2806b9f49eaa3dde8f45763b87aa6a2a4587da`.
- [registry/implementations.yaml](https://github.com/maxwellsantoro/sha256-benchmark-atlas/blob/71eda5d6480e0b9e39f914f3641d91f98402e943/registry/implementations.yaml) SHA-256 `6c3c46c58f181633be1ebfa4ad5c94cc3198a9f24fcd9eccce433185463d7267`.
- [.github/workflows/campaign.yml](https://github.com/maxwellsantoro/sha256-benchmark-atlas/blob/71eda5d6480e0b9e39f914f3641d91f98402e943/.github/workflows/campaign.yml) SHA-256 `a62b8f9d3673888e9d8d3e644d19f4b42a1893aed26da5229f12afa1b56f1823`.
- [pyproject.toml](https://github.com/maxwellsantoro/sha256-benchmark-atlas/blob/71eda5d6480e0b9e39f914f3641d91f98402e943/pyproject.toml) SHA-256 `8cd7494d8dfb416db53f20f91e37fd19a21afeed40e9201333ae831aa8c7f7f0`.

This is an overlay record, not a maintainer-controlled canonical record.
