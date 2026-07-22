#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autotests del emparejamiento apuntes ↔ partidas (pipeline.py), con fixtures sintéticos.
No tocan Google: prueban la lógica pura. Ejecuta:  python3 automation/test_emparejamiento.py
Casos cubiertos: día con práctica, partida a las 00:30 (hora de Madrid), fila de papel
(sin log), fila de ejemplo, bye/concede sin log, privacidad (sin nicks de rival) y que la
hoja de partidas gana al tracker legacy cuando solapan.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as PL


def utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def match(uuid, hora, arq, res='W', jg=2, jp=0, sr='Salida', opp='rivalNick', ngames=None):
    """Fabrica un match agregado como el que devuelve el parser (mínimo necesario)."""
    ng = ngames if ngames is not None else (jg + jp)
    games = []
    for i in range(1, ng + 1):
        games.append({'game_idx': i, 'local_on_play': (sr == 'Salida'),
                      'winner': 'local' if i <= jg else 'opp',
                      'turns': 5, 'prowess': 3, 'monks': 1})
    return {'match_uuid': uuid, 'hora': hora, 'arquetipo': arq, 'resultado': res,
            'jg': jg, 'jp': jp, 'salida_robo': sr, 'mull_local': 0, 'mull_opp': 0,
            'opp': opp, 'games_list': games}


def apunte(fecha, evento='', ronda='', lista='Stock', notas='', mazo='', mvp='',
           res='', jg='', jp='', sr='', origen='hoja', nick='feralo77'):
    return {'fecha': fecha, 'evento': evento, 'ronda': ronda, 'lista': lista,
            'notas': notas, 'mazo_rival': mazo, 'mvp': mvp, 'resultado': res,
            'jg': jg, 'jp': jp, 'salida_robo': sr, 'mull_local': '', 'mull_opp': '',
            'reportado_por': nick, 'origen': origen}


def rows(registro):
    return [r['row'] for r in sorted(registro, key=lambda r: r['sort'])]


def test_pareja_basica():
    ms = [match('u1', utc(2026, 7, 11, 18, 0), 'Broodscale'),
          match('u2', utc(2026, 7, 11, 19, 0), 'Boros Energy', res='L', jg=0, jp=2)]
    aps = [apunte('11/07/2026', 'Liga 1', '1', mazo='Broodscale', notas='ok'),
           apunte('11/07/2026', 'Liga 1', '2', mazo='Boros')]
    reg, games = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 2, r
    assert r[0]['Ronda'] == '1' and r[0]['Evento / Liga'] == 'Liga 1'
    assert r[0]['Fuente'] == 'log' and r[0]['match_uuid'] == 'u1'
    assert r[0]['Mazo del Oponente'] == 'Broodscale'  # nombre del apunte, no el arquetipo
    assert r[1]['Ronda'] == '2' and r[1]['Resultado (W/L)'] == 'L'
    assert len(games) == 4, len(games)  # 2 + 2 games
    print("OK pareja_basica")


def test_practica_extra():
    # 3 matches, 2 apuntes -> 2 emparejados + 1 práctica (Fuente log, Evento vacío)
    ms = [match('u1', utc(2026, 7, 12, 17, 0), 'Broodscale'),
          match('u2', utc(2026, 7, 12, 18, 0), 'Dimir Frog'),
          match('u3', utc(2026, 7, 12, 20, 0), 'Izzet Prowess')]
    aps = [apunte('12/07/2026', 'Liga 2', '4', mazo='Broodscale'),
           apunte('12/07/2026', 'Liga 2', '5', mazo='Dimir')]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 3, r
    prac = [x for x in r if x['Fuente'] == 'log' and x['Evento / Liga'] == '']
    assert len(prac) == 1, prac
    assert prac[0]['match_uuid'] == 'u3'
    assert prac[0]['Mazo del Oponente'] == 'Izzet Prowess'  # arquetipo detectado
    print("OK practica_extra")


def test_medianoche_madrid():
    # UTC 20/07 22:30 -> Madrid 21/07 00:30 (CEST +2). Debe caer el 21, no el 20.
    ms = [match('u1', utc(2026, 7, 20, 22, 30), 'Through the Breach')]
    aps = [apunte('21/07/2026', 'Liga 5', '1', mazo='Breach')]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 1, r
    assert r[0]['Fecha'] == '21/07/2026', r[0]['Fecha']
    assert r[0]['Evento / Liga'] == 'Liga 5' and r[0]['Ronda'] == '1'
    assert r[0]['Fuente'] == 'log'
    print("OK medianoche_madrid")


