"""Core memory exploration functionality using pymem."""

from __future__ import annotations

import struct
import re
import ctypes
import ctypes.wintypes
from dataclasses import dataclass, field
from typing import Any

import pymem
import pymem.process
import pymem.pattern
import pymem.memory


# Windows memory constants
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_READONLY = 0x02
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_WRITECOPY = 0x80

READABLE_PROTECTIONS = (
    PAGE_READWRITE, PAGE_READONLY, PAGE_EXECUTE_READ,
    PAGE_EXECUTE_READWRITE, PAGE_WRITECOPY, PAGE_EXECUTE_WRITECOPY,
)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.wintypes.DWORD),
        ("Protect", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
    ]


@dataclass
class ModuleInfo:
    """Information about a loaded module (DLL/EXE)."""
    name: str
    base_address: int
    size: int
    path: str | None = None


@dataclass
class ScanResult:
    """Result from a pattern scan."""
    address: int
    pattern: str
    module: str | None = None


@dataclass
class PointerChain:
    """Result of resolving a pointer chain."""
    base_address: int
    offsets: list[int]
    final_address: int
    values_at_each_step: list[int]


@dataclass
class MemoryRegion:
    """A region of memory with metadata."""
    address: int
    size: int
    data: bytes
    protection: str | None = None


@dataclass
class WatchedAddress:
    """An address being watched for changes."""
    address: int
    size: int
    label: str
    last_value: bytes | None = None
    value_type: str = "bytes"  # bytes, int32, int64, float, double, string


