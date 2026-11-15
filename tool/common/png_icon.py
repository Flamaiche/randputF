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
    """Itère les blocs PNG d'un fichier complet.

    Saute la signature de 8 octets puis yield ``(type, données)`` pour chaque
    bloc (type = 4 octets, données sans le CRC). Le parcours s'arrête à la fin
    du buffer ; un fichier tronqué peut produire un dernier bloc partiel.
    """
    pos = 8
    while pos < len(data):
        ln = struct.unpack(">I", data[pos : pos + 4])[0]
        typ = data[pos + 4 : pos + 8]
        yield typ, data[pos + 8 : pos + 8 + ln]
        pos += 12 + ln


def _decode(data: bytes):
    """Décode un PNG 8 bits non entrelacé en lignes de pixels bruts.

    Retourne ``(w, h, ct, chans, plte, trns, rows)`` : largeur, hauteur, type
    de couleur PNG, nombre de canaux, palette (``bytes`` vide si absente),
    table de transparence (``bytes`` ou ``None``) et ``rows`` (liste de listes
    d'octets, une par ligne, filtres PNG déjà appliqués). Retourne ``None``
    si l'en-tête ou les données manquent, ou si la profondeur/le type/
    l'entrelacement n'est pas supporté.
    """
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
    """Extrait un pixel RGBA d'une ligne décodée.

    ``ct``/``chans``/``plte``/``trns`` viennent de ``_decode``, ``row`` est la
    ligne de bytes et ``o`` l'offset du pixel (déjà multiplié par ``chans``).
    Gère les types RGB, RGBA, niveaux de gris (± alpha) et palette ; retourne
    toujours un tuple ``(r, g, b, a)`` d'octets 0-255, alpha opaque par défaut.
    """
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
    """Encode des lignes RGBA en PNG 8 bits non entrelacé.

    ``cw``/``ch`` sont les dimensions, ``out_rows`` une séquence de lignes
    d'octets RGBA (4 octets par pixel, sans filtre). Chaque ligne reçoit le
    filtre PNG 0 (aucun), puis IHDR/IDAT/IEND sont assemblés avec leurs CRC.
    Retourne les octets complets du fichier PNG.
    """
    out_raw = b"".join(b"\x00" + r for r in out_rows)

    def chunk(typ, data):
        """Emboîte un bloc PNG (type + données) avec sa longueur et son CRC.

        ``typ`` est le code de 4 octets du bloc et ``data`` son contenu. Retourne les octets du bloc complet, prêts à être concaténés au fichier PNG.
        """
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
        """Retourne le canal alpha (0-255) du pixel ``(x, y)``.

        ``x``/``y`` sont des coordonnées dans la copie pleine taille décodée ; la fonction lit la ligne correspondante et renvoie l'octet alpha. Utilisée pour calculer la boîte englobante non transparente.
        """
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