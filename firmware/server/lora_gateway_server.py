#!/usr/bin/env python3
"""Receive and decode sensor frames from a LoRa gateway.

The MCU protocol is a 22-byte little-endian frame:

    offset  size  field
    0       2     SOF, 0xAA 0x55
    2       1     protocol version, 1
    3       1     device id
    4       1     frame type, 0x10
    5       2     sequence number
    7       6     MQ-5/MQ-6/MQ-8 digital states (0 normal, 1 over threshold)
    13      6     reserved voltage fields, always zero in digital mode
    19      1     status flags
    20      2     CRC-16/CCITT-FALSE over bytes 2..19
"""

from __future__ import annotations

import argparse
import csv
import json
import signal
import socket
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path


FRAME_LENGTH = 22
SOF = b"\xAA\x55"
PROTOCOL_VERSION = 1
FRAME_TYPE_SENSORS = 0x10


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class SensorFrame:
    device_id: int
    sequence: int
    raw: tuple[int, int, int]
    sensor_mv: tuple[int, int, int]
    status: int


def decode_frame(frame: bytes) -> SensorFrame:
    if len(frame) != FRAME_LENGTH:
        raise ValueError("invalid frame length")
    if frame[:2] != SOF:
        raise ValueError("invalid frame header")

    version, device_id, frame_type, sequence, raw0, raw1, raw2, mv0, mv1, mv2, status = (
        struct.unpack_from("<BBBH6HB", frame, 2)
    )

    if version != PROTOCOL_VERSION:
        raise ValueError(f"unsupported protocol version {version}")
    if frame_type != FRAME_TYPE_SENSORS:
        raise ValueError(f"unsupported frame type {frame_type:#04x}")

    expected_crc = struct.unpack_from("<H", frame, 20)[0]
    actual_crc = crc16_ccitt_false(frame[2:20])
    if actual_crc != expected_crc:
        raise ValueError(
            f"CRC mismatch: got {expected_crc:#06x}, expected {actual_crc:#06x}"
        )

    return SensorFrame(
        device_id=device_id,
        sequence=sequence,
        raw=(raw0, raw1, raw2),
        sensor_mv=(mv0, mv1, mv2),
        status=status,
    )


