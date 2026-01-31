"""DNS resolver with retry logic."""

import asyncio
import ipaddress
import re
import time
from typing import Optional, Union

import dns.asyncresolver
import dns.resolver
import dns.rdatatype
import dns.reversename
from dns.exception import DNSException

from dns_mcp_server.types import (
    DNSRecord,
    LookupResponse,
    ReverseLookupResponse,
    ErrorResponse,
)

# Allowed DNS record types
ALLOWED_RECORD_TYPES = frozenset({
    "A", "AAAA", "MX", "TXT", "NS", "SOA", "CNAME", "SRV", "CAA",
    "PTR", "DNSKEY", "DS", "RRSIG", "NSEC", "NSEC3",
})

# Maximum queries per bulk request
MAX_BULK_QUERIES = 100

# Maximum concurrent DNS queries
MAX_CONCURRENT_QUERIES = 20

# Domain validation pattern (RFC 1035 compliant)
DOMAIN_LABEL_PATTERN = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$')


def validate_domain(domain: str) -> tuple[bool, str]:
    """Validate a domain name.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not domain:
        return False, "Domain name cannot be empty"

    # Check total length
    if len(domain) > 253:
        return False, "Domain name exceeds 253 characters"

    # Remove trailing dot if present
    if domain.endswith('.'):
        domain = domain[:-1]

    # Split into labels and validate each
    labels = domain.split('.')
    if not labels or labels == ['']:
        return False, "Invalid domain name format"

    for label in labels:
        if not label:
            return False, "Empty label in domain name"
        if len(label) > 63:
            return False, f"Label '{label}' exceeds 63 characters"
        if not DOMAIN_LABEL_PATTERN.match(label):
            return False, f"Invalid characters in label '{label}'"

    return True, ""


def validate_resolver_ip(ip: str) -> tuple[bool, str]:
    """Validate a resolver IP address.

    Blocks private and reserved IP ranges for security.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False, f"Invalid IP address format: {ip}"

    # Block private and reserved ranges
    if addr.is_private:
        return False, f"Private IP addresses not allowed: {ip}"
    if addr.is_loopback:
        return False, f"Loopback addresses not allowed: {ip}"
    if addr.is_link_local:
        return False, f"Link-local addresses not allowed: {ip}"
    if addr.is_multicast:
        return False, f"Multicast addresses not allowed: {ip}"
    if addr.is_reserved:
        return False, f"Reserved addresses not allowed: {ip}"

    return True, ""


