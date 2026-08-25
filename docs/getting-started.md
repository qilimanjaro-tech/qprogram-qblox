# Getting started

This page walks you from an empty environment to a Qblox program you can
run. It assumes Python 3.11 or newer, and that you have met the core DSL
before. If not, read the
[QProgram getting started](https://qilimanjaro-tech.github.io/qprogram/getting-started.html)
page first: everything here is the core language plus one namespace.

## Install

```bash
pip install qprogram-qblox
```

That pulls in `qprogram`, and through it `numpy` and `xarray`. There are no
other runtime dependencies and no extras.

### Working on this package

The repository uses [uv](https://docs.astral.sh/uv/). The core DSL is not on
PyPI yet, so `[tool.uv.sources]` points `qprogram` at `../qprogram`: it
resolves from a sibling checkout of
<https://github.com/qilimanjaro-tech/qprogram>. Clone both repositories into
the same parent directory, because a clone of this repository alone leaves
`uv sync` with nothing to resolve `qprogram` against and the sync fails.

```bash
git clone https://github.com/qilimanjaro-tech/qprogram
git clone https://github.com/qilimanjaro-tech/qprogram-qblox
cd qprogram-qblox

uv sync --group dev
uv run pytest
```

To preview the documentation:

```bash
uv run --group docs zensical serve
```

## Importing is the activation step

The package registers everything it adds as an import side effect: the
`qblox` namespace on `QProgram`, the vendor protocol version the `.qp`
parser checks, one serializer entry per operation, and the `qblox-default-v1`
capability profile. There is no setup call.

```python
import qprogram as qp

import qprogram_qblox  # importing is what registers the qblox vendor

program = qp.QProgram(label="markers")
program.qblox.set_markers("drive_q0", "0001")

print(qp.dumps(program))
```

Note the plain `qprogram.QProgram`. Registration is on the base class, so
`.qblox` resolves on any program instance. The namespace object is built on
first access and cached on the instance.

## The typed QProgram

Editors cannot complete an attribute that is resolved dynamically, so the
package also exports a `QProgram` with `.qblox` declared as a property:

```python
import qprogram as qp

from qprogram_qblox import QProgram

program = QProgram(label="acquisition")
m0 = program.qblox.acquire("readout_q0", "weights")

print(m0.name)  # m0, the auto-allocated measurement name
print(qp.dumps(program))
```

Either spelling builds the same AST and writes the same file, because
`.qblox` reaches the same namespace class both ways. What the typed one adds
is argument help and return types while you write the program.

## One program, several vendors

`QbloxMixin` is the property on its own. A platform that drives more than
one instrument family lists every vendor mixin in the bases of its own
program class:

```python
import qprogram as qp
from qprogram import QProgram as BaseQProgram
from qprogram_qdac import QdacMixin

from qprogram_qblox import QbloxMixin


class QProgram(QbloxMixin, QdacMixin, BaseQProgram):
    """A program for a platform with both a Qblox cluster and a QDAC."""


program = QProgram(label="two_vendors")
program.qdac.set_offset("flux_q0", 0.35)
program.qblox.set_markers("drive_q0", "0001")
program.qblox.acquire("readout_q0", "weights")

print(qp.dumps(program))
```

This one needs `qprogram-qdac` installed as well. The resulting file carries
a `require` line per vendor, and the parser checks each one against the
installed extension:

```
#!QProgram 1.0

require qblox 0.1
require qdac 0.1

metadata:
  label: "two_vendors"

body:
  qdac.set_offset "flux_q0" 0.35
  qblox.set_markers "drive_q0" "0001"
  qblox.acquire "readout_q0" "weights" name="m0"
```

## A first experiment

Save this as `rotation.py` and run it with `python rotation.py`. It builds
an acquisition-rotation calibration, checks it against a Qblox capability
set, writes it to a scratch directory, and runs it on the reference executor.

```python
import math
from pathlib import Path

import qprogram as qp
from qprogram.buses import BusSchema
from qprogram.protocol import BusCapabilities, CompilerCapabilities, PlatformCapabilities
from qprogram.waveforms import IQDrag, IQPair, Square

from qprogram_qblox import QProgram

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

# What a qblox-driven bus accepts, paired with the core block and expression tokens.
capabilities = PlatformCapabilities(
    bus={},
    platform=BusCapabilities(
        rt=CompilerCapabilities.from_profile("qprogram-base-v1"),
        host=CompilerCapabilities.from_profile("qprogram-base-v1"),
    ),
    default_bus_profile=BusCapabilities(
        rt=CompilerCapabilities.from_profile("qblox-default-v1"),
        host=CompilerCapabilities.from_profile("qblox-default-v1"),
    ),
)

diagnostics, plan = qp.validate(program, capabilities)
assert not diagnostics
print(qp.explain(program, capabilities))

Path(".tmp").mkdir(exist_ok=True)
qp.save(program, ".tmp/rotation.qp")

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

`qp.explain` prints the plan as a tree, one line per node, with the domains
each node can run in:

```
plan for 'rotation_calibration' — errors: 0 · warnings: 0 · info: 0
body
└─ average 1000:                                                                     [rt|host]
   └─ for angle in Linspace(start=0.0, stop=3.141592653589793, num=21):              [rt|host]
      ├─ qblox.set_acquisition_rotation q[0].readout angle                           [rt|host]
      ├─ play q[0].drive "pi_pulse"                                                  [rt|host]
      ├─ sync                                                                        [rt|host]
      └─ qblox.acquire q[0].readout "weights" name="q0/readout/m0" fields=["state"]  [rt|host]
```

## Load a file without importing anything

A `.qp` file names the extensions it needs, and the parser can fetch them.
Reading back the file the script above wrote works in a fresh interpreter
that has never heard of this package:

```python
import sys
from pathlib import Path

import qprogram as qp

reloaded = qp.load(".tmp/rotation.qp")

print("qprogram_qblox" in sys.modules)  # True, the parser imported it on demand
print(qp.dumps(reloaded) == Path(".tmp/rotation.qp").read_text())  # True, the file round-trips
```

The `require qblox 0.1` line sends the parser to the `qprogram.vendors`
entry point group, where it finds this package and imports it. Pass
`auto_activate=False` to `qp.load` or `qp.loads` to turn that off and get a
`ParseError` for an unregistered vendor instead.

## Where to next?

- [Operations](guide/operations.md) covers all six operations, their
  arguments, and their units.
- [Capabilities and profiles](guide/capabilities.md) explains
  `QBLOX_DEFAULT_V1`, its limits, and the two constraints it declares.
- [Saving and loading](guide/serialization.md) covers the wire form and
  version checking.
- [Lowering onto hardware](developer/lowering.md) is for platform authors
  turning these nodes into sequencer code.
