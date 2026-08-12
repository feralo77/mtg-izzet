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
           res='', jg='', jp='', sr='', origen='hoja', nick='feralo77', rival=''):
    return {'fecha': fecha, 'evento': evento, 'ronda': ronda, 'lista': lista,
            'notas': notas, 'mazo_rival': mazo, 'rival_nick': rival, 'mvp': mvp,
            'resultado': res, 'jg': jg, 'jp': jp, 'salida_robo': sr,
            'mull_local': '', 'mull_opp': '', 'reportado_por': nick, 'origen': origen}


def rows(registro):
    return [r['row'] for r in sorted(registro, key=lambda r: r['sort'])]


def test_columna_rival_nick():
    # Plantilla nueva (2026-07-22): columnas separadas Rival (nick) y Mazo rival.
    values = [
        ['Fecha', 'Evento / Liga', 'Ronda', 'Lista', 'Rival', 'Mazo rival', 'Notas'],
        ['22/07/2026', 'Liga 5', '5', '2.0', 'ls149950', 'Broodscale', ''],
    ]
    aps = PL.apuntes_de_valores(values, 'hoja', 'feralo77')
    assert len(aps) == 1, aps
    assert aps[0]['rival_nick'] == 'ls149950' and aps[0]['mazo_rival'] == 'Broodscale', aps[0]
    # y en la hoja vieja ("Mazo rival (opcional)") el mazo sigue mapeando bien, sin nick
    values_old = [
        ['Fecha', 'Evento / Liga', 'Ronda', 'Lista', 'Notas', 'Mazo rival (opcional)'],
        ['11/07/2026', 'Liga 1', '1', 'Stock', 'real', 'Boros'],
    ]
    aps_old = PL.apuntes_de_valores(values_old, 'hoja', 'feralo77')
    assert aps_old[0]['mazo_rival'] == 'Boros' and aps_old[0]['rival_nick'] == '', aps_old[0]
    print("OK columna_rival_nick")


def test_nick_es_la_llave():
    # Dos partidas el mismo día, mismo resultado: SOLO el nick permite colgar el apunte
    # de la partida correcta (la 2ª), dejando la 1ª como práctica.
    ms = [match('u1', utc(2026, 7, 15, 17, 0), 'Boros Energy', res='W', jg=2, jp=0, opp='Pepe'),
          match('u2', utc(2026, 7, 15, 19, 0), 'Broodscale', res='W', jg=2, jp=0, opp='Juan')]
    aps = [apunte('15/07/2026', 'Liga 9', '1', rival='Juan', mazo='Broodscale', res='W', jg=2, jp=0)]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    liga = [x for x in r if x['Evento / Liga'] == 'Liga 9']
    prac = [x for x in r if not x['Evento / Liga']]
    assert len(liga) == 1 and liga[0]['match_uuid'] == 'u2' and liga[0]['Rival'] == 'Juan', r
    assert len(prac) == 1 and prac[0]['match_uuid'] == 'u1', r
    # nick que NO coincide con ningún log -> mejor fuera que emparejar mal
    # (regla 12-ago: el apunte sin log no se publica; los logs quedan como práctica)
    aps2 = [apunte('15/07/2026', 'Liga 9', '2', rival='Desconocido77', mazo='Amulet Titan', res='L', jg=0, jp=2)]
    reg2, _ = PL.emparejar(ms, aps2, 'feralo77')
    r2 = rows(reg2)
    assert all(x['Fuente'] == 'log' and not x['Evento / Liga'] for x in r2) and len(r2) == 2, r2
    print("OK nick_es_la_llave")


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
    # Regla de Fer (12-ago-2026): un apunte sin log NO se publica, aunque lleve
    # resultado tecleado — la hoja se puede rellenar antes de jugar. Su fila
    # aparecerá cuando llegue el log. (Antes creaba una fila manual 'revisar'.)
    aps = [apunte('19/07/2026', 'Liga X', '1', mazo='Amulet Titan', res='W', jg=2, jp=1),
           apunte('20/07/2026', 'Liga X', '2', mazo='Storm')]
    reg, games = PL.emparejar([], aps, 'feralo77')
    assert rows(reg) == [] and games == [], rows(reg)
    # el bye sigue siendo la excepción: no hay log posible y completa la liga
    reg2, _ = PL.emparejar([], [apunte('19/07/2026', 'Liga X', '3', mazo='bye', res='W')], 'feralo77')
    r2 = rows(reg2)
    assert len(r2) == 1 and r2[0]['Fuente'] == 'manual', r2
    print("OK fila_papel (apunte sin log no se publica; bye sí)")


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


