"""python -m sp15_oasis            start the MCP server on stdio
python -m sp15_oasis sync      download OASIS into data/sp15.sqlite
python -m sp15_oasis status
python -m sp15_oasis export
"""

from __future__ import annotations

import sys

_COMMANDS = {"sync", "status", "export", "import-csv"}


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in _COMMANDS:
        from .cli import main as cli_main

        raise SystemExit(cli_main())
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        del sys.argv[1]
    # MCP clients speak JSON-RPC on stdout. Anything we print has to stay off it.
    from .server import mcp

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
