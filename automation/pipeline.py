#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — automatismo CARPETA-CÉNTRICO del tracker de Izzet.

Corre en GitHub Actions con una CUENTA DE SERVICIO de Google, SOLO LECTURA.
Cada día, sin que nadie toque nada:
  1) Lee las carpetas Logs_<nick> del Drive (dentro de "MTG · Izzet").
  2) De cada una:
       - baja los Match_GameLog*.dat de ESE jugador y los parsea (solo sus partidas),
       - lee su hoja de Google "Partidas — <nick>" (los apuntes: Evento/Liga, Ronda,
         Lista, Notas y, opcional, "Mazo rival").
  3) Empareja apuntes ↔ partidas por RIVAL (columna "Rival" de la hoja, el nick: la
     llave más fuerte) + FECHA (hora de Madrid) + orden cronológico.
  4) feralo77: además usa el tracker viejo (solo lectura, pestaña gid legacy) como
     apuntes históricos, con las mismas reglas de emparejamiento.
  5) Escribe registro.csv y games.csv en la raíz del repo. El workflow los commitea.

El robot NO escribe en ningún Google Sheet: SOLO lee. Scopes: drive.readonly +
spreadsheets.readonly. Por eso el 403 de escritura del flujo anterior desaparece por diseño.

Nicks de rivales: PÚBLICOS por decisión de Fer (2026-07-22). La columna "Rival" lleva
el nick de MTGO del oponente (sale del log); "Mazo del Oponente" sigue llevando el
nombre de mazo del apunte o el ARQUETIPO detectado, y "Confianza" la confianza del
clasificador. Además se escribe scouting.csv (agregado por rival: récord, mazos,
cartas vistas) para preparar la ronda cuando se repite oponente en la MoL.

Variables de entorno (secretos de GitHub):
  GOOGLE_SA_KEY       JSON de la cuenta de servicio
  TRACKER_SHEET_ID    id del tracker viejo (fuente de solo lectura de metadata histórica)
  MTG_FOLDER_ID       id de la carpeta "MTG · Izzet" (por defecto, la conocida)
  TRACKER_LEGACY_GID  gid de la pestaña manual del tracker (por defecto, 1091441461)