def test_concede_con_log_se_unifica():
    # Caso real Liga 2 R2 vs Zorro7x4: un 'concede' que EN REALIDAD se jugó y quedó logueado.
    # Antes salían DOS filas (un bye fantasma NA + un log huérfano con Liga vacía y '¿? revisar').
    # Ahora el log hereda la Liga/Ronda del concede y se funde en UNA sola fila.
    ms = [match('uz', utc(2026, 7, 12, 0, 30), '¿? (revisar)', res='W', jg=1, jp=0,
                sr='Salida', opp='Zorro7x4')]
    aps = [apunte('11/07/2026', 'Liga 2', '2', mazo='NA', res='W', jg=1, jp=0, sr='Salida',
                  notas='Concede')]
    reg, games = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 1, r                                   # una sola fila, no bye + huérfano
    assert r[0]['Fuente'] == 'log' and r[0]['match_uuid'] == 'uz', r
    assert r[0]['Evento / Liga'] == 'Liga 2' and r[0]['Ronda'] == '2', r
    assert r[0]['Rival'] == 'Zorro7x4', r                   # el rival lo pone el log
    assert r[0]['Notas de Match / Sideboard'] == 'Concede', r
    assert r[0]['Mazo del Oponente'] == '¿? (revisar)', r   # concedió: mazo desconocido, honesto
    assert r[0]['Fecha'] == '11/07/2026', r                 # gana la fecha del apunte
    assert len(games) == 1, games                           # el game del log SÍ cuenta
    # Un concede SIN log que le case (bye de verdad) sigue siendo fila manual.
    reg2, _ = PL.emparejar([], aps, 'feralo77')
    r2 = rows(reg2)
    assert len(r2) == 1 and r2[0]['Fuente'] == 'manual' and r2[0]['Ronda'] == '2', r2
    print("OK concede_con_log_se_unifica")


def test_fila_ejemplo():
    # La fila con nota "(ejemplo...)" se marca, no se descarta a ciegas.
    values = [
        ['Fecha', 'Evento / Liga', 'Ronda', 'Lista', 'Notas', 'Mazo rival (opcional)'],
        ['11/07/2026', 'Liga 1', '1', 'Stock', '(ejemplo: borra esta fila)', 'Broodscale'],
        ['11/07/2026', 'Liga 1', '2', 'Stock', 'partida real', 'Boros'],
    ]
    aps = PL.apuntes_de_valores(values, 'hoja', 'feralo77')
    assert len(aps) == 2 and aps[0].get('es_ejemplo') and aps[0]['notas'] == '', aps
    # (a) SIN log que le case: nada se publica (regla 12-ago), ni el ejemplo ni el real
    reg, _ = PL.emparejar([], aps, 'feralo77')
    assert rows(reg) == [], rows(reg)
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
    # un apunte sin log ya no se publica (regla 12-ago), así que no hay fila sin nick
    reg2, _ = PL.emparejar([], [apunte('14/07/2026', 'Liga 3', '3', mazo='Amulet Titan', res='W', jg=2, jp=0)], 'feralo77')
    assert rows(reg2) == []
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


def test_nick_con_errata():
    # Caso real (27-jul): Fer apuntó 'belfy' y el log dice 'bellfy'; 'PunThenWhine' y el
    # log 'PuntThenWhine'. Una letra bailada no debe romper el emparejamiento: antes esas
    # dos R3 quedaban como apunte manual sin resultado + log suelto sin liga.
    ms = [match('u1', utc(2026, 7, 26, 18, 0), 'Amulet Titan', res='W', jg=2, jp=0, opp='PuntThenWhine'),
          match('u2', utc(2026, 7, 27, 12, 0), 'Living End', res='L', jg=0, jp=2, opp='bellfy')]
    aps = [apunte('26/07/2026', 'Liga 7', '3', rival='PunThenWhine', mazo='Amulet', res='W'),
           apunte('27/07/2026', 'Liga 8', '3', rival='belfy', mazo='Living End', res='L')]
    reg, _ = PL.emparejar(ms, aps, 'feralo77')
    r = rows(reg)
    assert len(r) == 2 and all(x['Fuente'] == 'log' for x in r), r
    assert {x['Evento / Liga'] for x in r} == {'Liga 7', 'Liga 8'}, r
    assert {x['Ronda'] for x in r} == {'3'}, r
    # la tolerancia tiene límites: nicks muy cortos o distintos de verdad NO se funden
    assert PL.mismo_nick('belfy', 'bellfy') and PL.mismo_nick('punthenwhine', 'puntthenwhine')
    assert not PL.mismo_nick('mkc', 'mkd')          # 3 letras: a 1 edición es otro nick
    assert not PL.mismo_nick('juan', 'pepe')
    assert not PL.mismo_nick('', 'bellfy')
    print("OK nick_con_errata")


