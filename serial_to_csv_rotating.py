#!/usr/bin/env python3
import argparse
import csv
import os
import sys
import time
from datetime import datetime, timedelta

try:
    import serial
    import serial.tools.list_ports as list_ports
except Exception:
    print("ERROR: Necesitas instalar pyserial:  pip install pyserial", file=sys.stderr)
    raise

def guess_port():
    ports = list(list_ports.comports())
    ports.sort(key=lambda p: (("ACM" not in p.device), ("USB" not in p.device), p.device))
    return [p.device for p in ports]

def open_serial(port, baud):
    return serial.Serial(port, baudrate=baud, timeout=1)

def parse_line(line):
    # Espera: "<timestamp_ms> <cadena>"
    if not line:
        return None, None
    line = line.strip()
    if not line:
        return None, None
    parts = line.split(None, 1)
    if len(parts) != 2:
        return None, None
    ts_str, cadena = parts
    # validar número
    try:
        float(ts_str)
    except Exception:
        return None, None
    return ts_str, cadena

def new_csv_writer(outdir):
    ts = datetime.now()
    fname = ts.strftime("log_%Y%m%d_%H%M%S.csv")
    fpath = os.path.join(outdir, fname)
    f = open(fpath, "w", newline="", encoding="utf-8")
    writer = csv.writer(f)
    writer.writerow(["iso_time", "device_timestamp_ms", "cadena"])
    f.flush()
    print(f"[+] Nuevo archivo: {fpath}")
    return f, writer, ts

def main():
    ap = argparse.ArgumentParser(description="Leer Arduino por Serial y guardar CSV rotando cada N minutos.")
    ap.add_argument("--port", "-p", help="Puerto serial (ej. /dev/ttyACM0, /dev/ttyUSB0, COM3). Si no se da, intenta detectar.")
    ap.add_argument("--baud", "-b", type=int, default=115200, help="Baudrate (default: 115200).")
    ap.add_argument("--outdir", "-d", required=True, help="Directorio de salida para los CSV.")
    ap.add_argument("--period-min", "-m", type=float, default=2.0, help="Minutos por archivo (default: 2).")
    ap.add_argument("--show", action="store_true", help="Imprime en consola cada fila válida.")
    args = ap.parse_args()

    # Detectar puerto si no se especifica
    port = args.port
    if not port:
        candidates = guess_port()
        if not candidates:
            print("No se detectaron puertos seriales.", file=sys.stderr)
            sys.exit(2)
        print("Detectados:", ", ".join(candidates))
        port = candidates[0]
        print("Usando puerto:", port)

    # Preparar salida
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    # Abrir serial
    try:
        ser = open_serial(port, args.baud)
    except Exception as e:
        print(f"No se pudo abrir el puerto {port}: {e}", file=sys.stderr)
        sys.exit(1)

    # Crear primer CSV
    f, writer, created_at = new_csv_writer(outdir)
    rotate_after = created_at + timedelta(minutes=args.period_min)

    print(f"Grabando en {outdir}. Rotación cada {args.period_min} min. Ctrl+C para salir.")
    try:
        while True:
            try:
                raw = ser.readline()
            except serial.SerialException as e:
                print(f"Error de lectura serial: {e}", file=sys.stderr)
                time.sleep(0.5)
                continue

            if not raw:
                # timeout
                pass
            else:
                try:
                    line = raw.decode("utf-8", errors="replace").strip()
                except Exception:
                    line = raw.decode("latin1", errors="replace").strip()

                ts_str, cadena = parse_line(line)
                if ts_str is not None:
                    row = [datetime.now().isoformat(timespec="seconds"), ts_str, cadena]
                    writer.writerow(row)
                    f.flush()
                    if args.show:
                        print(",".join(row))

            # ¿Toca rotar?
            if datetime.now() >= rotate_after:
                try:
                    f.close()
                except Exception:
                    pass
                f, writer, created_at = new_csv_writer(outdir)
                rotate_after = created_at + timedelta(minutes=args.period_min)

    except KeyboardInterrupt:
        print("\nCerrando...")
    finally:
        try:
            ser.close()
        except Exception:
            pass
        try:
            f.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
