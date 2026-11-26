# QProgram Qblox

The Qblox vendor extension of the QProgram DSL: the operations, the capability profile and the `.qp` spelling a Qblox cluster adds to the portable language.

Terms shared across Qilimanjaro's stack are in the [shared glossary](https://github.com/qilimanjaro-tech/claude-skills/blob/main/onboarding/qilimanjaro-agent-starter-kit/org-context/qilimanjaro-glossary.md); terms of the core DSL are in the core `qprogram` documentation. This file holds this package's own.

## Language

### The extension

**Vendor extension**:
A package that adds instrument-specific operations, a capability profile and their `.qp` serialization to the core DSL, without changing the core. Importing it is the whole activation step.
_Avoid_: Plugin, backend, driver

**Vendor namespace**:
The name, `qblox`, under which the extension's operations are reached in Python (`program.qblox.<op>`) and spelled in `.qp` (`qblox.<op>`).
_Avoid_: Prefix, module

**Require line**:
The `require qblox <major>.<minor>` line of a `.qp` file, which the parser checks against the installed package version.
_Avoid_: Vendor header, version pin

**Vendor migration**:
A rewrite registered with `register_vendor_migration` that repairs an older operation spelling in a `.qp` file as it loads.
_Avoid_: Upgrade, converter

### Capabilities

**Capability profile**:
A named, versioned set of capability tokens, limits and predicates describing what a bus accepts. This package ships one, `qblox-default-v1`.
_Avoid_: Capability set, hardware spec

**Capability token**:
A string naming one thing a node needs, such as `vendor.qblox.scope` or `op.wait`; validation checks it against the profile of the bus the node targets.
_Avoid_: Feature flag, permission

**Host-side operation**:
An operation a platform realizes as a slow-control parameter write at execution time, with no sequencer instruction: `scope`, `set_acquisition_threshold` and `set_acquisition_rotation`.
_Avoid_: Slow operation, parameter operation

**Lowering**:
What a platform does to turn a validated program's nodes into Qblox sequencer instructions and parameter writes.
_Avoid_: Translation, transpiling

### Readout

**Acquisition**:
An integration of a readout bus's input against weights, without playing a pulse, producing the IQ point and the thresholded state (`qblox.acquire`).
_Avoid_: Measure (the core operation that also plays the readout pulse)

**Scope**:
The raw ADC trace of the QRM that drives a readout bus, recorded once per run rather than once per acquisition (`qblox.scope`).
_Avoid_: Raw field, raw measurement

**Thresholded acquisition**:
Qblox state discrimination: the integrated IQ point is rotated by the acquisition rotation, then compared with the acquisition threshold.
_Avoid_: Classification, state readout
