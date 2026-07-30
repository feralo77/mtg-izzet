#!/usr/bin/env python3
"""Comprueba que TODOS los nombres de carta de listas/*.txt existen de verdad.

Por qué existe: el 29-jul-2026 se descubrió `2 Boomerang Basics` en Basics.txt —
el nombre de la lista se había colado dentro del nombre de la carta. El comparador
se lo tragaba y lo contaba como una carta más de las 60, así que el fallo era
invisible. A ojo tampoco basta: `Flashback` PARECE un error y es una carta real
(Secrets of Strixhaven, abr-2026). La única fuente fiable es Scryfall.

Uso:
    python automation/validar_listas.py            # informe; sale 1 si hay errores
    python automation/validar_listas.py --aviso    # informe; sale 0 siempre

`--aviso` es lo que usa el robot: un corte de Scryfall no debe tumbar el pipeline
de datos, solo avisar en el log.
"""
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

LISTAS_DIR = Path(__file__).resolve().parent.parent / 'listas'
API = 'https://api.scryfall.com/cards/collection'
UA = 'mtg-izzet-hq/1.0 (github.com/feralo77/mtg-izzet)'


def _ctx():
    """En el Mac de Fer, Python no usa el almacén de certificados del sistema y
    la petición a Scryfall falla con CERTIFICATE_VERIFY_FAILED. certifi lo resuelve
    (en el runner de la Action no hace falta, pero no molesta)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return None


def cartas_de(path):
    """[(nombre, linea)] de un listas/<nombre>.txt (formato MTGO: '<n> Carta')."""
    out = []
    for i, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#') or line.lower().startswith('sideboard'):
            continue
        m = re.match(r'^(\d+)x?\s+(.*)$', line)
        if m:
            out.append((m.group(2).strip(), i))
    return out


def consultar(nombres):
    """{nombre pedido -> nombre oficial} para los que Scryfall reconoce.
    Scryfall acepta 75 identificadores por petición."""
    encontrados = {}
    for i in range(0, len(nombres), 75):
        lote = nombres[i:i + 75]
        body = json.dumps({'identifiers': [{'name': n} for n in lote]}).encode()
        # Scryfall exige User-Agent Y Accept: sin Accept devuelve 400 bad_request.
        req = urllib.request.Request(
            API, data=body,
            headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                     'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=30, context=_ctx()) as r:
            data = json.load(r)
        # Scryfall casa por nombre de forma laxa (mayúsculas, acentos): emparejamos
        # cada carta devuelta con el nombre que pedimos, normalizando.
        def k(s):
            return re.sub(r'[^a-z0-9]', '', s.lower())
        oficiales = {}
        for c in data.get('data', []):
            oficiales[k(c['name'])] = c['name']
            for cara in c.get('card_faces', []) or []:
                oficiales[k(cara.get('name', ''))] = c['name']
        for n in lote:
            if k(n) in oficiales:
                encontrados[n] = oficiales[k(n)]
    return encontrados


def main():
    aviso = '--aviso' in sys.argv
    ficheros = sorted(LISTAS_DIR.glob('*.txt'))
    if not ficheros:
        print('No hay listas en listas/ — nada que validar.')
        return 0

    por_fichero = {p: cartas_de(p) for p in ficheros}
    todas = sorted({n for cs in por_fichero.values() for n, _ in cs})
    print(f'Validando {len(todas)} nombres distintos de {len(ficheros)} listas contra Scryfall...')
    try:
        ok = consultar(todas)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f'! No se pudo consultar Scryfall ({e}). Validación omitida.')
        return 0

    malos = [n for n in todas if n not in ok]
    if not malos:
        print(f'Todo correcto: los {len(todas)} nombres existen en Scryfall.')
        return 0

    print(f'\n{len(malos)} nombre(s) que Scryfall NO reconoce:\n')
    for n in malos:
        print(f'  "{n}"')
        for p, cs in por_fichero.items():
            for nombre, linea in cs:
                if nombre == n:
                    print(f'      {p.name}:{linea}')
    print('\nSuele ser el nombre de la lista colado dentro del de la carta '
          '(ej. "Boomerang Basics" -> "Boomerang"), o una errata al teclear.')
    return 0 if aviso else 1


if __name__ == '__main__':
    sys.exit(main())
