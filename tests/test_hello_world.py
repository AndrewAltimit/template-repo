"""Test for hello world tool."""
from tools.mcp.hello_world import hello_world


def test_hello_world():
    """Test that hello world returns the correct message."""
    assert hello_world() == "Hello, World!"
