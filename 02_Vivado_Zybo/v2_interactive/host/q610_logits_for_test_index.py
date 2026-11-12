"""Print the Q6.10 software-reference logits (raw integers) for given test-split indices.

Usage: python q610_logits_for_test_index.py 0 4 353
Used to compare with the raw logits the FPGA writes to BRAM 0x6020.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "03_HW_SW_Validation/vitis_hls/z7_tiny_ecg_vit"))
import fixed_point_reference as fpr  # noqa: E402

with np.load(fpr.SPLIT) as s:
    x, rr, y = s["X_test"], s["RR_test"], s["y_test"]
x = x.reshape(len(y), -1)
idx = np.asarray([int(a) for a in sys.argv[1:]] or [0])
logits = fpr.infer_batch(x[idx], rr[idx], fpr.load_weights())
for i, row in zip(idx, logits):
    raw = [int(round(v * 1024)) for v in row]
    print(f"test#{i} true={'NSVFQ'[int(y[i])]} q610_class={'NSVFQ'[int(np.argmax(row))]} raw_logits={raw}")
