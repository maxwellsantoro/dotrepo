# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Imported repo.test from .github/CONTRIBUTING.md as `python -m pytest tests/.../test_file.py::test_explain_what_is_being_tested -v --capture=no`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.test pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.test` previously extracted from `.github/CONTRIBUTING.md` as `python -m pytest tests/.../test_file.py::test_explain_what_is_being_tested -v --capture=no`. Command is an incomplete example or setup-only step.

## 2026-10-06 bounded command/documentation source inspection

Inspected retained upstream revision `320e79704a9e921b3a11d8a1d1ba685e6b7ebc69` for `repo.build`, `repo.test`, and `docs.root`. Source instructions were treated as data. No upstream commands, model calls, or external documentation-page execution occurred. This field inspection preserves the existing record timestamp `2026-09-17T06:08:17.919082573Z`, status `inferred`, and all unrelated facts. New assessments do not imply whole-record reinspection; the public timestamp-binding gate may withhold them until a coherent full recrawl.

- `repo.build`: unsupported-inferred-command. python -m build is conventional inference, not a declared source entrypoint in inspected files. setup.py explicitly documents setup.py sdist/bdist_wheel; CI wraps it with required package selection and checks. Do not remove flags or silently copy CI environment. Action: withhold inferred scalar; retain packaging source alternatives as unassessed until package/environment selection is explicit.
- `repo.test`: missing-supported. Contributor guide explicitly documents make test from project root on Unix. Retaining the wrapper preserves clean and setup prerequisites, PACKAGE_NAME and other exported settings, and both PyTorch/Fabric coverage invocations. Action: add source-supported root make test candidate with explicit environment/setup prerequisite; preserve scalar abstention until whole-record verification.
- `docs.root`: present-supported. Pinned README explicitly labels the existing readthedocs stable root as Docs. External reachability or live content was not used to establish source semantics. Action: preserve current value and age/status; retain this bounded inspection receipt.

Retained source files used in the bounded inspection (URLs are pinned to the recorded revision; hashes cover raw bytes):

- [README.md](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/README.md) — SHA-256 `f7cd2824fca50d0761973646e06876563d23ae3cc87c9dde4bb53747f127466e`.
- [Makefile](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/Makefile) — SHA-256 `b427dcef29cbab910774bfda6451c42f7cd8a034558c7de4ab12a4e8aa8918bb`.
- [pyproject.toml](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/pyproject.toml) — SHA-256 `1d2e5027d1fae71c5260a29a78193d7f96788514591b6cbff23aeb41eff70b5d`.
- [setup.py](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/setup.py) — SHA-256 `c6b0de9403b41b0b6cccc7e42c393157a4dd9d97564cb68c80a9ee64cd37dc1c`.
- [.github/CONTRIBUTING.md](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/.github/CONTRIBUTING.md) — SHA-256 `a7824c25c6c3156a7e776d0f92ebe6e5d1685a48d0f0ab768cfdce3b8c894a62`.
- [requirements.txt](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/requirements.txt) — SHA-256 `44aa8dc2aac91e32eaa9e05506bcf1e4810d009ec5b25f31bd95e1fa0827ece1`.
- [requirements/pytorch/test.txt](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/requirements/pytorch/test.txt) — SHA-256 `86fe913e1822f0e0906c58c31f36c17c744fe11aa74b8f12c5d963754eabbb6c`.
- [requirements/pytorch/test_gpu.txt](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/requirements/pytorch/test_gpu.txt) — SHA-256 `d0dcddadb8e4058b04638d547ce4bd266df2c563fe7a01a4eb98510f9fcff040`.
- [requirements/fabric/test.txt](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/requirements/fabric/test.txt) — SHA-256 `c2d4d0ee294ed1ec9c321a23453bea241145935f5cb8e42a00892a52796df0f7`.
- [requirements/pytorch/base.txt](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/requirements/pytorch/base.txt) — SHA-256 `ec8cbc256cc5e36bb8958ad3fb949bcfa20d78d37c408861f9d8d8fbeb597927`.
- [requirements/fabric/base.txt](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/requirements/fabric/base.txt) — SHA-256 `fef7d76716887abe2b7620cf52b9d4860ef3ef750deea55a1e313729addd9c86`.
- [.github/workflows/_build-packages.yml](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/.github/workflows/_build-packages.yml) — SHA-256 `985ee152c30fee6f867f30125c39e2229381ce85010d13f3ce07c13c991a76f6`.
- [.github/workflows/ci-tests-pytorch.yml](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/.github/workflows/ci-tests-pytorch.yml) — SHA-256 `1b0569e30003506277e1936196c3f715614054766d9eb322eaf24e185d24a351`.
- [.github/workflows/ci-tests-fabric.yml](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/.github/workflows/ci-tests-fabric.yml) — SHA-256 `d0519c68d0daee3bb55ed6223aabf1fef81c9d2f5b4283c819991ac48d44b2f5`.
- [.github/actions/pkg-check/action.yml](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/.github/actions/pkg-check/action.yml) — SHA-256 `95625379bef1b43c605423f9170d568b3550be66ae44c502e22ccaf6d1b01d6b`.
- [requirements/ci.txt](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/requirements/ci.txt) — SHA-256 `aa617887b824f25d16dc7d14f3a7614b1acdb00ba916ea7f5f439fbc83d996c5`.
- [.actions/assistant.py](https://raw.githubusercontent.com/Lightning-AI/pytorch-lightning/320e79704a9e921b3a11d8a1d1ba685e6b7ebc69/.actions/assistant.py) — SHA-256 `0376000a5eecc5a70a21214761d1d0539b789078deb52237541de813582abb0d`.

All conventional missing-file probes and pinned tree listings are retained in the dated remainder audit source receipt. Not-found describes inspected source scope, not universal absence. Lightning packaging candidates remain unassessed because required package/environment selection is not fully represented. Candidate ordering and record status were not promoted.

This is an external overlay inspection, not a maintainer-controlled canonical record.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
