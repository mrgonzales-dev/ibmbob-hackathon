"""Generate a grungy noise texture PNG for the landing page background.

Writes public/noise.png — a 512x512 grayscale noise texture with random
scratches and blotches, encoded as a RGBA PNG with zlib. No dependencies
beyond the standard library. Deterministic (seeded) so re-runs produce the
same file.
"""

import random
import struct
import zlib

SIZE = 512
SEED = 42


def _chunk(tag: bytes, data: bytes) -> bytes:
    """Return one PNG chunk: length, tag, data, CRC."""
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def _noise(rng: random.Random, size: int) -> list:
    """Return a size x size grid of grayscale values (0-255)."""
    px = [[rng.randint(0, 255) for _ in range(size)] for _ in range(size)]

    # Blotches: soft dark radial spots.
    for _ in range(30):
        cx, cy = rng.randint(0, size - 1), rng.randint(0, size - 1)
        r = rng.randint(20, 90)
        depth = rng.randint(60, 140)
        for y in range(max(0, cy - r), min(size, cy + r)):
            for x in range(max(0, cx - r), min(size, cx + r)):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if d < r:
                    px[y][x] = max(0, px[y][x] - int(depth * (1 - d / r)))

    # Scratches: thin bright streaks at random angles.
    for _ in range(40):
        x, y = rng.randint(0, size - 1), rng.randint(0, size - 1)
        dx, dy = rng.choice([(1, 0), (0, 1), (1, 1), (1, -1)])
        length = rng.randint(10, 120)
        bright = rng.randint(30, 90)
        for _ in range(length):
            if 0 <= x < size and 0 <= y < size:
                px[y][x] = min(255, px[y][x] + bright)
            x, y = x + dx, y + dy

    return px


def write_png(path: str, px: list, size: int) -> None:
    """Encode the grayscale grid as a RGBA PNG at path."""
    raw = b""
    for row in px:
        raw += b"\x00"  # filter type: none
        for v in row:
            raw += bytes((v, v, v, 255))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def main() -> None:
    """Generate the texture and print the output path."""
    rng = random.Random(SEED)
    out = "public/noise.png"
    write_png(out, _noise(rng, SIZE), SIZE)
    print(out)


if __name__ == "__main__":
    main()
