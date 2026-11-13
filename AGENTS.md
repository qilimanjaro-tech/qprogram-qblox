# qprogram-qblox

qprogram-qblox is the Qblox vendor extension for the QProgram DSL: importing it registers seven `qblox.*` operations, the `qblox-default-v1` capability profile and their `.qp` serialization on top of `qprogram` from PyPI. Platform authors and experiment code use it to describe what a Qblox cluster adds to the portable language.

## Navigate by task
- Operations (the AST nodes a compiler reads): `src/qprogram_qblox/operations.py`. Builder methods: `src/qprogram_qblox/namespace.py`. Typed `.qblox` property: `src/qprogram_qblox/mixin.py`.
- Capability tokens, `QBLOX_DEFAULT_V1` and its predicates: `src/qprogram_qblox/profiles.py`.
- Registration at import (namespace, version, operations, profile) and `.qp` parse callbacks: `src/qprogram_qblox/__init__.py`.
- Module map, import order and how each operation reaches hardware: `docs/developer/lowering.md`. Adding an operation: the checklist in `docs/developer/contributing.md`.
- Tests: `tests/`, one file per module; shared fixtures in `tests/conftest.py`.
- Before writing or reviewing code or tests: read `CODING_STANDARDS.md` and `REVIEW.md`.
- Domain vocabulary: `GLOSSARY.md`; name code, tests and PRs with its terms. Decisions: `docs/adr/`. Tracker and triage: `docs/agents/`.
- Project knowledge base: TODO(human): link the domain wiki.

## Commands
- Setup: `uv sync --frozen --group dev --group docs`. Every dependency resolves from PyPI, `qprogram` included.
- Focused test: `uv run pytest tests/test_profile.py`
- **Verify (run before calling work done):** `uv run ruff check . && uv run ruff format --diff . && uv run ty check --python-version 3.11 && uv run ty check --python-version 3.12 && uv run ty check --python-version 3.13 && uv run ty check --python-version 3.14 && uv run pytest && uv run --group docs zensical build --strict`
  (the gates of the Code Quality, Tests and Documentation workflows).

<important if="you edit `docs/`, the README or a public docstring">
- Docs (`docs/`, `README.md`, public docstrings): follow the `qprogram-docs` skill in `.claude/skills/qprogram-docs/SKILL.md`, which carries the house style, the change checklist and the docs checker.
- Docs checker: `uv run python .claude/skills/qprogram-docs/scripts/check_docs.py docs`
</important>

## Boundaries
- Validate with synthetic inputs and offline tests; hardware, lab databases and production runcards are in scope only when the task names them.
- Report every gate you could not run and why.
- Keep credentials, runcards with real addresses and measurement data out of the repository and out of agent instructions.

## Critical invariants
- The repository is public and published to PyPI: keep internal links, hostnames and customer data out of code, docs, commits and PRs, because anyone can read them.

<important if="you change an existing operation's fields, meaning or `.qp` wire form">
- An operation's `.qp` wire form changes only with a major bump of the vendor protocol and a rewrite registered through `register_vendor_migration`, because `.qp` files users already have must keep loading ("Changing one that already exists" in `docs/developer/lowering.md`).
</important>

<important if="you add an operation">
- A new operation lands with its token registration and its `QBLOX_DEFAULT_V1` entry in `src/qprogram_qblox/profiles.py`, because without them the operation builds and serializes but every program using it fails validation.
</important>

<important if="you add or change imports in the operations or profiles module">
- Imports run one way: `src/qprogram_qblox/operations.py` and `src/qprogram_qblox/profiles.py` import from `qprogram` and nothing else in this package, because a compiler imports the node classes on their own (`docs/developer/lowering.md`).
</important>

<important if="you add a runtime dependency or an operation">
- The only runtime dependency is `qprogram`, and an operation that is not specific to Qblox belongs in the core `qprogram` repository, because every backend should get it there.
</important>

<important if="you touch numeric code, units, golden values or tolerances">
- Units: durations are integer ns, angles rad, the scope `trigger_level` is normalized to [-1, 1], and the acquisition threshold is V after integration. The full convention and its exceptions are in CODING_STANDARDS.md additions.
- Every numeric change ships with the before-and-after evidence REVIEW.md asks for.
</important>

## Branches and PRs

<important if="you create a branch, open or title a PR, or merge one">
Decision 2 (Qilimanjaro Software branch conventions); the rules below follow what the repository already does:
- Branch from `main`, named after the ticket: `qhc-####-<topic>` for a Linear QHC ticket. Experiments: `exp/<topic>`, no ticket key. Deliveries: `delivery/<project>-<topic>`.
- PR title: a short imperative sentence, with the ticket named and linked in the body (`Implements QHC-1692`). Decision 2 asks for `[TASK-ID] Name`; TODO(human): confirm the title rule with the maintainers.
- PRs are squash-merged into `main`.
</important>

<important if="you make a change a caller would notice">
- A PR with a change a caller would notice adds a towncrier fragment `changelog/<PR number>.<type>.md`; before the PR has a number, name it `+<topic>.<type>.md` and rename it once it does. Internal, test-only and docs-only changes need none.
- Changelog fragment: `uv run towncrier create <PR number>.<type>.md` (types in `[tool.towncrier]` in `pyproject.toml`).
</important>

<important if="you change the package version or cut a release">
- Releases go out from a release PR on `main` (`uv version`, `towncrier build`), then a GitHub Release tagged with the bare version (`0.2.0`, no `v`) starts `.github/workflows/publish.yml`. Steps in `docs/developer/contributing.md`.
</important>

## Agent workflow
- Gardener: TODO(human) (owns the environment-change list after each retro)
- Trust rung: 1 (Pair), proposed: the human drives and reads every diff live.
- Scratch output (research, specs, evidence) goes to `.agents/artifacts/`, which is gitignored.

## Agent skills

<important if="you read, file, label or triage issues">
### Issue tracker
Mixed, to be confirmed: GitHub Issues is the public intake and backlog; Linear team QHC holds the work QHC picks up. See `docs/agents/issue-tracker.md`.
### Triage labels
The five default triage roles, mapped to this repo's GitHub labels where one exists. See `docs/agents/triage-labels.md`.
</important>

<important if="you name a concept or record a decision">
### Domain docs
Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
</important>

## Completion
Work is ready for review when the verify command passes and its output is attached to the PR. The verify command runs the gates of the workflows that run on pull requests.
