# Capabilities and profiles

This package ships one capability profile: `qblox-default-v1`, exported as
`qprogram_qblox.QBLOX_DEFAULT_V1`. It is a **bus-level** profile. It describes
what a single qblox-driven bus can do, and a platform wires it into the bus
slots of a `PlatformCapabilities` while the core `qprogram-base-v1` fills the
platform slot.

Importing the package registers the profile, so `from_profile` finds it by name:

```python
import qprogram as qp
import qprogram_qblox  # registers qblox-default-v1 on import

qblox_bus = qp.CompilerCapabilities.from_profile("qblox-default-v1")
qblox_bus.profile  # 'qblox-default-v1'
qblox_bus.version  # (0, 1, 0)
```

If you have not met the capability protocol before, the [core capabilities
guide](https://qilimanjaro-tech.github.io/qprogram/guide/capabilities.html)
explains the shape: three axes (capabilities, limits, predicates) per
(bus, domain) slot, `validate` returning diagnostics plus an execution plan, and
`explain` rendering that plan as a tree. This page covers only what qblox puts
in them.

## Setup for the examples

Every snippet below assumes this preamble. [Wiring the profile into a
platform](#wiring-the-profile-into-a-platform) takes it apart line by line.

```python
import numpy as np

import qprogram as qp
import qprogram_qblox  # registers qblox-default-v1 on import
from qprogram.waveforms import IQDrag
from qprogram_qblox import QProgram
from qprogram_qblox.operations import SetTrigger

qblox_bus = qp.CompilerCapabilities.from_profile("qblox-default-v1")
base = qp.CompilerCapabilities.from_profile("qprogram-base-v1")

bus_slot = qp.BusCapabilities(rt=qblox_bus, host=None)
platform_slot = qp.BusCapabilities(rt=base, host=base)

schema = qp.BusSchema.transmon()
q = schema.q

caps = qp.PlatformCapabilities(
    bus={("q", "drive"): bus_slot, ("q", "readout"): bus_slot},
    platform=platform_slot,
    default_bus_profile=bus_slot,
)
```

## What the profile carries

```python
from qprogram_qblox import QBLOX_DEFAULT_V1

QBLOX_DEFAULT_V1.name  # 'qblox-default-v1'
QBLOX_DEFAULT_V1.version  # (0, 1, 0)
QBLOX_DEFAULT_V1.extends  # None
len(QBLOX_DEFAULT_V1.capabilities)  # 31
QBLOX_DEFAULT_V1.limits  # {'min_wait_duration_ns': 4}
QBLOX_DEFAULT_V1.vendor_versions  # {'qblox': (0, 1, 0)}
```

`extends` is `None`. The profile is declared from scratch rather than inherited,
because a bus profile and the platform-level base share no tokens.

`vendor_versions` records the qblox protocol version the profile was written
against, which is how a platform reports what it accepts in a `require qblox`
header.

### Core bus operations, 9 tokens

`op.play`, `op.measure`, `op.wait`, `op.sync`, `op.set_frequency`,
`op.set_phase`, `op.set_gain`, `op.reset_phase`, `op.set_offset`.

These are the core operations that reach a qblox sequencer, and they are what a
qblox bus runs in real time.

`op.set_parameter` and `op.get_parameter` are **not** in the set. They are
bus-scoped core operations, so they route to the bus slot, and a program that
uses them against a qblox-only bus gets a hard error:

```python
program = QProgram(schema=schema)
program.set_parameter(q[0].drive, "lo_frequency", 5e9)

diagnostics, _ = qp.validate(program, caps)
for diagnostic in diagnostics:
    print(diagnostic)
# [error] missing-capability: 'SetParameter' requires capability 'op.set_parameter' which is not supported by 'qblox-default-v1' (rt) (at body[0])
```

A platform that routes slow-control parameters through its own configuration
layer adds those two tokens to the bus profile it derives from this one. See
[Extending the profile](#extending-the-profile).

### Waveform tokens, 13 tokens

`waveform.single`, `waveform.iq`, `waveform.alias`, `waveform.arbitrary`,
`waveform.chained`, `waveform.flat_top`, `waveform.gaussian`,
`waveform.gaussian_drag_correction`, `waveform.ramp`, `waveform.snz`,
`waveform.square`, `waveform.iq_drag`, `waveform.iq_pair`.

Three of these are shape-agnostic. `waveform.single` and `waveform.iq` say the
bus accepts single-channel and two-path waveforms; `waveform.alias` says it
accepts a string name to be resolved from a waveform library before execution.
The other ten name the concrete pulse classes a qblox sequencer renders.

The core package registers more waveform classes than this list covers.
`waveform.cosine`, `waveform.iq_rotation`, `waveform.iq_zero`,
`waveform.modulated`, `waveform.sech`, `waveform.sine` and `waveform.tukey` are
absent, so playing one of those on a qblox bus is a hard error naming the token:

```python
from qprogram.waveforms import Tukey

program = QProgram()
program.play("flux_q0", Tukey(amplitude=0.5, duration=40, alpha=0.5))

diagnostics, _ = qp.validate(program, caps)
for diagnostic in diagnostics:
    print(diagnostic)
# [error] missing-capability: 'Play' requires capability 'waveform.tukey' which is not supported by 'qblox-default-v1' (rt) (at body[0])
```

### Measurement fields, 3 tokens

`measure.fields.iq`, `measure.fields.raw`, `measure.fields.state`.

The complete core vocabulary. A qblox readout path can return the integrated IQ
point, the raw ADC trace, and the thresholded state, so all three are supported.
`measure.fields.state` is what makes a conditional on `handle.state` validate on
a qblox bus, and it is the field `set_acquisition_threshold` and
`set_acquisition_rotation` exist to calibrate.

### Vendor operations, 6 tokens

`vendor.qblox.acquire`, `vendor.qblox.set_markers`, `vendor.qblox.set_trigger`,
`vendor.qblox.wait_trigger`, `vendor.qblox.set_acquisition_threshold`,
`vendor.qblox.set_acquisition_rotation`.

One per operation in the namespace. All six qblox operations declare `bus` as
their only bus attribute, so all six route to the bus slot, which is why their
tokens live here rather than on the platform profile.
[Operations](operations.md) documents each one.

The tokens are registered with the core `CAPABILITY_REGISTRY` before the profile
is constructed, because `Profile.__post_init__` rejects a token it has never
seen.

### Tokens the profile deliberately omits

`block.*`, `sweep.*` and `expr.*` are not in this profile. Blocks route to the
platform slot, and `expr.*` tokens are always checked against the platform slot
whatever node carries them, so putting them on a bus profile would have no
effect. They live in the core `qprogram-base-v1` bundle instead:

```python
sorted(qp.QPROGRAM_BASE_V1.capabilities)
# ['block.average', 'block.block', 'block.conditional', 'block.parallel',
#  'block.sweep', 'expr.binary_op', 'expr.comparison', 'expr.constant',
#  'expr.logical_and_or', 'expr.logical_not', 'expr.math.abs', 'expr.math.cos',
#  'expr.math.exp', 'expr.math.log', 'expr.math.maximum', 'expr.math.minimum',
#  'expr.math.sin', 'expr.math.sqrt', 'expr.math.tan', 'expr.measurement_ref',
#  'expr.unary_op', 'expr.variable', 'expr.where', 'sweep.arbitrary',
#  'sweep.concat', 'sweep.file', 'sweep.linear', 'sweep.linspace',
#  'sweep.logspace', 'sweep.range', 'sweep.repeat', 'sweep.rotate',
#  'sweep.values']
```

## Limits

The profile declares one limit:

```python
QBLOX_DEFAULT_V1.limits  # {'min_wait_duration_ns': 4}
```

`min_wait_duration_ns` is a bus-level limit, set here to 4 ns. The validator
compares it against every constant-valued `Wait.duration` on a bus wired to this
profile:

```python
program = QProgram(label="short-wait", schema=schema)
program.wait(q[0].drive, 2)

diagnostics, _ = qp.validate(program, caps)
for diagnostic in diagnostics:
    print(diagnostic)
# [error] limit-exceeded: Wait duration 2 ns is shorter than min_wait_duration_ns=4 (at body[0])
```

```python
print(qp.explain(program, caps))
# plan for 'short-wait' — errors: 1 · warnings: 0 · info: 0
# body
# └─ wait q[0].drive 2  [rt]       !! limit-exceeded: Wait duration 2 ns is shorter than min_wait_duration_ns=4
```

The three other limits the validator reads (`max_loop_nesting`,
`max_parallel_loops`, `max_measurements`) are platform-level, so a qblox
platform sets them on its platform slot, not here.

## Predicates

The profile declares two predicates. They are the two constraints that cannot be
written as a flat token, because each depends on how a `Play` or a `Wait`
interacts with the loop that binds its variable.

| Predicate                      | Fires when                                                      | Yields            | Code                            | Severity |
|--------------------------------|-----------------------------------------------------------------|-------------------|---------------------------------|----------|
| Arbitrary sweep at `Wait.duration` | `Wait.duration` is a `Variable` whose binding source is arbitrary-kind | `Diagnostic`      | `qblox.arbitrary-wait-sweep`    | `error`  |
| `IQDrag.sigma` swept in a loop     | `Play`'s waveform is an `IQDrag` whose `sigma` is a loop-bound `Variable` | `DomainConstraint` | `forced-host` (from the classifier) | `warning` |

### Arbitrary sweep at `Wait.duration`, a hard error

The exact condition: the node is a `Wait`, its `duration` is a `Variable`, and
`ctx.sweep_kind_of(duration)` is `"arbitrary"`. A qblox wait instruction takes
one integer cycle count from a register that is incremented by a fixed step, so
an arbitrary-kind source (`Values`, `Logspace`, `File`, or any of the
combinators) has no register pattern to compile to. Host-side dispatch does not
rescue it either, because qblox still emits the wait instruction per shot. That
is why this is a `Diagnostic` and not a `DomainConstraint`: no domain can run it.

A constant duration is fine, and so is a variable bound by `Range` or
`Linspace`, whose `KIND` is `"linear"`.

```python
program = QProgram(label="wait-scan", schema=schema)
dur = program.variable("dur")
with program.sweep(dur, qp.Values(np.array([100, 200, 400]))):
    program.wait(q[0].drive, dur)
    program.play(q[0].drive, "pi_pulse")

diagnostics, _ = qp.validate(program, caps)
for diagnostic in diagnostics:
    print(diagnostic.severity, diagnostic.code, qp.format_path(diagnostic.path))
# error qblox.arbitrary-wait-sweep body[0][0]
```

```python
print(qp.explain(program, caps))
# plan for 'wait-scan' — errors: 1 · warnings: 0 · info: 0
# body
# └─ for dur in [100.0, 200.0, 400.0]:  [--]
#    ├─ wait q[0].drive dur             [--]       !! qblox.arbitrary-wait-sweep: Variable 'dur' is swept with arbitrary values and used at Wait.duration, which qblox does not support (the wait instruction needs a linear step). Use a linear sweep source (Range / Linspace) instead, or a constant duration.
#    └─ play q[0].drive "pi_pulse"      [rt]
```

`[--]` is the empty domain set. The `Wait` cannot run anywhere, and the
enclosing `Sweep` inherits that by intersection. The sibling `play` is
unaffected and stays `[rt]`, which is how you read off that the loop itself is
not the problem.

Swapping the source fixes it, with no other change:

```python
program = QProgram(label="wait-scan", schema=schema)
dur = program.variable("dur")
with program.sweep(dur, qp.Range(100, 500, 100)):
    program.wait(q[0].drive, dur)

qp.validate(program, caps)[0]  # []
```

### `IQDrag.sigma` swept in a loop, a soft restriction

The exact condition: the node is a `Play`, its waveform is an `IQDrag`, its
`sigma` is a `Variable`, and `ctx.binding_loop_of(sigma)` finds a loop. A qblox
sequencer re-arms a real-time loop with a new amplitude or duration from a
register, but a Drag envelope's gaussian and derivative samples are computed at
upload time. Changing `sigma` means re-uploading the waveform, which means one
qblox shot per iteration, dispatched from the host.

Per-iteration dispatch does work, so this is a `DomainConstraint`, not an error.
It targets the **binding loop**, never the `Play`, and excludes `"rt"` only.
The classifier subtracts that from the loop's support set. The `Play` keeps
`[rt]`: what changes is the loop's iteration mechanism, not how the pulse is
emitted.

A `sigma` that is a bare unbound `Variable` does not fire the predicate. It is a
constant at upload time.

```python
program = QProgram(label="drag-sigma", schema=schema)
sigma = program.variable("sigma")
with program.average(100), program.sweep(sigma, qp.Range(4.0, 12.0, 2.0)):
    program.play(q[0].drive, IQDrag(amplitude=0.5, duration=40, sigma=sigma, beta=0.1))

diagnostics, plan = qp.validate(program, caps)
for diagnostic in diagnostics:
    print(diagnostic.severity, diagnostic.code, diagnostic.domain, qp.format_path(diagnostic.path))
# warning forced-host host body[0]
```

The user-visible diagnostic is the classifier's `forced-host` warning, not the
constraint itself. Constraints are silent when a fallback works; the warning
says the fallback happened, and names the immediate cause:

```python
print(qp.explain(program, caps))
# plan for 'drag-sigma' — errors: 0 · warnings: 1 · info: 0
# body
# └─ average 100:                                                                     [host]     ~ forced-host: contains host-side-only sub-block 'Sweep' (Variable 'sigma' sweeps IQDrag.sigma in a contained Play, which qblox cannot real-time-update; the loop dispatches per shot host-side instead.)
#    └─ for sigma in Range(start=4.0, stop=12.0, step=2.0):                           [host]
#       └─ play q[0].drive IQDrag(amplitude=0.5, duration=40, sigma=sigma, beta=0.1)  [rt]
```

The warning lands on `average`, the highest block in the forced chain, and its
reason is attributed to the sub-block that caused it. The program still runs. It
just runs slower than it looks, one upload per point.

Sweeping any other `IQDrag` field leaves the loop real-time:

```python
program = QProgram(label="drag-amp", schema=schema)
amp = program.variable("amp")
with program.sweep(amp, qp.Range(0.0, 1.0, 0.1)):
    program.play(q[0].drive, IQDrag(amplitude=amp, duration=40, sigma=8, beta=0.1))

diagnostics, plan = qp.validate(program, caps)
diagnostics  # []
sweep = next(node for node in program.body.walk() if type(node).__name__ == "Sweep")
sorted(plan[sweep])  # ['rt']
```

`['rt']` rather than `['rt', 'host']` because the bus slot in this wiring has no
`host` half, so every operation under the loop supports `rt` alone. What matters
is that `rt` survived.

## Wiring the profile into a platform

`qblox-default-v1` fills bus slots. The platform slot needs the core
`qprogram-base-v1`, which carries the block, sweep and expression tokens. A
qblox bus is real-time by design, so its `BusCapabilities` declares an `rt` half
and leaves `host` as `None`. The platform slot declares both halves, so a block
can land in either domain depending on what its operation children require.

```python
qblox_bus = qp.CompilerCapabilities.from_profile("qblox-default-v1")
base = qp.CompilerCapabilities.from_profile("qprogram-base-v1")

# Real-time only: a qblox sequencer has no host-side half.
bus_slot = qp.BusCapabilities(rt=qblox_bus, host=None)
# Both halves: a block may be classified into either domain.
platform_slot = qp.BusCapabilities(rt=base, host=base)

caps = qp.PlatformCapabilities(
    # Keyed by (element_kind, bus_kind), matched against a schema-backed BusRef.
    bus={("q", "drive"): bus_slot, ("q", "readout"): bus_slot},
    # block.* / sweep.* / expr.* live here.
    platform=platform_slot,
    # Buses with no entry above, and every raw-string bus.
    default_bus_profile=bus_slot,
)
```

The `bus` keys are `(element_kind, bus_kind)` pairs, matched against a
schema-backed `BusRef`'s `element` and `kind`. `default_bus_profile` catches
everything else: a bus with no entry in the map, and any raw-string bus. Setting
it to the same slot is what makes a plain-string bus behave like a schema-backed
one.

The mapping is where a mixed rack is expressed. A platform whose flux lines run
on a slow DAC gives `("q", "flux")` a different profile and leaves drive and
readout on qblox.

Checking the wiring directly:

```python
caps.for_bus(q[0].drive).rt.supports("op.play")  # True
caps.for_bus(q[0].drive).rt.supports("block.sweep")  # False
caps.platform.rt.supports("block.sweep")  # True
```

`block.sweep` is absent from the bus slot and present on the platform slot,
which is exactly the split the routing rules expect.

A program that stays inside the declaration validates clean:

```python
program = QProgram(label="spectroscopy", schema=schema)
freq = program.variable("freq", label="Drive frequency", units="Hz")
with program.average(1000), program.sweep(freq, qp.Range(5e9, 6e9, 2.5e8)):
    program.set_frequency(q[0].drive, freq)
    program.play(q[0].drive, "pi_pulse")
    program.sync()
    program.qblox.acquire(q[0].readout, "weights")

diagnostics, plan = qp.validate(program, caps)
diagnostics  # []
```

```python
print(qp.explain(program, caps))
# plan for 'spectroscopy' — errors: 0 · warnings: 0 · info: 0
# body
# └─ average 1000:                                                                   [rt|host]
#    └─ for freq in Range(start=5000000000.0, stop=6000000000.0, step=250000000.0):  [rt]
#       ├─ set_frequency q[0].drive freq                                             [rt]
#       ├─ play q[0].drive "pi_pulse"                                                [rt]
#       ├─ sync                                                                      [rt]
#       └─ qblox.acquire q[0].readout "weights" name="q0/readout/m0"                 [rt]
```

`average` shows `[rt|host]` while the `sweep` under it shows `[rt]`. An
`Average` takes its natural domain from its averaging-relevant operation
children only, and it has none directly: the acquisition sits inside the sweep,
which counts as a unit. The sweep is `[rt]` because the bus slot has no `host`
half, so every operation in it supports `rt` alone.

### Host-side operations still validate against `rt`

`set_acquisition_threshold` and `set_acquisition_rotation` are realized as
slow-control parameter writes, not sequencer instructions, yet in the wiring
above they land in `[rt]`:

```python
program = QProgram(label="discrimination", schema=schema)
angle = program.variable("angle")
with program.average(200), program.sweep(angle, qp.Linspace(0.0, np.pi, 5)):
    program.qblox.set_acquisition_rotation(q[0].readout, angle)
    program.qblox.set_acquisition_threshold(q[0].readout, 0.0)
    program.qblox.set_markers(q[0].drive, "0001")
    program.qblox.set_trigger(q[0].drive, duration=100)
    program.qblox.wait_trigger(q[0].drive, duration=10_000, port=2)
    program.play(q[0].drive, "pi_pulse")
    program.qblox.acquire(q[0].readout, "weights", fields=(qp.MeasurementField.STATE,))

diagnostics, _ = qp.validate(program, caps)
diagnostics  # []
```

```python
print(qp.explain(program, caps))
# plan for 'discrimination' — errors: 0 · warnings: 0 · info: 0
# body
# └─ average 200:                                                                      [rt|host]
#    └─ for angle in Linspace(start=0.0, stop=3.141592653589793, num=5):               [rt]
#       ├─ qblox.set_acquisition_rotation q[0].readout angle                           [rt]
#       ├─ qblox.set_acquisition_threshold q[0].readout 0.0                            [rt]
#       ├─ qblox.set_markers q[0].drive "0001"                                         [rt]
#       ├─ qblox.set_trigger q[0].drive 100                                            [rt]
#       ├─ qblox.wait_trigger q[0].drive 10000 port=2                                  [rt]
#       ├─ play q[0].drive "pi_pulse"                                                  [rt]
#       └─ qblox.acquire q[0].readout "weights" name="q0/readout/m0" fields=["state"]  [rt]
```

This is not a contradiction. A profile's capability set is domain-agnostic: the
same tokens are checked against whichever halves a platform fills. The domain
column says which halves accepted the node, not which piece of hardware executes
it. A platform that wants those two operations restricted to host-side dispatch
declares a bus profile with a `host` half and puts their tokens only there.

## Extending the profile

Two knobs cover most device-specific tightening without a new profile.

`limit_overrides` narrows a limit for one device:

```python
tight = qp.CompilerCapabilities.from_profile(
    "qblox-default-v1",
    limit_overrides={"min_wait_duration_ns": 8},
)
tight.limits  # {'min_wait_duration_ns': 8}
```

`extra_predicates` adds a rack-level constraint without republishing the bundle.
This one refuses a trigger pulse pinned to the end of its operation:

```python
def reject_end_position(node, ctx):
    if isinstance(node, SetTrigger) and node.position == "end":
        yield qp.Diagnostic(
            severity="error",
            code="myplatform.trigger-position",
            message="this module emits a trigger only at the start of an operation",
            node=node,
        )


site_bus = qp.CompilerCapabilities.from_profile(
    "qblox-default-v1",
    extra_predicates=(reject_end_position,),
)
site_caps = qp.PlatformCapabilities(
    bus={},
    platform=platform_slot,
    default_bus_profile=qp.BusCapabilities(rt=site_bus, host=None),
)

program = QProgram(schema=schema)
program.qblox.set_trigger(q[0].drive, duration=100, position="end")

diagnostics, _ = qp.validate(program, site_caps)
for diagnostic in diagnostics:
    print(diagnostic)
# [error] myplatform.trigger-position: this module emits a trigger only at the start of an operation (at body[0])
```

For a lasting change, declare a profile that extends this one. Capabilities and
predicates accumulate from parent to child; limits inherit and the child wins:

```python
platform_bus = qp.Profile(
    name="myplatform-qblox-bus-v1",
    version=(0, 1, 0),
    extends="qblox-default-v1",
    capabilities=frozenset({"op.set_parameter", "op.get_parameter"}),
    limits={"min_wait_duration_ns": 8},
    predicates=(),
)
qp.register_profile(platform_bus)

derived = qp.CompilerCapabilities.from_profile("myplatform-qblox-bus-v1")
"op.play" in derived.capabilities  # True, inherited
"op.set_parameter" in derived.capabilities  # True, added
derived.limits  # {'min_wait_duration_ns': 8}
len(derived.predicates)  # 2, both inherited
```

That is the shape a platform package uses to add the two slow-control tokens the
bus profile leaves out.

## See also

- [Operations](operations.md) for the tokens each operation declares.
- [Lowering onto hardware](../developer/lowering.md) for what a compiler does
  once validation passes.
- [API reference](../reference/api.md) for `QBLOX_DEFAULT_V1` and the
  operation classes.
- The [core capabilities
  guide](https://qilimanjaro-tech.github.io/qprogram/guide/capabilities.html)
  for routing rules, the full diagnostic-code list, and the classifier.
