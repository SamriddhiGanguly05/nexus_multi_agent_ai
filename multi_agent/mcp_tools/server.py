# mcp_tools/server.py
# Run this as a separate process: python -m mcp_tools.server
from mcp_tools.tools import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")