"""Tests for MCP server."""

import pytest
from mcp.types import ListToolsRequest

from dns_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_server_has_tools():
    """Test that server exposes expected tools."""
    server = create_server()

    # Get the list_tools handler from the registered request handlers
    handler = server.request_handlers.get(ListToolsRequest)
    assert handler is not None, "list_tools handler should be registered"

    # Call the handler to get the tools
    # The handler function is stored internally, we need to call it
    # Looking at the request_handlers, we find the underlying function
    result = await handler(None)

    tool_names = [tool.name for tool in result.root.tools]

    assert "dns_lookup" in tool_names
    assert "dns_reverse" in tool_names
    assert "dns_bulk" in tool_names
    assert "dns_reverse_bulk" in tool_names


@pytest.mark.asyncio
async def test_dns_lookup_tool_schema():
    """Test that dns_lookup tool has correct schema."""
    server = create_server()

    handler = server.request_handlers.get(ListToolsRequest)
    result = await handler(None)

    dns_lookup_tool = next((t for t in result.root.tools if t.name == "dns_lookup"), None)
    assert dns_lookup_tool is not None

    # Verify required properties
    assert "domain" in dns_lookup_tool.inputSchema["properties"]
    assert "domain" in dns_lookup_tool.inputSchema["required"]

    # Verify optional properties
    assert "record_types" in dns_lookup_tool.inputSchema["properties"]
    assert "resolver" in dns_lookup_tool.inputSchema["properties"]


@pytest.mark.asyncio
async def test_dns_reverse_tool_schema():
    """Test that dns_reverse tool has correct schema."""
    server = create_server()

    handler = server.request_handlers.get(ListToolsRequest)
    result = await handler(None)

    dns_reverse_tool = next((t for t in result.root.tools if t.name == "dns_reverse"), None)
    assert dns_reverse_tool is not None

    # Verify required properties
    assert "ip" in dns_reverse_tool.inputSchema["properties"]
    assert "ip" in dns_reverse_tool.inputSchema["required"]


@pytest.mark.asyncio
async def test_dns_bulk_tool_schema():
    """Test that dns_bulk tool has correct schema."""
    server = create_server()

    handler = server.request_handlers.get(ListToolsRequest)
    result = await handler(None)

    dns_bulk_tool = next((t for t in result.root.tools if t.name == "dns_bulk"), None)
    assert dns_bulk_tool is not None

    # Verify required properties
    assert "queries" in dns_bulk_tool.inputSchema["properties"]
    assert "queries" in dns_bulk_tool.inputSchema["required"]


@pytest.mark.asyncio
async def test_dns_reverse_bulk_tool_schema():
    """Test that dns_reverse_bulk tool has correct schema."""
    server = create_server()

    handler = server.request_handlers.get(ListToolsRequest)
    result = await handler(None)

    dns_reverse_bulk_tool = next((t for t in result.root.tools if t.name == "dns_reverse_bulk"), None)
    assert dns_reverse_bulk_tool is not None

    # Verify required properties
    assert "ips" in dns_reverse_bulk_tool.inputSchema["properties"]
    assert "ips" in dns_reverse_bulk_tool.inputSchema["required"]
