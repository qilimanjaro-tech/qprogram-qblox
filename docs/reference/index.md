# Reference

Generated API documentation for `qprogram_qblox`, plus the core material the
extension is written against.

| Topic                                                                                        | What you find there                                                   |
|----------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| [API reference](api.md)                                                                      | Every public name in `qprogram_qblox`, generated from the source.     |
| [.qp file format](https://qilimanjaro-tech.github.io/qprogram/reference/qp-format.html)      | The grammar the `qblox.<op>` statements are written in.               |
| [Errors](https://qilimanjaro-tech.github.io/qprogram/reference/errors.html)                  | The exception hierarchy `ParseError` and `UnsupportedOperationError` belong to. |
| [Core API reference](https://qilimanjaro-tech.github.io/qprogram/reference/api-qprogram.html) | `QProgram`, waveforms, blocks, and the capability protocol.           |

These pages describe the observable surface. For the wire form of each
operation and the `require qblox` header it needs, read
[Saving and loading](../guide/serialization.md). For what a platform has to
do with the AST nodes, read
[Lowering onto hardware](../developer/lowering.md).
