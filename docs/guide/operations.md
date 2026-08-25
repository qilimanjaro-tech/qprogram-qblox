# Operations

Every operation this package adds lives behind the `qblox` namespace:

```text
program.qblox.<operation>(...)
```

Importing `qprogram_qblox` registers the namespace, so the call works on any
`QProgram` instance. The `QProgram` re-exported from this package is the same
class with a typed `.qblox` property, which is what gives editors
autocomplete. See [Getting started](../getting-started.md) for the two import
styles.

There are six operations. Four are sequencer instructions; two are host-side
parameter sets.

| Operation                   | Kind                    | Lowers to                                                 |
|-----------------------------|-------------------------|-----------------------------------------------------------|
| `acquire`                   | sequencer instruction   | An acquisition on the readout module's sequencer          |
| `set_markers`               | sequencer instruction   | A write to the sequencer's marker output register         |
| `set_trigger`               | sequencer instruction   | A trigger pulse on the sequencer's trigger outputs        |
| `wait_trigger`              | sequencer instruction   | A blocking wait on the sequencer's trigger input          |
| `set_acquisition_threshold` | host-side parameter set | A slow-control parameter write before the sequence starts |
| `set_acquisition_rotation`  | host-side parameter set | A slow-control parameter write before the sequence starts |

QProgram itself draws no line between the two kinds. Both serialize the same
way, both validate through the same capability slot, and both are ordinary
`Operation` nodes in the AST. The difference is only in how a platform
realizes them, which is the subject of
[Lowering onto hardware](../developer/lowering.md).

## Conventions

All six operations take `bus` as their first argument, and it is their only bus
attribute. So each one routes to the capability slot of the bus it names, never
to the platform slot. A schema-backed `BusRef` is checked against the program's
schema; a plain string is not checked at all.

Every snippet below assumes this preamble:

```python
import numpy as np

import qprogram as qp
from qprogram.waveforms import IQPair, Square
from qprogram_qblox import QProgram

schema = qp.BusSchema.transmon()
q = schema.q
weights = IQPair(I=Square(amplitude=1.0, duration=200), Q=Square(amplitude=1.0, duration=200))
```

## `acquire(bus, weights, fields=(MeasurementField.IQ,), *, name=None)`

Acquire measurement data without playing a readout pulse. Core
`program.measure(...)` plays a readout pulse and acquires in one node; `acquire`
does only the acquisition, which is what you want when the readout pulse is
managed separately.

| Argument  | Meaning                                                                              |
|-----------|--------------------------------------------------------------------------------------|
| `bus`     | Readout bus to acquire on.                                                            |
| `weights` | Integration weights: an `IQWaveform`, or a string alias resolved later by `with_waveforms`. |
| `fields`  | Iterable of `MeasurementField` members naming which data the platform produces. Defaults to `(MeasurementField.IQ,)`. |
| `name`    | Explicit measurement name. Auto-allocated when omitted.                               |

It returns a `MeasurementHandle`, the same type core `measure` returns, and it
draws from the same per-bus name counter. Two acquisitions and a `measure` on
`q[0].readout` therefore get three distinct names in call order:

```python
program = QProgram(label="acquire", schema=schema)
first = program.qblox.acquire(q[0].readout, weights)
second = program.qblox.acquire(q[0].readout, "weights", name="tomography")
third = program.measure(q[0].readout, "readout", "weights")

print(first.name, second.name, third.name)
# q0/readout/m0 tomography q0/readout/m1
```

`fields` goes through the core `normalize_fields` chokepoint, so it behaves
exactly as it does on `measure`: duplicates collapse, order is canonicalized to
`state`, `iq`, `raw`, a bare string is rejected, and an unknown field name
raises `ValidationError` at the call site.

```python
program = QProgram(schema=schema)
handle = program.qblox.acquire(
    q[0].readout,
    weights,
    fields=(qp.MeasurementField.IQ, qp.MeasurementField.RAW),
)

program.body.elements[0].fields
# ('iq', 'raw')
```

On the wire the requested fields become a bracket list, omitted when the
acquisition wants only the default `iq`. That call serializes to:

