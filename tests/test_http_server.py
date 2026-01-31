"""Tests for HTTP server."""

from starlette.testclient import TestClient


def test_health_endpoint_returns_healthy():
    """Test that health endpoint returns healthy status."""
    from dns_mcp_server.http_server import create_http_server

    app = create_http_server()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
