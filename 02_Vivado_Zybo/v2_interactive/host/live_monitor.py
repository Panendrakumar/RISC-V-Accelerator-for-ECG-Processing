"""Live laptop view of the Zybo Z7-10 ECG accelerator (v2 interactive bitstream).

While you press the board buttons (BTN1 = classify the selected beat,
BTN3 = self-test of all 16 stored beats, BTN2 = hold for the true label), this
window shows, at the same time as the board LEDs:
  - the ECG waveform of the beat the FPGA just classified,
  - a heart coloured by the predicted class (N green, S yellow, V red,
    F magenta, Q blue) with the class name,
  - the true label, whether the FPGA matched the Q6.10 reference, the measured
    latency and the five logits,
  - a 16-slot self-test strip and a mirror of LD0-LD2, the RGB LED and the switches.

Every class shown here is read back from the board (firmware mailbox at
0x6000 and the AXI GPIO) over the USB-JTAG cable through Vivado's JTAG-to-AXI
master. The laptop does not compute any prediction.

Run through the V: drive (Vivado fails on spaces in the real path):
  V:\\.venv\\Scripts\\python.exe V:\\02_Vivado_Zybo\\v2_interactive\\host\\live_monitor.py --program
  ...live_monitor.py              (board already programmed with the v2 bitstream + .ltx)
  ...live_monitor.py --simulate   (preview the window without a board; fake data)
Close Vivado's Hardware Manager first; only one program can use the JTAG cable.
"""

from __future__ import annotations

import argparse
import json
import math
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import tkinter as tk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

HERE = Path(__file__).absolute().parent          # keep V: form, do not resolve()
V2 = HERE.parent
ROOT = HERE.parents[2]
LTX = V2 / "ECG_ViT_Zybo_v2/ECG_ViT_Zybo_v2.runs/impl_1/zybo_vit_v2_top.ltx"
BIT = V2 / "zybo_vit_v2_interactive.bit"
ENGINE = HERE / "live_monitor_engine.tcl"
STOP = HERE / "live_monitor.stop"
DEMO_JSON = V2 / "firmware/demo_beats.json"
SPLIT = ROOT / "04_Model_Software/third_party_models/TinyTransformer/software/consistent_data_splits.npz"
VIVADO = r"C:\Xilinx\Vivado\2023.2\bin\vivado.bat"

NAMES = "NSVFQ"
LONG = {"N": "Normal", "S": "Supraventricular ectopic", "V": "Ventricular ectopic",
        "F": "Fusion", "Q": "Unknown / paced"}
COLOR = {"N": "#2ecc71", "S": "#f1c40f", "V": "#e74c3c", "F": "#e056fd", "Q": "#3498db"}
COLOR_NAME = {"N": "green", "S": "yellow", "V": "red", "F": "magenta", "Q": "blue"}
BG, PANEL, TEXT, MUTED, OFF = "#0f172a", "#1e293b", "#f1f5f9", "#94a3b8", "#334155"
MAGIC = 0xEC600002
FS = 360.0
SELFTEST_GAP_S = 4.0   # results this close together, in beat order, are one self-test run


def tcl_path(p: Path) -> str:
    return str(p).replace("\\", "/")


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


# --------------------------------------------------------------------------- data
def load_demo_beats():
    meta = json.loads(DEMO_JSON.read_text())["beats"]
    with np.load(SPLIT) as s:
        x = s["X_test"].reshape(-1, 198)
        rr = s["RR_test"]
        idx = [b["test_index"] for b in meta]
        waves, rrs = x[idx].astype(float), rr[idx].astype(float)
    beats = []
    for k, b in enumerate(meta):
        beats.append({"slot": k, "switch": b["switch_binary"], "test_index": b["test_index"],
                      "true": b["true"], "ref": b["q610_pred"], "note": b.get("note", ""),
                      "wave": waves[k], "rr": rrs[k]})
    return beats