def test_listas_nombre_y_validez():
    # El nombre del fichero en Drive ES el nombre de la lista; los exports viejos ya
    # curados se ignoran y el prefijo "Deck - " del export de MTGO se limpia.
    assert PL._nombre_lista('UR Aggro Flashback') == 'UR Aggro Flashback'
    assert PL._nombre_lista('Pol 1 NF.txt') == 'Pol 1 NF'
    assert PL._nombre_lista('Deck - UR Twist (1).txt') == 'UR Twist'
    assert PL._nombre_lista('Deck - Izzet Stock (1).txt') is None   # legacy curado
    assert PL._nombre_lista('Izzet basics.txt') is None             # legacy curado
    assert PL._nombre_lista('') is None
    # al repo público solo pasan ficheros con pinta de mazo
    assert PL._es_lista_valida('\n'.join(f"4 Carta {i}" for i in range(10)))
    assert not PL._es_lista_valida('apuntes sueltos\nsin cartas\n1 linea suelta')
    assert not PL._es_lista_valida('4 Carta\n' * 20000)
    print("OK listas_nombre_y_validez")


def test_versiones_agrupan_el_mismo_maindeck():
    """Listas con el mismo maindeck y distinto sideboard son la MISMA versión.
    Medido el 2026-07-30: 'Ur Aggro Rage' (Pol) tiene 0 cartas de diferencia de
    maindeck con 'PT' (Fer), y 'Pol 1 NF' 1 carta con 'Stock'."""
    # 'PT' es el nombre de la LISTA (como está apuntada en la hoja); la VERSIÓN se
    # llama 'Aggro' desde el 30-jul. Renombrar la versión no toca los apuntes viejos.
    assert PL.version_de('PT') == 'Aggro'
    assert PL.version_de('Ur Aggro Rage') == 'Aggro'
    assert PL.version_de('UR Aggro Flashback') == 'Aggro'
    assert PL.version_de('Stock') == 'Stock'
    assert PL.version_de('2.0') == 'Stock'
    assert PL.version_de('Pol 1 NF') == 'Stock'
    assert PL.version_de('Basics') == 'Basics'
    # la de referencia NO es una versión jugada
    assert PL.version_de('Definitiva') == ''
    # desconocida o vacía -> vacío, nunca un cajón inventado
    assert PL.version_de('Lista que no existe') == ''
    assert PL.version_de('') == ''
    assert PL.version_de(None) == ''
    print("OK version_de agrupa por maindeck")


def test_lista_por_defecto_solo_donde_esta_declarada():
    """77 partidas de Pol salían de logs sin apunte y quedaban con Lista vacía,
    fuera de toda estadística. Fer confirmó que son Stock. Para quien no esté
    declarado se deja vacío: mejor un hueco que un dato inventado."""
    assert PL.lista_por_defecto('4c_PolG') == 'Stock'
    assert PL.lista_por_defecto('feralo77') == ''
    assert PL.lista_por_defecto('Inkmaster') == ''
    print("OK lista por defecto solo donde está declarada")


def test_fila_practica_lleva_lista_y_version():
    """Una partida de log sin apunte de Pol ya no sale con la Lista en blanco."""
    m = {'match_uuid': 'u1', '_fecha': '30/07/2026', 'arquetipo': 'Storm',
         'resultado': 'W', 'jg': 2, 'jp': 1, 'salida_robo': 'Salida',
         'mull_local': 0, 'mull_opp': 0, 'opp': 'algun_rival', 'confianza': 0.8}
    fila = PL._fila_practica(m, '4c_PolG')
    assert fila['Lista'] == 'Stock'
    assert fila['Versión'] == 'Stock'
    # Fer no tiene defecto declarado: se queda vacío, no se inventa
    assert PL._fila_practica(m, 'feralo77')['Lista'] == ''
    assert PL._fila_practica(m, 'feralo77')['Versión'] == ''
    print("OK la práctica de Pol lleva lista y versión")