```
body:
  qblox.acquire q[0].readout IQPair(I=Square(amplitude=1.0, duration=200), Q=Square(amplitude=1.0, duration=200)) name="q0/readout/m0" fields=["iq", "raw"]
```

The handle reads results back like any other measurement. Here the mock model's
excited-state probability tracks the swept amplitude, averaged over 200 shots
per point:

```python
program = QProgram(label="amplitude-scan", schema=schema)
amp = program.variable("amp", label="Drive amplitude")
with program.average(200), program.sweep(amp, qp.Linspace(0.0, 1.0, 5)):
    program.play(q[0].drive, "pi_pulse")
    m = program.qblox.acquire(
        q[0].readout,
        weights,
        fields=(qp.MeasurementField.IQ, qp.MeasurementField.STATE),
    )

model = qp.MockMeasurementModel(p_excited=lambda bus, env: env["amp"], seed=7)
result = qp.simulate(program, model=model)
print(result.get(m, field=qp.MeasurementField.STATE))
# <xarray.DataArray (amp: 5)> Size: 40B
# array([0.   , 0.245, 0.43 , 0.77 , 1.   ])
# Coordinates:
#   * amp      (amp) float64 40B 0.0 0.25 0.5 0.75 1.0
```

Two details of the node are worth knowing. It requires `waveform.iq`
unconditionally, because qblox integration weights are a two-path object even
when spelled as an alias. And unlike core `measure`, it does not check that the
bus has an ADC, so nothing rejects an `acquire` on a drive bus at build time.

Capability tokens: `vendor.qblox.acquire`, `waveform.iq`, one
`measure.fields.<field>` per requested field, plus `waveform.alias` or the
weights class token.

```python
program = QProgram(schema=schema)
program.qblox.acquire(q[0].readout, weights, fields=(qp.MeasurementField.IQ, qp.MeasurementField.RAW))
sorted(program.body.elements[0].required_capabilities())
# ['measure.fields.iq', 'measure.fields.raw', 'vendor.qblox.acquire', 'waveform.iq', 'waveform.iq_pair']
```

## `set_markers(bus, mask)`

Set the 4-bit marker output mask on the bus's sequencer. Markers are the
module's digital output lines.

| Argument | Meaning                                                            |
|----------|--------------------------------------------------------------------|
| `bus`    | Bus whose sequencer owns the marker outputs.                         |
| `mask`   | Four characters of `0` and `1`. `"0001"` raises marker 1.            |

The mask is stored verbatim. Nothing in this package checks its length or its
alphabet, so a malformed mask reaches the platform unchanged.

The operation sets a level. There is no duration argument, so raise the mask
before the pulse and lower it after.

```python
program = QProgram(label="gated", schema=schema)
program.qblox.set_markers(q[0].drive, "0001")
program.play(q[0].drive, "pi_pulse")
program.qblox.set_markers(q[0].drive, "0000")
```

Capability token: `vendor.qblox.set_markers`.

## `set_trigger(bus, duration, outputs=None, position="start")`

Emit a trigger pulse from the bus's sequencer.

| Argument   | Meaning                                                                  |
|------------|--------------------------------------------------------------------------|
| `bus`      | Bus whose sequencer emits the trigger.                                    |
| `duration` | Pulse width in nanoseconds.                                               |
| `outputs`  | Which trigger outputs to drive: one index, a list of indices, or `None`.   |
| `position` | `"start"` or `"end"`, whether the pulse lands at the beginning or the end of the operation it marks. |

`outputs=None` and `position="start"` are the defaults, and the writer omits
both when they are left alone. As with `set_markers`, neither `outputs` nor
`position` is validated here.

```python
program = QProgram(label="triggers", schema=schema)
program.qblox.set_trigger(q[0].drive, duration=100)
program.qblox.set_trigger(q[0].drive, duration=100, outputs=[1, 2], position="end")
```

```
body:
  qblox.set_trigger q[0].drive 100
  qblox.set_trigger q[0].drive 100 outputs=[1, 2] position="end"
```

Capability token: `vendor.qblox.set_trigger`.

## `wait_trigger(bus, duration, port=None)`