class MemoryExplorer:
    """
    Memory exploration tool for reverse engineering games.

    Provides functionality for:
    - Process attachment
    - Memory reading/writing
    - Pattern scanning
    - Pointer chain resolution
    - Memory watching
    """

    def __init__(self) -> None:
        self._pm: pymem.Pymem | None = None
        self._process_name: str | None = None
        self._modules: dict[str, ModuleInfo] = {}
        self._watches: dict[str, WatchedAddress] = {}
        self._scan_results: list[ScanResult] = []

    @property
    def is_attached(self) -> bool:
        """Check if attached to a process."""
        return self._pm is not None

    @property
    def process_name(self) -> str | None:
        """Get the attached process name."""
        return self._process_name

    def list_processes(self, filter_name: str | None = None) -> list[dict[str, Any]]:
        """
        List running processes.

        Args:
            filter_name: Optional substring to filter process names

        Returns:
            List of process info dicts with name and pid
        """
        processes = []
        for proc in pymem.process.list_processes():
            name = proc.szExeFile.decode("utf-8", errors="ignore")
            if filter_name is None or filter_name.lower() in name.lower():
                processes.append({
                    "name": name,
                    "pid": proc.th32ProcessID,
                })
        return sorted(processes, key=lambda p: p["name"].lower())

    def attach(self, process_name: str) -> dict[str, Any]:
        """
        Attach to a process by name.

        Args:
            process_name: Name of the process (e.g., "NMS.exe")

        Returns:
            Dict with process info
        """
        if self._pm is not None:
            self.detach()

        self._pm = pymem.Pymem(process_name)
        self._process_name = process_name
        self._refresh_modules()

        return {
            "attached": True,
            "process_name": process_name,
            "pid": self._pm.process_id,
            "base_address": hex(self._pm.process_base.lpBaseOfDll),
            "module_count": len(self._modules),
        }

    def detach(self) -> None:
        """Detach from the current process."""
        if self._pm is not None:
            self._pm.close_process()
            self._pm = None
            self._process_name = None
            self._modules.clear()
            self._watches.clear()

    def _refresh_modules(self) -> None:
        """Refresh the list of loaded modules."""
        if self._pm is None:
            return

        self._modules.clear()
        for module in self._pm.list_modules():
            name = module.name
            self._modules[name.lower()] = ModuleInfo(
                name=name,
                base_address=module.lpBaseOfDll,
                size=module.SizeOfImage,
                path=module.filename,
            )

    def get_modules(self) -> list[dict[str, Any]]:
        """
        Get list of loaded modules.

        Returns:
            List of module info dicts
        """
        self._require_attached()
        self._refresh_modules()

        return [
            {
                "name": m.name,
                "base_address": hex(m.base_address),
                "size": m.size,
                "size_mb": round(m.size / 1024 / 1024, 2),
                "path": m.path,
            }
            for m in sorted(self._modules.values(), key=lambda x: x.base_address)
        ]

    def get_module_base(self, module_name: str) -> int:
        """Get the base address of a module."""
        self._require_attached()

        key = module_name.lower()
        if key not in self._modules:
            self._refresh_modules()

        if key not in self._modules:
            raise ValueError(f"Module not found: {module_name}")

        return self._modules[key].base_address

    def read_bytes(self, address: int, size: int) -> bytes:
        """
        Read raw bytes from memory.

        Args:
            address: Memory address to read from
            size: Number of bytes to read

        Returns:
            Raw bytes
        """
        self._require_attached()
        return self._pm.read_bytes(address, size)

    def read_int32(self, address: int) -> int:
        """Read a 32-bit signed integer."""
        self._require_attached()
        return self._pm.read_int(address)

    def read_int64(self, address: int) -> int:
        """Read a 64-bit signed integer."""
        self._require_attached()
        return self._pm.read_longlong(address)

    def read_uint32(self, address: int) -> int:
        """Read a 32-bit unsigned integer."""
        self._require_attached()
        return self._pm.read_uint(address)

    def read_uint64(self, address: int) -> int:
        """Read a 64-bit unsigned integer."""
        self._require_attached()
        return self._pm.read_ulonglong(address)

    def read_float(self, address: int) -> float:
        """Read a 32-bit float."""
        self._require_attached()
        return self._pm.read_float(address)

    def read_double(self, address: int) -> float:
        """Read a 64-bit double."""
        self._require_attached()
        return self._pm.read_double(address)

    def read_pointer(self, address: int) -> int:
        """Read a pointer (64-bit on x64)."""
        self._require_attached()
        return self._pm.read_ulonglong(address)

    def read_string(self, address: int, max_length: int = 256, encoding: str = "utf-8") -> str:
        """
        Read a null-terminated string.

        Args:
            address: Memory address
            max_length: Maximum bytes to read
            encoding: String encoding

        Returns:
            The string value
        """
        self._require_attached()
        data = self._pm.read_bytes(address, max_length)
        null_pos = data.find(b'\x00')
        if null_pos >= 0:
            data = data[:null_pos]
        return data.decode(encoding, errors="replace")

    def read_matrix4x4(self, address: int) -> list[list[float]]:
        """
        Read a 4x4 float matrix (common for view/projection matrices).

        Args:
            address: Memory address of the matrix

        Returns:
            4x4 list of floats
        """
        self._require_attached()
        data = self._pm.read_bytes(address, 64)  # 16 floats * 4 bytes
        floats = struct.unpack("16f", data)
        return [
            list(floats[0:4]),
            list(floats[4:8]),
            list(floats[8:12]),
            list(floats[12:16]),
        ]

    def read_vector3(self, address: int) -> dict[str, float]:
        """Read a 3D vector (3 floats)."""
        self._require_attached()
        data = self._pm.read_bytes(address, 12)
        x, y, z = struct.unpack("3f", data)
        return {"x": x, "y": y, "z": z}

    def read_vector4(self, address: int) -> dict[str, float]:
        """Read a 4D vector (4 floats)."""
        self._require_attached()
        data = self._pm.read_bytes(address, 16)
        x, y, z, w = struct.unpack("4f", data)
        return {"x": x, "y": y, "z": z, "w": w}

    def resolve_pointer_chain(
        self,
        base_address: int,
        offsets: list[int],
    ) -> PointerChain:
        """
        Resolve a pointer chain (base + offsets).

        Args:
            base_address: Starting address
            offsets: List of offsets to follow

        Returns:
            PointerChain with final address and intermediate values
        """
        self._require_attached()

        current = base_address
        values = [current]

        for i, offset in enumerate(offsets):
            if i < len(offsets) - 1:
                # Read pointer and add offset
                current = self._pm.read_ulonglong(current) + offset
            else:
                # Last offset is just added
                current = current + offset
            values.append(current)

        return PointerChain(
            base_address=base_address,
            offsets=offsets,
            final_address=current,
            values_at_each_step=values,
        )

    def scan_pattern(
        self,
        pattern: str,
        module_name: str | None = None,
        return_multiple: bool = False,
        max_results: int = 100,
    ) -> list[ScanResult]:
        """
        Scan memory for a byte pattern.

        Pattern format: "48 8B 05 ?? ?? ?? ?? 48 85 C0"
        Use ?? for wildcard bytes.

        Args:
            pattern: Byte pattern with optional wildcards
            module_name: Limit scan to a specific module
            return_multiple: Return all matches, not just first
            max_results: Maximum results to return

        Returns:
            List of ScanResult
        """
        self._require_attached()

        results = []

        if module_name:
            # Scan specific module
            module = self._modules.get(module_name.lower())
            if not module:
                self._refresh_modules()
                module = self._modules.get(module_name.lower())
            if not module:
                raise ValueError(f"Module not found: {module_name}")

            matches = self._scan_module(pattern, module, max_results if return_multiple else 1)
            for addr in matches:
                results.append(ScanResult(address=addr, pattern=pattern, module=module_name))
                if not return_multiple:
                    break
        else:
            # Scan main module
            main_module = self._modules.get(self._process_name.lower())
            if main_module:
                matches = self._scan_module(pattern, main_module, max_results if return_multiple else 1)
                for addr in matches:
                    results.append(ScanResult(address=addr, pattern=pattern, module=self._process_name))
                    if not return_multiple and results:
                        break

        self._scan_results.extend(results)
        return results

    def scan_all_regions(
        self,
        pattern: str,
        max_results: int = 50,
        min_address: int = 0,
        max_address: int = 0x7FFFFFFFFFFF,
    ) -> list[ScanResult]:
        """
        Scan ALL committed readable memory regions for a pattern.
        This includes heap, stack, and mapped memory - not just modules.

        Args:
            pattern: Byte pattern with optional wildcards (??)
            max_results: Maximum results to return
            min_address: Minimum address to start scanning
            max_address: Maximum address to stop scanning

        Returns:
            List of ScanResult
        """
        self._require_attached()

        pattern_bytes, mask = self._parse_pattern(pattern)
        results = []

        kernel32 = ctypes.windll.kernel32
        handle = self._pm.process_handle

        address = min_address
        mbi = MEMORY_BASIC_INFORMATION()
        mbi_size = ctypes.sizeof(mbi)

        while address < max_address and len(results) < max_results:
            result = kernel32.VirtualQueryEx(
                handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                mbi_size,
            )

            if result == 0:
                break

            region_base = mbi.BaseAddress if mbi.BaseAddress else address
            region_size = mbi.RegionSize

            # Only scan committed, readable regions
            if (mbi.State == MEM_COMMIT and
                    mbi.Protect in READABLE_PROTECTIONS and
                    region_size > 0 and region_size < 256 * 1024 * 1024):
                try:
                    data = self._pm.read_bytes(region_base, region_size)
                    pos = 0
                    while pos < len(data) - len(pattern_bytes) and len(results) < max_results:
                        match = True
                        for i, (b, m) in enumerate(zip(pattern_bytes, mask)):
                            if m and data[pos + i] != b:
                                match = False
                                break
                        if match:
                            results.append(ScanResult(
                                address=region_base + pos,
                                pattern=pattern,
                                module=None,
                            ))
                        pos += 1
                except Exception:
                    pass  # Skip unreadable regions

            address = region_base + region_size
            if address <= region_base:
                break

        self._scan_results.extend(results)
        return results

    def _scan_module(self, pattern: str, module: ModuleInfo, max_results: int) -> list[int]:
        """Scan a specific module for a pattern."""
        # Convert pattern string to bytes with mask
        pattern_bytes, mask = self._parse_pattern(pattern)

        results = []
        try:
            # Read module memory
            data = self._pm.read_bytes(module.base_address, module.size)

            # Search for pattern
            pos = 0
            while pos < len(data) - len(pattern_bytes) and len(results) < max_results:
                match = True
                for i, (b, m) in enumerate(zip(pattern_bytes, mask)):
                    if m and data[pos + i] != b:
                        match = False
                        break
                if match:
                    results.append(module.base_address + pos)
                pos += 1

        except Exception:
            pass  # Memory region may not be readable

        return results

    def _parse_pattern(self, pattern: str) -> tuple[bytes, list[bool]]:
        """Parse a pattern string into bytes and mask."""
        parts = pattern.strip().split()
        pattern_bytes = []
        mask = []

        for part in parts:
            if part in ("??", "?"):
                pattern_bytes.append(0)
                mask.append(False)  # Wildcard
            else:
                pattern_bytes.append(int(part, 16))
                mask.append(True)

        return bytes(pattern_bytes), mask

    def dump_memory(
        self,
        address: int,
        size: int,
        format: str = "hex",
    ) -> dict[str, Any]:
        """
        Dump a memory region.

        Args:
            address: Starting address
            size: Number of bytes to dump
            format: Output format (hex, bytes, ascii)

        Returns:
            Dict with address, size, and formatted data
        """
        self._require_attached()

        data = self._pm.read_bytes(address, size)

        if format == "hex":
            # Format as hex dump with ASCII
            lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_part = " ".join(f"{b:02X}" for b in chunk)
                ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(f"{address + i:016X}  {hex_part:<48}  {ascii_part}")
            formatted = "\n".join(lines)
        elif format == "bytes":
            formatted = data.hex()
        else:  # ascii
            formatted = data.decode("utf-8", errors="replace")

        return {
            "address": hex(address),
            "size": size,
            "data": formatted,
        }

    def add_watch(
        self,
        label: str,
        address: int,
        size: int = 4,
        value_type: str = "int32",
    ) -> dict[str, Any]:
        """
        Add an address to watch for changes.

        Args:
            label: Name for this watch
            address: Memory address
            size: Number of bytes
            value_type: How to interpret (bytes, int32, int64, float, double, string)

        Returns:
            Watch info
        """
        self._require_attached()

        self._watches[label] = WatchedAddress(
            address=address,
            size=size,
            label=label,
            value_type=value_type,
        )

        return self.read_watch(label)

    def read_watch(self, label: str) -> dict[str, Any]:
        """Read the current value of a watched address."""
        self._require_attached()

        if label not in self._watches:
            raise ValueError(f"Watch not found: {label}")

        watch = self._watches[label]
        data = self._pm.read_bytes(watch.address, watch.size)

        # Interpret based on type
        if watch.value_type == "int32":
            value = struct.unpack("<i", data[:4])[0]
        elif watch.value_type == "int64":
            value = struct.unpack("<q", data[:8])[0]
        elif watch.value_type == "uint32":
            value = struct.unpack("<I", data[:4])[0]
        elif watch.value_type == "uint64":
            value = struct.unpack("<Q", data[:8])[0]
        elif watch.value_type == "float":
            value = struct.unpack("<f", data[:4])[0]
        elif watch.value_type == "double":
            value = struct.unpack("<d", data[:8])[0]
        elif watch.value_type == "string":
            null_pos = data.find(b'\x00')
            if null_pos >= 0:
                data = data[:null_pos]
            value = data.decode("utf-8", errors="replace")
        else:
            value = data.hex()

        changed = watch.last_value is not None and watch.last_value != data
        watch.last_value = data

        return {
            "label": label,
            "address": hex(watch.address),
            "value": value,
            "raw_hex": data.hex(),
            "changed": changed,
        }

    def read_all_watches(self) -> list[dict[str, Any]]:
        """Read all watched addresses."""
        return [self.read_watch(label) for label in self._watches]

    def remove_watch(self, label: str) -> None:
        """Remove a watch."""
        self._watches.pop(label, None)

    def find_value(
        self,
        value: int | float,
        value_type: str = "int32",
        module_name: str | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search memory for a specific value.

        Args:
            value: The value to search for
            value_type: Value type (int32, int64, float, double)
            module_name: Limit search to a module
            max_results: Maximum results

        Returns:
            List of addresses where the value was found
        """
        self._require_attached()

        # Pack the value into bytes
        if value_type == "int32":
            search_bytes = struct.pack("<i", int(value))
        elif value_type == "int64":
            search_bytes = struct.pack("<q", int(value))
        elif value_type == "uint32":
            search_bytes = struct.pack("<I", int(value))
        elif value_type == "uint64":
            search_bytes = struct.pack("<Q", int(value))
        elif value_type == "float":
            search_bytes = struct.pack("<f", float(value))
        elif value_type == "double":
            search_bytes = struct.pack("<d", float(value))
        else:
            raise ValueError(f"Unknown value type: {value_type}")

        # Convert to pattern string
        pattern = " ".join(f"{b:02X}" for b in search_bytes)

        results = self.scan_pattern(
            pattern,
            module_name=module_name,
            return_multiple=True,
            max_results=max_results,
        )

        return [
            {
                "address": hex(r.address),
                "module": r.module,
                "value": value,
                "type": value_type,
            }
            for r in results
        ]

    def get_scan_history(self) -> list[dict[str, Any]]:
        """Get history of scan results."""
        return [
            {
                "address": hex(r.address),
                "pattern": r.pattern,
                "module": r.module,
            }
            for r in self._scan_results
        ]

    def clear_scan_history(self) -> None:
        """Clear scan result history."""
        self._scan_results.clear()

    def _require_attached(self) -> None:
        """Raise if not attached to a process."""
        if self._pm is None:
            raise RuntimeError("Not attached to any process. Call attach() first.")


# Global explorer instance
_explorer: MemoryExplorer | None = None


def get_explorer() -> MemoryExplorer:
    """Get the global MemoryExplorer instance."""
    global _explorer
    if _explorer is None:
        _explorer = MemoryExplorer()
    return _explorer
