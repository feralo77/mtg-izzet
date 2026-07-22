#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autotests del emparejamiento apuntes ↔ partidas (pipeline.py), con fixtures sintéticos.
No tocan Google: prueban la lógica pura. Ejecuta:  python3 automation/test_emparejamiento.py
Casos: pareja básica, día con práctica intercalada (mid-secuencia), sesión de madrugada que
cae el día siguiente (00:30 hora de Madrid), fila de papel (sin log), fila de ejemplo,
bye/concede sin log, nicks de rival públicos (columna Rival; decisión de Fer 2026-07-22),
scouting por rival y que la hoja gana al tracker legacy.
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
    ms = [match('u1', utc(2026, 7, 11, 18, 0), 'Broodscale', res='W', jg=2, jp=0, sr='Salida'),
          match('u2', utc(2026, 7, 11, 19, 0), 'Boros Energy', res='L', jg=0, jp=2, sr='Robo')]
    aps = [apunte('11/07/2026', 'Liga 1', '1', mazo='Broodscale', notas='ok', res='W', jg=2, jp=0, sr='Salida'),
           apunte('11/07/2026', 'Liga 1', '2', mazo='Boros', res='L', jg=0, jp=2, sr='Robo')]
    reg, games = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 2, r
    assert r[0]['Ronda'] == '1' and r[0]['Evento / Liga'] == 'Liga 1'
    assert r[0]['Fuente'] == 'log' and r[0]['match_uuid'] == 'u1'
    assert r[0]['Mazo del Oponente'] == 'Broodscale'  # nombre del apunte, no el arquetipo
    assert r[0]['Fecha'] == '11/07/2026'
    assert r[1]['Ronda'] == '2' and r[1]['Resultado (W/L)'] == 'L'
    assert len(games) == 4, len(games)  # 2 + 2 games
    print("OK pareja_basica")


def test_practica_intercalada():
    # Una partida de práctica INTERCALADA entre dos rondas de liga: debe saltarse como
    # práctica (Fuente log, Evento vacío) sin desplazar la Ronda de las de liga.
    ms = [match('u1', utc(2026, 7, 12, 17, 0), 'Broodscale', res='W', jg=2, jp=0, sr='Salida'),
          match('up', utc(2026, 7, 12, 18, 0), 'Izzet Prowess', res='W', jg=2, jp=1, sr='Robo'),
          match('u2', utc(2026, 7, 12, 20, 0), 'Dimir Frog', res='L', jg=0, jp=2, sr='Robo')]
    aps = [apunte('12/07/2026', 'Liga 2', '4', mazo='Broodscale', res='W', jg=2, jp=0, sr='Salida'),
           apunte('12/07/2026', 'Liga 2', '5', mazo='Dimir', res='L', jg=0, jp=2, sr='Robo')]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 3, r
    prac = [x for x in r if x['Fuente'] == 'log' and x['Evento / Liga'] == '']
    assert len(prac) == 1 and prac[0]['match_uuid'] == 'up', prac
    liga = {x['match_uuid']: x['Ronda'] for x in r if x['Evento / Liga']}
    assert liga == {'u1': '4', 'u2': '5'}, liga
    print("OK practica_intercalada")


def test_sesion_de_madrugada():
    # Sesión jugada de madrugada: los apuntes dicen 18/07 pero los logs (Madrid) caen el 19.
    # El desfase de ±1 día no debe romper el emparejamiento; la Fecha final es la del apunte.
    ms = [match('u1', utc(2026, 7, 19, 0, 30), 'Boros Ponza', res='W', jg=2, jp=0, sr='Robo'),
          match('u2', utc(2026, 7, 19, 1, 30), 'Esper Goryo', res='L', jg=0, jp=2, sr='Robo')]
    aps = [apunte('18/07/2026', 'Liga 3', '3', mazo='Ponza', res='W', jg=2, jp=0, sr='Robo'),
           apunte('18/07/2026', 'Liga 3', '4', mazo='Gorys', res='L', jg=0, jp=2, sr='Robo')]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 2 and all(x['Fuente'] == 'log' for x in r), r
    assert all(x['Fecha'] == '18/07/2026' for x in r), [x['Fecha'] for x in r]
    assert {x['Ronda'] for x in r} == {'3', '4'}
    print("OK sesion_de_madrugada")


def test_medianoche_00_30():
    # UTC 20/07 22:30 -> Madrid 21/07 00:30 (CEST +2). El match cae el 21, no el 20.
    ms = [match('u1', utc(2026, 7, 20, 22, 30), 'Through the Breach', res='W', jg=2, jp=1, sr='Salida')]
    aps = [apunte('21/07/2026', 'Liga 5', '1', mazo='Breach', res='W', jg=2, jp=1, sr='Salida')]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 1 and r[0]['Fecha'] == '21/07/2026', r
    assert r[0]['Evento / Liga'] == 'Liga 5' and r[0]['Ronda'] == '1' and r[0]['Fuente'] == 'log'
    print("OK medianoche_00_30")


