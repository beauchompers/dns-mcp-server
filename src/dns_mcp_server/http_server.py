"""HTTP server for MCP with Streamable HTTP transport."""

import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Callable

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from dns_mcp_server.server import create_server

logger = logging.getLogger(__name__)


def create_http_server() -> Callable:
    """Create HTTP server wrapping the MCP server.

    Returns an ASGI application that serves the MCP protocol
    over Streamable HTTP transport.
    """
    mcp_server = create_server()

    # Create the session manager for handling HTTP connections
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=False,  # Use SSE streaming
        stateless=False,  # Maintain session state
    )

    # Track whether the session manager is running
    session_manager_context = None

    async def health_response(send):
        """Send a health check response."""
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": json.dumps({"status": "healthy"}).encode(),
        })

    async def not_found_response(send):
        """Send a 404 response."""
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": json.dumps({"error": "Not found"}).encode(),
        })

    async def app(scope, receive, send):
        """ASGI application entry point."""
        nonlocal session_manager_context

        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    try:
                        session_manager_context = session_manager.run()
                        await session_manager_context.__aenter__()
                        logger.info("MCP session manager started")
                        await send({"type": "lifespan.startup.complete"})
                    except Exception as e:
                        logger.error(f"Startup failed: {e}")
                        await send({"type": "lifespan.startup.failed", "message": str(e)})
                elif message["type"] == "lifespan.shutdown":
                    if session_manager_context:
                        await session_manager_context.__aexit__(None, None, None)
                        logger.info("MCP session manager stopped")
                    await send({"type": "lifespan.shutdown.complete"})
                    return

        elif scope["type"] == "http":
            path = scope["path"]

            if path == "/health":
                await health_response(send)
            elif path == "/mcp":
                # Delegate to the MCP session manager
                await session_manager.handle_request(scope, receive, send)
            else:
                await not_found_response(send)

    return app


def main():
    """Run the HTTP server."""
    import uvicorn

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))

    logger.info(f"Starting DNS MCP Server on http://{host}:{port}/mcp")

    # Create the app
    app = create_http_server()

    # Run with uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
