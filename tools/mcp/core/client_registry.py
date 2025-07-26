"""Client registry for dynamic MCP client registration"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ClientRegistry:
    """Manages registered MCP clients"""

    def __init__(self, storage_path: str = "/tmp/mcp_clients.json"):
        self.storage_path = Path(storage_path)
        self.clients: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
        self._load_clients()

    def _load_clients(self):
        """Load clients from persistent storage"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    self.clients = json.load(f)
                self.logger.info(f"Loaded {len(self.clients)} registered clients")
            except Exception as e:
                self.logger.error(f"Failed to load clients: {e}")
                self.clients = {}

    def _save_clients(self):
        """Save clients to persistent storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump(self.clients, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save clients: {e}")

    def register_client(self, client_name: str, client_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Register a new client or update existing one

        Args:
            client_name: Name/ID of the client
            client_metadata: Additional metadata about the client

        Returns:
            Registration response with client_id and credentials
        """
        # Generate or use existing client ID
        client_id = client_metadata.get("client_id") if client_metadata else None
        if not client_id:
            client_id = f"{client_name}_{uuid4().hex[:8]}"

        # Check if client already exists
        is_update = client_id in self.clients

        # Create client record
        client_record = {
            "client_id": client_id,
            "client_name": client_name,
            "registered_at": self.clients.get(client_id, {}).get("registered_at", datetime.utcnow().isoformat()),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": client_metadata or {},
            "active": True,
            "last_seen": datetime.utcnow().isoformat(),
            "request_count": self.clients.get(client_id, {}).get("request_count", 0),
        }

        # Store client
        self.clients[client_id] = client_record
        self._save_clients()

        # Return registration response
        return {
            "client_id": client_id,
            "client_name": client_name,
            "registered": True,
            "is_update": is_update,
            "registration_time": client_record["registered_at"],
            "server_time": datetime.utcnow().isoformat(),
        }

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client information"""
        return self.clients.get(client_id)

    def list_clients(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List all registered clients"""
        clients = list(self.clients.values())
        if active_only:
            clients = [c for c in clients if c.get("active", True)]
        return clients

    def update_client_activity(self, client_id: str):
        """Update client's last seen timestamp and request count"""
        if client_id in self.clients:
            self.clients[client_id]["last_seen"] = datetime.utcnow().isoformat()
            self.clients[client_id]["request_count"] = self.clients[client_id].get("request_count", 0) + 1
            self._save_clients()

    def deactivate_client(self, client_id: str) -> bool:
        """Deactivate a client"""
        if client_id in self.clients:
            self.clients[client_id]["active"] = False
            self.clients[client_id]["deactivated_at"] = datetime.utcnow().isoformat()
            self._save_clients()
            return True
        return False

    def get_client_stats(self) -> Dict[str, Any]:
        """Get statistics about registered clients"""
        total_clients = len(self.clients)
        active_clients = sum(1 for c in self.clients.values() if c.get("active", True))

        # Calculate activity in last hour
        now = time.time()
        hour_ago = now - 3600
        recent_active = sum(
            1
            for c in self.clients.values()
            if c.get("last_seen") and datetime.fromisoformat(c["last_seen"]).timestamp() > hour_ago
        )

        return {
            "total_clients": total_clients,
            "active_clients": active_clients,
            "inactive_clients": total_clients - active_clients,
            "clients_active_last_hour": recent_active,
            "total_requests": sum(c.get("request_count", 0) for c in self.clients.values()),
        }
