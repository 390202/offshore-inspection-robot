#!/usr/bin/env python3
"""Send one valid sensor frame to the local gateway server for testing."""

from __future__ import annotations

import argparse
import socket
import struct

from lora_gateway_server import FRAME_LENGTH, SOF, crc16_ccitt_false


def build_frame(
    device_id: int,
    sequence: int,
    raw: tuple[int, int, int],
    sensor_mv: tuple[int, int, int],
    status: int,
) -> bytes:
    payload = struct.pack(
        "<BBBH6HB",
        1,
        device_id,
        0x10,
        sequence,
        *raw,
        *sensor_mv,
        status,
    )
    body = SOF + payload
    crc = crc16_ccitt_false(payload)
    frame = body + struct.pack("<H", crc)
    if len(frame) != FRAME_LENGTH:
        raise AssertionError("internal frame length error")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a test MQ sensor frame.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--sequence", type=int, default=1)
    parser.add_argument("--raw", type=int, nargs=3, default=(0, 1, 0))
    parser.add_argument(
        "--mv", type=int, nargs=3, default=(0, 0, 0)
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = tuple(args.raw)
    sensor_mv = tuple(args.mv)
    frame = build_frame(args.device_id, args.sequence, raw, sensor_mv, 0)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(frame, (args.host, args.port))

    print(frame.hex(" "))


if __name__ == "__main__":
    main()