# ---------------------------------------------------------------------- data sources
class BoardLink:
    """Runs the Vivado engine in the background and restarts it if it stops or hangs."""

    def __init__(self, out: queue.Queue, program: bool):
        self.out = out
        self.gen = 0
        self.proc = None
        self.closing = False
        self.last_line = time.time()
        self.start(program)

    def start(self, program: bool) -> None:
        if STOP.exists():
            STOP.unlink()
        self.gen += 1
        gen = self.gen
        args = [tcl_path(LTX), tcl_path(STOP), tcl_path(BIT) if program else "-"]
        cmd = ["cmd", "/c", VIVADO, "-mode", "batch", "-nojournal", "-nolog", "-notrace",
               "-source", tcl_path(ENGINE), "-tclargs", *args]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                cwd=str(HERE), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.proc = proc
        self.last_line = time.time() + 40          # grace period while Vivado starts

        def pump():
            for line in proc.stdout:
                line = line.strip()
                if gen != self.gen:
                    break
                if line.startswith(("POLL", "INFO", "FATAL", "WARN", "ALIVE", "ERROR", "RECOVER")):
                    self.last_line = max(self.last_line, time.time())
                    self.out.put(line)
            if gen == self.gen and not self.closing:
                self.out.put("EXIT")

        threading.Thread(target=pump, daemon=True).start()

    def kill(self) -> None:
        if self.proc and self.proc.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True)

    def restart(self) -> None:
        self.gen += 1                                  # ignore anything the old engine still prints
        self.kill()
        self.start(program=False)

    def stop(self) -> None:
        self.closing = True
        try:
            STOP.write_text("stop")
            if self.proc:
                self.proc.wait(timeout=5)
        except Exception:
            self.kill()
        finally:
            if STOP.exists():
                STOP.unlink()


def simulator(out: queue.Queue, beats, stop: threading.Event) -> None:
    """Fake board: idles, runs a BTN3 self-test, shows BTN2, repeats."""
    seq = 0
    logits_hex = ["00000000"] * 5
    mb = lambda cls, src, cyc: ["ec600002", "00000000", "00000002", f"{seq:08x}", f"{cls:08x}",
                                f"{cyc:08x}", f"{src:08x}", "00000000", *logits_hex]
    rgb = {0: 2, 1: 6, 2: 4, 3: 5, 4: 1}   # R,G,B bits for N,S,V,F,Q
    out.put("INFO simulation (no board)")
    out.put("INFO connected")
    cls = 0
    while not stop.is_set():
        out.put("POLL " + " ".join(mb(cls, 1, 3128915)) + " 00000000 00000000")
        time.sleep(2.0)
        for b in beats:                                    # self-test
            if stop.is_set():
                return
            seq += 1
            cls = NAMES.index(b["ref"])
            raw = [int(-800 + 1600 * (i == cls) + 100 * math.sin(i + seq)) for i in range(5)]
            logits_hex = [f"{v & 0xFFFFFFFF:08x}" for v in raw]
            gout = (cls + 1) | (rgb[cls] << 3)
            out.put("POLL " + " ".join(mb(cls, b["slot"] + 1, 3128915 + seq % 80)) + f" {gout:08x} 00000080")
            time.sleep(1.0)
            out.put("POLL " + " ".join(mb(cls, b["slot"] + 1, 3128915 + seq % 80)) + " 00000000 00000000")
            time.sleep(0.3)
        out.put("POLL " + " ".join(mb(cls, 16, 3128915)) + f" {7 | (2 << 3):08x} 00000000")
        time.sleep(3.0)
        out.put("POLL " + " ".join(mb(cls, 16, 3128915)) + f" {NAMES.index('S') + 1:08x} 00000049")
        time.sleep(2.0)                                   # BTN2 held on beat 9