class FrameStreamDecoder:
    """Resynchronize and decode frames from UDP datagrams or a TCP byte stream."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> tuple[list[SensorFrame], int]:
        self._buffer.extend(data)
        frames: list[SensorFrame] = []
        crc_errors = 0

        while True:
            start = self._buffer.find(SOF)
            if start < 0:
                if self._buffer[-1:] == SOF[:1]:
                    self._buffer[:] = self._buffer[-1:]
                else:
                    self._buffer.clear()
                break

            if start:
                del self._buffer[:start]

            if len(self._buffer) < FRAME_LENGTH:
                break

            candidate = bytes(self._buffer[:FRAME_LENGTH])
            try:
                frames.append(decode_frame(candidate))
                del self._buffer[:FRAME_LENGTH]
            except ValueError:
                crc_errors += 1
                del self._buffer[0]

        return frames, crc_errors


class SensorServer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.stop_event = threading.Event()
        self.csv_lock = threading.Lock()
        self.csv_path = Path(args.csv)
        self.csv_file = None
        self.csv_writer = None
        self.valid_frames = 0
        self.bad_frames = 0

    def start(self) -> None:
        self._open_csv()

        udp_thread = threading.Thread(
            target=self._udp_worker, name="udp-listener", daemon=True
        )
        tcp_thread = threading.Thread(
            target=self._tcp_worker, name="tcp-listener", daemon=True
        )
        udp_thread.start()
        tcp_thread.start()

        print(
            f"Listening on {self.args.bind}: UDP {self.args.udp_port}, "
            f"TCP {self.args.tcp_port}"
        )
        print(f"CSV output: {self.csv_path.resolve()}")

        while not self.stop_event.wait(0.5):
            pass

        self._close_csv()

    def stop(self, _signum: int | None = None, _frame: object | None = None) -> None:
        self.stop_event.set()

    def _open_csv(self) -> None:
        needs_header = not self.csv_path.exists() or self.csv_path.stat().st_size == 0
        self.csv_file = self.csv_path.open("a", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)
        if needs_header:
            self.csv_writer.writerow(
                [
                    "timestamp",
                    "remote",
                    "device_id",
                    "sequence",
                    "mq5_raw",
                    "mq6_raw",
                    "mq8_raw",
                    "mq5_mv",
                    "mq6_mv",
                    "mq8_mv",
                    "mq5_alarm",
                    "mq6_alarm",
                    "mq8_alarm",
                    "status",
                ]
            )
            self.csv_file.flush()

    def _close_csv(self) -> None:
        with self.csv_lock:
            if self.csv_file is not None:
                self.csv_file.flush()
                self.csv_file.close()
                self.csv_file = None
                self.csv_writer = None

    def _record(
        self, sensor_frame: SensorFrame, remote: str, transport: str
    ) -> None:
        now = time.time()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        record = {
            "timestamp": timestamp,
            "transport": transport,
            "remote": remote,
            "device_id": sensor_frame.device_id,
            "sequence": sensor_frame.sequence,
            "raw": list(sensor_frame.raw),
            "sensor_mv": list(sensor_frame.sensor_mv),
            "threshold_alarm": [bool(value) for value in sensor_frame.raw],
            "status": sensor_frame.status,
        }

        if self.args.json:
            print(json.dumps(record, ensure_ascii=False), flush=True)
        else:
            print(
                f"{timestamp} {transport} {remote} "
                f"dev={sensor_frame.device_id} seq={sensor_frame.sequence} "
                f"alarm={tuple(bool(value) for value in sensor_frame.raw)} "
                f"status={sensor_frame.status:#04x}",
                flush=True,
            )

        with self.csv_lock:
            if self.csv_writer is not None:
                self.csv_writer.writerow(
                    [
                        timestamp,
                        remote,
                        sensor_frame.device_id,
                        sensor_frame.sequence,
                        *sensor_frame.raw,
                        *sensor_frame.sensor_mv,
                        *[int(bool(value)) for value in sensor_frame.raw],
                        sensor_frame.status,
                    ]
                )
                self.csv_file.flush()

    def _consume(self, decoder: FrameStreamDecoder, data: bytes, remote: str, transport: str) -> None:
        frames, bad_frames = decoder.feed(data)
        self.bad_frames += bad_frames
        for sensor_frame in frames:
            self.valid_frames += 1
            self._record(sensor_frame, remote, transport)

    def _udp_worker(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.args.bind, self.args.udp_port))
        sock.settimeout(0.5)

        decoders: dict[str, FrameStreamDecoder] = {}
        while not self.stop_event.is_set():
            try:
                data, address = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            remote = f"{address[0]}:{address[1]}"
            decoder = decoders.setdefault(remote, FrameStreamDecoder())
            self._consume(decoder, data, remote, "udp")

        sock.close()

    def _tcp_worker(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.args.bind, self.args.tcp_port))
        listener.listen(8)
        listener.settimeout(0.5)

        while not self.stop_event.is_set():
            try:
                client, address = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            thread = threading.Thread(
                target=self._tcp_client_worker,
                args=(client, address),
                name=f"tcp-{address[0]}:{address[1]}",
                daemon=True,
            )
            thread.start()

        listener.close()

    def _tcp_client_worker(
        self, client: socket.socket, address: tuple[str, int]
    ) -> None:
        remote = f"{address[0]}:{address[1]}"
        decoder = FrameStreamDecoder()
        client.settimeout(0.5)

        try:
            while not self.stop_event.is_set():
                try:
                    data = client.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    break
                self._consume(decoder, data, remote, "tcp")
        finally:
            client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode STM32 MQ sensor frames received from a LoRa gateway."
    )
    parser.add_argument("--bind", default="0.0.0.0", help="local bind address")
    parser.add_argument("--udp-port", type=int, default=5000, help="UDP listen port")
    parser.add_argument("--tcp-port", type=int, default=5001, help="TCP listen port")
    parser.add_argument("--csv", default="lora_data.csv", help="CSV output path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print one JSON object per valid frame",
    )
    return parser.parse_args()


def main() -> None:
    server = SensorServer(parse_args())
    signal.signal(signal.SIGINT, server.stop)
    signal.signal(signal.SIGTERM, server.stop)
    server.start()


if __name__ == "__main__":
    main()
