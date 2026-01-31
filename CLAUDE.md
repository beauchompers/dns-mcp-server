# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest                          # all tests
pytest tests/test_resolver.py   # single file
pytest -k "test_lookup"         # by name pattern

# Run server locally
dns-mcp-server                  # stdio mode (for MCP clients)
dns-mcp-server-http             # HTTP mode (port 8000)

# Docker deployment
docker compose up -d            # start nginx + mcp-server (certs auto-generate)
docker compose down             # stop
docker compose logs -f          # view logs
```

## Architecture

This is an MCP (Model Context Protocol) server that exposes DNS lookup capabilities as tools.

### Core Components

**server.py** - MCP server with tool definitions
- `create_server()` returns an MCP `Server` instance
- Defines 4 tools: `dns_lookup`, `dns_reverse`, `dns_bulk`, `dns_reverse_bulk`
- Uses `@server.list_tools()` and `@server.call_tool()` decorators

**http_server.py** - HTTP transport layer
- Wraps MCP server with `StreamableHTTPSessionManager` for HTTP access
- Uses Starlette ASGI with uvicorn
- Exposes `/mcp` endpoint for MCP protocol, `/health` for health checks

**resolver.py** - DNS query logic
- `DNSResolver` class with async methods: `lookup()`, `reverse_lookup()`, `bulk_lookup()`, `bulk_reverse_lookup()`
- Retry logic with exponential backoff (0.5s, 1.0s, 2.0s)
- Uses dnspython's `dns.asyncresolver`

**types.py** - Response dataclasses
- `DNSRecord`, `LookupResponse`, `ReverseLookupResponse`, `ErrorResponse`

### Request Flow

```
MCP Client → http_server.py (Starlette/StreamableHTTP)
           → server.py (MCP tool handlers)
           → resolver.py (dnspython async queries)
```

### Configuration

Environment variables read in `server.py`:
- `DNS_TIMEOUT`, `DNS_RETRIES`, `DEFAULT_RESOLVER`, `LOG_LEVEL`

Environment variables read in `http_server.py`:
- `MCP_HOST`, `MCP_PORT`, `LOG_LEVEL`, `DEBUG`
