"""Minimal, dependency-free reader for the safetensors format.

The format is an 8-byte little-endian header length, a JSON header mapping
tensor names to dtype, shape, and byte offsets, then the raw data. Tensors
are memory-mapped, so inspecting a large checkpoint does not load it into
RAM. Sharded checkpoints are handled through ``model.safetensors.index.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct

import numpy as np

_DTYPES = {
    "F64": np.float64,
    "F32": np.float32,
    "F16": np.float16,
    "I64": np.int64,
    "I32": np.int32,
    "I16": np.int16,
    "I8": np.int8,
    "U16": np.uint16,
    "U8": np.uint8,
    "BOOL": np.bool_,
    "BF16": np.uint16,  # converted to float32 on load
}


@dataclass(frozen=True)
class TensorInfo:
    name: str
    dtype: str
    shape: tuple[int, ...]
    path: Path
    start: int  # absolute byte offset in the file
    end: int

    @property
    def nbytes(self) -> int:
        return self.end - self.start


def read_header(path: str | Path) -> dict[str, TensorInfo]:
    """Parse the header of one ``.safetensors`` file."""
    path = Path(path)
    with open(path, "rb") as fh:
        (n,) = struct.unpack("<Q", fh.read(8))
        if n > 100_000_000:
            raise ValueError(f"implausible safetensors header length {n}")
        header = json.loads(fh.read(n))
    base = 8 + n
    out: dict[str, TensorInfo] = {}
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        b, e = meta["data_offsets"]
        out[name] = TensorInfo(name, meta["dtype"], tuple(meta["shape"]), path, base + b, base + e)
    return out


def read_checkpoint(path: str | Path) -> dict[str, TensorInfo]:
    """Read a single file, a directory with one file, or a sharded directory."""
    path = Path(path)
    if path.is_file():
        return read_header(path)
    index = path / "model.safetensors.index.json"
    if index.exists():
        weight_map = json.loads(index.read_text(encoding="utf-8"))["weight_map"]
        out: dict[str, TensorInfo] = {}
        for shard in sorted(set(weight_map.values())):
            out.update(read_header(path / shard))
        return out
    files = sorted(path.glob("*.safetensors"))
    if not files:
        raise FileNotFoundError(f"no .safetensors files in {path}")
    out = {}
    for f in files:
        out.update(read_header(f))
    return out


def load_tensor(info: TensorInfo) -> np.ndarray:
    """Return the tensor as a numpy array (BF16 is widened to float32)."""
    if info.dtype not in _DTYPES:
        raise ValueError(f"unsupported dtype {info.dtype} for {info.name}")
    np_dtype = _DTYPES[info.dtype]
    count = int(np.prod(info.shape)) if info.shape else 1
    mm = np.memmap(info.path, dtype=np_dtype, mode="r", offset=info.start, shape=(count,))
    arr = np.asarray(mm)
    if info.dtype == "BF16":
        arr = (arr.astype(np.uint32) << 16).view(np.float32)
    return arr.reshape(info.shape)


def tensor_digest(info: TensorInfo, chunk: int = 1 << 24) -> str:
    """SHA-256 of the raw tensor bytes (detects exact duplicates)."""
    h = hashlib.sha256()
    with open(info.path, "rb") as fh:
        fh.seek(info.start)
        remaining = info.nbytes
        while remaining > 0:
            buf = fh.read(min(chunk, remaining))
            if not buf:
                break
            h.update(buf)
            remaining -= len(buf)
    return h.hexdigest()


def write_safetensors(path: str | Path, tensors: dict[str, np.ndarray]) -> None:
    """Write float32/float16/int tensors in safetensors format (used for fixtures)."""
    rev = {np.dtype(v): k for k, v in _DTYPES.items() if k != "BF16"}
    header: dict[str, dict] = {}
    blobs = []
    offset = 0
    for name, arr in tensors.items():
        arr = np.ascontiguousarray(arr)
        raw = arr.tobytes()
        header[name] = {"dtype": rev[arr.dtype], "shape": list(arr.shape), "data_offsets": [offset, offset + len(raw)]}
        blobs.append(raw)
        offset += len(raw)
    hbytes = json.dumps(header).encode("utf-8")
    hbytes += b" " * ((8 - len(hbytes) % 8) % 8)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<Q", len(hbytes)))
        fh.write(hbytes)
        for b in blobs:
            fh.write(b)
