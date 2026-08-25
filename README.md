# QProgram Qblox

[![Tests](https://github.com/qilimanjaro-tech/qprogram-qblox/actions/workflows/tests.yml/badge.svg)](https://github.com/qilimanjaro-tech/qprogram-qblox/actions/workflows/tests.yml)
[![Code Quality](https://github.com/qilimanjaro-tech/qprogram-qblox/actions/workflows/code_quality.yml/badge.svg)](https://github.com/qilimanjaro-tech/qprogram-qblox/actions/workflows/code_quality.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Qblox extensions for [QProgram](https://github.com/qilimanjaro-tech/qprogram), a Python DSL for
pulse-level quantum experiments.

The core DSL knows nothing about any instrument. This package teaches it about the Qblox cluster.
It adds six operations that the portable language does not cover, a capability profile that says
what QCM and QRM sequencers accept, and `.qp` serialization for everything it adds. Importing the
package is the whole activation step.

## Installation

```bash
pip install qprogram-qblox
```

The core `qprogram` package installs with it.

## A first program

Calibrate the acquisition rotation angle of a readout bus: sweep the angle, discriminate the
qubit state at each point, and average the outcome.

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

`qp.simulate` is the reference software executor that ships with the core package. It runs the
qblox operations generically: `qblox.acquire` produces measurement records, the rest have no
effect on the simulated outcome. A Qblox platform is a drop-in for the same call and lowers each
operation onto real sequencers.

## What you get

- **Six operations under `program.qblox`.** `acquire` reads a bus without playing a readout
  pulse. `set_markers` and `set_trigger` drive the digital outputs, `wait_trigger` waits on a
  digital input. `set_acquisition_threshold` and `set_acquisition_rotation` configure
  thresholded acquisition, and take effect off the sequencer as slow-control parameter writes
  at execution time.
- **Typed or dynamic access.** `qprogram_qblox.QProgram` has `.qblox` typed for autocomplete,
  `QbloxMixin` composes with other vendor mixins, and the plain `qprogram.QProgram` gets the
  same namespace at runtime once this package is imported.
- **A capability profile.** `QBLOX_DEFAULT_V1` declares the operations, waveforms, measurement
  fields, and limits of a qblox-driven bus, plus the two constraints the hardware imposes: an
  arbitrary-valued sweep cannot drive a wait duration, and sweeping an `IQDrag` sigma forces its
  loop to iterate host-side.
- **Round-tripping `.qp` files.** Every operation serializes as `qblox.<name> <args>` and reloads
  to a structurally equal program. Files carry `require qblox 0.1`, which the parser checks
  against the installed version.
- **Auto-activation on load.** `qprogram.load("file.qp")` imports this package on demand when the
  file requires the `qblox` vendor, so a reader never has to know which extensions a file uses.

## Documentation

Full documentation, including the operation reference, the capability profile, and the generated
API reference, lives at <https://qilimanjaro-tech.github.io/qprogram-qblox/>.

## Development

The project uses [uv](https://docs.astral.sh/uv/). The core DSL is not on PyPI yet, so
`[tool.uv.sources]` in `pyproject.toml` points `qprogram` at `../qprogram`: it resolves from a
sibling checkout of <https://github.com/qilimanjaro-tech/qprogram>. Clone both repositories into
the same parent directory. A clone of this repository alone has nothing to resolve `qprogram`
against, and `uv sync` fails.

```bash
git clone https://github.com/qilimanjaro-tech/qprogram
git clone https://github.com/qilimanjaro-tech/qprogram-qblox
cd qprogram-qblox

uv sync --group dev                  # create .venv and install the package plus dev tools
uv run pytest                        # run the test suite
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run ty check                      # type-check
uv run --group docs zensical serve   # preview the documentation
```

## License

Apache License 2.0 - see [LICENSE](LICENSE).