Block the bus's sequencer until an external trigger arrives.

| Argument   | Meaning                                                        |
|------------|----------------------------------------------------------------|
| `bus`      | Bus whose sequencer waits.                                      |
| `duration` | Timeout in nanoseconds.                                         |
| `port`     | Trigger input port to listen on, or `None` for the platform's default. |

`duration` is a timeout, not a delay: it bounds how long the sequencer waits,
not how long it idles.

```python
program = QProgram(label="externally-triggered", schema=schema)
program.qblox.wait_trigger(q[0].drive, duration=10_000, port=2)
program.play(q[0].drive, "pi_pulse")
```

```
body:
  qblox.wait_trigger q[0].drive 10000 port=2
  play q[0].drive "pi_pulse"
```

Capability token: `vendor.qblox.wait_trigger`.

## `set_acquisition_threshold(bus, value)`

Set the qubit-state discrimination threshold on a readout bus. Integrated IQ
points above the threshold classify as excited, points below as ground.

| Argument | Meaning                                                                 |
|----------|-------------------------------------------------------------------------|
| `bus`    | Readout bus whose threshold to set.                                      |
| `value`  | Threshold in volts after integration. Accepts an `Expression`.            |

This is a host-side parameter set. The platform translates it to a
slow-control parameter write at execution time and emits no sequencer
instruction for it.

`value` accepts an `Expression`, so an enclosing loop can sweep it. That is how
the threshold is normally found: scan it, measure the classified state, and pick
the value that separates the two populations.

```python
program = QProgram(label="threshold-scan", schema=schema)
thr = program.variable("thr", label="Discrimination threshold", units="V")
with program.sweep(thr, qp.Linspace(-0.2, 0.2, 5)):
    program.qblox.set_acquisition_threshold(q[0].readout, thr)
    program.play(q[0].drive, "pi_pulse")
    program.qblox.acquire(q[0].readout, "weights", fields=(qp.MeasurementField.STATE,))
```

```
body:
  var thr label="Discrimination threshold" units="V"

  for thr in Linspace(start=-0.2, stop=0.2, num=5):
    qblox.set_acquisition_threshold q[0].readout thr
    play q[0].drive "pi_pulse"
    qblox.acquire q[0].readout "weights" name="q0/readout/m0" fields=["state"]
```

Capability tokens: `vendor.qblox.set_acquisition_threshold`, plus one `expr.*`
token per expression node kind in `value`. A literal float contributes none.

## `set_acquisition_rotation(bus, angle)`

Set the acquisition rotation angle on a readout bus. The integrated IQ point is
rotated by `angle` before the threshold comparison, so the ground and excited
populations separate along one axis.

| Argument | Meaning                                                                |
|----------|------------------------------------------------------------------------|
| `bus`    | Readout bus whose rotation to set.                                      |
| `angle`  | Rotation angle in radians. Accepts an `Expression`.                     |

The companion of `set_acquisition_threshold`, and also a host-side parameter
set. Setting one without the other is legal, since they are independent
parameters, but a calibrated discrimination writes both.

`angle` is in radians, matching core `set_phase` and every other angle in the
DSL. The Qblox instrument parameter `thresholded_acq_rotation` takes degrees in
`[0, 360)`, so a compiler lowering this node converts and normalizes. The
conversion belongs on the platform side: the `.qp` file records what the user
asked for, in the DSL's own units. Because `angle` may be an `Expression`, the
conversion runs per iteration on the evaluated value rather than once on a
literal. [Lowering onto hardware](../developer/lowering.md) has the code.

Values outside `[0, 2π)` are not checked here. A swept angle has no literal
value to check at build time, so normalizing or rejecting is the platform's
call.

The two together are a rotation calibration: sweep the angle, average the
classified state, and keep the angle that separates the populations best.

