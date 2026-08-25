# Lowering onto hardware

This page is for the person writing the platform: the code that takes a
validated `QProgram` and drives real Qblox instruments with it. It covers
what each module of this package owns, what runs when the package is
imported, what a platform has to do with each of the six operations, which
conversions the DSL leaves to the platform on purpose, and how the
capability profile limits what a platform may accept.

The core DSL's
[building a vendor extension](https://qilimanjaro-tech.github.io/qprogram/developer/vendor-extensions.html)
page is the general template. This page is the qblox half of it.

## The five modules

```
src/qprogram_qblox/
├── __init__.py      # the registration calls, __version__, the pre-combined QProgram
├── operations.py    # six Operation subclasses: the AST nodes
├── namespace.py     # QbloxNamespace: one typed method per operation
├── mixin.py         # QbloxMixin: the .qblox property, for autocomplete
└── profiles.py      # capability tokens, QBLOX_DEFAULT_V1, two predicates
```

| Module          | What it owns                                                                                                                                                                                    |
|-----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `operations.py` | The six node classes. Each holds its arguments as plain attributes and declares the capability tokens that instance needs. This is the module a compiler reads.                                   |
| `namespace.py`  | The builder surface. One typed method per operation, each constructing a node and handing it to `VendorNamespace._append` (or `_append_measurement` for `acquire`). No logic beyond that.          |
| `mixin.py`      | The `.qblox` property, which instantiates `QbloxNamespace` once and caches it on the program instance. Autocomplete only; the runtime lookup works without it.                                    |
| `profiles.py`   | The `vendor.qblox.*` token registrations, the `QBLOX_DEFAULT_V1` profile, and the two predicates that encode hardware constraints.                                                               |
| `__init__.py`   | The glue: the four registration steps, the package version, and `QProgram`, the pre-combined class with `.qblox` typed.                                                                              |

Imports run one way. `operations.py` and `profiles.py` import from
`qprogram` and nothing else in this package; `namespace.py` imports the
operations; `mixin.py` imports the namespace; `__init__.py` imports all
four. A compiler that only wants the node classes can import
`qprogram_qblox.operations` directly, though it then misses the registration
side effects described below.

`profiles.py` importing no local operations is not an accident: both
predicates constrain **core** operations (`Play` and `Wait`) on a
qblox-driven bus. The qblox operations themselves carry no constraints
beyond their tokens.

## What runs at import

The package hooks into the core three ways: the runtime namespace, the typed
mixin, and the serialization registry. Two of the three need a call; the
mixin is only a class definition. The capability profile is a fourth
registration, on the protocol side rather than the builder side.

Importing `qprogram_qblox` is the activation step, and it is the only one.
`__init__.py` performs four registrations, in this order.

1. **Runtime namespace.**
   `QProgram.register_vendor("qblox", QbloxNamespace)` puts the class in the
   core builder's vendor registry, so `program.qblox` resolves through
   `QProgram.__getattr__` on any program, the plain base class included.
2. **Protocol version.** `register_vendor_version("qblox", __version__)`
   records the version, which `__init__.py` reads from the installed
   distribution metadata. This is the number the parser checks a file's
   `require qblox 0.1` line against: same major, file minor not ahead of
   installed minor.
3. **Operations.** One `register_vendor_operation("qblox", name, cls)` call
   per class. `acquire` additionally passes the core measurement callbacks,
   so its handle serializes as a `name="..."` keyword like every other
   measurement.
4. **Profile.** `_register()` from `profiles.py` puts `QBLOX_DEFAULT_V1` on
   the global profile registry, where `CompilerCapabilities.from_profile`
   finds it by name.

One more registration runs before all four, as a side effect of importing
`profiles.py` at the top of `__init__.py`: `register_capability_tokens` adds
the six `vendor.qblox.*` tokens. It has to run before the profile object is
constructed, because `Profile.__post_init__` rejects a capability set naming
a token nobody registered. That is the check that turns a typo into an
import error instead of a silent validation miss.

The typed mixin registers nothing. Nothing in `mixin.py` runs at import
beyond the class definition, because `.qblox` is a property that builds the
namespace on first access.

Everything above is observable:

```python
import qprogram as qp
import qprogram_qblox
from qprogram.protocol import CAPABILITY_REGISTRY, resolve_profile
from qprogram.serialization import registry

print("version:  ", qprogram_qblox.__version__)
print("vendor:   ", registry.get_vendor_version("qblox"))
print("acquire:  ", registry.get_operation_class("qblox", "acquire").__name__)
print("set_markers name:", registry.get_operation_vendor_name(qprogram_qblox.SetMarkers))
print("profile:  ", resolve_profile("qblox-default-v1").name)
print("tokens:   ", sorted(t for t in CAPABILITY_REGISTRY if t.startswith("vendor.qblox")))

program = qp.QProgram()  # the base class, no mixin in sight
program.qblox.set_markers("drive_q0", "0001")
print("namespace:", type(program.qblox).__name__)
```

```text
version:   0.1.0
vendor:    0.1.0
acquire:   Acquire
set_markers name: ('qblox', 'set_markers')
profile:   qblox-default-v1
tokens:    ['vendor.qblox.acquire', 'vendor.qblox.set_acquisition_rotation', 'vendor.qblox.set_acquisition_threshold', 'vendor.qblox.set_markers', 'vendor.qblox.set_trigger', 'vendor.qblox.wait_trigger']
namespace: QbloxNamespace
```

A platform never has to trigger the import itself. The
`[project.entry-points."qprogram.vendors"]` table in `pyproject.toml` maps
the vendor name `qblox` to the module `qprogram_qblox`, and `qprogram.loads`
imports it on demand when a file's header requires a vendor that is not
registered yet. `loads(text, auto_activate=False)` opts out of that and
rejects the file instead.

## Reading the program

A platform reads the AST, not the text. `program.body.walk()` yields every
node in pre-order, blocks and operations together, and `isinstance` against
the classes in `qprogram_qblox.operations` is the whole dispatch:

```python
import qprogram as qp
from qprogram_qblox import QProgram
from qprogram_qblox.operations import Acquire, SetMarkers, SetTrigger, WaitTrigger

schema = qp.BusSchema.transmon()
q = schema.q

program = QProgram(schema=schema)
program.qblox.set_markers(q[0].drive, "0001")
program.qblox.set_trigger(q[0].drive, duration=40, outputs=[1, 2], position="end")
program.qblox.wait_trigger(q[0].drive, duration=100, port=1)
program.qblox.acquire(q[0].readout, "readout_weights", fields=("iq", "raw"))

for node in program.body.walk():
    if isinstance(node, SetMarkers):
        print("set_markers ", node.bus, node.mask)
    elif isinstance(node, SetTrigger):
        print("set_trigger ", node.bus, node.duration, node.outputs, node.position)
    elif isinstance(node, WaitTrigger):
        print("wait_trigger", node.bus, node.duration, node.port)
    elif isinstance(node, Acquire):
        print("acquire     ", node.bus, node.weights, node.handle.name, node.fields)
```

```text
set_markers  q0/drive 0001
set_trigger  q0/drive 40 [1, 2] end
wait_trigger q0/drive 100 1
acquire      q0/readout readout_weights q0/readout/m0 ('iq', 'raw')
```

Three things come from the core `Operation` base and need no per-class code:
`node.buses()`, `node.waveforms()` and `node.variables()`, driven by the
`BUS_ATTRS` and `WAVEFORM_ATTRS` class attributes. Use them for the passes
that do not care which operation they are looking at: allocating sequencers
per bus, collecting waveforms to upload, or finding the variables a loop has
to bind.

Two things to do before lowering anything. Call `program.expand()` if
`program.fragments` is non-empty, so every fragment call becomes a plain
block. Then call `validate(program, caps)` and honor the result: raise on an
`error` diagnostic, warn on a `warning`, pass `info` through. The plan
returned alongside the diagnostics says, per node instance, which domains
can run it, which is what tells you whether a loop compiles into the
sequencer or steps from the host.

## What each operation asks of the platform

| Operation                          | Wire form                                                    | What the platform does                                                                        |
|------------------------------------|--------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `acquire`                          | `qblox.acquire q[0].readout "weights" name="q0/readout/m0"`   | Arm an acquisition on the bus's sequencer. Play nothing.                                       |
| `set_markers`                      | `qblox.set_markers "drive_q0" "0001"`                        | Drive the four marker outputs of that bus's module with the mask.                               |
| `set_trigger`                      | `qblox.set_trigger q[0].drive 40 outputs=[1, 2]`             | Assert the named trigger outputs for the duration, at the requested edge of the operation.      |
| `wait_trigger`                     | `qblox.wait_trigger q[0].drive 100 port=1`                   | Block the sequencer until a trigger arrives on the port, giving up after the timeout.           |
| `set_acquisition_threshold`        | `qblox.set_acquisition_threshold q[0].readout 0.42`          | Write the sequencer's thresholded-acquisition threshold. No sequencer instruction.              |
| `set_acquisition_rotation`         | `qblox.set_acquisition_rotation q[0].readout angle`          | Write `thresholded_acq_rotation`, converted to degrees. No sequencer instruction.               |

Keyword arguments appear on the wire only when they differ from their
default, so a `set_trigger` at the default `position="start"` writes without
a `position` keyword and reloads to the same node. A measurement's `name=`
is the exception: it is always written, so a reloaded program keeps the keys
its results are stored under.

### `acquire`

`Acquire(bus, weights, handle, fields=(MeasurementField.IQ,))` is a
`MeasurementOperation`. It acquires without playing, which is the difference
from core `measure`: use it when a separate `play` (or another bus) provides
the readout pulse.

- `weights` is either an `IQWaveform` to upload as integration weights or a
  `str` naming one. A name is a promise the caller keeps, not the platform:
  `program.with_waveforms(library)` resolves names against a
  `WaveformLibrary` before execution, and a platform receives the resolved
  program. A `str` still reaching the platform is a program that was never
  bound.
- `handle.name` is the key of the record in the result. Keep it: it is what
  `QProgramResult.get(handle)` looks up, and it is the same name the `.qp`
  file carries.
- `fields` is a tuple of field names in canonical order (`state`, `iq`,
  `raw`), deduplicated at construction. The platform produces exactly those
  arrays. `iq` is the default, and the primary array
  (`MeasurementResult.data`) is `iq` when requested and the first field in
  canonical order otherwise.
- The node carries no integration length and no acquisition index.
  Integration length is bus configuration, so it reaches the platform
  through the core `program.set_parameter(bus, name, value)` under whatever
  name the platform exposes, or through the platform's own setup, not
  through this node. Acquisition indices are the platform's bookkeeping.

### `set_markers`

`SetMarkers(bus, mask)`. The mask is a four-character string of `0` and `1`,
where `"0001"` enables marker 1.

The node does not check the string. Nothing in the DSL knows how wide a
marker port is, so a platform validates the width and the alphabet itself
and rejects the rest, or its profile adds a predicate that turns a bad mask
into a diagnostic before execution starts. Which physical output each
character drives is the module's business, and the DSL takes no position on
it.

The node also says nothing about duration. It carries a mask and a bus; when
the mask takes effect relative to the surrounding pulses is a scheduling
decision the platform makes.

### `set_trigger`

`SetTrigger(bus, duration, outputs=None, position="start")`.

- `duration` is nanoseconds. Converting to sequencer clock cycles, and
  honoring the module's timing granularity, is the platform's job.
- `outputs` is a list of output numbers, a single number, or `None`. `None`
  means the caller did not choose, so the platform picks its default.
  Numbering is the instrument's.
- `position` is `"start"` or `"end"` of the operation, as a plain string.
  The node accepts any string. Reject an unrecognized one rather than
  guessing.

`duration` is typed `int`. A varying trigger duration is outside the
operation's contract: the node declares no `expr.*` token for it, so nothing
checks whether a platform can vary it between iterations.

### `wait_trigger`

`WaitTrigger(bus, duration, port=None)`. The sequencer blocks until an
external trigger arrives.

- `duration` is the timeout in nanoseconds, again converted to cycles by the
  platform.
- `port` is the trigger input port, or `None` for the platform's default.

What happens when the timeout expires is not in the node. Pick a policy, and
document it: continuing and failing the shot are both defensible, and a
program cannot tell them apart from the DSL side.

### `set_acquisition_threshold`

`SetAcquisitionThreshold(bus, value)` is host-side only. It emits no
sequencer instruction. The platform writes an instrument parameter at
execution time, once per occurrence, in program order relative to the
operations around it.

`value` is the threshold in volts after integration, and it accepts an
`Expression`. If the instrument parameter is defined on another scale, for
instance in integrated ADC counts, the platform converts. The node stays in
the DSL's unit for the same reason the rotation does, described next.

### `set_acquisition_rotation`

`SetAcquisitionRotation(bus, angle)` is the other half of thresholded
acquisition, and also host-side only: the integrated IQ point is rotated by
`angle` so the two populations separate along one axis, then compared
against the threshold. Setting one without the other is legal; a calibrated
discrimination normally writes both.

**`angle` is in radians. The instrument parameter is in degrees.** The DSL
uses radians for every angle, matching core `set_phase`. The QCoDeS
parameter `thresholded_acq_rotation` takes degrees in `[0, 360)`. So the
platform converts, and normalizes into range:

```python
import math

angle = math.pi / 4  # radians, as the DSL recorded it
rotation_deg = math.degrees(angle) % 360.0
print(rotation_deg)  # 45.0, in the unit the instrument wants
```

The modulo is not decoration. A calibration sweep that runs past `2π`, or
one that starts below zero, produces angles outside the parameter's range,
and `%` maps them back without changing the physical rotation.

The conversion lives on the platform side, not in the AST node, and that is
a deliberate choice. The `.qp` file records what the user asked for, in the
DSL's own units. A program written against radians stays readable, keeps
comparing equal to the program that produced it, and stays portable: a
second backend whose parameter wants radians, or milliradians, or turns,
reads the same file and applies its own conversion. Bake degrees into the
node instead and the file starts describing one instrument's API rather than
the experiment.

There is a second reason, and it is the subject of the next section: a swept
angle has no literal value at build time, so there is nothing to convert
until the loop runs.

## Conversions the DSL does not perform

| The node holds                       | The instrument wants                   | Who converts                                              |
|--------------------------------------|----------------------------------------|-----------------------------------------------------------|
| `angle` in radians                    | degrees in `[0, 360)`                  | Platform: `math.degrees(angle) % 360.0`                   |
| `value` in volts after integration    | whatever scale the parameter uses      | Platform                                                  |
| `duration` in nanoseconds             | sequencer clock cycles                 | Platform, honoring the module's granularity               |
| `mask` as a four-character string     | marker bits, in the module's order     | Platform                                                  |
| `weights` as a name                   | uploaded samples                       | The caller, with `program.with_waveforms(library)`         |

The rule behind the table: **a node holds what the user wrote, in the DSL's
units, and the platform converts at the boundary.** Two things pay for that.
The `.qp` file stays a description of an experiment rather than of one
vendor's API, which is what makes the same file run on a second backend. And
a program keeps round-tripping unchanged, because nothing in the writer or
the parser has to know an instrument's unit conventions.

The DSL does check the things it can know about. A bus reference is
validated against the schema that produced it, a waveform's channel kind has
to match the bus, and the profile's limits and predicates run before
execution. Anything that depends on an instrument's API, or on a value that
only exists once a loop is running, is left to the platform on purpose.

## Swept arguments evaluate per iteration

Two arguments in this package accept an `Expression`:
`set_acquisition_threshold`'s `value` and `set_acquisition_rotation`'s
`angle`. Sweeping the rotation is how it is normally calibrated. Everything
else takes a plain value.

An `Expression` is not a value. A `Variable` inside it carries a value only
while the loop that binds it is on its current iteration, and the executor
sets that value once per iteration. So the platform reads it inside the
iteration:

```python
from qprogram.variable import Expression

angle = 0.5  # a node's attribute, either a float or an Expression
value = angle.evaluate_or_raise() if isinstance(angle, Expression) else angle
print(value)
```

Then convert **the evaluated value**, per iteration. Converting once, at
compile time, is the bug this section exists to prevent: on an unassigned
variable `evaluate_or_raise` raises, and on an assigned one it silently
freezes the first point of the sweep into every iteration.

The reference executor makes the whole loop runnable in a few lines. Its
`vendor_op_handlers` argument maps an operation class to a callable that
receives the node and the parameter store, and an operation with a handler
skips the executor's own eager evaluation, so the handler owns it:

```python
import math

import qprogram as qp
from qprogram.executor import ReferencePlatform
from qprogram.variable import Expression
from qprogram_qblox import QProgram
from qprogram_qblox.operations import SetAcquisitionRotation

written: list[float] = []


def apply_rotation(op: SetAcquisitionRotation, params: dict[str, float]) -> None:
    """Stand in for ``sequencer.thresholded_acq_rotation(...)``."""
    angle = op.angle.evaluate_or_raise() if isinstance(op.angle, Expression) else op.angle
    degrees = math.degrees(angle) % 360.0
    params[f"{op.bus}.thresholded_acq_rotation"] = degrees
    written.append(degrees)


schema = qp.BusSchema.transmon()
q = schema.q

program = QProgram(schema=schema)
angle = program.variable("angle", units="rad")
with program.sweep(angle).from_linspace(0.0, math.pi, 3):
    program.qblox.set_acquisition_rotation(q[0].readout, angle)
    program.qblox.acquire(q[0].readout, "weights")

platform = ReferencePlatform(schema=schema, vendor_op_handlers={SetAcquisitionRotation: apply_rotation})
platform.execute(program)
print([round(deg, 1) for deg in written])
```

```text
[0.0, 90.0, 180.0]
```

Three degrees written for three iterations, from one node. A real platform
does the same thing in whichever loop it runs the sweep in.

Which loop that is matters. If the platform steps the sweep from the host,
one parameter write per iteration is exactly right. If it compiles the sweep
into the sequencer, the angle never reaches the host at all, and a parameter
write cannot be part of a real-time sequence. A platform that treats these
two operations as host-side only says so in its capabilities: it puts
`vendor.qblox.set_acquisition_threshold` and
`vendor.qblox.set_acquisition_rotation` in the `host` half of the bus slot
and leaves them out of the `rt` half, and it ships a predicate yielding a
`DomainConstraint` on the binding loop when the value is swept. That drops
the loop to host-side dispatch while the operations around it stay
real-time. The core reference platform does exactly this for the core
`set_parameter` and `get_parameter`, and it is the pattern to copy.
`QBLOX_DEFAULT_V1` itself makes no such split: it is one capability set, and
the platform decides which slots to put it in.

## What the profile constrains

`QBLOX_DEFAULT_V1` is the bus-level answer to "will this program run here?".
It declares four things:

- **Capabilities.** The tokens a qblox-driven bus accepts: nine core bus
  operations, thirteen waveform tokens, the three measurement fields, and
  the six `vendor.qblox.*` operations. A program using a token the set omits
  gets one `missing-capability` error per use site.
- **Limits.** `min_wait_duration_ns = 4`, checked by the core validator.
- **Predicates.** Two, described below.
- **Vendor versions.** `{"qblox": (0, 1, 0)}`, informational: a record of
  the extension version the profile was written against.

A platform materializes it into a slot and pairs it with the core-shipped
`qprogram-base-v1` at the platform slot:

```python
import qprogram as qp
from qprogram.protocol import BusCapabilities, CompilerCapabilities, PlatformCapabilities
from qprogram_qblox import QProgram  # importing anything from the package registers the profile

qblox_caps = CompilerCapabilities.from_profile("qblox-default-v1")
base_caps = CompilerCapabilities.from_profile("qprogram-base-v1")

caps = PlatformCapabilities(
    bus={},
    platform=BusCapabilities(rt=base_caps, host=base_caps),
    default_bus_profile=BusCapabilities(rt=qblox_caps, host=qblox_caps),
)
print(len(qblox_caps.capabilities), "tokens,", qblox_caps.limits)
```

```text
31 tokens, {'min_wait_duration_ns': 4}
```

A real platform maps `(element_kind, bus_kind)` selectors to per-bus slots
instead of leaning on `default_bus_profile`, and it fills `rt` and `host`
separately where the two differ. It may also tighten any limit at that point
with `from_profile(..., limit_overrides={...})`, and it may withhold tokens
to hand a narrower grant to one client. What it cannot do is widen: a token
that was never registered cannot be named in a profile at all.

The split between the two slots decides where a token is looked up.
Bus-touching operations, waveforms and `measure.fields.*` are checked
against the bus slot, which is why they are in this profile. Blocks, sweep
sources and `expr.*` tokens are checked against the platform slot, which is
why this profile has none of them: a swept `angle` on a qblox bus needs
`expr.variable` from `qprogram-base-v1`, not from here. Put the
`vendor.qblox.*` tokens on the platform slot by mistake and every qblox
operation fails validation, because that is not where they are looked up.

### `min_wait_duration_ns`

The limit applies to the core `wait`, on any bus this profile covers:

```python
program = QProgram()
program.wait("drive_q0", 2)

for diag in qp.validate(program, caps)[0]:
    print(diag.severity, diag.code, "|", diag.message)
```

```text
error limit-exceeded | Wait duration 2 ns is shorter than min_wait_duration_ns=4
```

### An arbitrary sweep cannot drive a wait duration

The first predicate is a hard error. A qblox wait instruction takes one
integer cycle count from a register that advances by a fixed step, so a
`Range` or a `Linspace` fits and an arbitrary array of values does not.
Host-side dispatch does not rescue it either, since the instruction still
has to be emitted per shot, so the predicate yields a `Diagnostic` rather
than a `DomainConstraint`:

```python
import numpy as np

program = QProgram()
duration = program.variable("duration")
with program.sweep(duration).from_values(np.array([40, 100, 220])):
    program.wait("drive_q0", duration)

for diag in qp.validate(program, caps)[0]:
    print(diag.severity, diag.code)
```

```text
error qblox.arbitrary-wait-sweep
```

The message names the variable and says what to use instead: a linear
source, or a constant. Every source declares `KIND`, and the predicate reads
it through `ctx.sweep_kind_of`, so a new arbitrary-valued source is covered
the day it appears without touching this package.

### A swept Drag sigma forces its loop host-side

The second predicate is a soft restriction. A qblox sequencer can re-arm a
real-time loop with a new amplitude or duration, but a Drag envelope's
`sigma` shapes samples that were computed at upload, so varying it means
re-uploading the waveform once per iteration. The `Play` is still a
real-time operation; what cannot stay real-time is the **loop**. So the
predicate yields a `DomainConstraint` excluding `"rt"` from the loop that
binds the variable, found with `ctx.binding_loop_of`:

```python
from qprogram.waveforms import IQDrag

program = QProgram()
sigma = program.variable("sigma")
with program.sweep(sigma).from_range(4, 12, 2):
    program.play("drive_q0", IQDrag(amplitude=0.5, duration=40, sigma=sigma, beta=0.1))
    program.qblox.acquire("readout_q0", "weights")

print(qp.explain(program, caps))
```

```text
plan — errors: 0 · warnings: 1 · info: 0
body
└─ for sigma in Range(start=4.0, stop=12.0, step=2.0):                           [host]     ~ forced-host: Variable 'sigma' sweeps IQDrag.sigma in a contained Play, which qblox cannot real-time-update; the loop dispatches per shot host-side instead
   ├─ play "drive_q0" IQDrag(amplitude=0.5, duration=40, sigma=sigma, beta=0.1)  [rt|host]
   └─ qblox.acquire "readout_q0" "weights" name="m0"                             [rt|host]
```

The loop is `[host]`, its children are `[rt|host]`, and the diagnostic is a
`warning`: the program runs, one real-time shot per host-side iteration, and
the platform re-uploads the waveform between them. This is the shape every
"hardware cannot vary this, but the host can step it" constraint takes. A
constraint has to target a block, never an operation; an operation-targeted
one is reported as `bad-domain-constraint`.

A platform that adds its own constraints does it the same way, in its own
profile, and both sets of predicates run.

## Adding an operation

Five edits, in dependency order. The example is a hypothetical
`qblox.set_integration_length`.

**1. The node class**, in `operations.py`:

```python
from __future__ import annotations

from qprogram.operations.operation import Operation
from qprogram.variable import Expression


class SetIntegrationLength(Operation):
    """Set the acquisition integration length on a readout bus.

    Args:
        bus (str): Readout bus whose integration length to set.
        length (int | Expression): Integration length in ns.
    """

    def __init__(self, bus: str, length: int | Expression) -> None:
        self.bus = bus
        self.length = length

    def required_capabilities(self) -> set[str]:
        """Return ``vendor.qblox.set_integration_length`` plus the ``length`` expression tokens."""
        from qprogram.protocol import expression_tokens  # ruff: ignore[import-outside-top-level]

        return {"vendor.qblox.set_integration_length"} | expression_tokens(self.length)
```

Attributes go in `__init__` order: that is the order the writer emits
positional arguments in and the parser binds them back. `BUS_ATTRS` defaults
to `("bus",)`, so an operation with one bus attribute named `bus` declares
nothing. Declare it when the attribute has another name or the operation
touches several buses, and declare `WAVEFORM_ATTRS` for waveform arguments,
as `Acquire` does for its `weights`. Accepting an `Expression` means adding
`expression_tokens(...)` to the token set, and it means every consumer has
to evaluate per iteration, as described above.

**2. The namespace method**, in `namespace.py`, which is the only public way
to build the node:

```python
from qprogram.vendor import VendorNamespace


class QbloxNamespace(VendorNamespace):
    ...

    def set_integration_length(self, bus: str, length: int | Expression) -> None:
        """Set the acquisition integration length in ns.

        Args:
            bus (str): Readout bus whose integration length to set.
            length (int | Expression): Integration length in ns. Accepts an
                :class:`~qprogram.Expression` so it can be swept.
        """
        self._append(SetIntegrationLength(bus=bus, length=length))
```

`_append` runs every bus attribute through the program's schema check before
appending, so a bus from a foreign schema cannot slip in. A measurement
operation calls `_append_measurement` instead, which allocates the name,
builds the node and returns the handle. Add the import of the new class to
the group at the top of the module.

**3. The capability token**, in `profiles.py`. Add it to the
`register_capability_tokens` call that already runs above the profile:

```python
from qprogram.protocol import register_capability_tokens

register_capability_tokens("vendor.qblox.set_integration_length")
```

The call is variadic and idempotent, so the existing one takes the new name
as one more argument. It has to stay above the `Profile`, which rejects a
capability set naming an unregistered token.

**4. Profile membership**, also in `profiles.py`. Registering a token only
makes it spellable; the profile is what advertises it:

```python
_VENDOR: frozenset[str] = frozenset(
    {
        ...,
        "vendor.qblox.set_integration_length",
    },
)
```

Skip this edit and the operation exists, serializes, and fails validation
with `missing-capability` on every use.

**5. The serializer registration**, in `__init__.py`, next to the others,
plus the class in `__all__`:

```python
from qprogram.serialization.registry import register_vendor_operation

register_vendor_operation("qblox", "set_integration_length", SetIntegrationLength)
```

That is all the serialization work. The default writer reflects on
`__init__` and the default parser binds by signature, so the operation reads
and writes without a line of format code:

```python
import qprogram as qp

text = """#!QProgram 1.0

require qblox 0.1

body:
  qblox.set_integration_length "readout_q0" 2000
"""
program = qp.loads(text)
print(type(program.body.elements[0]).__name__)
print(qp.dumps(program) == text)
```

```text
SetIntegrationLength
True
```

An operation with a shape the default reflection cannot express, such as a
measurement handle or a variadic argument list, passes explicit `serialize=`
and `parse=` callbacks to `register_vendor_operation`. `acquire` is the
worked example.

### The tests that come with it

One per module the change touched, matching the suite's existing layout:

- `tests/test_operations.py`: construction, the attributes, `buses()`,
  `waveforms()` and `variables()`, structural equality against an identical
  node, and `required_capabilities()` for both a literal and an `Expression`
  argument.
- `tests/test_namespace.py`: the method appends the right node to the active
  block, passes its arguments through, and validates its bus.
- `tests/test_serialization.py`: a round trip through `dumps` and `loads`
  that is byte-stable, and the `require qblox 0.1` line in the output.
- `tests/test_registration.py`: the operation resolves from the registry
  under `("qblox", "set_integration_length")`.
- `tests/test_profile.py`: a program using the operation validates clean
  against `QBLOX_DEFAULT_V1`, and the token is in the profile's capability
  set.

Then the docs: the operation belongs in
[Operations](../guide/operations.md), and the class in the
[API reference](../reference/api.md). The full checklist is on the
[contributing](contributing.md) page.