def test_fila_papel():
    # apunte sin log (papel/log perdido) -> fila manual con nota de revisar
    aps = [apunte('19/07/2026', 'Liga X', '1', mazo='Amulet Titan', res='W', jg=2, jp=1)]
    reg, games = PL.emparejar([], aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 1 and r[0]['Fuente'] == 'manual' and r[0]['match_uuid'] == '', r
    assert 'revisar' in r[0]['Notas de Match / Sideboard']
    assert games == []
    print("OK fila_papel")


def test_bye_no_consume_match():
    # El bye/concede (Mazo=NA) NO consume un log; los reales se emparejan por resultado.
    ms = [match('u1', utc(2026, 7, 11, 17, 0), 'Broodscale', res='L', jg=0, jp=2, sr='Robo'),
          match('u2', utc(2026, 7, 11, 18, 0), 'Boros Energy', res='W', jg=2, jp=1, sr='Robo')]
    aps = [apunte('11/07/2026', 'Liga 2', '1', mazo='Broodscale', res='L', jg=0, jp=2, sr='Robo'),
           apunte('11/07/2026', 'Liga 2', '2', mazo='NA', res='W', jg=1, jp=0, notas='Concede'),
           apunte('11/07/2026', 'Liga 2', '3', mazo='Boros', res='W', jg=2, jp=1, sr='Robo')]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    logs = [x for x in r if x['Fuente'] == 'log']
    manual = [x for x in r if x['Fuente'] == 'manual']
    assert len(logs) == 2 and len(manual) == 1, r
    assert manual[0]['Resultado (W/L)'] == 'W' and manual[0]['Notas de Match / Sideboard'] == 'Concede'
    assert {x['Ronda'] for x in logs} == {'1', '3'}   # ni un log toca la Ronda 2 (el bye)
    print("OK bye_no_consume_match")


def test_fila_ejemplo():
    # La fila con nota "(ejemplo...)" se marca, no se descarta a ciegas.
    values = [
        ['Fecha', 'Evento / Liga', 'Ronda', 'Lista', 'Notas', 'Mazo rival (opcional)'],
        ['11/07/2026', 'Liga 1', '1', 'Stock', '(ejemplo: borra esta fila)', 'Broodscale'],
        ['11/07/2026', 'Liga 1', '2', 'Stock', 'partida real', 'Boros'],
    ]
    aps = PL.apuntes_de_valores(values, 'hoja', 'feralo77')
    assert len(aps) == 2 and aps[0].get('es_ejemplo') and aps[0]['notas'] == '', aps
    # (a) SIN log que le case: la fila de ejemplo jamás inventa una partida manual
    reg, _ = PL.emparejar([], aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 1 and r[0]['Mazo del Oponente'] == 'Boros', r
    # (b) CON log que le casa (caso real: Fer edita la fila de ejemplo con la Liga 5 R5):
    # la fila cuenta, propaga Liga/Ronda/Lista y la nota de plantilla no aparece
    values_r5 = [
        ['Fecha', 'Evento / Liga', 'Ronda', 'Lista', 'Notas', 'Mazo rival (opcional)'],
        ['22/07/2026', 'Liga 5', '5', '2.0', '(ejemplo: bórrame cuando apuntes)', 'ls149950'],
    ]
    aps_r5 = PL.apuntes_de_valores(values_r5, 'hoja', 'feralo77')
    ms = [match('u9', utc(2026, 7, 22, 18, 0), 'Broodscale', res='L', jg=0, jp=2, sr='Salida',
                opp='ls149950')]
    reg2, _ = PL.emparejar(ms, aps_r5, 'feralo77')
    r2 = rows(reg2)
    assert len(r2) == 1 and r2[0]['Fuente'] == 'log', r2
    assert r2[0]['Evento / Liga'] == 'Liga 5' and r2[0]['Ronda'] == '5' and r2[0]['Lista'] == '2.0', r2
    assert r2[0]['Notas de Match / Sideboard'] == '', r2
    # y el nick escrito en la casilla de mazo NO se cuela como mazo
    assert r2[0]['Mazo del Oponente'] == 'Broodscale', r2
    print("OK fila_ejemplo")


def test_fallback_apunte_si_revisar():
    # Clasificador sin confianza + mazo apuntado -> manda el apunte, normalizado a canónico.
    ms = [match('u1', utc(2026, 7, 12, 18, 0), '¿? (revisar)', res='L', jg=1, jp=2, opp='Ciraris')]
    aps = [apunte('12/07/2026', 'Liga 2', '4', mazo='Vivoras', res='L', jg=1, jp=2)]
    reg, games = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert r[0]['Arquetipo'] == 'Sultai Midrange', r[0]
    assert r[0]['Confianza'] == 'apunte', r[0]
    assert games[0]['Arquetipo'] == 'Sultai Midrange', games[0]
    # con confianza suficiente, el apunte NO pisa al clasificador
    ms2 = [match('u2', utc(2026, 7, 12, 19, 0), 'Boros Energy', res='W', jg=2, jp=0, opp='otro')]
    aps2 = [apunte('12/07/2026', 'Liga 2', '5', mazo='Boros', res='W', jg=2, jp=0)]
    reg2, _ = PL.emparejar(ms2, aps2, 'feralo77')
    assert rows(reg2)[0]['Arquetipo'] == 'Boros Energy'
    print("OK fallback_apunte_si_revisar")


def test_nicks_de_rival_publicos():
    # Decisión de Fer (2026-07-22): el nick del rival SÍ sale, en su columna "Rival".
    # "Mazo del Oponente" y "Arquetipo" siguen siendo nombres de mazo, nunca el nick.
    ms = [match('u1', utc(2026, 7, 13, 18, 0), 'Neoform', res='L', jg=1, jp=2, opp='RIVAL_NICK')]
    aps = [apunte('13/07/2026', 'Liga 3', '2', mazo='Neoform', res='L', jg=1, jp=2)]
    reg, games = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert r[0]['Rival'] == 'RIVAL_NICK', r[0]
    assert r[0]['Mazo del Oponente'] == 'Neoform' and r[0]['Arquetipo'] == 'Neoform', r[0]
    assert 'RIVAL_NICK' not in str(games), 'games.csv no lleva nicks (no los necesita)'
    # una fila manual (sin log) no tiene nick
    reg2, _ = PL.emparejar([], [apunte('14/07/2026', 'Liga 3', '3', mazo='Amulet Titan', res='W', jg=2, jp=0)], 'feralo77')
    assert rows(reg2)[0]['Rival'] == ''
    print("OK nicks_de_rival_publicos")


def test_scouting_por_rival():
    ms1 = [match('u1', utc(2026, 7, 13, 18, 0), 'Neoform', res='L', jg=1, jp=2, opp='Rivalote'),
           match('u2', utc(2026, 7, 14, 18, 0), 'Neoform', res='W', jg=2, jp=0, opp='Rivalote')]
    ms2 = [match('u3', utc(2026, 7, 15, 18, 0), 'Dimir Frog', res='W', jg=2, jp=1, opp='Rivalote')]
    for m in ms1 + ms2:
        m['confianza'] = 0.8
        m['turns_avg'] = 5.0
        m['opp_cards'] = ['Neoform', 'Allosaurus Rider']
    filas = PL.scouting_por_rival([('feralo77', ms1), ('Inkmaster', ms2)])
    assert len(filas) == 1 and filas[0]['Rival'] == 'Rivalote', filas
    assert filas[0]['Matches'] == 3 and filas[0]['Récord'] == '2-1', filas[0]
    assert 'Neoform (2)' in filas[0]['Mazo(s)'] and 'Dimir Frog' in filas[0]['Mazo(s)']
    assert filas[0]['Visto por'] == 'Inkmaster, feralo77'
    assert 'Neoform x3' in filas[0]['Cartas más vistas']
    print("OK scouting_por_rival")


def test_hoja_gana_legacy():
    legacy = [apunte('11/07/2026', 'Liga 1', '1', mazo='Loki', notas='legacy', origen='legacy')]
    hoja = [apunte('11/07/2026', 'Liga 1 (corregida)', '1', mazo='Azorius Loki',
                   notas='hoja', origen='hoja')]
    comb = PL.combinar_apuntes(legacy, hoja)
    assert len(comb) == 1 and comb[0]['origen'] == 'hoja' and comb[0]['notas'] == 'hoja', comb
    legacy2 = legacy + [apunte('12/07/2026', 'Liga 2', '4', mazo='Vivoras', origen='legacy')]
    comb2 = PL.combinar_apuntes(legacy2, hoja)
    assert len(comb2) == 2, comb2  # si la hoja no cubre un día, se conserva el legacy
    print("OK hoja_gana_legacy")


def test_norm_fecha_y_bye():
    assert PL.norm_fecha('2026-07-11') == '11/07/2026'
    assert PL.norm_fecha('11/07/2026') == '11/07/2026'
    assert PL.is_bye('NA') and PL.is_bye('N/A (bye/concede)') and PL.is_bye('bye')
    assert not PL.is_bye('Broodscale') and not PL.is_bye('')
    print("OK norm_fecha_y_bye")


if __name__ == '__main__':
    test_pareja_basica()
    test_practica_intercalada()
    test_sesion_de_madrugada()
    test_medianoche_00_30()
    test_fila_papel()
    test_bye_no_consume_match()
    test_fila_ejemplo()
    test_fallback_apunte_si_revisar()
    test_nicks_de_rival_publicos()
    test_scouting_por_rival()
    test_hoja_gana_legacy()
    test_norm_fecha_y_bye()
    print("\nTodos los autotests del emparejamiento OK")
