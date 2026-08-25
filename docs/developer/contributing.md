# Contributing

The short version: keep the PR small, run the linter and the tests, and
write the docs for anything a caller can see.

## Before you start

Two things to read first.

1. **[Lowering onto hardware](lowering.md).** It describes the five modules,
   the registration that runs at import, and what a platform does with each
   operation. Almost every change to this package touches one of those.
2. **The core DSL's own developer guide**, in particular
   [building a vendor extension](https://qilimanjaro-tech.github.io/qprogram/developer/vendor-extensions.html)
   and
   [capability protocol internals](https://qilimanjaro-tech.github.io/qprogram/developer/capability-protocol.html).
   This package is one instance of that template. A change that fits the
   template is easy to review; a change that fights it usually belongs in
   the core instead.

## The core DSL is a sibling checkout

`qprogram` is not on PyPI yet. The published wheel depends on it as a normal
version constraint, but `[tool.uv.sources]` in `pyproject.toml` points the
name at `../qprogram`, so local and CI environments resolve it from a
sibling checkout of <https://github.com/qilimanjaro-tech/qprogram>. Clone
both repositories into the same parent directory. `uv sync` in a lone clone
of this repository has nothing to resolve `qprogram` against and fails.

```bash
git clone https://github.com/qilimanjaro-tech/qprogram
git clone https://github.com/qilimanjaro-tech/qprogram-qblox
cd qprogram-qblox
```

The core is installed as an editable dependency, so a change in
`../qprogram/src` is visible here without reinstalling. That cuts both ways:
a test failing here may be a core change, and the fix may belong in the
other repository.

## Development workflow

1. **Install the package and the dev tools.**

   ```bash
   uv sync --group dev
   ```

2. **Install the docs environment** (only if you change docs).

   ```bash
   uv sync --group docs
   uv run --group docs zensical serve
   ```

   `mkdocstrings` imports the package to render the API reference, so the
   docs build needs the project installed, not just the docs tooling.

3. **Make your change.**

4. **Lint and format.**

   ```bash
   uv run ruff check .
   uv run ruff format .
   ```

5. **Type-check.**

   ```bash
   uv run ty check
   ```

6. **Run the tests.**

   ```bash
   uv run pytest
   uv run pytest --cov=qprogram_qblox --cov-report=term-missing
   uv run pytest tests/test_profile.py -v      # one file
   uv run pytest -k "rotation"                 # by keyword
   ```

   The suite is function-style, roughly a hundred tests across six modules,
   and runs in about a second. Anything much slower than that is doing work
   a unit test should not.

7. **Update the docs.** Anything a caller can see needs an entry in the
   guide, and every new public class or method needs its `mkdocstrings`
   entry in the [API reference](../reference/api.md).

8. **Open the PR.** The workflows under `.github/workflows/` run on it. All
   three check out the core DSL as a sibling directory first, the same way
   you did. `tests.yml` runs the suite on 3.11 and 3.14 for a pull request,
   and on the whole of 3.11 through 3.14 for a push to `main`; the coverage
   upload rides on the 3.13 job, so only a push produces it.
   `code_quality.yml` runs `ruff check` and `ruff format --diff` once on
   3.13, then `ty check` once per supported version. `docs.yml` builds this
   site.

## What "small PR" means

One concept per PR. A new operation plus a profile change plus a fix in the
namespace is three PRs. Each one is easier to review, easier to revert, and
easier to bisect against.

## The checklist for a new operation

Four kinds of change land together, in the same PR. The
[five source edits](lowering.md#adding-an-operation) are the
first item.

| Kind          | What it means here                                                                                                                                                            |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Code          | The node class in `operations.py`, the typed method in `namespace.py`, the token registration and profile membership in `profiles.py`, the `register_vendor_operation` call and the `__all__` entry in `__init__.py`. |
| Tests         | `tests/test_operations.py`, `tests/test_namespace.py`, `tests/test_serialization.py`, `tests/test_registration.py`, `tests/test_profile.py`. One per module the change touched. |
| Docs          | [Operations](../guide/operations.md) for what it means and when to reach for it, and [Capabilities and profiles](../guide/capabilities.md) if the profile changed.               |
| API reference | The class and the namespace method in [the API reference](../reference/api.md), so `mkdocstrings` renders the docstrings you just wrote.                                        |

A missing token registration or a missing profile entry is the failure mode
to watch for: the operation builds and serializes, and every program using
it fails validation. `tests/test_profile.py` is where that gets caught.

## Style notes

These are the rules the project enforces. All of them are configured in
`pyproject.toml`.

- **Ruff with `preview = true` and `select = ["ALL"]`**, minus a curated
  ignore list written as rule *names* rather than codes, so the config says
  why each exemption exists. Line length is 120 and the formatter owns it.
  Expect the linter to push back on most external code.
- **Suppressions use the same names.** Write
  `# ruff: ignore[import-outside-top-level]`, not a numeric code. There is
  not a single numeric suppression in this package.
- **Docstrings are enforced.** Preview mode runs both the `D` and the `DOC`
  families under the Google convention. Every parameter gets a
  `name (type): Description.` entry: the parenthesized type is house style
  even though the signature is annotated. A function returning something
  either opens its summary with the word "Return" or carries a `Returns:`
  section, and every exception a caller can observe gets a `Raises:` entry
  reading `ExceptionType: If <condition>.` Constructor arguments are
  documented in an `Args:` section on the **class** docstring, with no
  docstring on `__init__`, because `mkdocstrings` runs with
  `merge_init_into_class = true`.
- **Cross-references are Markdown, not Sphinx roles.** Write
  `` [`Acquire`][qprogram_qblox.Acquire] `` for a target this site documents, and
  `` [`Expression`][qprogram.Expression] `` for one the core DSL documents:
  `zensical.toml` loads that project's published `objects.inv` as an
  `inventories` entry, so a core type resolves to its page on that site. Plain
  `` `Expression` `` is for anything neither site renders, such as a builtin or
  a stdlib name. A Sphinx role such as `` :class:`~qprogram.Expression` ``
  would reach the page as literal text, since mkdocstrings reads a docstring as
  Markdown and has no reStructuredText reader;
  `tests/test_docstring_style.py` fails the suite on one. The docs build runs
  with `--strict`, so a cross-reference neither site can resolve fails CI as
  well.
- **Every file carries the Apache header**, the standard 13-line notice with
  `Copyright 2026 Qilimanjaro Quantum Tech`, before the module docstring and
  in test files too. Ruff's `missing-copyright-notice` rule fails the lint
  on a file without it.
- **Comments say something the code does not.** A comment that restates the
  next line is worse than no comment. Docstrings follow the same rule and
  describe current behavior, never the change that produced it.
- **Type hints everywhere.** `ty` checks `src` against every supported
  Python version.
- **Two-space indentation in `.qp` text.** Match it in test fixtures.
- **Function-style tests.** No test classes. Use fixtures and
  parametrization. `tests/conftest.py` holds the shared schema and program
  fixtures.
- **No new runtime dependencies.** This package depends on `qprogram` and
  nothing else, and it should stay that way. Anything a single operation
  needs belongs behind an optional extra, if anywhere.

## Commit messages

Short, imperative, explanatory. The body matters more than the title:
explain why, not what. `git log` is a good template.

## License and attribution

Apache License 2.0. The full text is in `LICENSE` at the repository root,
and every source file carries the matching header. By opening a PR you agree
to license your contribution under the same terms.

## Where to ask

- **Bugs and feature requests.** Open an issue with a minimal program that
  reproduces the problem, and the `.qp` text for it.
- **Design questions.** Open an issue naming the affected code, the behavior
  you expect, and the page that documents it.
- **Something that belongs in the core language.** Open it against
  <https://github.com/qilimanjaro-tech/qprogram> instead. If you are not
  sure which side a change belongs on, say so in the issue; the boundary is
  the interesting part of the question.
