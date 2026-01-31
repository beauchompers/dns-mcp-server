# DNS MCP Server

A Python MCP server providing comprehensive DNS lookup capabilities.

## Features

- **dns_lookup**: Query any DNS record type (A, AAAA, MX, TXT, NS, SOA, CNAME, SRV, CAA, DNSSEC records)
- **dns_reverse**: Reverse DNS lookup (PTR) for IPv4/IPv6 addresses
- **dns_bulk**: Query multiple domains in one call
- **dns_reverse_bulk**: Reverse lookup for multiple IPs

## Quick Start

```bash
docker compose up -d
```

The server will be available at `https://localhost:8088/mcp`.

Self-signed certificates are automatically generated on first startup.

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTPS_PORT` | `8088` | External HTTPS port |
| `DOMAIN` | `localhost` | Domain for certificate generation |
| `MCP_HOST` | `0.0.0.0` | Server bind address |
| `MCP_PORT` | `8000` | Server port |
| `DNS_TIMEOUT` | `5` | Query timeout in seconds |
| `DNS_RETRIES` | `3` | Max retry attempts |
| `DEFAULT_RESOLVER` | (system) | Default DNS resolver IP |
| `LOG_LEVEL` | `INFO` | Logging level |

## Claude Desktop Integration

To use this server with Claude Desktop, you'll need [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) to bridge the HTTP transport.

### 1. Install mcp-proxy

```bash
pip install mcp-proxy
# or
uv tool install mcp-proxy
```

### 2. Start the server

```bash
docker compose up -d
```

### 3. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "dns-lookup": {
      "command": "mcp-proxy",
      "args": [
        "--transport=streamablehttp",
        "--no-verify-ssl",
        "https://localhost:8088/mcp"
      ]
    }
  }
}
```

> **Note:** Use the full path to mcp-proxy if Claude shows ENOENT errors (run `which mcp-proxy` to find it).

### 4. Restart Claude Desktop

The DNS tools will now be available in Claude Desktop.

### Available Tools

| Tool | Description |
|------|-------------|
| `dns_lookup` | Query DNS records (A, AAAA, MX, TXT, NS, etc.) |
| `dns_reverse` | Reverse DNS lookup for an IP address |
| `dns_bulk` | Query multiple domains at once |
| `dns_reverse_bulk` | Reverse lookup for multiple IPs |

## Development

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

### Run locally (stdio mode)

```bash
dns-mcp-server
```

### Run locally (HTTP mode)

```bash
dns-mcp-server-http
```

## License

MIT
