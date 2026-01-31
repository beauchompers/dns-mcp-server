"""MCP server for DNS lookups."""

import asyncio
import json
import logging
import os
from dataclasses import asdict
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from dns_mcp_server.resolver import DNSResolver
from dns_mcp_server.types import LookupResponse, ReverseLookupResponse

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default configuration from environment
DEFAULT_TIMEOUT = float(os.getenv("DNS_TIMEOUT", "5"))
DEFAULT_RETRIES = int(os.getenv("DNS_RETRIES", "3"))
DEFAULT_RESOLVER = os.getenv("DEFAULT_RESOLVER")


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("dns-mcp-server")
    resolver = DNSResolver(
        default_resolver=DEFAULT_RESOLVER,
        timeout=DEFAULT_TIMEOUT,
        max_retries=DEFAULT_RETRIES,
    )

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available DNS tools."""
        return [
            Tool(
                name="dns_lookup",
                description="Query DNS records for a domain. Supports all record types including DNSSEC.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain name to query",
                        },
                        "record_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Record types to query (default: ['A']). Examples: A, AAAA, MX, TXT, NS, SOA, CNAME, SRV, CAA, DNSKEY, DS, RRSIG",
                            "default": ["A"],
                        },
                        "resolver": {
                            "type": "string",
                            "description": "DNS resolver IP to use (optional, defaults to system resolver)",
                        },
                    },
                    "required": ["domain"],
                },
            ),
            Tool(
                name="dns_reverse",
                description="Reverse DNS lookup (PTR) for an IP address.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ip": {
                            "type": "string",
                            "description": "IPv4 or IPv6 address",
                        },
                        "resolver": {
                            "type": "string",
                            "description": "DNS resolver IP to use (optional)",
                        },
                    },
                    "required": ["ip"],
                },
            ),
            Tool(
                name="dns_bulk",
                description="Query DNS records for multiple domains in one call.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "domain": {"type": "string"},
                                    "record_types": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["domain"],
                            },
                            "description": "List of queries with domain and optional record_types",
                        },
                        "resolver": {
                            "type": "string",
                            "description": "DNS resolver IP to use for all queries (optional)",
                        },
                    },
                    "required": ["queries"],
                },
            ),
            Tool(
                name="dns_reverse_bulk",
                description="Reverse DNS lookup for multiple IP addresses.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ips": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of IPv4 or IPv6 addresses",
                        },
                        "resolver": {
                            "type": "string",
                            "description": "DNS resolver IP to use for all queries (optional)",
                        },
                    },
                    "required": ["ips"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        logger.info(f"Tool call: {name} with arguments: {arguments}")

        try:
            if name == "dns_lookup":
                result = await resolver.lookup(
                    domain=arguments["domain"],
                    record_types=arguments.get("record_types", ["A"]),
                    resolver_ip=arguments.get("resolver"),
                )

            elif name == "dns_reverse":
                result = await resolver.reverse_lookup(
                    ip=arguments["ip"],
                    resolver_ip=arguments.get("resolver"),
                )

            elif name == "dns_bulk":
                results = await resolver.bulk_lookup(
                    queries=arguments["queries"],
                    resolver_ip=arguments.get("resolver"),
                )
                result = [asdict(r) for r in results]
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "dns_reverse_bulk":
                results = await resolver.bulk_reverse_lookup(
                    ips=arguments["ips"],
                    resolver_ip=arguments.get("resolver"),
                )
                result = [asdict(r) for r in results]
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                error_response = {"error": f"Unknown tool: {name}", "success": False}
                return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

            # Convert single result to JSON
            return [TextContent(type="text", text=json.dumps(asdict(result), indent=2))]

        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            error_response = {"error": str(e), "success": False}
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

    return server


def main():
    """Run the MCP server."""
    server = create_server()

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
