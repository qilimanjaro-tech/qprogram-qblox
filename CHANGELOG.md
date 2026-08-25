# Changelog

Notable changes to QProgram Qblox, newest first. Each entry starts life as a
news fragment under `changelog/`, and `towncrier build` assembles the fragments
into a release section here. See
[Contributing](https://qilimanjaro-tech.github.io/qprogram-qblox/developer/contributing.html)
for how to add one.

<!-- towncrier release notes start -->

## 0.1.0 (2026-08-25)

### Added

- First release. QProgram Qblox teaches the core DSL about the Qblox cluster,
  and importing the package is the whole activation step.
- Six operations that the portable language does not cover, reached through the
  `qblox` vendor namespace.
- A capability profile describing what QCM and QRM sequencers accept, so a
  program is validated against the hardware before it is run.
- `.qp` serialization for everything the package adds, registered so that a file
  naming the `qblox` vendor resolves without the caller importing this package
  first.
