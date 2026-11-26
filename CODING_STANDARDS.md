# qprogram-qblox coding standards

Shared core v0.2 (Qilimanjaro Software), a draft until the software leads agree it. Copied verbatim, followed by qprogram-qblox additions. Mechanical rules live in the tools configured in `pyproject.toml` and in CI; this file holds the judgement they cannot make. The review contract is `REVIEW.md`; findings cite the section they apply.

## Tests

Tests are behaviour tests: they drive the public interface at an agreed seam and assert what a caller observes.

- **Seams.** Test at the seams listed in the additions below. A new seam is named in the PR description before tests target it.
- **Observable outcomes.** Assert returned values, raised errors, emitted programs and waveforms, and results read back through the public reader.
- **Independent expected values.** Take expected values from a literal, a worked example, the specification, a published reference or a hardware-validated fixture, never recomputed the way the code computes them.
- **Boundary mocks.** Mock instrument drivers and hardware execution, network, databases, the file system when needed, time and randomness. The package's own classes and functions run for real.
- **Public reach.** When a behaviour is visible only through a `_private` name, add a public accessor or move the test to the seam above.
- **Regressions.** A bug fix starts with a test that fails on the bug.
- **Coverage is evidence.** A line counts as covered when a behaviour test exercises it. Hardware-only code goes in the coverage `omit` list with a reason.

## Code

- **Design.** Prefer deep modules: a small interface over a lot of behaviour. Name things with the terms in `GLOSSARY.md`; a new concept gets a glossary entry first.
- **Units.** Physical quantities carry their unit in the name, a type alias or the docstring (Hz, ns, V, rad, dBm), fixtures included, in the convention the additions state.
- **Suppressions.** Every suppression (`# noqa`, `# type: ignore`, `# ty: ignore`, `# pragma: no cover`, a coverage `omit`) names its rule code and a one-line reason.
- **Comments.** Explain why. A comment that excuses a workaround becomes a type, a lint or a test.
- **Dependencies.** A dependency on another Qilimanjaro package names the released version that carries the needed behaviour.
- **Compatibility.** Public API changes go through a deprecation release unless the PR links an accepted decision to break compatibility.

## Change hygiene

- User-facing changes add a towncrier fragment in `changes/`, in repos that use towncrier.
- Interface or architecture decisions link their decision record; proposals stay labelled as proposals until accepted.

## qprogram-qblox additions

- **Seams:** the builder (`program.qblox.<op>(...)` on the `qblox_program`, `empty_qblox_program` and `base_program` fixtures in `tests/conftest.py`), asserting the node appended to the program and the errors raised at the call; `.qp` text through `qprogram.dumps` and `qprogram.loads` (`tests/test_serialization.py`), asserting the text and a structurally equal reload; validation through `qprogram.validate` against `QBLOX_DEFAULT_V1` (`tests/test_profile.py`), asserting diagnostics and the execution plan; registration through the core registries after import (`tests/test_registration.py`).
- **Boundary mocks:** none beyond the core. Nothing here touches hardware; the suite runs on the core DSL and its reference executor `qprogram.simulate`.
- **Fixture headers:** `.qp` fixtures take their `#!QProgram` header and `require qblox` line from the installed libraries through `tests/_header.py`, never as literals, so a release of either package does not break the suite.
- **Units:** durations are integer ns: `SetTrigger.duration` and `WaitTrigger.duration` (`src/qprogram_qblox/operations.py:196`, `src/qprogram_qblox/operations.py:225`) and the `min_wait_duration_ns` limit of 4 ns (`src/qprogram_qblox/profiles.py:251`); the scope trace's `time` axis is ns (`docs/guide/operations.md:135`). Angles are rad: `SetAcquisitionRotation.angle` (`src/qprogram_qblox/operations.py:280`); the platform converts to the instrument's degrees in [0, 360) when lowering (`docs/guide/operations.md:284`). The scope `trigger_level` is normalized to [-1, 1] and checked at construction (`src/qprogram_qblox/operations.py:136`, `src/qprogram_qblox/operations.py:153`). Exception: the acquisition threshold is V after integration (`src/qprogram_qblox/operations.py:251`). Frequencies, gains and offsets reach a Qblox bus through the core operations (`op.set_frequency`, `op.set_gain`, `op.set_offset` in `src/qprogram_qblox/profiles.py:166`), so the core `qprogram` package owns their units; this repo states none. TODO(human): confirm whether gain and offset are normalized to [-1, 1] here as in Qililab.
- **Coverage:** no `fail_under` in `pyproject.toml`; CI reports coverage to Codecov on pushes to `main`. TODO(human): agree a coverage floor.
- **Changelog:** towncrier fragments, the core's Change hygiene line, go in `changelog/` here, named `<PR number>.<type>.md` (`docs/developer/contributing.md`).
- **Tooling:** suppressions use ruff rule names, not codes (`# ruff: ignore[import-outside-top-level]`), because the ignore list in `pyproject.toml` is written by name to say why each exemption exists.
