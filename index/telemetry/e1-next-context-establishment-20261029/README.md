# Next E1 context establishment: frozen Compose source proposal

Selected known development identity:
`github.com/docker/compose@343bb382d2192b88d84af49971bb5cb99bee268c`.
The unchanged exposed repository task is to establish the maintainer default
automated unit-test instruction, distinguishing separate modules and e2e lanes.
The proposed command is `make test`, from repository root, with the Linux
prerequisite branch retained. Coverage is the documented main-module unit target;
it is not every module or end-to-end lane.

`source-proposal.json` freezes the tuple, prerequisites, exact retained file and
passage hashes, uncertainty, selection rationale and original task identity before
any code change. `implementation-proposal.json` names the prospective helper,
minimal context wiring, refusal controls and dependencies. No code ownership has
been transferred and no implementation or high assessment is authorized here.

`BUILDING.md` supplies the natural unit-test command and platform prerequisites.
The root Makefile routes it through Docker Buildx Bake, the Bake target maps to the
Dockerfile test/coverage stages, and those stages declare image/tool/module setup,
CGO/race options and package exclusions. The root Go module declares a host minimum of 1.26.10 through the BUILDING
reference; the in-image builder Go version is a separate Dockerfile default.
Buildx availability follows from the command, but its minimum version is unknown. This
is a stronger retained multi-file route than the broader Photocraft or Pixi
default suites, and avoids extending the Keras grammar or compiling arbitrary
AGENTS instructions.

Two source questions remain explicit for independent assessment. The Dockerfile
literally contains shell `$(TAGS)` inside package enumeration; this packet does
not reinterpret it as a configuration flag, invent a TAGS executable prerequisite,
declare the token fatal, or claim that it executed. Also, the
selected source set does not establish absence of automatic Bake override files.
The proposed default route cannot silently assume those away. The assessor must
decide whether retained evidence establishes the documented tuple or needs a
separately authorized source supplement; uncertainty requires abstention rather
than a lower definition of completeness.

The proposed private helper would recover only this bounded natural recipe family
with complete source attribution, preserving existing scalar/default policy and
the existing candidate/evidence shape. Unsupported Make/HCL/Docker/shell routing
must abstain. It would emit at most Medium while source-completeness assessment
remains separate. Mechanical hashes are necessary integrity checks, not high
confidence or prerequisite completeness. Current crawler materialization lacks
three of these root inputs; local extraction does not imply hosted availability.

The reviewer is the prior E1 extractor/gold author and has seen the existing
development results. This is known development, not a fresh holdout or independent
second gold review. Only retained pinned sources and current importer policy were
read. No evaluated index/profile or F-05 sources, network, Cargo, upstream/native
commands, models/providers, Docker or shared edits were used. The source proposal
does not claim execution success, complete instruction establishment, high
promotion, consumer acceptance, or consumer benefit.
