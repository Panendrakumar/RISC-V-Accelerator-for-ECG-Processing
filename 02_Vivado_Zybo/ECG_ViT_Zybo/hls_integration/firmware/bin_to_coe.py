"""Convert a little-endian RISC-V binary to Vivado COE and MEM images."""

from __future__ import annotations

import sys
from pathlib import Path

DEPTH = 8192


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python bin_to_coe.py input.bin output.coe")
    binary = Path(sys.argv[1]).read_bytes()
    if len(binary) > DEPTH * 4:
        raise SystemExit(f"Firmware image is {len(binary)} bytes; BRAM limit is {DEPTH * 4} bytes")
    binary += bytes(DEPTH * 4 - len(binary))
    words = [int.from_bytes(binary[i : i + 4], "little") for i in range(0, len(binary), 4)]
    text = "memory_initialization_radix=16;\nmemory_initialization_vector=\n"
    text += ",\n".join(f"{word:08X}" for word in words) + ";\n"
    coe_path = Path(sys.argv[2])
    coe_path.write_text(text, encoding="ascii")
    mem_path = coe_path.with_suffix(".mem")
    # Vivado MEM initialization uses a start-address record followed by the
    # 32-bit words, one word per line.
    mem_text = "@00000000\n" + "\n".join(f"{word:08X}" for word in words) + "\n"
    mem_path.write_text(mem_text, encoding="ascii")
    print(f"Wrote {coe_path} and {mem_path} with {DEPTH} words ({DEPTH * 4} bytes).")


if __name__ == "__main__":
    main()
