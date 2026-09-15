# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MCP server exposing Excel manipulation as tools, built on `openpyxl` (no Microsoft Excel required) and the `mcp` Python SDK's `FastMCP`. Published to PyPI as `excel-mcp-server`; users typically run it via `uvx excel-mcp-server <transport>`.

## Commands

The project uses `uv` with a committed `uv.lock`. `pytest` is **not** a dependency — tests are stdlib `unittest`.

```bash
uv sync                                    # install deps into .venv
uv run python -m unittest discover -s tests -v          # full suite
uv run python -m unittest tests.test_sandbox_paths.TestGetExcelPathSandbox.test_remote_blocks_traversal   # single test

uv run excel-mcp-server stdio              # run locally (stdio)
uv run excel-mcp-server streamable-http    # run locally (HTTP, port 8017)

hatch build                                # build sdist/wheel (what CI publishes)
```

Docker (streamable HTTP only):

```bash
docker compose up -d --build   # serves http://localhost:8017/mcp
docker compose logs -f
```

There is no linter or formatter configured, and no test/lint CI. `.github/workflows/publish.yml` only builds with `hatch` and publishes to PyPI on GitHub release.

## Architecture

**Two layers, deliberately separated:**

- `src/excel_mcp/server.py` — the *only* file with `@mcp.tool` decorators. Every tool is a thin wrapper: resolve the path, delegate, translate errors. It holds the `FastMCP` instance and the three `run_*` transport entrypoints.
- Everything else (`workbook.py`, `sheet.py`, `data.py`, `formatting.py`, `calculations.py`, `chart.py`, `pivot.py`, `tables.py`, `validation.py`, `cell_utils.py`, `cell_validation.py`) — pure `openpyxl` logic that knows nothing about MCP. These take **absolute paths** and raise typed exceptions.

When adding a tool: put the real work in the relevant impl module, then add a wrapper in `server.py`, and register it in `manifest.json` (the MCPB bundle lists tools separately) and `TOOLS.md`.

**Impl modules are imported *inside* tool function bodies**, not at module top level, e.g. `from excel_mcp.workbook import create_workbook as create_workbook_impl`. Top-level imports in `server.py` use `_impl` aliases for the same reason — to keep the tool namespace from colliding with the impl names. Follow the existing pattern rather than hoisting imports.

**Error convention in tool wrappers:** catch the typed exceptions from `exceptions.py` (all subclass `ExcelMCPError`) and `return f"Error: {str(e)}"` as a normal string result; let anything unexpected propagate after `logger.error(...)`. The two paths are not equivalent — a returned string is a successful tool call the model can read and recover from, a raised exception becomes an MCP protocol error.

**`src/excel_mcp/` has no `__init__.py`** (implicit namespace package). Use the `excel-mcp-server` console script or `excel_mcp.__main__:app`; don't assume `python -m excel_mcp` works.

### Path handling — the central security boundary

`get_excel_path()` in `server.py` is dual-mode, driven by the module-global `EXCEL_FILES_PATH`:

- **stdio** (`EXCEL_FILES_PATH is None`): the client sends a path per call, and only **absolute** paths are accepted.
- **SSE / streamable HTTP**: `run_sse()` / `run_streamable_http()` set `EXCEL_FILES_PATH` from the env (default `./excel_files`). Now only **relative** paths are accepted, resolved under that root via `realpath` + `commonpath`; absolute paths, `..` traversal and NUL bytes are rejected.

This inversion is intentional — a remote server must not let callers reach arbitrary files. `tests/test_sandbox_paths.py` is the regression suite for exactly this, and is the one thing to keep green when touching path logic.

### Transports

`__main__.py` is a Typer app with three commands: `stdio`, `sse` (deprecated), `streamable-http`. Host/port come from `FASTMCP_HOST` / `FASTMCP_PORT` (default `0.0.0.0:8017`), read at `FastMCP` construction time — so they must be set in the environment before import, not mutated later. The HTTP endpoint is `/mcp` (the server 307-redirects to `/mcp/`).

**Logging:** `server.py` writes to `excel-mcp.log` resolved relative to the *package location*, not the working directory. In stdio mode nothing may be written to stdout, which is why there is a `FileHandler` and no `StreamHandler`. That path assumption is why the Docker image has to make `/app` writable by the non-root user.

## Docs to keep in sync

`TOOLS.md` (per-tool reference), `manifest.json` (MCPB bundle: version, tool list), `pyproject.toml` version, and the README's transport sections all describe the same surface. A tool signature change usually touches several of them.
