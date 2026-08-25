# Saving and loading

Qblox operations cross the `.qp` boundary through the same four functions as
the core DSL, and through the same writer and parser. This package ships no
format code of its own. It registers each operation at import time, and the
core serializer works out the rest from the operation's constructor
signature.

```python
import qprogram as qp
from qprogram_qblox import QProgram

program = QProgram()
program.qblox.set_markers("drive_q0", "0001")

text = qp.dumps(program)  # program -> str
program = qp.loads(text)  # str -> program

qp.save(program, "experiment.qp")  # program -> file
program = qp.load("experiment.qp")  # file -> program
```

A loaded program is a plain `qprogram.QProgram`, not the pre-combined class
from this package. `program.qblox.set_markers(...)` still works on it: the
namespace is registered on the base class, and the mixin only adds static
types. See [Operations](operations.md) for the builder side.

## The `require` line

A program that touches a qblox operation carries one `require` line under the
format header:

```
#!QProgram 1.0

require qblox 0.1
```

The writer emits it for you, and it walks the whole program to do so, so a
`qblox.*` operation buried in a conditional arm or a fragment body still
produces the line. A program with no qblox content produces no line at all.

The line is what makes a file self-contained. The parser does not require it:
a hand-written file that calls `qblox.set_markers` with no `require qblox`
line loads as long as the extension is already imported. Without the line
nothing tells the parser which extension to go and find, and in a fresh
interpreter that has never imported it the first dotted operation fails
instead:

```python
qp.loads('#!QProgram 1.0\n\nbody:\n  qblox.set_markers "drive_q0" "0001"\n')
# ParseError: Line 4: unknown vendor operation qblox.'set_markers': no operation is
#             registered under that name. Import the 'qblox' extension package before
#             loading, and check the file's `require qblox <x.y>` declaration.
```

## Where the version comes from

The package reads its own distribution version at import and registers it as
the qblox protocol version:

```python
from importlib.metadata import version

from qprogram.serialization.registry import register_vendor_version

register_vendor_version("qblox", version("qprogram-qblox"))
```

That one number is what every `.qp` file is checked against. Major and minor
govern compatibility; the patch component is informational, and the writer
truncates it. An installed `0.1.0` therefore writes `require qblox 0.1`, and
`qprogram.serialization.registry.get_vendor_version("qblox")` returns the full
`0.1.0`.

On load, the parser resolves each `require` line against the installed
extension:

- The **major** version must match exactly.
- The installed **minor** must be greater than or equal to the file's minor.

Both checks run before the body is read, so an incompatible file never
half-loads. With `0.1.0` installed:

```python
qp.loads(text)  # the file says: require qblox 1.0
# ParseError: Line 3: file requires qblox 1.0 (major 1); installed qblox is 0.1.0
#             (major 0) — major versions must match

qp.loads(text)  # the file says: require qblox 0.9
# ParseError: Line 3: file requires qblox 0.9 or compatible; installed qblox is
#             0.1.0 — minor version too old
```

An older minor is fine in the other direction: `require qblox 0.1` loads
against an installed `0.4.2`, because everything `0.1` can spell is still
there.

## Auto-activation

If the vendor is installed but not yet imported, the parser imports it on the
spot. `qprogram-qblox` declares the discovery hook in its `pyproject.toml`:

```toml
[project.entry-points."qprogram.vendors"]
qblox = "qprogram_qblox"
```

The entry-point *name* is the vendor namespace as it appears in `require` and
in `qblox.<op>` statements. The *value* is the module whose import side
effects do the registration. When `qp.load` reaches `require qblox 0.1` and
finds no qblox extension registered, it looks the name up in that entry-point
group and imports the module, then runs the version check against what the
import registered. So this works in a fresh interpreter:

```python
import qprogram as qp

program = qp.load("calibration.qp")  # imports qprogram_qblox on demand
```

Discovery only runs for a vendor that is not registered yet, and only for a
vendor named in a `require` line. Pass `auto_activate=False` to turn it off
and get a hard error instead:

