"""Integration tests for the DNS MCP server."""

import pytest
from dns_mcp_server.resolver import DNSResolver


@pytest.mark.asyncio
async def test_full_lookup_flow():
    """Test complete lookup flow with multiple record types."""
    resolver = DNSResolver()

    # Test A record
    result = await resolver.lookup("google.com", ["A", "AAAA"])
    assert result.success is True
    assert len(result.records) > 0

    # Test MX record
    result = await resolver.lookup("google.com", ["MX"])
    assert result.success is True
    assert any(r.type == "MX" for r in result.records)


@pytest.mark.asyncio
async def test_custom_resolver():
    """Test using a custom DNS resolver."""
    resolver = DNSResolver()

    # Use Google's public DNS
    result = await resolver.lookup("example.com", ["A"], resolver_ip="8.8.8.8")
    assert result.success is True
    assert result.resolver == "8.8.8.8"


@pytest.mark.asyncio
async def test_bulk_operations_concurrent():
    """Test that bulk operations run concurrently."""
    resolver = DNSResolver()

    domains = ["google.com", "cloudflare.com", "github.com", "example.com"]
    queries = [{"domain": d, "record_types": ["A"]} for d in domains]

    results = await resolver.bulk_lookup(queries)

    assert len(results) == 4
    assert all(r.success for r in results)
