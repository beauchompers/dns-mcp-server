"""Response type definitions for DNS MCP Server."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DNSRecord:
    """A single DNS record."""

    type: str
    value: str
    ttl: int
    priority: Optional[int] = None
    # DNSSEC fields
    algorithm: Optional[int] = None
    key_tag: Optional[int] = None
    signature: Optional[str] = None
    signer: Optional[str] = None


@dataclass
class LookupResponse:
    """Response for a successful DNS lookup."""

    domain: str
    records: list[DNSRecord]
    query_time_ms: int
    resolver: Optional[str] = None
    success: bool = True


@dataclass
class ReverseLookupResponse:
    """Response for a successful reverse DNS lookup."""

    ip: str
    hostname: str
    ttl: int
    query_time_ms: int
    resolver: Optional[str] = None
    success: bool = True


@dataclass
class ErrorResponse:
    """Response for a failed DNS query."""

    error: str
    retries_attempted: int
    domain: Optional[str] = None
    ip: Optional[str] = None
    success: bool = False
