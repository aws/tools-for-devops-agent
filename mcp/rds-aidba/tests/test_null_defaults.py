import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_none_default_params_accept_null():
    """A parameter that defaults to None must accept an explicit null.

    Some MCP clients send every optional argument with its advertised
    default (null). If the schema type excludes null, the call fails
    validation before the tool runs.
    """
    from fastmcp import Client
    from server import mcp

    async def schemas():
        async with Client(mcp) as client:
            return {t.name: t.inputSchema for t in await client.list_tools()}

    offenders = []
    for tool, schema in asyncio.run(schemas()).items():
        for name, prop in schema.get("properties", {}).items():
            if "default" not in prop or prop["default"] is not None:
                continue
            types = [prop.get("type")] + [o.get("type") for o in prop.get("anyOf", [])]
            if "null" not in types:
                offenders.append(f"{tool}.{name}")
    assert offenders == []
