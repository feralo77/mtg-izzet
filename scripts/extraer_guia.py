#!/usr/bin/env python3
"""
Extrae el texto de la guia premium de ethanmtg (guia.pages) a texto plano.

Por que existe: la guia es un documento vivo (el autor la actualiza y avisa).
Cuando Fer vuelve a guardar guia.pages con la version nueva, este script saca
el texto y se puede comparar con la foto anterior para ver SOLO lo que cambio,
en vez de releer 11.000 palabras a mano.

Uso:
    python3 scripts/extraer_guia.py                     # -> data/guia-texto.txt
    python3 scripts/extraer_guia.py otra.pages salida.txt

Y para ver los cambios respecto a la foto anterior:
    diff data/guia-texto-<fecha>.txt data/guia-texto.txt

La salida va a data/ (gitignored): es contenido de pago, NO se sube al repo.

Un .pages es un zip con los indices en formato IWA de Apple: protobuf comprimido
con snappy en bloques con cabecera de 4 bytes. Aqui se descomprime a mano para no
depender de librerias externas ni de tener Pages abierto.
"""
import os
import sys
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def snappy_raw(data):
    """Descomprime un bloque snappy 'raw' (sin framing de stream)."""
    i = shift = ulen = 0
    while True:
        b = data[i]
        i += 1
        ulen |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            break
    out = bytearray()
    n = len(data)
    while i < n:
        tag = data[i]
        i += 1
        kind = tag & 0x03
        if kind == 0:                                   # literal
            ln = tag >> 2
            if ln < 60:
                ln += 1
            else:
                nb = ln - 59
                ln = int.from_bytes(data[i:i + nb], 'little') + 1
                i += nb
            out += data[i:i + ln]
            i += ln
            continue
        if kind == 1:                                   # copia, offset 1 byte
            ln = 4 + ((tag >> 2) & 0x07)
            off = ((tag >> 5) << 8) | data[i]
            i += 1
        elif kind == 2:                                 # copia, offset 2 bytes
            ln = (tag >> 2) + 1
            off = int.from_bytes(data[i:i + 2], 'little')
            i += 2
        else:                                           # copia, offset 4 bytes
            ln = (tag >> 2) + 1
            off = int.from_bytes(data[i:i + 4], 'little')
            i += 4
        if not 0 < off <= len(out):
            break
        start = len(out) - off
        for k in range(ln):
            out.append(out[start + k])
    return bytes(out)


def iwa_descomprimir(raw):
    """Un .iwa son bloques: cabecera de 4 bytes (00 + longitud) + bloque snappy."""
    out = bytearray()
    i = 0
    while i + 4 <= len(raw):
        if raw[i] != 0x00:
            break
        blen = int.from_bytes(raw[i + 1:i + 4], 'little')
        i += 4
        try:
            out += snappy_raw(raw[i:i + blen])
        except Exception as e:
            sys.stderr.write('aviso: bloque ilegible, se corta aqui (%s)\n' % e)
            break
        i += blen
    return bytes(out)


def texto_utf8(data, minimo=6):
    """Saca las tiradas de texto UTF-8 legible del protobuf ya descomprimido."""
    lineas, cur, i, n = [], bytearray(), 0, len(data)

    def cerrar():
        if len(cur) >= minimo:
            try:
                lineas.append(cur.decode('utf-8'))
            except UnicodeDecodeError:
                pass
        cur.clear()

    while i < n:
        b = data[i]
        if 0x20 <= b < 0x7F or b == 0x09:
            cur.append(b)
            i += 1
        elif 0xC2 <= b <= 0xDF and i + 1 < n and 0x80 <= data[i + 1] <= 0xBF:
            cur += data[i:i + 2]
            i += 2
        elif 0xE0 <= b <= 0xEF and i + 2 < n and all(0x80 <= data[i + k] <= 0xBF for k in (1, 2)):
            cur += data[i:i + 3]
            i += 3
        else:
            cerrar()
            i += 1
    cerrar()
    return lineas


def main():
    origen = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, 'guia.pages')
    destino = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, 'data', 'guia-texto.txt')

    if not os.path.exists(origen):
        sys.exit('No encuentro %s. Guarda la guia como guia.pages en la raiz del repo.' % origen)

    with zipfile.ZipFile(origen) as z:
        raw = z.read('Index/Document.iwa')

    lineas = texto_utf8(iwa_descomprimir(raw))

    # El documento arranca con metadatos de idioma y formatos de fecha del sistema:
    # el texto de verdad empieza en el indice.
    for n, linea in enumerate(lineas):
        if 'Standard TOC' in linea or linea.strip() == 'Introduction':
            lineas = lineas[n:]
            break

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lineas) + '\n')

    palabras = sum(len(l.split()) for l in lineas)
    print('%s -> %s (%d lineas, ~%d palabras)' % (
        os.path.basename(origen), os.path.relpath(destino, BASE), len(lineas), palabras))


if __name__ == '__main__':
    main()