def test_copia_de_fichero_no_dobla_games():
    # Caso real (11-ago): 'Match_GameLog_X.dat' + 'Match_GameLog_X (1).dat' con los
    # mismos bytes -> los games del match salían doblados (2-1 se convertía en 4-2).
    # parse_player debe saltarse el segundo fichero por CONTENIDO antes de parsearlo.
    import io, tempfile as tf
    from contextlib import redirect_stdout
    with tf.TemporaryDirectory() as d:
        raw = b'bytes de mentira que el parser no entiende'
        (Path(d) / 'Match_GameLog_x.dat').write_bytes(raw)
        (Path(d) / 'Match_GameLog_x (1).dat').write_bytes(raw)
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = PL.parse_player(d, 'feralo77')
        assert out == [], out
        assert buf.getvalue().count('contenido duplicado') == 1, buf.getvalue()
    print("OK copia_de_fichero_no_dobla_games")


def test_alias_de_arquetipo_unifica():
    # 'Storm' y 'Ruby Storm' son el mismo mazo (Fer, 12-ago): el registro, los games y
    # el fallback del apunte salen ya unificados al nombre canónico.
    assert PL.alias_arq('Storm') == 'Ruby Storm'
    assert PL.alias_arq('Eldrazi PT') == 'Eldrazi' and PL.alias_arq('Eldrazi Ramp') == 'Eldrazi'
    assert PL.alias_arq('Izzet Prowess') == 'Izzet Prowess'   # sin alias, se queda igual
    ms = [match('u1', utc(2026, 8, 1, 18, 0), 'Storm', opp='rival1'),
          match('u2', utc(2026, 8, 1, 19, 0), 'Ruby Storm', opp='rival2')]
    reg, games = PL.emparejar(ms, [], 'feralo77')
    assert {r['Arquetipo'] for r in rows(reg)} == {'Ruby Storm'}, rows(reg)
    assert {g['Arquetipo'] for g in games} == {'Ruby Storm'}, games
    assert PL.canon_mazo('Eldrazi Ramp') == 'Eldrazi'
    print("OK alias_de_arquetipo_unifica")


def test_liga_anulada_descarta_apuntes():
    # Liga anulada (anuladas.json): los apuntes de ese jugador y evento hasta el corte
    # (o sin fecha) desaparecen; una ronda posterior al corte SÍ cuenta (liga retomada),
    # y los demás jugadores no se ven afectados aunque jueguen la misma liga.
    reglas = [{'jugador': 'feralo77', 'evento': 'Liga 9', 'hasta': '10/08/2026'}]
    aps = [
        apunte('27/07/2026', evento='Liga 9', ronda='1', mazo='Mono-Green Eldrazi'),
        apunte('', evento='Liga 9', ronda='2', mazo='Ponza'),
        apunte('28/07/2026', evento='Liga 8', ronda='1', mazo='Storm'),
        apunte('20/08/2026', evento='Liga 9', ronda='1', mazo='Burn'),
    ]
    out = PL.filtrar_anuladas(aps, 'feralo77', reglas)
    assert [(a['evento'], a['fecha']) for a in out] == \
        [('Liga 8', '28/07/2026'), ('Liga 9', '20/08/2026')], out
    otros = PL.filtrar_anuladas([apunte('27/07/2026', evento='Liga 9', nick='4c_PolG')],
                                '4c_PolG', reglas)
    assert len(otros) == 1, otros
    print("OK liga_anulada_descarta_apuntes")


def test_version_esta_en_las_columnas_del_registro():
    assert 'Versión' in PL.REGISTRO_COLS
    assert PL.REGISTRO_COLS.index('Versión') == PL.REGISTRO_COLS.index('Lista') + 1
    print("OK la columna Versión existe y va junto a Lista")


if __name__ == '__main__':
    test_columna_rival_nick()
    test_nick_es_la_llave()
    test_pareja_basica()
    test_practica_intercalada()
    test_sesion_de_madrugada()
    test_medianoche_00_30()
    test_fila_papel()
    test_bye_no_consume_match()
    test_concede_con_log_se_unifica()
    test_fila_ejemplo()
    test_fallback_apunte_si_revisar()
    test_nicks_de_rival_publicos()
    test_scouting_por_rival()
    test_hoja_gana_legacy()
    test_norm_fecha_y_bye()
    test_nick_con_errata()
    test_listas_nombre_y_validez()
    test_versiones_agrupan_el_mismo_maindeck()
    test_lista_por_defecto_solo_donde_esta_declarada()
    test_fila_practica_lleva_lista_y_version()
    test_copia_de_fichero_no_dobla_games()
    test_alias_de_arquetipo_unifica()
    test_liga_anulada_descarta_apuntes()
    test_version_esta_en_las_columnas_del_registro()
    print("\nTodos los autotests del emparejamiento OK")
