"""Recadrage des icônes Factorio.

Les ``graphics/icons/*.png`` sont des feuilles de mipmaps : l'icône pleine
taille (``icon_size``, en haut à gauche) suivie des versions réduites de
moitié en largeur (32, 16, 8…), alignées en haut à gauche. Le jeu infère le
nombre de mipmaps et n'affiche que la copie de la taille demandée. On
reproduit ce découpage : ne garder que le premier carré ``icon_size`` (= la
hauteur de la feuille), sans les copies réduites.

Décodage/encodage PNG en pur Python, sans bibliothèque tierce.
"""

from __future__ import annotations

import functools
import struct
import zlib

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _png_chunks(data: bytes):
    pos = 8
    while pos < len(data):
        ln = struct.unpack(">I", data[pos : pos + 4])[0]
        typ = data[pos + 4 : pos + 8]
        yield typ, data[pos + 8 : pos + 8 + ln]
        pos += 12 + ln


def _decode(data: bytes):
    """Retourne (w, h, chans, rows) pour les PNG 8-bit non entrelacés."""
    ihdr = None
    idat = b""
    plte = b""
    trns = None
    for typ, blk in _png_chunks(data):
        if typ == b"IHDR":
            w, h, bd, ct, _comp, _f, il = struct.unpack(">IIBBBBB", blk)
            ihdr = (w, h, bd, ct)
        elif typ == b"IDAT":
            idat += blk
        elif typ == b"PLTE":
            plte = blk
        elif typ == b"tRNS":
            trns = blk
    if ihdr is None or not idat:
        return None
    w, h, bd, ct = ihdr
    if bd != 8 or il != 0:
        return None
    if ct not in (0, 2, 3, 4, 6):
        return None
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    stride = w * chans
    raw = zlib.decompress(idat)
    rows = []
    prev = [0] * stride
    p = 0
    for _ in range(h):
        f = raw[p]
        p += 1
        line = list(raw[p : p + stride])
        p += stride
        if f == 1:
            for i in range(chans, stride):
                line[i] = (line[i] + line[i - chans]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - chans] if i >= chans else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - chans] if i >= chans else 0
                b = prev[i]
                c = prev[i - chans] if i >= chans else 0
                pv = a + b - c
                pa, pb, pc = abs(pv - a), abs(pv - b), abs(pv - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        rows.append(line)
        prev = line
    return w, h, ct, chans, plte, trns, rows


def _pix4(ct, chans, plte, trns, row, o):
    if ct == 6:
        return row[o], row[o + 1], row[o + 2], row[o + 3]
    if ct == 4:
        g = row[o]
        return g, g, g, row[o + 1]
    if ct == 2:
        return row[o], row[o + 1], row[o + 2], 255
    if ct == 0:
        g = row[o]
        return g, g, g, 255
    idx = row[o]
    rgb = plte[idx * 3 : idx * 3 + 3]
    r = rgb[0] if len(rgb) == 3 else 0
    g = rgb[1] if len(rgb) == 3 else 0
    b = rgb[2] if len(rgb) == 3 else 0
    a = trns[idx] if trns is not None and idx < len(trns) else 255
    return r, g, b, a


def _encode(cw: int, ch: int, out_rows) -> bytes:
    out_raw = b"".join(b"\x00" + r for r in out_rows)

    def chunk(typ, data):
        """Emboîte un bloc PNG (type + données) avec sa longueur et son CRC."""
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    out = _PNG_SIG
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", cw, ch, 8, 6, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(out_raw, 6))
    out += chunk(b"IEND", b"")
    return out


@functools.lru_cache(maxsize=4096)
def crop_mip(png: bytes) -> bytes:
    """Recadre une icône Factorio sur sa seule copie pleine taille.

    Feuille de mipmaps (largeur > hauteur) : on ne garde que le premier
    carré ``icon_size`` (côté = hauteur de la feuille) puis on rogne les
    marges transparentes. Image simple (carrée ou haute) : on rogne
    simplement les marges transparentes. La boîte englobante est ensuite
    recentrée sur une toile carrée (padding transparent) pour que
    graphviz calcule des nœuds 1:1. Le PNG d'origine est renvoyé
    tel quel si le format n'est pas décodable.
    """
    dec = _decode(png)
    if dec is None:
        return png
    if len(png) < 29 or png[:8] != _PNG_SIG:
        return png
    w, h, ct, chans, plte, trns, rows = dec
    if w > h:
        xmax = ymax = h
    else:
        xmax, ymax = w, h

    def alpha(x, y):
        """Canal alpha (0-255) du pixel (x, y) de l'image décodée."""
        return _pix4(ct, chans, plte, trns, rows[y], x * chans)[3]

    x0, y0, x1, y1 = xmax, ymax, -1, -1
    for y in range(ymax):
        for x in range(xmax):
            if alpha(x, y) > 16:
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
    if x1 < 0:
        return png
    out_rows = [
        bytes(c for x in range(x0, x1 + 1) for c in _pix4(ct, chans, plte, trns, rows[y], x * chans))
        for y in range(y0, y1 + 1)
    ]
    cw = x1 - x0 + 1
    ch = y1 - y0 + 1
    if cw != ch:
        side = max(cw, ch)
        left = (side - cw) // 2
        right = side - cw - left
        top = (side - ch) // 2
        bottom = side - ch - top
        blank = bytes(side * 4)
        out_rows = (
            [blank] * top
            + [bytes(left * 4) + r + bytes(right * 4) for r in out_rows]
            + [blank] * bottom
        )
        cw = ch = side
    return _encode(cw, ch, out_rows)