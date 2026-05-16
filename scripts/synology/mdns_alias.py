#!/usr/bin/env python3
"""Publish a simple IPv4 `.local` alias via multicast DNS."""

from __future__ import annotations

import argparse
import ipaddress
import socket
import struct
import time


MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
TYPE_A = 1
TYPE_ANY = 255
CLASS_IN = 1


def encode_name(name: str) -> bytes:
    labels = name.rstrip(".").split(".")
    return b"".join(bytes([len(label)]) + label.encode("utf-8") for label in labels) + b"\x00"


def decode_name(packet: bytes, offset: int) -> tuple[str, int]:
    labels = []
    original_offset = offset
    jumped = False
    seen = set()
    while offset < len(packet):
        length = packet[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(packet):
                return "", original_offset + 2
            pointer = ((length & 0x3F) << 8) | packet[offset + 1]
            if pointer in seen:
                return "", original_offset + 2
            seen.add(pointer)
            if not jumped:
                original_offset = offset + 2
                jumped = True
            offset = pointer
            continue
        offset += 1
        labels.append(packet[offset:offset + length].decode("utf-8", errors="ignore"))
        offset += length
    return ".".join(labels), original_offset if jumped else offset


def questions(packet: bytes) -> list[tuple[str, int, int]]:
    if len(packet) < 12:
        return []
    qdcount = struct.unpack("!H", packet[4:6])[0]
    offset = 12
    parsed = []
    for _ in range(qdcount):
        name, offset = decode_name(packet, offset)
        if offset + 4 > len(packet):
            break
        qtype, qclass = struct.unpack("!HH", packet[offset:offset + 4])
        offset += 4
        parsed.append((name.rstrip(".").lower(), qtype, qclass & 0x7FFF))
    return parsed


def response(packet: bytes, alias: str, address: str, ttl: int) -> bytes:
    record = (
        encode_name(alias)
        + struct.pack("!HHIH", TYPE_A, 0x8000 | CLASS_IN, ttl, 4)
        + socket.inet_aton(address)
    )
    return packet[:2] + struct.pack("!HHHHH", 0x8400, 0, 1, 0, 0) + record


def run(alias: str, address: str, ttl: int) -> None:
    alias = alias.rstrip(".").lower()
    ipaddress.ip_address(address)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    sock.bind(("", MDNS_PORT))
    membership = socket.inet_aton(MDNS_GROUP) + socket.inet_aton("0.0.0.0")
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)

    print(f"Publishing {alias} -> {address} via mDNS", flush=True)
    while True:
        packet, source = sock.recvfrom(9000)
        if any(name == alias and qtype in (TYPE_A, TYPE_ANY) and qclass == CLASS_IN for name, qtype, qclass in questions(packet)):
            payload = response(packet, alias, address, ttl)
            sock.sendto(payload, source)
            sock.sendto(payload, (MDNS_GROUP, MDNS_PORT))
        time.sleep(0.01)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--address", required=True)
    parser.add_argument("--ttl", type=int, default=120)
    args = parser.parse_args()
    run(args.name, args.address, args.ttl)


if __name__ == "__main__":
    main()