# ---------------------------------------------------------------------------- GUI
class Monitor:
    def __init__(self, root: tk.Tk, beats, src_queue: queue.Queue, simulate: bool):
        self.root, self.beats, self.q = root, beats, src_queue
        self.link = None                  # BoardLink when connected to real hardware
        self.last_seq = None
        self.last_src, self.last_t = None, 0.0
        self.heart_scale = 1.0
        self.heart_color = OFF
        self.connected = False
        self.last_alive = time.time()

        self.s = s = max(1.0, root.winfo_fpixels("1i") / 96.0)   # Windows display scaling
        px = self.px = lambda v: int(round(v * s))
        root.title("ECG Accelerator - Live Board Monitor (Zybo Z7-10)")
        root.configure(bg=BG)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(px(1280), sw - 20)}x{min(px(780), sh - 80)}+5+5")
        root.minsize(min(px(1000), sw - 20), min(px(620), sh - 80))
        if sys.platform == "win32":
            try:
                root.state("zoomed")
            except tk.TclError:
                pass

        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(top, text="RISC-V ECG Accelerator  |  Live view of the FPGA board", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        self.status = tk.Label(top, text="Simulation (no board)" if simulate else "Starting Vivado ...",
                               bg=BG, fg="#fbbf24", font=("Segoe UI", 11))
        self.status.pack(side="right")

        self.banner = tk.Label(root, text="Press BTN3 on the board for the self-test, or set the switches and press BTN1",
                               bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold"), pady=8)
        self.banner.pack(fill="x", padx=16, pady=4)

        # Bottom: legend and self-test strip (packed first so they always stay visible)
        self.legend()
        bottom = tk.Frame(root, bg=PANEL)
        bottom.pack(side="bottom", fill="x", padx=16, pady=(4, 6))
        tk.Label(bottom, text="Stored beats (switch value): fill = FPGA result  |  outline = true label", bg=PANEL,
                 fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(6, 0))
        self.strip = tk.Canvas(bottom, height=px(76), bg=PANEL, highlightthickness=0)
        self.strip.pack(fill="x", padx=10, pady=4)
        self.slots = []
        self.slot_results = {}
        self.strip.bind("<Configure>", lambda e: self.draw_strip_frame())

        mid = tk.Frame(root, bg=BG)
        mid.pack(fill="both", expand=True, padx=16, pady=4)

        # Heart and result panel (packed before the plot so it keeps its width)
        right = tk.Frame(mid, bg=PANEL, width=px(470))
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        # ECG plot
        left = tk.Frame(mid, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.fig = Figure(figsize=(4, 2.5), dpi=int(100 * s), facecolor=PANEL)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)
        self.draw_wave(None, None)
        self.heart = tk.Canvas(right, width=px(440), height=px(200), bg=PANEL, highlightthickness=0)
        self.heart.pack(pady=(10, 0))
        self.heart_id = self.heart.create_polygon(self.heart_points(1.0), fill=OFF, outline="", smooth=True)
        self.code_text = self.heart.create_text(px(220), px(100), text="", fill="#0f172a", font=("Consolas", 26, "bold"))
        self.cls_label = tk.Label(right, text="Waiting for the board", bg=PANEL, fg=TEXT, font=("Segoe UI", 20, "bold"),
                                  wraplength=px(450))
        self.cls_label.pack()
        self.cls_sub = tk.Label(right, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 12))
        self.cls_sub.pack()
        self.details = tk.Label(right, text="", bg=PANEL, fg=TEXT, font=("Consolas", 10), justify="left", anchor="w",
                                wraplength=px(440))
        self.details.pack(fill="x", padx=18, pady=(10, 4))
        self.check = tk.Label(right, text="", bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold"), wraplength=px(440))
        self.check.pack(pady=(2, 6))

        # Board LED / switch mirror
        leds = tk.Frame(right, bg=PANEL)
        leds.pack(pady=4)
        tk.Label(leds, text="Board LEDs:", bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).grid(row=0, column=0, padx=4)
        self.led_cv = tk.Canvas(leds, width=px(250), height=px(46), bg=PANEL, highlightthickness=0)
        self.led_cv.grid(row=0, column=1)
        self.led_ids = []
        for i, name in enumerate(["LD2", "LD1", "LD0"]):
            x = px(22 + i * 52)
            self.led_ids.append(self.led_cv.create_oval(x - px(11), px(6), x + px(11), px(28), fill=OFF, outline=""))
            self.led_cv.create_text(x, px(39), text=name, fill=MUTED, font=("Segoe UI", 8))
        self.rgb_id = self.led_cv.create_oval(px(190), px(4), px(216), px(30), fill=OFF, outline="")
        self.led_cv.create_text(px(203), px(39), text="RGB LD6", fill=MUTED, font=("Segoe UI", 8))
        self.sw_label = tk.Label(right, text="Switches SW3..SW0: ----   Buttons: -", bg=PANEL, fg=MUTED,
                                 font=("Consolas", 10))
        self.sw_label.pack(pady=(2, 8))


        root.protocol("WM_DELETE_WINDOW", self.close)
        self.on_close = None
        root.after(50, self.poll)
        root.after(30, self.animate)

    # ---------------- drawing helpers
    def heart_points(self, scale: float):
        pts = []
        for k in range(60):
            t = 2 * math.pi * k / 60
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            k = 5.0 * scale * self.s
            pts += [self.px(220) + k * x, self.px(98) - k * y]
        return pts

    def legend(self):
        f = tk.Frame(self.root, bg=BG)
        f.pack(side="bottom", fill="x", padx=16, pady=(0, 8))
        for c in NAMES:
            tk.Label(f, text="  ", bg=COLOR[c]).pack(side="left", padx=(10, 4))
            tk.Label(f, text=f"{c} = {LONG[c]} (LED {NAMES.index(c) + 1:03b}, {COLOR_NAME[c]})", bg=BG, fg=MUTED,
                     font=("Segoe UI", 10)).pack(side="left")

    def draw_strip_frame(self):
        self.strip.delete("all")
        w = max(self.strip.winfo_width(), self.px(800))
        px = self.px
        n = len(self.beats)
        cell = (w - 10) / n
        self.slots = []
        for b in self.beats:
            x0 = 5 + b["slot"] * cell
            box = self.strip.create_rectangle(x0 + px(3), px(5), x0 + cell - px(3), px(52), fill=OFF,
                                              outline=COLOR[b["true"]], width=px(3))
            txt = self.strip.create_text(x0 + cell / 2, px(29), text="", fill="#0f172a", font=("Segoe UI", 15, "bold"))
            self.strip.create_text(x0 + cell / 2, px(66), text=f"{b['slot']} ({b['switch']})", fill=MUTED, font=("Consolas", 8))
            self.slots.append((box, txt))
        for slot, cls in self.slot_results.items():
            self.paint_slot(slot, cls)

    def paint_slot(self, slot, cls):
        if not self.slots:
            return
        box, txt = self.slots[slot]
        if cls is None:
            self.strip.itemconfigure(box, fill=OFF)
            self.strip.itemconfigure(txt, text="")
        else:
            self.strip.itemconfigure(box, fill=COLOR[cls])
            self.strip.itemconfigure(txt, text=cls)

    def draw_wave(self, beat, cls):
        ax = self.ax
        ax.clear()
        ax.set_facecolor("#0b1220")
        for s in ax.spines.values():
            s.set_color(OFF)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.grid(True, color="#1f2a3d", linewidth=0.8)
        t = (np.arange(198) - 99) / FS * 1000.0
        if beat is None:
            ax.set_title("ECG beat (waiting for a result from the board)", color=MUTED, fontsize=12)
            ax.plot(t, np.zeros(198), color=OFF)
        else:
            col = COLOR[cls] if cls else "#cbd5e1"
            ax.plot(t, beat["wave"], color=col, linewidth=2.2)
            ax.axvline(0, color=MUTED, linestyle="--", linewidth=1)
            ax.annotate("R peak", xy=(0, beat["wave"][99]), xytext=(25, beat["wave"][99]),
                        color=MUTED, fontsize=9, va="center")
            title = (f"Stored beat {beat['slot']} (switches {beat['switch']})  -  MIT-BIH test beat #{beat['test_index']}\n"
                     f"pre-RR {beat['rr'][0]:.3f} s   post-RR {beat['rr'][1]:.3f} s")
            ax.set_title(title, color=TEXT, fontsize=11)
        ax.set_xlabel("time from R peak (ms)", color=MUTED)
        ax.set_ylabel("normalized amplitude", color=MUTED)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ---------------- events from the board
    def poll(self):
        try:
            while True:
                self.handle(self.q.get_nowait())
        except queue.Empty:
            pass
        if self.link and not self.link.closing and time.time() - self.link.last_line > 10:
            self.status.configure(text="No answer from Vivado for 10 s - restarting the link ...", fg="#fbbf24")
            self.connected = False
            self.link.restart()
        self.root.after(40, self.poll)

    def handle(self, line: str):
        if line.startswith("POLL"):
            self.last_alive = time.time()
            if not self.connected:
                self.connected = True
                self.status.configure(text="Connected to the board over USB-JTAG", fg="#4ade80")
            w = [int(v, 16) for v in line.split()[1:]]
            if len(w) < 15:
                return
            mb, gout, gin = w[:13], w[13], w[14]
            if mb[0] != MAGIC:
                self.banner.configure(text="Board is not running the v2 interactive firmware (wrong magic). "
                                           "Program zybo_vit_v2_interactive.bit", bg="#7f1d1d")
                return
            seq = mb[3]
            if self.last_seq is None:
                self.last_seq = seq                     # ignore results from before we started
            elif seq == 0 and self.last_seq != 0:
                self.last_seq = 0                       # firmware restarted (BTN0 reset)
                self.board_reset()
            elif seq != self.last_seq:
                self.last_seq = seq
                self.new_result(mb[6], mb[4], mb[5], [s32(v) for v in mb[8:13]])
            self.mirror(gout, gin)
        elif line.startswith("ALIVE"):
            self.last_alive = time.time()
        elif line.startswith("INFO"):
            msg = line[5:]
            if "programming" in msg:
                self.status.configure(text="Programming the FPGA ...", fg="#fbbf24")
            elif "connected" in msg and not self.connected:
                self.status.configure(text="Connected, reading the board ...", fg="#4ade80")
        elif line.startswith(("FATAL", "ERROR")):
            self.status.configure(text=line[:90], fg="#f87171")
            self.banner.configure(text=line, bg="#7f1d1d")
        elif line.startswith(("WARN", "RECOVER")):
            self.status.configure(text="Board reset or link lost - reconnecting ...", fg="#fbbf24")
            self.connected = False
        elif line == "EXIT":
            if self.link and not self.link.closing:
                self.status.configure(text="Vivado link stopped - restarting ...", fg="#fbbf24")
                self.connected = False
                self.root.after(2000, self.link.restart)

    def new_result(self, source: int, cls_idx: int, cycles: int, logits):
        now = time.time()
        cls = NAMES[cls_idx] if cls_idx < 5 else "?"
        if 1 <= source <= len(self.beats):
            beat = self.beats[source - 1]
            slot = beat["slot"]
            in_test = (self.last_src is not None and source == self.last_src + 1
                       and now - self.last_t < SELFTEST_GAP_S)
            if slot == 0:                                  # a self-test always starts at beat 0
                for k in list(self.slot_results):
                    self.slot_results[k] = None
                    self.paint_slot(k, None)
            if in_test:
                mode = f"Self-test (BTN3): beat {slot + 1} of {len(self.beats)}"
            else:
                mode = f"Stored beat {slot} (switches {beat['switch']})"
            self.slot_results[slot] = cls
            self.paint_slot(slot, cls)
            self.draw_wave(beat, cls)
            match = cls == beat["ref"]
            correct = cls == beat["true"]
            self.check.configure(
                text=("FPGA = Q6.10 reference \u2714" if match else "FPGA differs from Q6.10 reference \u2718")
                + ("  |  correct vs true label" if correct else "  |  model mistake (true label " + beat["true"] + ")"),
                fg="#4ade80" if match else "#f87171")
            true_txt = f"{beat['true']} - {LONG[beat['true']]}"
            note = beat["note"] if beat["note"] and "golden" not in beat["note"] else ""
        else:
            mode, beat, true_txt, note = "Beat sent from the laptop", None, "(laptop beat)", ""
            self.draw_wave(None, None)
            self.check.configure(text="")
        self.last_src, self.last_t = source, now

        col = COLOR.get(cls, OFF)
        self.heart_color = col
        self.heart.itemconfigure(self.heart_id, fill=col)
        self.heart.itemconfigure(self.code_text, text=f"{cls_idx + 1:03b}" if cls_idx < 5 else "")
        self.heart_scale = 1.22
        self.cls_label.configure(text=f"{LONG.get(cls, '?')} ({cls})", fg=col)
        self.cls_sub.configure(text=mode)
        ms = cycles / 1e5
        lg = " ".join(f"{n}{v / 1024:+.1f}" for n, v in zip(NAMES, logits))
        self.details.configure(text=f"True label : {true_txt}\n"
                                    f"Latency    : {cycles:,} cycles = {ms:.2f} ms @ 100 MHz\n"
                                    f"Logits     : {lg}"
                                    + (f"\nNote       : {note}" if note else ""))
        self.banner.configure(text=f"{mode}  ->  FPGA says {LONG.get(cls, '?')} ({cls}), "
                                   f"LEDs {cls_idx + 1:03b}, {COLOR_NAME.get(cls, '')}", bg=PANEL)

    def board_reset(self):
        for k in list(self.slot_results):
            self.slot_results[k] = None
            self.paint_slot(k, None)
        self.last_src = None
        self.heart.itemconfigure(self.heart_id, fill=OFF)
        self.heart.itemconfigure(self.code_text, text="")
        self.cls_label.configure(text="Board was reset", fg=TEXT)
        self.cls_sub.configure(text="")
        self.details.configure(text="")
        self.check.configure(text="")
        self.draw_wave(None, None)
        self.banner.configure(text="Board reset (BTN0). Press BTN3 for the self-test, or set the switches and press BTN1",
                              bg=PANEL)

    def mirror(self, gout: int, gin: int):
        code = gout & 7
        r, g, b = (gout >> 5) & 1, (gout >> 4) & 1, (gout >> 3) & 1
        for i, lid in enumerate(self.led_ids):            # LD2, LD1, LD0
            on = (code >> (2 - i)) & 1
            self.led_cv.itemconfigure(lid, fill="#22c55e" if on else OFF)
        rgb = "#%02x%02x%02x" % (255 * r, 220 * g, 255 * b) if (r or g or b) else OFF
        self.led_cv.itemconfigure(self.rgb_id, fill=rgb)
        sw = gin & 0xF
        btn = (gin >> 4) & 0xF
        pressed = " ".join(f"BTN{i}" for i in range(4) if (btn >> i) & 1) or "-"
        self.sw_label.configure(text=f"Switches SW3..SW0: {sw:04b} (beat {sw})   Buttons: {pressed}")

        if code == 7 and g and not r:
            self.banner.configure(text="SELF-TEST PASSED: all stored beats match the Q6.10 reference (LEDs 111, green)",
                                  bg="#166534")
        elif code == 6 and r:
            self.banner.configure(text="SELF-TEST FAILED: an FPGA result differed (blinking 110, red)", bg="#7f1d1d")
        elif 1 <= code <= 5 and not (r or g or b) and (btn >> 2) & 1:
            t = NAMES[code - 1]
            self.banner.configure(text=f"BTN2 held: TRUE label of beat {sw} is {LONG[t]} ({t}), LEDs {code:03b}, RGB off",
                                  bg="#1e3a8a")

    def animate(self):
        if self.heart_scale > 1.0:
            self.heart_scale = max(1.0, self.heart_scale - 0.02)
            self.heart.coords(self.heart_id, *self.heart_points(self.heart_scale))
        self.root.after(30, self.animate)

    def close(self):
        if self.on_close:
            self.on_close()
        self.root.destroy()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--program", action="store_true", help="program zybo_vit_v2_interactive.bit before monitoring")
    ap.add_argument("--simulate", action="store_true", help="fake data, no board needed")
    ap.add_argument("--exit-after", type=float, default=0, help="close automatically after N seconds (testing)")
    ap.add_argument("--snapshot", default="", help="save a PNG of the window just before --exit-after (testing)")
    args = ap.parse_args()

    if not args.simulate:
        if " " in str(HERE):
            raise SystemExit("Run through the V: drive, e.g. V:\\02_Vivado_Zybo\\v2_interactive\\host\\live_monitor.py")
        for p in (LTX, ENGINE, VIVADO) + ((BIT,) if args.program else ()):
            if not Path(p).exists():
                raise SystemExit(f"Missing file: {p}")

    beats = load_demo_beats()
    q: queue.Queue = queue.Queue()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)      # sharp text on scaled displays
        except Exception:
            pass
    root = tk.Tk()
    mon = Monitor(root, beats, q, args.simulate)

    if args.simulate:
        stop = threading.Event()
        threading.Thread(target=simulator, args=(q, beats, stop), daemon=True).start()
        mon.on_close = stop.set
    else:
        mon.link = BoardLink(q, args.program)
        mon.on_close = mon.link.stop

    if args.exit_after:
        if args.snapshot:
            def snap():
                from PIL import ImageGrab
                root.lift()
                root.attributes("-topmost", True)
                root.update()
                x, y = root.winfo_rootx(), root.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(args.snapshot)
            root.after(int(args.exit_after * 1000) - 300, snap)
        root.after(int(args.exit_after * 1000), mon.close)
    root.mainloop()


if __name__ == "__main__":
    main()