def validate_record_types(record_types: list[str]) -> tuple[bool, str]:
    """Validate DNS record types against allowlist.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not record_types:
        return False, "At least one record type is required"

    invalid = set(record_types) - ALLOWED_RECORD_TYPES
    if invalid:
        return False, f"Invalid record types: {', '.join(sorted(invalid))}. Allowed: {', '.join(sorted(ALLOWED_RECORD_TYPES))}"

    return True, ""


class DNSResolver:
    """DNS resolver with configurable resolver and retry logic."""

    def __init__(
        self,
        default_resolver: Optional[str] = None,
        timeout: float = 5.0,
        max_retries: int = 3,
    ):
        self.default_resolver = default_resolver
        self.timeout = timeout
        self.max_retries = max_retries
        self._backoff_times = [0.5, 1.0, 2.0]
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)

    def _create_resolver(
        self, resolver_ip: Optional[str] = None
    ) -> Union[dns.asyncresolver.Resolver, ErrorResponse]:
        """Create a resolver instance with optional custom nameserver.

        Returns:
            Resolver on success, ErrorResponse if resolver_ip validation fails
        """
        # Validate custom resolver IP if provided
        if resolver_ip:
            is_valid, error = validate_resolver_ip(resolver_ip)
            if not is_valid:
                return ErrorResponse(
                    domain="",
                    error=error,
                    retries_attempted=0,
                )

        res = dns.asyncresolver.Resolver()
        res.lifetime = self.timeout

        nameserver = resolver_ip or self.default_resolver
        if nameserver:
            res.nameservers = [nameserver]

        return res

    def _should_retry(self, exception: Exception) -> bool:
        """Determine if an exception is retryable."""
        # Don't retry definitive failures
        non_retryable = (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
        )
        return not isinstance(exception, non_retryable)

    def _parse_record(self, rdata, rdtype: str) -> DNSRecord:
        """Parse a DNS record into our response type."""
        record = DNSRecord(
            type=rdtype,
            value=str(rdata),
            ttl=0,  # Will be set from rrset
        )

        # Handle MX priority
        if rdtype == "MX":
            record.priority = rdata.preference
            record.value = str(rdata.exchange)

        # Handle SRV
        if rdtype == "SRV":
            record.priority = rdata.priority
            record.value = f"{rdata.target}:{rdata.port}"

        # Handle DNSSEC records
        if rdtype == "DNSKEY":
            record.algorithm = rdata.algorithm
            record.key_tag = dns.dnssec.key_id(rdata)

        if rdtype == "RRSIG":
            record.algorithm = rdata.algorithm
            record.signer = str(rdata.signer)

        return record

    async def lookup(
        self,
        domain: str,
        record_types: list[str],
        resolver_ip: Optional[str] = None,
    ) -> Union[LookupResponse, ErrorResponse]:
        """
        Look up DNS records for a domain.

        Args:
            domain: Domain name to query
            record_types: List of record types (A, AAAA, MX, etc.)
            resolver_ip: Optional resolver IP to use

        Returns:
            LookupResponse on success, ErrorResponse on failure
        """
        # Validate domain
        is_valid, error = validate_domain(domain)
        if not is_valid:
            return ErrorResponse(
                domain=domain,
                error=error,
                retries_attempted=0,
            )

        # Validate record types
        is_valid, error = validate_record_types(record_types)
        if not is_valid:
            return ErrorResponse(
                domain=domain,
                error=error,
                retries_attempted=0,
            )

        # Create resolver (validates resolver_ip if provided)
        resolver = self._create_resolver(resolver_ip)
        if isinstance(resolver, ErrorResponse):
            resolver.domain = domain
            return resolver

        records: list[DNSRecord] = []
        start_time = time.monotonic()
        last_error: Optional[Exception] = None

        async with self._semaphore:
            for rdtype in record_types:
                for attempt in range(self.max_retries):
                    try:
                        answer = await resolver.resolve(domain, rdtype)
                        for rdata in answer:
                            record = self._parse_record(rdata, rdtype)
                            record.ttl = answer.rrset.ttl
                            records.append(record)
                        break  # Success, move to next record type

                    except dns.resolver.NXDOMAIN:
                        return ErrorResponse(
                            domain=domain,
                            error="NXDOMAIN: Domain does not exist",
                            retries_attempted=attempt + 1,
                        )

                    except dns.resolver.NoAnswer:
                        # No records of this type, continue to next type
                        break

                    except DNSException as e:
                        last_error = e
                        if not self._should_retry(e) or attempt == self.max_retries - 1:
                            break
                        await asyncio.sleep(self._backoff_times[min(attempt, len(self._backoff_times) - 1)])

            query_time = int((time.monotonic() - start_time) * 1000)

            if not records and last_error:
                return ErrorResponse(
                    domain=domain,
                    error=str(last_error),
                    retries_attempted=self.max_retries,
                )

            return LookupResponse(
                domain=domain,
                resolver=resolver_ip or self.default_resolver,
                records=records,
                query_time_ms=query_time,
            )

    async def reverse_lookup(
        self,
        ip: str,
        resolver_ip: Optional[str] = None,
    ) -> Union[ReverseLookupResponse, ErrorResponse]:
        """
        Perform reverse DNS lookup for an IP address.

        Args:
            ip: IPv4 or IPv6 address
            resolver_ip: Optional resolver IP to use

        Returns:
            ReverseLookupResponse on success, ErrorResponse on failure
        """
        # Create resolver (validates resolver_ip if provided)
        resolver = self._create_resolver(resolver_ip)
        if isinstance(resolver, ErrorResponse):
            resolver.ip = ip
            return resolver

        start_time = time.monotonic()

        try:
            rev_name = dns.reversename.from_address(ip)
        except Exception as e:
            return ErrorResponse(
                ip=ip,
                error=f"Invalid IP address: {e}",
                retries_attempted=0,
            )

        async with self._semaphore:
            for attempt in range(self.max_retries):
                try:
                    answer = await resolver.resolve(rev_name, "PTR")
                    hostname = str(answer[0]).rstrip(".")
                    query_time = int((time.monotonic() - start_time) * 1000)

                    return ReverseLookupResponse(
                        ip=ip,
                        hostname=hostname,
                        ttl=answer.rrset.ttl,
                        query_time_ms=query_time,
                        resolver=resolver_ip or self.default_resolver,
                    )

                except dns.resolver.NXDOMAIN:
                    return ErrorResponse(
                        ip=ip,
                        error="NXDOMAIN: No PTR record found",
                        retries_attempted=attempt + 1,
                    )

                except DNSException as e:
                    if not self._should_retry(e) or attempt == self.max_retries - 1:
                        query_time = int((time.monotonic() - start_time) * 1000)
                        return ErrorResponse(
                            ip=ip,
                            error=str(e),
                            retries_attempted=attempt + 1,
                        )
                    await asyncio.sleep(self._backoff_times[min(attempt, len(self._backoff_times) - 1)])

            return ErrorResponse(
                ip=ip,
                error="Max retries exceeded",
                retries_attempted=self.max_retries,
            )

    async def bulk_lookup(
        self,
        queries: list[dict],
        resolver_ip: Optional[str] = None,
    ) -> Union[list[Union[LookupResponse, ErrorResponse]], ErrorResponse]:
        """
        Perform bulk DNS lookups.

        Args:
            queries: List of {"domain": str, "record_types": list[str]}
            resolver_ip: Optional resolver IP to use for all queries

        Returns:
            List of responses (LookupResponse or ErrorResponse), or ErrorResponse if limit exceeded
        """
        if len(queries) > MAX_BULK_QUERIES:
            return ErrorResponse(
                domain="",
                error=f"Bulk query limit exceeded: {len(queries)} queries requested, maximum is {MAX_BULK_QUERIES}",
                retries_attempted=0,
            )

        tasks = [
            self.lookup(
                q["domain"],
                q.get("record_types", ["A"]),
                resolver_ip,
            )
            for q in queries
        ]
        return await asyncio.gather(*tasks)

    async def bulk_reverse_lookup(
        self,
        ips: list[str],
        resolver_ip: Optional[str] = None,
    ) -> Union[list[Union[ReverseLookupResponse, ErrorResponse]], ErrorResponse]:
        """
        Perform bulk reverse DNS lookups.

        Args:
            ips: List of IPv4 or IPv6 addresses
            resolver_ip: Optional resolver IP to use for all queries

        Returns:
            List of responses (ReverseLookupResponse or ErrorResponse), or ErrorResponse if limit exceeded
        """
        if len(ips) > MAX_BULK_QUERIES:
            return ErrorResponse(
                ip="",
                error=f"Bulk query limit exceeded: {len(ips)} queries requested, maximum is {MAX_BULK_QUERIES}",
                retries_attempted=0,
            )

        tasks = [self.reverse_lookup(ip, resolver_ip) for ip in ips]
        return await asyncio.gather(*tasks)
