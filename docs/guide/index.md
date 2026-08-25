# User guide

Three pages, in the order you usually need them.

| Topic                                             | What it covers                                                                            |
|---------------------------------------------------|-------------------------------------------------------------------------------------------|
| [Operations](operations.md)                       | All six qblox operations: arguments, units, return values, and where each one takes effect. |
| [Capabilities and profiles](capabilities.md)      | `QBLOX_DEFAULT_V1`, the tokens and limits it declares, and the two constraints it enforces. |
| [Saving and loading](serialization.md)            | The `qblox.<name>` wire form, `require qblox 0.1`, version checks, and auto-activation.     |

These pages cover only what this package adds. Everything portable, which is
most of what a program contains, is documented in the
[QProgram user guide](https://qilimanjaro-tech.github.io/qprogram/guide/index.html):
buses, waveforms, variables and expressions, control flow, measurements, and
results.

If you are writing the platform that runs these programs rather than the
programs themselves, the [developer guide](../developer/lowering.md)
describes how each operation reaches a sequencer, and
[Reference](../reference/index.md) holds the generated API.