```python
program = QProgram(label="discrimination", schema=schema)
angle = program.variable("angle", label="Acquisition rotation", units="rad")
with program.average(200), program.sweep(angle, qp.Linspace(0.0, np.pi, 5)):
    program.qblox.set_acquisition_rotation(q[0].readout, angle)
    program.qblox.set_acquisition_threshold(q[0].readout, 0.0)
    program.play(q[0].drive, "pi_pulse")
    cal = program.qblox.acquire(q[0].readout, "weights", fields=(qp.MeasurementField.STATE,))

model = qp.MockMeasurementModel(p_excited=lambda bus, env: np.cos(env["angle"]) ** 2, seed=7)
result = qp.simulate(program, model=model)
print(result.get(cal, field=qp.MeasurementField.STATE))
# <xarray.DataArray (angle: 5)> Size: 40B
# array([1.  , 0.48, 0.  , 0.49, 1.  ])
# Coordinates:
#   * angle    (angle) float64 40B 0.0 0.7854 1.571 2.356 3.142
```

The same program serializes to:

```
#!QProgram 1.0

require qblox 0.1

metadata:
  label: "discrimination"

schema:
  element q:
    drive info=IQ
    readout info=IQ+acquires

body:
  var angle label="Acquisition rotation" units="rad"

  average 200:
    for angle in Linspace(start=0.0, stop=3.141592653589793, num=5):
      qblox.set_acquisition_rotation q[0].readout angle
      qblox.set_acquisition_threshold q[0].readout 0.0
      play q[0].drive "pi_pulse"
      qblox.acquire q[0].readout "weights" name="q0/readout/m0" fields=["state"]
```

Capability tokens: `vendor.qblox.set_acquisition_rotation`, plus one `expr.*`
token per expression node kind in `angle`.

## What can be swept

Only two arguments in this package accept an `Expression`:

| Operation                   | Argument | Type                 |
|-----------------------------|----------|----------------------|
| `set_acquisition_threshold` | `value`  | `float \| Expression` |
| `set_acquisition_rotation`  | `angle`  | `float \| Expression` |

Everything else is a build-time constant. `acquire`'s `weights` is a waveform
or an alias, `set_markers`'s `mask` is a string, and the `duration`, `outputs`,
`port` and `position` arguments of the trigger operations are typed `int`,
`list[int] | int | None`, `int | None` and `str`. Sweeping a pulse parameter
instead is the usual answer: core `play` takes waveforms whose parameters
accept expressions.

The two expression-bearing operations report their expression node kinds in
`required_capabilities()`, which is what lets a platform declare that it cannot
sweep them. Nothing enforces the type annotations at runtime, so a `Variable`
passed to `set_trigger(duration=...)` is accepted and serialized, but reports no
`expr.*` token, and a platform gets no signal to reject it.

## Capability tokens at a glance

| Node                      | Tokens                                                                       |
|---------------------------|------------------------------------------------------------------------------|
| `Acquire`                 | `vendor.qblox.acquire`, `waveform.iq`, `measure.fields.<field>` per field, plus `waveform.alias` or the weights class token |
| `SetMarkers`              | `vendor.qblox.set_markers`                                                    |
| `SetTrigger`              | `vendor.qblox.set_trigger`                                                    |
| `WaitTrigger`             | `vendor.qblox.wait_trigger`                                                   |
| `SetAcquisitionThreshold` | `vendor.qblox.set_acquisition_threshold`, plus the `expr.*` tokens of `value`  |
| `SetAcquisitionRotation`  | `vendor.qblox.set_acquisition_rotation`, plus the `expr.*` tokens of `angle`   |

All six `vendor.qblox.*` tokens are in `qblox-default-v1`, along with the
waveform and measurement-field tokens `Acquire` needs, so a bus wired to that
profile accepts every operation on this page. [Capabilities and
profiles](capabilities.md) covers the profile and the two constraints it
declares.

## See also

- [Capabilities and profiles](capabilities.md) for what a qblox-driven bus
  supports and the diagnostics it produces.
- [Saving and loading](serialization.md) for the `.qp` wire form of these
  operations and the `require qblox` header.
- [Lowering onto hardware](../developer/lowering.md) for what a compiler does
  with each node.
- [API reference](../reference/api.md) for the generated signatures.
- The [core operations
  guide](https://qilimanjaro-tech.github.io/qprogram/guide/operations.html) for
  `play`, `measure`, `wait`, `sync`, and the parameter operations these compose
  with.
