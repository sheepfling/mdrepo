# Validation record

Validated on 2026-08-02 with CPython 3.14.6 on Windows.

## Completed

- `python -m compileall -q src scripts tests`
- 33 pytest tests passing
- 80% branch-aware coverage reported during the validation run
- Pyright strict-mode check: zero errors and zero warnings
- Ruff lint check: clean
- Marker-free Ruff formatting compatibility check: clean
- Scope Markers check: 31 files clean
- rumdl check: clean
- Pre-commit configuration and published hook manifest validation: clean
- Pre-commit hook execution against `README.md`: clean
- Project self-check with orphan analysis enabled: zero findings
- Wheel and source-distribution construction through `setuptools.build_meta` in a temporary output
  directory
- `twine check` validation for both built distributions
- Wheel metadata inspection: only `markdown-it-py`, `pathspec`, and Pydantic runtime dependencies
- Clean source-distribution extraction followed by all 28 tests and a repository self-check
- Wheel installation into an isolated target and execution of `python -m mdrepo --version`
- Installed-wheel self-check against the source tree: zero findings
- CRLF-preserving safe-fix test
- Responsibility documentation linked into the repository graph and covered by the self-check
- Full-directory checks report unused structured exceptions while partial file checks remain scoped
- Repository URL ports are validated and included in same-repository identity matching
- Home-relative Markdown destinations are rejected as machine-local paths
- The formatter regression check is read-only and verifies marker-free temporary source copies
- Complete local `python scripts/ci.py` pass using the development environment

## Not completed in this environment

- The full GitHub Actions matrix has not been observed from this workspace: Ubuntu and CPython 3.12
  and 3.13 still require the hosted CI run.
- A real TestPyPI publication has not been attempted. The release workflow still requires the
  configured PyPI trusted publisher and protected environment.
