# Developer guide

These pages document the internals: what you need to drive real instruments
from this package's operations, or to add one.

| Topic                                        | What you find there                                                                              |
|----------------------------------------------|--------------------------------------------------------------------------------------------------|
| [Lowering onto hardware](lowering.md)        | The five modules, what runs at import, what a platform does with each operation and what it must convert. |
| [Contributing](contributing.md)              | The uv workflow, the lint and type-check and test gate, the checklist for a change.               |

The [user guide](../guide/index.md) covers the same six operations from the
caller's side: what they mean ([Operations](../guide/operations.md)), what a
platform has to advertise before it accepts them
([Capabilities and profiles](../guide/capabilities.md)), and how they read
and write as text ([Saving and loading](../guide/serialization.md)). The
[API reference](../reference/api.md) is generated from the docstrings under
`src/qprogram_qblox`, so the code and the reference move together.

The core DSL documents its own internals. Two of those pages are the
background for everything here:
[building a vendor extension](https://qilimanjaro-tech.github.io/qprogram/developer/vendor-extensions.html)
is the template this package follows, and
[capability protocol internals](https://qilimanjaro-tech.github.io/qprogram/developer/capability-protocol.html)
is the normative account of tokens, slots and predicates.