```python
qp.load("calibration.qp", auto_activate=False)
# ParseError: Line 3: file requires vendor 'qblox' 0.1 but no matching extension is
#             registered in this environment — auto-activation is disabled; import
#             the extension before loading (e.g. `import qprogram_qblox`)
```

## Statement form

Every operation in this package writes as one line, `qblox.<op>` followed by
its arguments:

```
body:
  qblox.acquire q[0].readout "weights" name="q0/readout/m0"
  qblox.acquire q[0].readout "weights" name="q0_raw_trace" fields=["iq", "raw"]
  qblox.set_markers q[0].drive "0001"
  qblox.set_trigger q[0].drive 100
  qblox.set_trigger q[0].drive 100 outputs=[1, 2] position="end"
  qblox.wait_trigger q[0].readout 1000
  qblox.wait_trigger q[0].readout 1000 port=2
  qblox.set_acquisition_threshold q[0].readout 0.42
  qblox.set_acquisition_rotation q[0].readout 0.7854
```

The shape comes from the operation class's `__init__` signature, which the
generic vendor serializer introspects. Constructor parameters with no default
are written positionally, in declaration order. Parameters with a default are
written as `key=value`, and only when the value differs from that default.
That is why `set_trigger` appears twice above with two different lengths:
`outputs` and `position` are optional, so the second line names them and the
first does not.

Nothing in this package registers a custom writer or parser callback except
`acquire`, which needs the measurement handle. Adding an operation with an
introspectable signature costs no serialization work at all.

## How arguments are spelled

Quoting is the type distinction. A quoted token is a plain string: a raw bus
name, a weights alias, a marker mask. A bare token is a variable reference or
a schema-backed bus path.

| Python value                | Wire form                | Example                                        |
|-----------------------------|--------------------------|------------------------------------------------|
| `str`                       | quoted                   | `"0001"`, `"weights"`, `"readout_q0"`          |
| schema-backed `BusRef`      | bare bus path            | `q[0].readout`                                 |
| `int` / `float`             | decimal literal          | `100`, `0.42`, `5e9`                           |
| `Variable`                  | bare identifier          | `angle`                                        |
| `Expression`                | parenthesized            | `(0.5 - (t / 1000))`                           |
| `list` / `tuple`            | bracket literal          | `outputs=[1, 2]`, `fields=["state", "iq"]`     |
| `dict` with string keys     | brace literal            | `matrix={"a": 1.0, "b": -0.5}`                 |
| `None`                      | `null`                   | `port=null`                                    |
| `Waveform` / `IQWaveform`   | constructor call         | `IQPair(I=Square(amplitude=1.0, duration=200), Q=Square(amplitude=0.0, duration=200))` |

Two notes on the table:

- No operation in this package takes a dict argument. The brace form belongs
  to the shared value grammar, so an operation that carries one needs no
  writer or parser change either.
- `null` is accepted on the way in but rarely appears on the way out, because
  an optional argument left at its `None` default is not written at all.
  `qblox.wait_trigger "readout_q0" 1000 port=null` loads with `port` set to
  `None`, and writes back as `qblox.wait_trigger "readout_q0" 1000`.

Bus paths are promoted back to a `BusRef` only for the attributes an operation
lists in its `BUS_ATTRS`, and only against the file's `schema:` block. A
quoted bus stays a string even when it looks like a path, so a raw-string bus
survives the round trip as a raw string.

Expressions work in the argument positions that accept them.
`set_acquisition_threshold` and `set_acquisition_rotation` both take a float or
an `Expression`, which is what lets an enclosing loop sweep them:

```
  for t in Range(start=0.0, stop=100.0, step=10.0):
    qblox.set_acquisition_threshold q[0].readout (0.5 - (t / 1000))
```

## `acquire` carries its measurement name

`Acquire` is a measurement operation, so it serializes through the same pair of
callbacks as core `measure`. The handle name rides on a `name=` kwarg and the
requested fields on a `fields=[...]` list:

```
  qblox.acquire q[0].readout "weights" name="q0_raw_trace" fields=["iq", "raw"]
```

The writer omits `fields=` when the acquisition asks for only the default
`iq`, and canonically orders the names it does write. `fields=("iq", "state")`
and `fields=("state", "iq")` both save as `fields=["state", "iq"]`, and both
programs produce byte-identical text.

Three spellings load:

- `name="q0_m0"`, the form the writer emits.
- A quoted token in the handle position:
  `qblox.acquire "readout_q0" "weights" "cal_point"`.
- Neither, in which case the parser allocates a name.

Every reference to one name resolves to a single `MeasurementHandle` instance.
That is what keeps a `MeasurementRef` in a conditional guard pointing at the
acquisition it came from:

```
body:
  qblox.acquire q[0].readout "weights" name="q0/readout/m0" fields=["state"]
  if q0/readout/m0.state == 1:
    qblox.set_markers q[0].drive "0010"
```

## A full round trip

A discrimination calibration: sweep the acquisition rotation, set the
threshold, drive the qubit, and acquire both the classified state and the raw
IQ point.

```python
import qprogram as qp
from qprogram_qblox import QProgram

schema = qp.BusSchema.transmon()
program = QProgram(schema=schema, label="discrimination calibration")
angle = program.variable("angle", units="rad")

with program.average(2000):
    with program.sweep(angle).from_linspace(start=0.0, stop=3.14159, num=8):
        program.qblox.set_acquisition_rotation(schema.q[0].readout, angle)
        program.qblox.set_acquisition_threshold(schema.q[0].readout, 0.42)
        program.play(schema.q[0].drive, "pi_pulse")
        program.sync()
        program.qblox.acquire(schema.q[0].readout, "weights", fields=("state", "iq"))

text = qp.dumps(program)
reloaded = qp.loads(text)

assert qp.dumps(reloaded) == text
assert reloaded.body == program.body
```

`print(text)` gives:

```
#!QProgram 1.0

require qblox 0.1

metadata:
  label: "discrimination calibration"

schema:
  element q:
    drive info=IQ
    readout info=IQ+acquires

body:
  var angle units="rad"

  average 2000:
    for angle in Linspace(start=0.0, stop=3.14159, num=8):
      qblox.set_acquisition_rotation q[0].readout angle
      qblox.set_acquisition_threshold q[0].readout 0.42
      play q[0].drive "pi_pulse"
      sync
      qblox.acquire q[0].readout "weights" name="q0/readout/m0" fields=["state", "iq"]
```

Both assertions hold for any program built through the public API. The vendor
operations are structural value objects like the core ones, so equality covers
their bus references, their waveforms, their expression trees, and the
requested field tuple.

## Where the parser stays strict

A malformed qblox line fails on load rather than loading with content
missing. Each message below is prefixed with the 1-based line number of the
offending input and carries the same number on `ParseError.line_num`.

- An operation name that no `qblox` registration matches:
  `qblox.set_marker "drive_q0" "0001"` is an unknown vendor operation.
- Too many positional tokens:
  `qblox.set_markers "drive_q0" "0001" "extra"` reports `3 positional tokens
  but the operation takes at most 2`.
- A missing required argument, or a keyword the constructor does not accept.
- A `name=` value that is not a quoted string: `name=5` reports
  `measurement name= must be a quoted string, got 5`.
- A `require` line the installed extension cannot satisfy.

Argument *types* are not checked, because the parser feeds the tokens straight
into the constructor. `qblox.set_markers "drive_q0" 0001` loads with a mask of
`1`, the number. Keep the quotes on values that are strings.

## See also

- [Operations](operations.md) covers the builder side of each statement: the
  arguments, their defaults, and which of them accept an expression.
- [Capabilities and profiles](capabilities.md) covers what validation adds on
  top of a successful load.
- The core project's
  [.qp file format reference](https://qilimanjaro-tech.github.io/qprogram/reference/qp-format.html)
  specifies the grammar these statements sit inside: the header, the `schema:`
  block, and the value literals.
