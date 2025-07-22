"""
Utility functions for handling Gaea2 connection formats
"""

from typing import Any, Dict, List


def normalize_connection(connection: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize connection format to the standard flat structure.

    Standard format:
    {
        "from_node": 100,
        "to_node": 101,
        "from_port": "Out",
        "to_port": "In"
    }

    Args:
        connection: Connection in any supported format

    Returns:
        Connection in standard flat format
    """
    # If already in standard format, return as-is
    if "from_node" in connection and "to_node" in connection:
        return connection

    # Convert from nested format
    if "from" in connection and "to" in connection:
        from_info = connection["from"]
        to_info = connection["to"]

        # Handle nested structure
        if isinstance(from_info, dict) and "node_id" in from_info:
            return {
                "from_node": from_info["node_id"],
                "to_node": to_info["node_id"],
                "from_port": from_info.get("port", "Out"),
                "to_port": to_info.get("port", "In"),
            }
        # Handle simple format (just IDs)
        else:
            return {
                "from_node": from_info,
                "to_node": to_info,
                "from_port": connection.get("from_port", "Out"),
                "to_port": connection.get("to_port", "In"),
            }

    # If we can't normalize, return as-is
    return connection


def normalize_connections(connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize a list of connections to standard format.

    Args:
        connections: List of connections in any format

    Returns:
        List of connections in standard format
    """
    return [normalize_connection(conn) for conn in connections]


def convert_to_nested_format(connection: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert standard flat format to nested format (for testing compatibility).

    Args:
        connection: Connection in standard flat format

    Returns:
        Connection in nested format
    """
    return {
        "from": {
            "node_id": connection.get("from_node"),
            "port": connection.get("from_port", "Out"),
        },
        "to": {
            "node_id": connection.get("to_node"),
            "port": connection.get("to_port", "In"),
        },
    }


def convert_to_gaea2_internal(connection: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert standard format to Gaea2's internal format.

    Args:
        connection: Connection in standard flat format

    Returns:
        Connection in Gaea2 internal format
    """
    return {
        "From": connection.get("from_node"),
        "To": connection.get("to_node"),
        "FromPort": connection.get("from_port", "Out"),
        "ToPort": connection.get("to_port", "In"),
    }
