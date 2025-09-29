#!/usr/bin/env python3
"""
PC-side logger for Arduino lick events.
- Reads serial lines at 9600 baud (configurable).
- Extracts timestamps for lick events from lines containing the token: '\tlick\t'
- Writes to CSV with columns: timestamp_ms, lick_number
- Rotates to a new CSV every N minutes (configurable).
Usage:
  python pc_lick_logger.py --port /dev/ttyACM0 --baud 9600 --minutes 15 --dir ./logs
"""
import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime, timedelta

try:
    import serial
    from serial.tools import list_ports
except Exception as e:
    print("ERROR: pyserial not installed. Install with: pip install pyserial", file=sys.stderr)
    raise

LICK_RE = re.compile(r'(\d+)\tlick\t')

def suggest_ports():
    ports = list(list_ports.comports())
    if not ports:
        return "No serial ports found."
    s = ["Detected serial ports:"]
    for p in ports:
        s.append(f"  - {p.device} : {p.description}")
    return "\n".join(s)

def open_csv(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = os.path.join(log_dir, f"licks_{stamp}.csv")
    f = open(fname, "w", newline="", encoding="utf-8")
    w = csv.writer(f)
    w.writerow(["timestamp_ms", "lick_number"])
    print(f"[logger] Writing to {fname}")
    return f, w, time.time()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=False, default=None, help="Serial port (e.g., /dev/ttyACM0, COM3). If omitted, tries to auto-detect.")
    ap.add_argument("--baud", type=int, default=9600, help="Baud rate")
    ap.add_argument("--minutes", type=int, default=15, help="Rotation interval in minutes")
    ap.add_argument("--dir", default="logs", help="Directory to store CSV files")
    args = ap.parse_args()

    if args.port is None:
        # Try to pick the first Arduino-like port
        ports = list(list_ports.comports())
        if not ports:
            print("No serial port provided and none detected.\n" + suggest_ports(), file=sys.stderr)
            sys.exit(2)
        args.port = ports[0].device
        print(f"[logger] Auto-selected port: {args.port}")

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except Exception as e:
        print(f"Could not open serial port {args.port}: {e}\n" + suggest_ports(), file=sys.stderr)
        sys.exit(2)

    csv_file, writer, opened_at = open_csv(args.dir)
    lick_count = 0
    rotate_after = args.minutes * 60.0

    print("[logger] Listening... Press Ctrl+C to stop.")
    try:
        buf = b""
        while True:
            line = ser.readline()
            if not line:
                # small sleep to avoid busy loop
                time.sleep(0.01)
                # check rotation even if no lines
            else:
                try:
                    s = line.decode("utf-8", errors="replace").strip()
                except Exception:
                    s = str(line)
                # Example line contains:  "<...>\t123456\tlick\t<...>"
                m = LICK_RE.search(s)
                if m:
                    lick_ts = int(m.group(1))
                    lick_count += 1
                    writer.writerow([lick_ts, lick_count])
                    csv_file.flush()
                    # Optional console echo:
                    print(f"LICK #{lick_count} @ {lick_ts} ms")

            # rotation check
            if (time.time() - opened_at) >= rotate_after:
                try:
                    csv_file.flush()
                    csv_file.close()
                except Exception:
                    pass
                csv_file, writer, opened_at = open_csv(args.dir)
                # keep lick_count continuous across files

    except KeyboardInterrupt:
        print("\n[logger] Stopping...")
    finally:
        try:
            csv_file.flush()
            csv_file.close()
        except Exception:
            pass
        try:
            ser.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
