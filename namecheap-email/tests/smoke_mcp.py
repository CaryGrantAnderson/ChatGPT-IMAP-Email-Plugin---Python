"""End-to-end SDK client/server handshake without loading mailbox credentials."""
import asyncio
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable,
        args=["-B", str(Path(__file__).resolve().parents[1] / "scripts" / "server.py")])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 4
            # Invalid arguments are rejected locally, before any connection or vault access.
            response = await session.call_tool("read_message", {"uid": "1:*", "uid_validity": "123"})
            assert "Use one UID" in str(response)
            print("PASS: MCP initialize, tool discovery, and safe tool invocation.")


if __name__ == "__main__":
    asyncio.run(main())
