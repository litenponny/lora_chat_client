#!/usr/bin/env python3
import argparse
import re
import threading

import serial

PORT = "/dev/ttyACM0"
BAUDRATE = 115200

SEND_TEXT_CMD = 0x02
MAX_CHAT_LEN = 16  # wrap at the badge screen's 16-char line width

DATA_FIELD_RE = re.compile(r"data=([0-9a-fA-F ]+)")
SRC_FIELD_RE = re.compile(r"src=(0x[0-9a-fA-F]+)")

def spaced_hex(data):
    return " ".join(f"{b:02x}" for b in data)

def reader_loop(ser, stop_event):
    buf = b""
    while not stop_event.is_set():
        chunk = ser.read(ser.in_waiting or 1)
        if not chunk:
            continue
        buf += chunk
        while b"\n" in buf:
            raw_line, buf = buf.split(b"\n", 1)
            line = raw_line.decode(errors="replace").strip()
            match = DATA_FIELD_RE.search(line)
            if not match:
                continue
            data = bytes(int(tok, 16) for tok in match.group(1).split())
            if not data or data[0] != SEND_TEXT_CMD:
                continue
            src_match = SRC_FIELD_RE.search(line)
            src = src_match.group(1) if src_match else "unknown"
            print(f"\n[{src}] {data[1:].decode(errors='replace')}")

def send_chat(ser, text, debug=False):
    for i in range(0, len(text), MAX_CHAT_LEN):
        chunk = text[i : i + MAX_CHAT_LEN].encode("ascii", errors="replace")
        payload = bytes([SEND_TEXT_CMD]) + chunk
        command = f"lora tx {spaced_hex(payload)}\r\n"
        ser.write(command.encode("ascii"))
        if debug:
            print(f"sent: {command.strip()}")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print the raw 'lora tx 02 ...' command for each outgoing chat message",
    )
    return parser.parse_args()

def main():
    args = parse_args()

    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.2,
    )

    stop_event = threading.Event()
    reader_thread = threading.Thread(target=reader_loop, args=(ser, stop_event), daemon=True)
    reader_thread.start()

    print("Chat ready - type a message and press enter (Ctrl-C to quit)")
    try:
        while True:
            text = input("> ")
            if text:
                send_chat(ser, text, debug=args.debug)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        stop_event.set()
        reader_thread.join()
        ser.close()

if __name__ == "__main__":
    main()