def test_fila_papel():
    # apunte sin log (papel/log perdido) -> fila manual con nota de revisar
    ms = []
    aps = [apunte('19/07/2026', 'Liga X', '1', mazo='Amulet Titan')]
    reg, games = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 1 and r[0]['Fuente'] == 'manual', r
    assert r[0]['match_uuid'] == ''
    assert 'revisar' in r[0]['Notas de Match / Sideboard']
    assert games == []
    print("OK fila_papel")


def test_bye_no_consume_match():
    # Día con un bye intercalado: el bye NO consume un log; los reales se alinean por orden.
    ms = [match('u1', utc(2026, 7, 11, 17, 0), 'Broodscale'),
          match('u2', utc(2026, 7, 11, 18, 0), 'Boros Energy')]
    aps = [apunte('11/07/2026', 'Liga 2', '1', mazo='Broodscale'),
           apunte('11/07/2026', 'Liga 2', '2', mazo='NA', res='W', jg=1, jp=0, notas='Concede'),
           apunte('11/07/2026', 'Liga 2', '3', mazo='Boros')]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    logs = [x for x in r if x['Fuente'] == 'log']
    manual = [x for x in r if x['Fuente'] == 'manual']
    assert len(logs) == 2 and len(manual) == 1, r
    # el bye conserva su resultado legacy y su nota
    assert manual[0]['Resultado (W/L)'] == 'W' and manual[0]['Notas de Match / Sideboard'] == 'Concede'
    # los dos reales se emparejan con Ronda 1 y 3 (no con el bye)
    assert {logs[0]['Ronda'], logs[1]['Ronda']} == {'1', '3'}
    print("OK bye_no_consume_match")


def test_fila_ejemplo_ignorada():
    values = [
        ['Fecha', 'Evento / Liga', 'Ronda', 'Lista', 'Notas', 'Mazo rival (opcional)'],
        ['11/07/2026', 'Liga 1', '1', 'Stock', '(ejemplo: borra esta fila)', 'Broodscale'],
        ['11/07/2026', 'Liga 1', '1', 'Stock', 'partida real', 'Boros'],
    ]
    aps = PL.apuntes_de_valores(values, 'hoja', 'feralo77')
    assert len(aps) == 1, aps
    assert aps[0]['notas'] == 'partida real' and aps[0]['mazo_rival'] == 'Boros'
    print("OK fila_ejemplo_ignorada")


def test_privacidad_sin_nicks():
    ms = [match('u1', utc(2026, 7, 13, 18, 0), 'Neoform', opp='SECRET_RIVAL_NICK')]
    aps = [apunte('13/07/2026', 'Liga 3', '2', mazo='Neoform')]
    reg, games = PL.emparejar(ms, aps, 'feralo77')
    blob = str(rows(reg)) + str(games)
    assert 'SECRET_RIVAL_NICK' not in blob, 'se ha filtrado un nick de rival'
    print("OK privacidad_sin_nicks")


def test_hoja_gana_legacy():
    legacy = [apunte('11/07/2026', 'Liga 1', '1', mazo='Loki', notas='legacy', origen='legacy')]
    hoja = [apunte('11/07/2026', 'Liga 1 (corregida)', '1', mazo='Azorius Loki',
                   notas='hoja', origen='hoja')]
    comb = PL.combinar_apuntes(legacy, hoja)
    assert len(comb) == 1 and comb[0]['origen'] == 'hoja', comb
    assert comb[0]['notas'] == 'hoja'
    # si la hoja no cubre un día, se conserva el legacy
    legacy2 = legacy + [apunte('12/07/2026', 'Liga 2', '4', mazo='Vivoras', origen='legacy')]
    comb2 = PL.combinar_apuntes(legacy2, hoja)
    assert len(comb2) == 2, comb2
    print("OK hoja_gana_legacy")


def test_norm_fecha_y_bye():
    assert PL.norm_fecha('2026-07-11') == '11/07/2026'
    assert PL.norm_fecha('11/07/2026') == '11/07/2026'
    assert PL.is_bye('NA') and PL.is_bye('N/A (bye/concede)') and PL.is_bye('bye')
    assert not PL.is_bye('Broodscale') and not PL.is_bye('')
    print("OK norm_fecha_y_bye")


if __name__ == '__main__':
    test_pareja_basica()
    test_practica_extra()
    test_medianoche_madrid()
    test_fila_papel()
    test_bye_no_consume_match()
    test_fila_ejemplo_ignorada()
    test_privacidad_sin_nicks()
    test_hoja_gana_legacy()
    test_norm_fecha_y_bye()
    print("\nTodos los autotests del emparejamiento OK")
