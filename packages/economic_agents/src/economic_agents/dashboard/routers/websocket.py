"""WebSocket endpoint router for real-time updates."""

from datetime import datetime
import json
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return

        # Convert datetime objects to ISO format strings
        message_json = json.dumps(message, default=str)

        # Send to all connections, remove failed ones
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.add(connection)

        # Remove disconnected clients
        self.active_connections -= disconnected


# Global connection manager
manager = ConnectionManager()


@router.websocket("/updates")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.

    Clients connect to this endpoint to receive real-time updates about:
    - Agent status changes
    - New decisions
    - Resource transactions
    - Metric updates
    - Company events
    """
    await manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {"type": "connected", "timestamp": datetime.now().isoformat(), "data": {"message": "Connected to updates"}}
        )

        # Keep connection alive and handle incoming messages
        while True:
            # Receive messages from client (e.g., subscribe/unsubscribe)
            data = await websocket.receive_text()

            # Echo back for now (can add subscription logic later)
            await websocket.send_json(
                {"type": "acknowledged", "timestamp": datetime.now().isoformat(), "data": {"received": data}}
            )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def broadcast_update(update_type: str, data: dict):
    """Broadcast an update to all connected WebSocket clients.

    Args:
        update_type: Type of update ("status", "decision", "transaction", "metric", "company")
        data: Update data to broadcast
    """
    message = {"type": update_type, "timestamp": datetime.now().isoformat(), "data": data}

    await manager.broadcast(message)


# Helper function to get the manager (for external use)
def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager
