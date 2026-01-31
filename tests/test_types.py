"""Tests for response types."""

from dns_mcp_server.types import (
    DNSRecord,
    LookupResponse,
    ReverseLookupResponse,
    ErrorResponse,
)


def test_dns_record_creation():
    record = DNSRecord(type="A", value="93.184.216.34", ttl=3600)
    assert record.type == "A"
    assert record.value == "93.184.216.34"
    assert record.ttl == 3600


def test_dns_record_with_priority():
    record = DNSRecord(type="MX", value="mail.example.com", ttl=3600, priority=10)
    assert record.priority == 10


def test_lookup_response_creation():
    record = DNSRecord(type="A", value="93.184.216.34", ttl=3600)
    response = LookupResponse(
        domain="example.com",
        resolver="8.8.8.8",
        records=[record],
        query_time_ms=45,
    )
    assert response.domain == "example.com"
    assert response.success is True
    assert len(response.records) == 1


def test_reverse_lookup_response_creation():
    response = ReverseLookupResponse(
        ip="8.8.8.8",
        hostname="dns.google",
        ttl=3600,
        query_time_ms=32,
    )
    assert response.ip == "8.8.8.8"
    assert response.hostname == "dns.google"
    assert response.success is True


def test_error_response_creation():
    response = ErrorResponse(
        domain="nonexistent.invalid",
        error="NXDOMAIN",
        retries_attempted=3,
    )
    assert response.success is False
    assert response.error == "NXDOMAIN"
