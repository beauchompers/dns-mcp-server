"""Tests for DNS resolver."""

import pytest
from dns_mcp_server.resolver import (
    DNSResolver,
    validate_domain,
    validate_resolver_ip,
    validate_record_types,
    MAX_BULK_QUERIES,
    ALLOWED_RECORD_TYPES,
)
from dns_mcp_server.types import LookupResponse, ReverseLookupResponse, ErrorResponse


# Tests for validation functions


def test_validate_domain_valid():
    """Test valid domain names pass validation."""
    valid_domains = [
        "example.com",
        "sub.example.com",
        "a.b.c.example.com",
        "example123.com",
        "123.com",
        "a-b-c.example.com",
        "example.co.uk",
    ]
    for domain in valid_domains:
        is_valid, error = validate_domain(domain)
        assert is_valid, f"Domain '{domain}' should be valid: {error}"


def test_validate_domain_invalid():
    """Test invalid domain names fail validation."""
    invalid_domains = [
        ("", "empty"),
        ("-example.com", "starts with hyphen"),
        ("example-.com", "ends with hyphen"),
        ("exam_ple.com", "contains underscore"),
        ("a" * 64 + ".com", "label too long"),
        ("example..com", "empty label"),
    ]
    for domain, reason in invalid_domains:
        is_valid, error = validate_domain(domain)
        assert not is_valid, f"Domain '{domain}' should be invalid ({reason})"


def test_validate_resolver_ip_valid():
    """Test valid public resolver IPs pass validation."""
    valid_ips = [
        "8.8.8.8",
        "1.1.1.1",
        "208.67.222.222",
        "2001:4860:4860::8888",
    ]
    for ip in valid_ips:
        is_valid, error = validate_resolver_ip(ip)
        assert is_valid, f"IP '{ip}' should be valid: {error}"


def test_validate_resolver_ip_blocks_private():
    """Test private IP addresses are blocked."""
    private_ips = [
        ("127.0.0.1", "loopback"),
        ("10.0.0.1", "private class A"),
        ("172.16.0.1", "private class B"),
        ("192.168.1.1", "private class C"),
        ("169.254.1.1", "link-local"),
        ("::1", "IPv6 loopback"),
        ("fe80::1", "IPv6 link-local"),
    ]
    for ip, reason in private_ips:
        is_valid, error = validate_resolver_ip(ip)
        assert not is_valid, f"IP '{ip}' should be blocked ({reason})"


def test_validate_record_types_valid():
    """Test valid record types pass validation."""
    is_valid, error = validate_record_types(["A", "AAAA", "MX", "TXT"])
    assert is_valid, f"Valid record types should pass: {error}"


def test_validate_record_types_invalid():
    """Test invalid record types fail validation."""
    is_valid, error = validate_record_types(["A", "INVALID", "FAKE"])
    assert not is_valid
    assert "INVALID" in error
    assert "FAKE" in error


def test_validate_record_types_empty():
    """Test empty record types list fails validation."""
    is_valid, error = validate_record_types([])
    assert not is_valid
    assert "At least one" in error


@pytest.mark.asyncio
async def test_lookup_a_record():
    """Test basic A record lookup."""
    resolver = DNSResolver()
    result = await resolver.lookup("google.com", ["A"])

    assert isinstance(result, LookupResponse)
    assert result.domain == "google.com"
    assert result.success is True
    assert len(result.records) > 0
    assert result.records[0].type == "A"


@pytest.mark.asyncio
async def test_lookup_nonexistent_domain():
    """Test lookup of nonexistent domain returns error."""
    resolver = DNSResolver()
    result = await resolver.lookup("this-domain-definitely-does-not-exist.invalid", ["A"])

    assert isinstance(result, ErrorResponse)
    assert result.success is False
    assert "NXDOMAIN" in result.error


