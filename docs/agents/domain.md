# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root. Its intro links the shared Qilimanjaro glossary for terms used across the stack.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.
- **`docs/developer/lowering.md`**: the module map, the registration that runs at import, and what a platform does with each operation.

If any of these files don't exist or are empty, **proceed silently**. Don't flag their absence. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates entries lazily when terms or decisions actually get resolved.

## File structure

Single-context repo:

```
/
├── GLOSSARY.md
├── docs/adr/
└── src/qprogram_qblox/
```

`docs/` is also the source of the published documentation site (`zensical.toml` sets `docs_dir = "docs"`). The files under `docs/agents/` and `docs/adr/` are not in the site nav.

## Use the glossary's vocabulary

When your output names a domain concept (an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0001 (title), but worth reopening because…_
