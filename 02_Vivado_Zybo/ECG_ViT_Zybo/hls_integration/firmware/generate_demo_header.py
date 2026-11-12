"""Quantize golden vector zero into the bare-metal Q6.10 firmware header."""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = (
    HERE.parents[3]
    / "03_HW_SW_Validation"
    / "vitis_hls"
    / "z7_tiny_ecg_vit"
    / "golden_test_vectors.h"
)
OUT = HERE / "demo_model_data.h"


def read_rows(name: str) -> list[list[float]]:
    source = GOLDEN.read_text(encoding="utf-8")
    match = re.search(
        rf"static const float {name}\[[^;]*?=\s*\{{(.*?)\n\}};",
        source,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"Could not find {name} in {GOLDEN}")
    rows = re.findall(r"\{([^{}]+)\}", match.group(1))
    return [[float(x.rstrip("f")) for x in re.findall(r"[-+0-9.eE]+f?", row)] for row in rows]


def read_ints(name: str) -> list[int]:
    source = GOLDEN.read_text(encoding="utf-8")
    match = re.search(
        rf"static const int {name}\[[^;]*?=\s*\{{(.*?)\}};",
        source,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"Could not find {name} in {GOLDEN}")
    return [int(x) for x in re.findall(r"-?\d+", match.group(1))]


def q610(value: float) -> int:
    # Python round is ties-to-even, matching the generated Q6.10 conversion.
    return max(-32768, min(32767, round(value * 1024)))


def c_array(name: str, values: list[int]) -> str:
    lines = [", ".join(str(x) for x in values[i : i + 12]) for i in range(0, len(values), 12)]
    return f"static const int16_t {name}[{len(values)}] = {{\n    " + ",\n    ".join(lines) + "\n};"


if __name__ == "__main__":
    ecg = read_rows("GOLDEN_ECG")[0]
    rr = read_rows("GOLDEN_RR")[0]
    expected = read_ints("GOLDEN_EXPECTED_CLASS")[0]
    if len(ecg) != 198 or len(rr) != 2:
        raise RuntimeError("Golden test vector zero must have 198 ECG and 2 RR samples")
    content = "\n".join(
        [
            "// Generated from golden_test_vectors.h; raw signed Q6.10 values.",
            "#ifndef DEMO_MODEL_DATA_H",
            "#define DEMO_MODEL_DATA_H",
            "#include <stdint.h>",
            c_array("demo_ecg_q10", [q610(x) for x in ecg]),
            c_array("demo_rr_q10", [q610(x) for x in rr]),
            f"#define DEMO_EXPECTED_CLASS {expected}u",
            "#endif",
            "",
        ]
    )
    OUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT} for {len(ecg)} samples; expected class index {expected} (N,S,V,F,Q order).")
