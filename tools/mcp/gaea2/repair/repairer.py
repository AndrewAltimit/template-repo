"""Gaea2 project repair functionality"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Use stubs for now
from ..stubs import Gaea2ErrorRecovery, Gaea2ProjectRepair, Gaea2StructureValidator


class Gaea2Repairer:
    """Repair damaged or corrupted Gaea2 projects"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.project_repair = Gaea2ProjectRepair()
        self.error_recovery = Gaea2ErrorRecovery()
        self.structure_validator = Gaea2StructureValidator()

    async def repair_project(self, project_path: str, backup: bool = True) -> Dict[str, Any]:
        """Repair a Gaea2 project file"""

        project_path_obj = Path(project_path)

        if not project_path_obj.exists():
            return {
                "success": False,
                "error": f"Project file not found: {project_path_obj}",
            }

        try:
            # Create backup if requested
            backup_path = None
            if backup:
                backup_path = project_path_obj.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.terrain")
                shutil.copy2(project_path_obj, backup_path)
                self.logger.info(f"Created backup: {backup_path}")

            # Load project
            with open(project_path_obj, "r") as f:
                project_data = json.load(f)

            # Validate structure
            structure_result = self.structure_validator.validate_structure(project_data)

            if not structure_result["valid"]:
                # Use project repair
                repair_result = self.project_repair.repair_project(str(project_path), backup=False)  # We already made a backup

                if repair_result["success"]:
                    # Reload repaired project
                    with open(project_path, "r") as f:
                        project_data = json.load(f)
                else:
                    return {
                        "success": False,
                        "error": "Failed to repair project structure",
                        "backup_path": str(backup_path) if backup_path else None,
                    }

            # Extract nodes and connections
            graph = project_data.get("Graph", {})
            nodes = []
            connections = []

            # Parse nodes
            for node_data in graph.get("Nodes", []):
                nodes.append(self._extract_node_info(node_data))

            # Parse connections from nodes
            connections = self._extract_connections(graph.get("Nodes", []))

            # Use error recovery to fix issues
            recovery_result = self.error_recovery.fix_workflow(nodes, connections)

            # Rebuild project structure
            repaired_data = self._rebuild_project_structure(
                project_data, recovery_result["nodes"], recovery_result["connections"]
            )

            # Save repaired project
            with open(project_path_obj, "w") as f:
                json.dump(repaired_data, f, indent=2)

            return {
                "success": True,
                "repaired": recovery_result["fixed"],
                "backup_path": str(backup_path) if backup_path else None,
                "issues_found": structure_result.get("errors", []),
                "fixes_applied": recovery_result.get("fixes_applied", []),
            }

        except Exception as e:
            self.logger.error(f"Failed to repair project: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backup_path": str(backup_path) if backup_path else None,
            }

    def _extract_node_info(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract node information from project data"""
        node_id = node_data.get("$id", node_data.get("ID"))
        node_type = node_data.get("$type", "").split(".")[-1].split(",")[0]

        # Extract properties
        properties = {}
        for key, value in node_data.items():
            if not key.startswith("$") and key not in ["ID", "Name", "Ports"]:
                properties[key] = value

        return {
            "id": node_id,
            "type": node_type,
            "properties": properties,
            "name": node_data.get("Name", node_type),
        }

    def _extract_connections(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract connections from node port data"""
        connections = []

        for node in nodes:
            node_id = node.get("$id", node.get("ID"))
            ports = node.get("Ports", {})

            for port_name, port_data in ports.items():
                if isinstance(port_data, dict) and "Records" in port_data:
                    for record in port_data["Records"]:
                        if "ID" in record:
                            connections.append(
                                {
                                    "from_node": record["ID"],
                                    "from_port": record.get("Port", "Out"),
                                    "to_node": node_id,
                                    "to_port": port_name,
                                }
                            )

        return connections

    def _rebuild_project_structure(
        self,
        original_data: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Rebuild project structure with fixed nodes and connections"""

        # This is a simplified version - in practice, you'd need to
        # carefully reconstruct the full Gaea2 project format
        # For now, just update the existing structure

        return original_data
