# qprogram-qblox review contract

Shared core v0.2 (Qilimanjaro Software), a draft until the software leads agree it. Copied verbatim, followed by qprogram-qblox additions. Applies to humans and agents. AI review is advisory: a qualified human reads every line of the same revision before merge.

## Findings
- Each finding gives `path:line` and quotes the line, then the trigger, the consequence, the evidence and a concrete next step. No citation, no finding.
- Separate confirmed defects from questions and missing evidence. Recheck earlier findings on the current revision and state the inspected scope.
- Review on two axes: standards (`CODING_STANDARDS.md`, citing the section) and spec (the linked ticket, PRD or TRD: missing, extra, wrong; quote the spec line).
- Green CI is evidence, not a verdict: say what it covers and what it misses.

## Severity
Lead with the highest.
- **blocker**: wrong results, data loss, a security hole, or a broken invariant from AGENTS.md. Fix before merge.
- **major**: a likely bug, or a design problem the next change will trip over. Fix, or justify in the PR.
- **minor**: worth fixing, not blocking.
- **nit**: taste. At most 3 per review; drop the rest.

## qprogram-qblox additions
- **New operation.** It lands with all four kinds of change in the checklist of `docs/developer/contributing.md` (code in the five modules, tests, the guide, the API reference). A missing token registration or `QBLOX_DEFAULT_V1` entry is a blocker: the operation builds and serializes, and every program using it fails validation.
- **Wire form.** A change to how an operation spells in `.qp` (its name, a parameter's name, order or meaning) is a major bump of the vendor protocol and registers a rewrite through `register_vendor_migration`; without the rewrite it is a blocker, because existing files stop loading. Round-trip tests in `tests/test_serialization.py` cover the new spelling.
- **Profile.** A change to `src/qprogram_qblox/profiles.py` (tokens, limits, predicates) names the Qblox hardware behaviour it encodes, and `docs/guide/capabilities.md` moves with it. Check the domain (`rt` or `host`) the change claims against the profile, not against the operation's name.
- **Core boundary.** An operation that is not specific to Qblox, or a fix that reproduces without importing `qprogram_qblox`, belongs in the core `qprogram` repository. A change that needs a newer `qprogram` raises the floor in `pyproject.toml` to the release that carries the behaviour.
- **Docs and changelog.** A change a caller would notice brings its docs (the `qprogram-docs` skill's checklist in `.claude/skills/qprogram-docs/SKILL.md`) and a towncrier fragment in `changelog/`.
- **Public repository.** No internal links, hostnames, customer data or measurement data in the diff, the PR text or the commit messages.
- **Units.** Values follow the convention in CODING_STANDARDS.md additions; check every conversion where a value leaves this repo (compiler, driver, instrument).
- **Parity.** Any numeric change ships before-and-after output, with each difference explained. The repo has no example data, so use a synthetic input that reaches the changed code: a program built on the `transmon_schema` fixture in `tests/conftest.py`, or the example programs in `docs/getting-started.md`, showing the emitted `.qp` text (`qp.dumps`) and the `qp.validate` diagnostics before and after.
