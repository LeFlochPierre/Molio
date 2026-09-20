"""Exercise the real MCP stdio transport from an existing agent or terminal."""
import asyncio
import json
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(command=str(root/'.venv-alchemi-agent/bin/python'),
                                  args=['-m', 'cyp_pipeline.agent_tools', 'mcp'], cwd=str(root))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if len(sys.argv) == 1:
                result = await session.list_tools()
                print(json.dumps({'tools': [tool.name for tool in result.tools]}, indent=2))
            else:
                result = await session.call_tool(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {})
                if result.isError:
                    print(result.model_dump_json(indent=2))
                    raise SystemExit(1)
                if result.structuredContent is not None:
                    print(json.dumps(result.structuredContent, indent=2))
                else:
                    for item in result.content:
                        if item.type == 'text':
                            print(item.text)


asyncio.run(main())