Jugadores registrados: automation/jugadores.json  {"players": ["feralo77", ...]}
"""
import os, sys, json, csv, tempfile
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / 'parser'))
import mtgo_gamelog_parser as P

MADRID = ZoneInfo('Europe/Madrid')
LEGACY_PLAYER = 'feralo77'                       # el único con histórico en el tracker viejo
DEFAULT_LEGACY_GID = 1091441461

REGISTRO_COLS = ["match_uuid", "Fecha", "Evento / Liga", "Lista", "Ronda",
                 "Mazo del Oponente", "Arquetipo", "Resultado (W/L)", "Juegos Ganados",
                 "Juegos Perdidos", "Salida / Robo (G1)", "Mulligans (Yo)",
                 "Mulligans (Rival)", "Cartas Clave / MVP", "Notas de Match / Sideboard",
                 "Reportado por", "Fuente", "Rival", "Confianza"]
SCOUT_COLS = ["Rival", "Matches", "Récord", "WR %", "Mazo(s)", "Confianza media",
              "Turnos medios", "Cartas más vistas", "Visto por"]
GAMES_COLS = ["match_uuid", "Game", "Arquetipo", "Salida / Robo", "Ganado", "Turnos",
              "Prowess", "Monjes", "Mulls yo", "Mulls rival", "Mano yo", "Mano rival",
              "Robos yo", "Robos rival", "Tierras yo", "Tierras T1-3", "Accion T1",
              "Turno 1a amenaza", "Turno Cutter", "Hechizos yo", "Removal yo",
              "Descartes yo", "Reportado por"]

# ---------------------------------------------------------------- utilidades de datos
def norm(s):
    return (s or '').strip()

def key(s):
    return ' '.join(norm(s).lower().split())

def norm_fecha(s):
    s = norm(s)
    if not s:
        return ''
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%d/%m/%Y')
        except ValueError:
            pass
    return s

def day_key(s):
    try:
        return datetime.strptime(s, '%d/%m/%Y')
    except Exception:
        return datetime.max

def is_bye(mazo):
    """Un apunte de bye/concede/N-A no espera un log: se trata como fila manual."""
    m = key(mazo)
    return m in {'na', 'n/a', 'bye', 'concede', 'n/a (bye/concede)', 'bye/concede',
                 'bye / concede', 'sin rival'}

# Nombres cortos que se usan en los apuntes -> arquetipo canónico del dashboard.
# Se aplican cuando el clasificador no llega ('¿? (revisar)') y el apunte SÍ trae mazo.
CANON = {
    'dimir': 'Dimir Frog', 'vivoras': 'Sultai Midrange', 'gorys': "Esper Goryo's",
    'goryos': "Esper Goryo's", 'breach': 'Through the Breach', 'sam': 'Sam Combo',
    'loki': 'Azorius Loki', 'devoted': 'Devoted Combo', 'affinity': 'Izzet Affinity',
    'izzet': 'Izzet Prowess', 'ponza': 'Boros Ponza', 'boros': 'Boros Energy',
    'uw': 'Azorius Control', 'monob reanimator': 'Reanimator (MonoB)',
    'monor artifacts': 'MonoR Artifacts',
}

def canon_mazo(s):
    return CANON.get(key(s), norm(s))

# ------------------------------------------------------------- clientes Google (lectura)
def clients():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    info = json.loads(os.environ['GOOGLE_SA_KEY'])
    creds = service_account.Credentials.from_service_account_info(info, scopes=[
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/spreadsheets.readonly'])
    return (build('drive', 'v3', credentials=creds, cache_discovery=False),
            build('sheets', 'v4', credentials=creds, cache_discovery=False))

def list_children(drive, parent_id, only_folders=False):
    q = f"'{parent_id}' in parents and trashed=false"
    if only_folders:
        q += " and mimeType='application/vnd.google-apps.folder'"
    out, tok = [], None
    while True:
        r = drive.files().list(q=q, fields='nextPageToken,files(id,name,mimeType,createdTime)',
                               pageToken=tok, pageSize=1000).execute()
        out += r.get('files', [])
        tok = r.get('nextPageToken')
        if not tok:
            break
    return out

def find_gamelogs(drive, folder_id):
    logs, stack = [], [folder_id]
    while stack:
        for f in list_children(drive, stack.pop()):
            if f['mimeType'] == 'application/vnd.google-apps.folder':
                stack.append(f['id'])
            elif 'Match_GameLog' in f['name']:
                logs.append(f)
    return logs

def find_partidas_sheet(drive, folder_id):
    """La hoja de Google 'Partidas — <nick>' dentro de la carpeta del jugador.
    Si hay varias (p. ej. la vieja sin columna Rival y la nueva), gana la MÁS NUEVA:
    el conector no puede borrar la antigua y así el robot siempre lee el formato vigente."""
    hojas = [f for f in list_children(drive, folder_id)
             if f['mimeType'] == 'application/vnd.google-apps.spreadsheet']
    if not hojas:
        return None
    pref = [f for f in hojas if 'partidas' in key(f['name'])]
    pref.sort(key=lambda f: f.get('createdTime', ''), reverse=True)
    hojas.sort(key=lambda f: f.get('createdTime', ''), reverse=True)
    return (pref or hojas)[0]

def download(drive, file_id, dest):
    from googleapiclient.http import MediaIoBaseDownload
    with open(dest, 'wb') as fh:
        dl = MediaIoBaseDownload(fh, drive.files().get_media(fileId=file_id))
        done = False
        while not done:
            _, done = dl.next_chunk()

# ------------------------------------------------------------------ parseo de los logs
def parse_player(logdir, nick):
    """Matches (agregados, con games_list) donde 'nick' juega. Dedupe de ficheros por nombre."""
    seen, games = set(), []
    for fp in P.find_files(str(logdir)):
        b = os.path.basename(fp)
        if b in seen:
            continue
        seen.add(b)
        try:
            p = P.parse_gamelog(open(fp, 'rb').read())
        except Exception as e:
            print(f"    ! {b}: {e}")
            continue
        if not p:
            continue
        names = P.detect_names([e['message'] for e in p['entries']])
        if nick not in names:
            continue                             # solo SUS partidas
        opp = next((n for n in names if n != nick), None)
        for gm in P.split_games(p['entries']):
            games.append(P.extract_game(gm, nick, opp, p['match_uuid']))
    out = P.aggregate(games)
    for m in out:
        m['reported_by'] = nick
    return out

# ---------------------------------------------------------------- lectura de apuntes
COLMAP = {
    'fecha': ['fecha'],
    'evento': ['evento / liga', 'evento/liga', 'evento', 'liga'],
    'ronda': ['ronda', 'rnd'],
    'lista': ['lista'],
    'notas': ['notas de match / sideboard', 'notas', 'nota'],
    'mazo_rival': ['mazo rival (opcional)', 'mazo rival', 'mazo del oponente', 'mazo', 'oponente'],
    'rival_nick': ['rival', 'rival (nick)', 'rival mtgo', 'nick rival', 'nick'],
    'mvp': ['cartas clave / mvp', 'mvp', 'cartas clave'],
    'resultado': ['resultado (w/l)', 'resultado', 'res'],
    'jg': ['juegos ganados', 'ganados'],
    'jp': ['juegos perdidos', 'perdidos'],
    'salida_robo': ['salida / robo (g1)', 'salida / robo', 'salida/robo', 'g1'],
    'mull_local': ['mulligans (yo)', 'mulligans yo'],
    'mull_opp': ['mulligans (rival)', 'mulligans rival'],
    'reportado_por': ['reportado por', 'reportado', 'usuario'],
}

def _apunte_from_row(header_keys, cells, origen, nick):
    def col(field):
        for name in COLMAP[field]:
            if name in header_keys:
                i = header_keys.index(name)
                return norm(cells[i]) if i < len(cells) else ''
        return ''
    return {
        'fecha': norm_fecha(col('fecha')),
        'evento': col('evento'),
        'ronda': col('ronda'),
        'lista': col('lista'),
        'notas': col('notas'),
        'mazo_rival': col('mazo_rival'),
        'rival_nick': col('rival_nick'),
        'mvp': col('mvp'),
        'resultado': col('resultado').upper(),
        'jg': col('jg'),
        'jp': col('jp'),
        'salida_robo': col('salida_robo'),
        'mull_local': col('mull_local'),
        'mull_opp': col('mull_opp'),
        'reportado_por': col('reportado_por') or nick,
        'origen': origen,
    }

def leer_valores(sheets, spreadsheet_id, gid=None):
    """Devuelve la matriz de valores de una pestaña (por gid, o la primera)."""
    meta = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    hojas = meta.get('sheets', [])
    if not hojas:
        return []
    title = hojas[0]['properties']['title']
    if gid is not None:
        for s in hojas:
            if s['properties'].get('sheetId') == gid:
                title = s['properties']['title']
                break
    rng = f"'{title}'!A1:Z2000"
    r = sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
    return r.get('values', [])

def apuntes_de_valores(values, origen, nick):
    """Convierte una matriz de valores (con cabecera en la fila 1) en apuntes."""
    if not values:
        return []
    header_keys = [key(h) for h in values[0]]
    out = []
    for cells in values[1:]:
        if not any(norm(c) for c in cells):
            continue
        a = _apunte_from_row(header_keys, cells, origen, nick)
        # Fila con nota "(ejemplo...)": NO se descarta a ciegas — puede ser una fila real
        # editada sobre la plantilla (caso real: Liga 5 R5 de Fer). Se marca y decide el
        # emparejamiento: si casa con un log es real; si no, se tira (nunca crea manual).
        if key(a['notas']).startswith('(ejemplo'):
            a['es_ejemplo'] = True
            a['notas'] = ''                          # el texto de plantilla no aporta
        if not a['fecha'] and not a['mazo_rival'] and not a['evento']:
            continue
        out.append(a)
    return out

def combinar_apuntes(base, override):
    """Une apuntes por fecha+posición: 'override' (la hoja de partidas) pisa a 'base'
    (el tracker legacy) cuando ambos tienen fila en la misma posición del día."""
    by = defaultdict(list)
    for a in base:
        by[a['fecha']].append(a)
    ov = defaultdict(list)
    for a in override:
        ov[a['fecha']].append(a)
    out = []
    for day in list(by.keys()) + [d for d in ov if d not in by]:
        b, o = by.get(day, []), ov.get(day, [])
        for i in range(max(len(b), len(o))):
            out.append(o[i] if i < len(o) else b[i])
    return out

# -------------------------------------------------------------------- emparejamiento
def _mazo_apunte(m, a):
    """El mazo del apunte, salvo que el usuario haya escrito ahí el NICK del rival
    (error frecuente: la casilla es para el mazo) — en ese caso se ignora."""
    mazo = a['mazo_rival']
    if mazo and key(mazo) in (key(m.get('opp') or ''), key(a.get('rival_nick') or '')):
        return ''
    return mazo

def _fila_pareja(m, a, nick):
    mazo = _mazo_apunte(m, a) or m['arquetipo']    # nombre del apunte o arquetipo detectado
    return {
        'match_uuid': m['match_uuid'], 'Fecha': a['fecha'] or m['_fecha'], 'Evento / Liga': a['evento'],
        'Lista': a['lista'], 'Ronda': a['ronda'], 'Mazo del Oponente': mazo,
        'Arquetipo': m['arquetipo'], 'Resultado (W/L)': m['resultado'],
        'Juegos Ganados': m['jg'], 'Juegos Perdidos': m['jp'],
        'Salida / Robo (G1)': m['salida_robo'], 'Mulligans (Yo)': m['mull_local'],
        'Mulligans (Rival)': m['mull_opp'], 'Cartas Clave / MVP': a['mvp'],
        'Notas de Match / Sideboard': a['notas'], 'Reportado por': nick, 'Fuente': 'log',
        'Rival': m.get('opp') or '', 'Confianza': m.get('confianza_txt') or f"{int(m.get('confianza', 0) * 100)}%",
    }

def _fila_practica(m, nick):
    return {
        'match_uuid': m['match_uuid'], 'Fecha': m['_fecha'], 'Evento / Liga': '',
        'Lista': '', 'Ronda': '', 'Mazo del Oponente': m['arquetipo'],
        'Arquetipo': m['arquetipo'], 'Resultado (W/L)': m['resultado'],
        'Juegos Ganados': m['jg'], 'Juegos Perdidos': m['jp'],
        'Salida / Robo (G1)': m['salida_robo'], 'Mulligans (Yo)': m['mull_local'],
        'Mulligans (Rival)': m['mull_opp'], 'Cartas Clave / MVP': '',
        'Notas de Match / Sideboard': '', 'Reportado por': nick, 'Fuente': 'log',
        'Rival': m.get('opp') or '', 'Confianza': f"{int(m.get('confianza', 0) * 100)}%",
    }

def _fila_manual(a, nick):
    return {
        'match_uuid': '', 'Fecha': a['fecha'], 'Evento / Liga': a['evento'],
        'Lista': a['lista'], 'Ronda': a['ronda'], 'Mazo del Oponente': a['mazo_rival'],
        'Arquetipo': a['mazo_rival'], 'Resultado (W/L)': a['resultado'],
        'Juegos Ganados': a['jg'], 'Juegos Perdidos': a['jp'],
        'Salida / Robo (G1)': a['salida_robo'], 'Mulligans (Yo)': a['mull_local'],
        'Mulligans (Rival)': a['mull_opp'], 'Cartas Clave / MVP': a['mvp'],
        'Notas de Match / Sideboard': a['notas'] or 'revisar (sin log)',
        'Reportado por': a.get('reportado_por') or nick, 'Fuente': 'manual',
        'Rival': a.get('rival_nick', ''), 'Confianza': '',
    }

def _games_de_match(m, nick):
    filas = []
    for g in m['games_list']:
        lp = g['local_on_play']
        sr = 'Salida' if lp else ('Robo' if lp is not None else '')
        filas.append({
            'match_uuid': m['match_uuid'], 'Game': g.get('game_idx', ''),
            'Arquetipo': m['arquetipo'], 'Salida / Robo': sr,
            'Ganado': 1 if g['winner'] == 'local' else 0, 'Turnos': g['turns'],
            'Prowess': g['prowess'], 'Monjes': g['monks'],
            'Mulls yo': g.get('mull_local', 0), 'Mulls rival': g.get('mull_opp', 0),
            'Mano yo': g.get('hand_local', 7), 'Mano rival': g.get('hand_opp', 7),
            'Robos yo': g.get('draws_local', 0), 'Robos rival': g.get('draws_opp', 0),
            'Tierras yo': g.get('lands_local', 0), 'Tierras T1-3': g.get('lands_t3', 0),
            'Accion T1': 1 if g.get('t1_action') else 0,
            'Turno 1a amenaza': g.get('first_threat_turn', 0),
            'Turno Cutter': g.get('cutter_turn', 0),
            'Hechizos yo': len(g.get('my_casts', [])),
            'Removal yo': len(g.get('removal', [])),
            'Descartes yo': g.get('disc_local', 0),
            'Reportado por': nick,
        })
    return filas

def _ronda_int(a):
    try:
        return int(str(a.get('ronda', '')).strip())
    except Exception:
        return 99

def _ts(dt):
    """Clave de orden numérica y comparable (POSIX) a partir de un datetime."""
    if dt is None:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MADRID)
    return dt.timestamp()

def _sim(a, m):
    """Compatibilidad apunte ↔ partida: RIVAL (nick, la llave más fuerte — columna Rival
    de la hoja), fecha (±1 día, ancla por el desfase de medianoche), resultado, marcador
    de juegos y salida/robo. Cuanto mayor, mejor pareja."""
    s = 0.0
    na, nm = key(a.get('rival_nick')), key(m.get('opp') or '')
    if na and nm:
        s += 3.0 if na == nm else -3.0
    fa, fm = day_key(a['fecha']), day_key(m['_fecha'])
    if fa != datetime.max and fm != datetime.max:
        dd = abs((fa - fm).days)
        s += 2.0 if dd <= 1 else (-1.5 if dd == 2 else -4.0)
    ra, rm = (a.get('resultado') or '').upper(), (m.get('resultado') or '').upper()
    if ra in ('W', 'L') and rm in ('W', 'L'):
        s += 2.0 if ra == rm else -2.0
    try:
        if str(a.get('jg')).strip() != '' and str(a.get('jp')).strip() != '':
            if int(a['jg']) == int(m['jg']) and int(a['jp']) == int(m['jp']):
                s += 1.0
    except Exception:
        pass
    sa, sm = key(a.get('salida_robo')), key(m.get('salida_robo'))
    if sa and sm:
        s += 0.5 if sa == sm else -0.25
    return s

def emparejar(matches, apuntes, nick):
    """Empareja apuntes ↔ partidas por ORDEN CRONOLÓGICO GLOBAL (alineación de secuencias
    tipo diff, anclada por fecha en hora de Madrid ±1 día + resultado + marcador). Es robusto
    al desfase de medianoche (una sesión de liga jugada de madrugada cae el día siguiente) y a
    una partida de práctica intercalada. Devuelve (registro, games)."""
    for m in matches:
        h = m.get('hora')
        m['_madrid'] = h.astimezone(MADRID) if h else None
        m['_fecha'] = m['_madrid'].strftime('%d/%m/%Y') if m['_madrid'] else norm_fecha(m.get('fecha', ''))

    logs = sorted(matches, key=lambda m: m['_madrid'] or datetime.min.replace(tzinfo=timezone.utc))
    byes = [a for a in apuntes if is_bye(a.get('mazo_rival')) and not a.get('es_ejemplo')]
    reales = [a for a in apuntes if not is_bye(a.get('mazo_rival'))]

    # Alineación por programación dinámica (Needleman-Wunsch): emparejar, saltar un log
    # (práctica) o saltar un apunte (papel/log perdido). Maximiza la similitud total.
    SKIP = -0.05
    n, ml = len(reales), len(logs)
    dp = [[0.0] * (ml + 1) for _ in range(n + 1)]
    bt = [[None] * (ml + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + SKIP
        bt[i][0] = 'A'
    for j in range(1, ml + 1):
        dp[0][j] = dp[0][j - 1] + SKIP
        bt[0][j] = 'L'
    for i in range(1, n + 1):
        for j in range(1, ml + 1):
            pair = dp[i - 1][j - 1] + _sim(reales[i - 1], logs[j - 1])
            skipA = dp[i - 1][j] + SKIP
            skipL = dp[i][j - 1] + SKIP
            best = max(pair, skipA, skipL)
            dp[i][j] = best
            bt[i][j] = 'P' if best == pair else ('A' if best == skipA else 'L')

    registro, games = [], []
    i, j = n, ml
    while i > 0 or j > 0:
        c = bt[i][j]
        if c == 'P':
            a, m = reales[i - 1], logs[j - 1]
            # Clasificador sin confianza + mazo apuntado por el jugador -> manda el apunte
            # (normalizado a nombre canónico). La Confianza queda como 'apunte'.
            mazo_a = _mazo_apunte(m, a)
            if m['arquetipo'].startswith('¿?') and mazo_a:
                m['arquetipo'] = canon_mazo(mazo_a)
                m['confianza_txt'] = 'apunte'
            registro.append({'row': _fila_pareja(m, a, nick), 'sort': _ts(m['_madrid']),
                             'uuid': m['match_uuid']})
            games += _games_de_match(m, nick)
            i -= 1; j -= 1
        elif c == 'A':                            # apunte sin log -> manual (papel/log perdido)
            a = reales[i - 1]
            if not a.get('es_ejemplo'):           # una fila de ejemplo jamás inventa un match
                registro.append({'row': _fila_manual(a, nick),
                                 'sort': _ts(day_key(a['fecha'])) + _ronda_int(a) * 60, 'uuid': ''})
            i -= 1
        else:                                     # log sin apunte -> práctica
            m = logs[j - 1]
            registro.append({'row': _fila_practica(m, nick), 'sort': _ts(m['_madrid']),
                             'uuid': m['match_uuid']})
            games += _games_de_match(m, nick)
            j -= 1
    for a in byes:                                # bye/concede sin log -> manual
        registro.append({'row': _fila_manual(a, nick),
                         'sort': _ts(day_key(a['fecha'])) + _ronda_int(a) * 60, 'uuid': ''})
    return registro, games

# ------------------------------------------------------------- scouting por rival
def scouting_por_rival(matches_por_nick):
    """Agrega por RIVAL (nick de MTGO): récord nuestro, mazos que le hemos visto,
    confianza del clasificador, turnos medios y sus cartas más vistas. Alimenta
    scouting.csv y la pestaña Scouting del dashboard (nicks públicos por decisión
    de Fer, 2026-07-22)."""
    by = {}
    for nick, matches in matches_por_nick:
        for m in matches:
            opp = m.get('opp')
            if not opp:
                continue
            r = by.setdefault(opp, {'n': 0, 'w': 0, 'l': 0, 'arqs': Counter(), 'conf': [],
                                    'turns': [], 'cards': Counter(), 'vistos': set()})
            r['n'] += 1
            if m['resultado'] == 'W':
                r['w'] += 1
            elif m['resultado'] == 'L':
                r['l'] += 1
            r['arqs'][m['arquetipo']] += 1
            r['conf'].append(m.get('confianza', 0))
            if m.get('turns_avg'):
                r['turns'].append(m['turns_avg'])
            for c in m.get('opp_cards', []):
                r['cards'][c] += 1
            r['vistos'].add(nick)
    filas = []
    for opp, r in sorted(by.items(), key=lambda kv: (-kv[1]['n'], kv[0].lower())):
        jugados = r['w'] + r['l']
        filas.append({
            'Rival': opp, 'Matches': r['n'], 'Récord': f"{r['w']}-{r['l']}",
            'WR %': f"{round(100 * r['w'] / jugados)}%" if jugados else '',
            'Mazo(s)': ", ".join(f"{a} ({k})" if k > 1 else a for a, k in r['arqs'].most_common()),
            'Confianza media': f"{int(100 * sum(r['conf']) / len(r['conf']))}%" if r['conf'] else '',
            'Turnos medios': round(sum(r['turns']) / len(r['turns']), 1) if r['turns'] else '',
            'Cartas más vistas': P.top_cards(r['cards'], 12),
            'Visto por': ", ".join(sorted(r['vistos'])),
        })
    return filas

# ------------------------------------------------------------------------ escritura
def escribir_csv(path, cols, filas):
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for f in filas:
            w.writerow(f)

# ------------------------------------------------------------------------------ main
def main():
    if not os.environ.get('GOOGLE_SA_KEY'):
        print("Sin GOOGLE_SA_KEY: el automatismo aún no está configurado. Saliendo sin error.")
        return
    folder_id = os.environ.get('MTG_FOLDER_ID', '16WDaeVHuOtyTaJDrNlVlpgbcN39iVhY6')
    tracker_id = os.environ.get('TRACKER_SHEET_ID')
    legacy_gid = int(os.environ.get('TRACKER_LEGACY_GID', DEFAULT_LEGACY_GID))
    players = json.loads((HERE / 'jugadores.json').read_text(encoding='utf-8')).get('players', [])
    drive, sheets = clients()

    # apuntes legacy (tracker viejo), solo lectura, solo para feralo77
    legacy_apuntes = []
    if tracker_id:
        try:
            vals = leer_valores(sheets, tracker_id, gid=legacy_gid)
            legacy_apuntes = apuntes_de_valores(vals, 'legacy', LEGACY_PLAYER)
            print(f"Legacy (tracker viejo, solo lectura): {len(legacy_apuntes)} apuntes históricos.")
        except Exception as e:
            print(f"! No pude leer el tracker legacy: {e}")

    logs_folders = [f for f in list_children(drive, folder_id, only_folders=True)
                    if f['name'].startswith('Logs_')]
    tmp = Path(tempfile.mkdtemp())
    registro_all, games_all, scout_src = [], [], []

    for lf in logs_folders:
        nick = lf['name'][len('Logs_'):]
        if players and nick not in players:
            print(f"- {lf['name']}: nick no registrado en jugadores.json, se ignora")
            continue
        # 1) logs -> matches
        pdir = tmp / nick
        pdir.mkdir(parents=True, exist_ok=True)
        gl = find_gamelogs(drive, lf['id'])
        for g in gl:
            download(drive, g['id'], pdir / g['name'])
        matches = parse_player(pdir, nick)
        # 2) apuntes de la hoja "Partidas — <nick>"
        sheet_apuntes = []
        ps = find_partidas_sheet(drive, lf['id'])
        if ps:
            try:
                sheet_apuntes = apuntes_de_valores(leer_valores(sheets, ps['id']), 'hoja', nick)
            except Exception as e:
                print(f"    ! No pude leer '{ps['name']}': {e}")
        # 3) para feralo77, el legacy complementa como apuntes (la hoja gana si solapa)
        apuntes = sheet_apuntes
        if nick == LEGACY_PLAYER:
            apuntes = combinar_apuntes(legacy_apuntes, sheet_apuntes)
        # 4) emparejar
        reg, gm = emparejar(matches, apuntes, nick)
        registro_all += reg
        games_all += gm
        scout_src.append((nick, matches))
        print(f"- {nick}: {len(gl)} ficheros -> {len(matches)} partidas · "
              f"apuntes: {len(sheet_apuntes)} hoja + {len(apuntes) - len(sheet_apuntes)} legacy "
              f"-> {len(reg)} filas de registro / {len(gm)} games")

    # dedupe por match_uuid (los manual sin uuid se conservan todos), orden cronológico
    registro_all.sort(key=lambda r: r['sort'])
    vistos, filas = set(), []
    for r in registro_all:
        uid = r['uuid']
        if uid:
            if uid in vistos:
                continue
            vistos.add(uid)
        filas.append(r['row'])

    escribir_csv(REPO / 'registro.csv', REGISTRO_COLS, filas)
    escribir_csv(REPO / 'games.csv', GAMES_COLS, games_all)
    scout = scouting_por_rival(scout_src)
    escribir_csv(REPO / 'scouting.csv', SCOUT_COLS, scout)
    logs = sum(1 for f in filas if f['Fuente'] == 'log')
    manual = sum(1 for f in filas if f['Fuente'] == 'manual')
    print(f"OK: registro.csv -> {len(filas)} filas ({logs} log + {manual} manual) · "
          f"games.csv -> {len(games_all)} games · scouting.csv -> {len(scout)} rivales.")

if __name__ == '__main__':
    main()
