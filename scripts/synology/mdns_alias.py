#!/usr/bin/env python3
"""Publish a simple IPv4 `.local` alias via multicast DNS."""

from __future__ import annotations

import argparse
import ipaddress
import socket
import select
import struct
import time


MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
TYPE_A = 1
TYPE_AAAA = 28
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


def record(alias: str, rtype: int, packed_address: bytes, ttl: int) -> bytes:
    return (
        encode_name(alias)
        + struct.pack("!HHIH", rtype, 0x8000 | CLASS_IN, ttl, len(packed_address))
        + packed_address
    )


def records(alias: str, address: str, address6: str, ttl: int) -> list[bytes]:
    items = [record(alias, TYPE_A, socket.inet_aton(address), ttl)]
    if address6:
        items.append(record(alias, TYPE_AAAA, socket.inet_pton(socket.AF_INET6, address6), ttl))
    return items


def response(packet: bytes, alias: str, address: str, address6: str, ttl: int, requested_types: set[int]) -> bytes:
    selected = [
        item for item in records(alias, address, address6, ttl)
        if TYPE_ANY in requested_types or struct.unpack("!H", item[len(encode_name(alias)):len(encode_name(alias)) + 2])[0] in requested_types
    ]
    if not selected:
        selected = records(alias, address, address6, ttl)
    return packet[:2] + struct.pack("!HHHHH", 0x8400, 0, len(selected), 0, 0) + b"".join(selected)


def announcement(alias: str, address: str, address6: str, ttl: int) -> bytes:
    selected = records(alias, address, address6, ttl)
    return b"\x00\x00" + struct.pack("!HHHHH", 0x8400, 0, len(selected), 0, 0) + b"".join(selected)


def run(alias: str, address: str, address6: str, ttl: int) -> None:
    alias = alias.rstrip(".").lower()
    ipaddress.ip_address(address)
    if address6:
        ipaddress.ip_address(address6)

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

    target = f"{address}, {address6}" if address6 else address
    print(f"Publishing {alias} -> {target} via mDNS", flush=True)
    next_announce = 0.0
    while True:
        now = time.monotonic()
        if now >= next_announce:
            sock.sendto(announcement(alias, address, address6, ttl), (MDNS_GROUP, MDNS_PORT))
            next_announce = now + 10

        ready, _, _ = select.select([sock], [], [], 1)
        if not ready:
            continue

        packet, source = sock.recvfrom(9000)
        matches = [
            qtype for name, qtype, qclass in questions(packet)
            if name == alias and qtype in (TYPE_A, TYPE_AAAA, TYPE_ANY) and qclass == CLASS_IN
        ]
        if matches:
            payload = response(packet, alias, address, address6, ttl, set(matches))
            sock.sendto(payload, source)
            sock.sendto(payload, (MDNS_GROUP, MDNS_PORT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--address", required=True)
    parser.add_argument("--address6", default="")
    parser.add_argument("--ttl", type=int, default=120)
    args = parser.parse_args()
    run(args.name, args.address, args.address6, args.ttl)


if __name__ == "__main__":
    main()
