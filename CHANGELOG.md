# Changelog

Notable changes to QProgram Qblox, newest first. Each entry starts life as a news fragment under `changelog/`, and `towncrier build` assembles the fragments into a release section here. See [Contributing](https://qilimanjaro-tech.github.io/qprogram-qblox/developer/contributing.html) for how to add one.

<!-- towncrier release notes start -->

## 0.3.0 (2026-11-25)

### Added

- `qp.qblox.scope(bus, *, averaging=True, trigger_level=None, name=None)` records the raw ADC trace of the QRM that drives a readout bus, for the whole run, and returns a `MeasurementHandle` to pass to `result.get(scope, field="raw")`. Scopes are named `scope0`, `scope1`, ... on a counter of their own, so adding one never renames an acquisition. ([PR #8](https://github.com/qilimanjaro-tech/qprogram-qblox/pull/8))

### Changed

- This package now requires qprogram 0.3, and the `qblox-default-v1` check on DRAG pulses reads `IQDrag`'s `duration` and `num_sigmas` in place of the removed `sigma`. A loop that changes the gaussian's sigma, `duration / num_sigmas`, now runs host-side whether it sweeps either field directly or through an expression such as `2 * v`; before, only a bare variable at `sigma` did. ([PR #9](https://github.com/qilimanjaro-tech/qprogram-qblox/pull/9))

### Removed

- `qblox-default-v1` no longer lists `measure.fields.raw`, so a `measure` or a `qblox.acquire` that asks for the `raw` field now fails `qp.validate` with `missing-capability`. A QRM records one scope trace per run rather than one per measurement; use `qp.qblox.scope` for it. ([PR #8](https://github.com/qilimanjaro-tech/qprogram-qblox/pull/8))


## 0.2.0 (2026-09-08)

This release requires qprogram 0.2, which is what a `require qblox` line is now read against. One thing follows from the core release rather than from anything here: a `.qp` file written before it no longer loads, because its `#!QProgram 1.0` header reads as a later version than the `0.2` the core writes now, and nothing runs backwards. A file whose header is current is carried up instead, since a `require qblox` line naming an earlier major is migrated rather than refused.

### Changed

- The `require qblox <major>.<minor>` line is read by the rule the core DSL applies to a file header, which needs qprogram 0.2. A line asking for more than the installed package provides is still refused, and the message now names what to install: `file requires qblox 1.0, newer than the installed qblox 0.2.0 — install qblox 1.0 or newer`. A line carrying a patch (`require qblox 0.1.0`) is refused rather than rounded down, since a patch release of this package changes code and never the wire form. A line naming an earlier major loads instead of being refused, so a release that changes an operation's wire form registers a rewrite for it with `qp.register_vendor_migration("qblox", "<major>.<minor>")` and the files users already have go on loading. Nothing in this package's own API changes. ([PR #4](https://github.com/qilimanjaro-tech/qprogram-qblox/pull/4))


## 0.1.0 (2026-08-25)

### Added

- First release. QProgram Qblox teaches the core DSL about the Qblox cluster, and importing the package is the whole activation step.
- Six operations that the portable language does not cover, reached through the `qblox` vendor namespace.
- A capability profile describing what QCM and QRM sequencers accept, so a program is validated against the hardware before it is run.
- `.qp` serialization for everything the package adds, registered so that a file naming the `qblox` vendor resolves without the caller importing this package first.