@pytest.mark.asyncio
async def test_reverse_lookup():
    """Test reverse DNS lookup."""
    resolver = DNSResolver()
    result = await resolver.reverse_lookup("8.8.8.8")

    assert isinstance(result, ReverseLookupResponse)
    assert result.ip == "8.8.8.8"
    assert result.success is True
    assert result.hostname is not None


@pytest.mark.asyncio
async def test_reverse_lookup_ipv6():
    """Test reverse DNS lookup for IPv6."""
    resolver = DNSResolver()
    # Google's public DNS IPv6
    result = await resolver.reverse_lookup("2001:4860:4860::8888")

    assert isinstance(result, (ReverseLookupResponse, ErrorResponse))
    if isinstance(result, ReverseLookupResponse):
        assert result.success is True


@pytest.mark.asyncio
async def test_bulk_lookup():
    """Test bulk DNS lookup."""
    resolver = DNSResolver()
    queries = [
        {"domain": "google.com", "record_types": ["A"]},
        {"domain": "cloudflare.com", "record_types": ["A"]},
    ]
    results = await resolver.bulk_lookup(queries)

    assert len(results) == 2
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_bulk_lookup_partial_failure():
    """Test bulk lookup with some failures."""
    resolver = DNSResolver()
    queries = [
        {"domain": "google.com", "record_types": ["A"]},
        {"domain": "nonexistent.invalid", "record_types": ["A"]},
    ]
    results = await resolver.bulk_lookup(queries)

    assert len(results) == 2
    # First should succeed, second should fail
    assert results[0].success is True
    assert results[1].success is False


@pytest.mark.asyncio
async def test_bulk_reverse_lookup():
    """Test bulk reverse DNS lookup."""
    resolver = DNSResolver()
    ips = ["8.8.8.8", "1.1.1.1"]
    results = await resolver.bulk_reverse_lookup(ips)

    assert len(results) == 2


# Tests for security validations in resolver methods


@pytest.mark.asyncio
async def test_lookup_rejects_invalid_domain():
    """Test lookup rejects invalid domain names."""
    resolver = DNSResolver()
    result = await resolver.lookup("-invalid.com", ["A"])

    assert isinstance(result, ErrorResponse)
    assert result.success is False
    assert "Invalid" in result.error


@pytest.mark.asyncio
async def test_lookup_rejects_invalid_record_types():
    """Test lookup rejects invalid record types."""
    resolver = DNSResolver()
    result = await resolver.lookup("example.com", ["INVALID"])

    assert isinstance(result, ErrorResponse)
    assert result.success is False
    assert "Invalid record types" in result.error


@pytest.mark.asyncio
async def test_lookup_rejects_private_resolver():
    """Test lookup rejects private resolver IPs."""
    resolver = DNSResolver()
    result = await resolver.lookup("example.com", ["A"], resolver_ip="192.168.1.1")

    assert isinstance(result, ErrorResponse)
    assert result.success is False
    assert "Private" in result.error


@pytest.mark.asyncio
async def test_bulk_lookup_limit():
    """Test bulk lookup enforces query limit."""
    resolver = DNSResolver()
    # Create queries exceeding the limit
    queries = [{"domain": f"example{i}.com", "record_types": ["A"]} for i in range(MAX_BULK_QUERIES + 1)]
    result = await resolver.bulk_lookup(queries)

    assert isinstance(result, ErrorResponse)
    assert result.success is False
    assert "limit exceeded" in result.error


@pytest.mark.asyncio
async def test_bulk_reverse_lookup_limit():
    """Test bulk reverse lookup enforces query limit."""
    resolver = DNSResolver()
    # Create IPs exceeding the limit
    ips = [f"8.8.{i // 256}.{i % 256}" for i in range(MAX_BULK_QUERIES + 1)]
    result = await resolver.bulk_reverse_lookup(ips)

    assert isinstance(result, ErrorResponse)
    assert result.success is False
    assert "limit exceeded" in result.error
