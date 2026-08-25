# API reference

Auto-generated reference for the `qprogram_qblox` package. Everything listed
here is exported from the top-level module, so
`from qprogram_qblox import X` works for every name on this page.

## Program entry points

Two ways to get a `QProgram` with a typed `.qblox` namespace. Use the
pre-combined class for a qblox-only setup, and the mixin when a platform
combines several vendor extensions on one program class.

Neither is needed at runtime: importing `qprogram_qblox` registers the
namespace on the base `qprogram.QProgram`, so `program.qblox.acquire(...)`
resolves through the dynamic vendor lookup on any program. The typed surface
is what editors and type checkers read.

::: qprogram_qblox.QProgram
    options:
      show_root_full_path: false

::: qprogram_qblox.QbloxMixin
    options:
      show_root_full_path: false

## Vendor namespace

The builder surface. Each method appends one AST node to the program's
current block, so the methods obey the same nesting as the core builder
calls around them. `acquire` returns a `MeasurementHandle`; the rest return
`None`.

::: qprogram_qblox.QbloxNamespace
    options:
      show_root_full_path: false
      members:
        - acquire
        - set_markers
        - set_trigger
        - wait_trigger
        - set_acquisition_threshold
        - set_acquisition_rotation

## Operations

The AST nodes the namespace methods append. They are structural value
objects: two nodes with equal attributes compare equal, which is what makes
a program survive a `.qp` round trip unchanged. Each one reports the
capability tokens a platform has to declare in `required_capabilities`.

Construct them directly for tests and program transformations; build
programs through the namespace.

::: qprogram_qblox.Acquire
    options:
      show_root_full_path: false

::: qprogram_qblox.SetMarkers
    options:
      show_root_full_path: false

::: qprogram_qblox.SetTrigger
    options:
      show_root_full_path: false

::: qprogram_qblox.WaitTrigger
    options:
      show_root_full_path: false

::: qprogram_qblox.SetAcquisitionThreshold
    options:
      show_root_full_path: false

::: qprogram_qblox.SetAcquisitionRotation
    options:
      show_root_full_path: false

## Capability profile

The bundle a platform puts in the bus slots of every qblox-driven bus: the
tokens those buses support, the numeric limits that go with them, and the
predicates that flag combinations the tokens alone would let through. See
[Capabilities and profiles](../guide/capabilities.md) for how a platform
assembles it into a `PlatformCapabilities`.

::: qprogram_qblox.QBLOX_DEFAULT_V1
