"""
Plugin manager for backend adapters.

Handles discovery, loading, and lifecycle management of backend plugins.
"""

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import pkg_resources

from ..backends.base import BackendAdapter

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages backend plugin lifecycle."""

    def __init__(self, plugin_directory: Optional[str] = None):
        """
        Initialize plugin manager.

        Args:
            plugin_directory: Optional directory to scan for plugins
        """
        self.plugins: Dict[str, Type[BackendAdapter]] = {}
        self.instances: Dict[str, BackendAdapter] = {}
        self.active_backend: Optional[str] = None
        self.plugin_directory = plugin_directory

        # Default plugin paths
        self.plugin_paths = [
            Path(__file__).parent.parent / "backends",
        ]

        if plugin_directory:
            self.plugin_paths.append(Path(plugin_directory))

    async def discover_plugins(self) -> List[str]:
        """
        Discover available plugins via multiple methods.

        Returns:
            List of discovered plugin names
        """
        discovered = []

        # Method 1: Entry points (for installed packages)
        discovered.extend(self._discover_entry_points())

        # Method 2: Directory scanning
        discovered.extend(await self._discover_from_directories())

        # Method 3: Built-in plugins
        discovered.extend(self._discover_builtin())

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for name in discovered:
            if name not in seen:
                seen.add(name)
                unique.append(name)

        logger.info(f"Discovered {len(unique)} plugins: {unique}")
        return unique

    def _discover_entry_points(self) -> List[str]:
        """Discover plugins via Python entry points."""
        discovered = []

        try:
            for entry_point in pkg_resources.iter_entry_points("virtual_character.backends"):
                try:
                    plugin_class = entry_point.load()
                    if self._is_valid_plugin(plugin_class):
                        self.plugins[entry_point.name] = plugin_class
                        discovered.append(entry_point.name)
                        logger.debug(f"Loaded entry point plugin: {entry_point.name}")
                except Exception as e:
                    logger.error(f"Failed to load entry point {entry_point.name}: {e}")
        except Exception as e:
            logger.debug(f"Entry points not available: {e}")

        return discovered

    async def _discover_from_directories(self) -> List[str]:
        """Discover plugins from directories."""
        discovered = []

        for plugin_path in self.plugin_paths:
            if not plugin_path.exists():
                continue

            for file_path in plugin_path.glob("*.py"):
                if file_path.name.startswith("_") or file_path.name == "base.py":
                    continue

                plugin_name = file_path.stem

                try:
                    # Load module
                    spec = importlib.util.spec_from_file_location(f"virtual_character.backends.{plugin_name}", file_path)

                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[spec.name] = module
                        spec.loader.exec_module(module)

                        # Find adapter class
                        for name, obj in inspect.getmembers(module):
                            if inspect.isclass(obj) and issubclass(obj, BackendAdapter) and obj != BackendAdapter:

                                self.plugins[plugin_name] = obj
                                discovered.append(plugin_name)
                                logger.debug(f"Loaded directory plugin: {plugin_name}")
                                break

                except Exception as e:
                    logger.error(f"Failed to load plugin from {file_path}: {e}")

        return discovered

    def _discover_builtin(self) -> List[str]:
        """Discover built-in plugins."""
        discovered = []

        # Import built-in backends
        builtin_backends = ["mock", "vrchat_remote", "blender", "unity_websocket"]  # For testing

        for backend_name in builtin_backends:
            try:
                module = importlib.import_module(f"tools.mcp.virtual_character.backends.{backend_name}")

                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, BackendAdapter) and obj != BackendAdapter:

                        self.plugins[backend_name] = obj
                        discovered.append(backend_name)
                        logger.debug(f"Loaded built-in plugin: {backend_name}")
                        break

            except ImportError as e:
                logger.debug(f"Built-in backend {backend_name} not available: {e}")

        return discovered

    def _is_valid_plugin(self, plugin_class: Type) -> bool:
        """Check if a class is a valid plugin."""
        return (
            inspect.isclass(plugin_class)
            and issubclass(plugin_class, BackendAdapter)
            and plugin_class != BackendAdapter
            and not inspect.isabstract(plugin_class)
        )

    async def load_plugin(self, name: str, config: Dict[str, Any]) -> BackendAdapter:
        """
        Load and initialize a specific plugin.

        Args:
            name: Plugin name
            config: Plugin configuration

        Returns:
            Initialized backend adapter instance

        Raises:
            ValueError: If plugin not found
            RuntimeError: If plugin fails to initialize
        """
        if name not in self.plugins:
            # Try to discover again
            await self.discover_plugins()

            if name not in self.plugins:
                raise ValueError(f"Plugin '{name}' not found")

        # Create instance
        plugin_class = self.plugins[name]

        try:
            instance = plugin_class()

            # Connect with config
            success = await instance.connect(config)

            if not success:
                raise RuntimeError(f"Plugin '{name}' failed to connect")

            # Store instance
            self.instances[name] = instance

            logger.info(f"Loaded plugin '{name}' successfully")
            return instance

        except Exception as e:
            logger.error(f"Failed to load plugin '{name}': {e}")
            raise RuntimeError(f"Failed to load plugin '{name}': {e}")

    async def switch_backend(self, name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Switch to a different backend.

        Args:
            name: Backend name to switch to
            config: Optional new configuration

        Returns:
            True if switch successful
        """
        # Disconnect current backend if active
        if self.active_backend:
            await self.disconnect_current()

        # Load new backend if not already loaded
        if name not in self.instances:
            if config is None:
                raise ValueError(f"Configuration required for new backend '{name}'")

            await self.load_plugin(name, config)

        # Set as active
        self.active_backend = name

        logger.info(f"Switched to backend '{name}'")
        return True

    async def disconnect_current(self) -> None:
        """Disconnect the currently active backend."""
        if self.active_backend and self.active_backend in self.instances:
            instance = self.instances[self.active_backend]

            try:
                await instance.disconnect()
                logger.info(f"Disconnected backend '{self.active_backend}'")
            except Exception as e:
                logger.error(f"Error disconnecting backend '{self.active_backend}': {e}")

            self.active_backend = None

    def get_active_backend(self) -> Optional[BackendAdapter]:
        """
        Get the currently active backend instance.

        Returns:
            Active backend or None
        """
        if self.active_backend and self.active_backend in self.instances:
            return self.instances[self.active_backend]
        return None

    async def cleanup(self) -> None:
        """Clean up all plugin instances."""
        # Disconnect all backends
        for name, instance in self.instances.items():
            try:
                if instance.is_connected:
                    await instance.disconnect()
                    logger.info(f"Disconnected backend '{name}'")
            except Exception as e:
                logger.error(f"Error disconnecting backend '{name}': {e}")

        self.instances.clear()
        self.active_backend = None

    def list_available_plugins(self) -> List[Dict[str, Any]]:
        """
        List all available plugins with their capabilities.

        Returns:
            List of plugin information dictionaries
        """
        plugin_info = []

        for name, plugin_class in self.plugins.items():
            info = {
                "name": name,
                "class": plugin_class.__name__,
                "module": plugin_class.__module__,
                "loaded": name in self.instances,
                "active": name == self.active_backend,
            }

            # Get capabilities if instance exists
            if name in self.instances:
                info["capabilities"] = self.instances[name].capabilities.to_dict()

            plugin_info.append(info)

        return plugin_info

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all loaded plugins.

        Returns:
            Health status for all plugins
        """
        health: Dict[str, Any] = {"active_backend": self.active_backend, "backends": {}}

        for name, instance in self.instances.items():
            try:
                backend_health = await instance.health_check()
                health["backends"][name] = backend_health
            except Exception as e:
                health["backends"][name] = {"error": str(e), "connected": False}

        return health
