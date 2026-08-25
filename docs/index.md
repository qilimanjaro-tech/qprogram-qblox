# QProgram Qblox

Qblox extensions for
[QProgram](https://qilimanjaro-tech.github.io/qprogram/), a Python DSL for
pulse-level quantum experiments.

The core DSL describes what is portable across instruments. This package
describes what a Qblox cluster adds on top: acquisitions without a readout
pulse, marker and trigger lines, and thresholded-acquisition setup on the
QCM and QRM sequencers. Importing the package registers all of it. Nothing
in the core changes.

## What the qblox namespace gives you

Every operation is reached as `program.qblox.<name>(...)` and writes one
`qblox.<name>` line into a `.qp` file.

| Operation                     | What it does                                                                                   |
|-------------------------------|------------------------------------------------------------------------------------------------|
| `acquire`                     | Integrate a readout bus against weights without playing a pulse. Returns a `MeasurementHandle`. |
| `set_markers`                 | Drive the four marker outputs from a 4-character mask, for example `"0001"`.                    |
| `set_trigger`                 | Emit a trigger of a given duration on selected outputs, at the start or end of the operation.   |
| `wait_trigger`                | Block the sequencer until a trigger arrives on an input port, up to a timeout.                  |
| `set_acquisition_threshold`   | Set the state-discrimination threshold of a readout bus.                                        |
| `set_acquisition_rotation`    | Rotate the integrated IQ point before it meets the threshold. Radians, as everywhere in the DSL. |

The last two take effect off the sequencer, as slow-control parameter writes
at execution time. Both accept an `Expression`, so a loop can sweep them the
way a discrimination is normally calibrated.

Alongside the operations, the package ships `QBLOX_DEFAULT_V1`, the
capability profile that says what a qblox-driven bus accepts, and
`QbloxMixin`, the typed property that gives editors something to complete.

## A first program

```python
import math

import qprogram as qp
from qprogram.buses import BusSchema
from qprogram.waveforms import IQDrag, IQPair, Square

from qprogram_qblox import QProgram  # qprogram.QProgram with a typed .qblox namespace

schema = BusSchema.transmon()
q = schema.q

program = QProgram(label="rotation_calibration", schema=schema)
angle = program.variable("angle", units="rad")

with program.average(shots=1000):
    with program.sweep(angle).from_linspace(0.0, math.pi, 21):
        program.qblox.set_acquisition_rotation(q[0].readout, angle)
        program.play(q[0].drive, "pi_pulse")
        program.sync()
        m0 = program.qblox.acquire(q[0].readout, "weights", fields=(qp.MeasurementField.STATE,))

# Bind calibrated waveforms at the very end; the program itself only names them.
resolved = program.with_waveforms(
    {
        "pi_pulse": IQDrag(amplitude=0.5, duration=40, sigma=8, beta=0.1),
        "weights": IQPair(Square(1.0, 2000), Square(1.0, 2000)),
    }
)

result = qp.simulate(resolved)
population = result.get(m0, field=qp.MeasurementField.STATE)
print(population.dims, population.shape)  # ('angle',) (21,)
```

`qp.simulate` is the reference software executor from the core package. It
runs qblox operations generically: `qblox.acquire` produces measurement
records, the rest leave the simulated outcome alone. A Qblox platform is a
drop-in for the same call and lowers each operation onto real sequencers.

## Where to go next

| If you want to ...                                   | Read                                                     |
|------------------------------------------------------|----------------------------------------------------------|
| install the package and run something                | [Getting started](getting-started.md)                    |
| see every operation and its arguments                | [Operations](guide/operations.md)                        |
| know which programs a qblox platform accepts         | [Capabilities and profiles](guide/capabilities.md)       |
| read and write `.qp` files that use qblox operations | [Saving and loading](guide/serialization.md)             |
| browse the generated API                             | [API reference](reference/api.md)                        |
| turn these operations into sequencer code            | [Lowering onto hardware](developer/lowering.md)          |
| work on this package                                 | [Contributing](developer/contributing.md)                |

## How it plugs in

The core package defines three hooks and this one uses all three at import
time: a runtime namespace registered with `QProgram.register_vendor`, a
typed mixin for editors, and the serialization registry that maps each
operation class to its `.qp` spelling. A fourth line, the `qprogram.vendors`
entry point in `pyproject.toml`, lets `qprogram.load` import this package on
demand when a file's header carries `require qblox 0.1`.

Because all four are declarations rather than patches, the same program can
also carry operations from other vendor packages.
[Getting started](getting-started.md) shows how to combine them.

## Status

The package is pre-1.0 and tracks the core DSL, so the Python API is allowed
to move. The wire format is steadier: a `.qp` file that requires `qblox 0.1`
loads against any installed version that shares its major number and is no
older in minor, and anything else is a `ParseError` rather than a silent
partial load.
