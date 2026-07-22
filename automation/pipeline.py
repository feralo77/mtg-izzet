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
  3) Empareja apuntes ↔ partidas por FECHA (hora de Madrid) + orden cronológico.
  4) feralo77: además usa el tracker viejo (solo lectura, pestaña gid legacy) como
     apuntes históricos, con las mismas reglas de emparejamiento.
  5) Escribe registro.csv y games.csv en la raíz del repo. El workflow los commitea.

El robot NO escribe en ningún Google Sheet: SOLO lee. Scopes: drive.readonly +
spreadsheets.readonly. Por eso el 403 de escritura del flujo anterior desaparece por diseño.

Privacidad: ningún nick de rival de MTGO sale en los ficheros. En "Mazo del Oponente"
va el nombre de mazo legacy si el apunte lo trae; si no, el ARQUETIPO detectado por el
parser. La columna "Arquetipo" lleva siempre el arquetipo detectado.

Variables de entorno (secretos de GitHub):
  GOOGLE_SA_KEY       JSON de la cuenta de servicio
  TRACKER_SHEET_ID    id del tracker viejo (fuente de solo lectura de metadata histórica)
  MTG_FOLDER_ID       id de la carpeta "MTG · Izzet" (por defecto, la conocida)
  TRACKER_LEGACY_GID  gid de la pestaña manual del tracker (por defecto, 1091441461)

Jugadores registrados: automation/jugadores.json  {"players": ["feralo77", ...]}
"""
import os, sys, json, csv, tempfile
from pathlib import Path
from collections import defaultdict
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
                 "Reportado por", "Fuente"]
GAMES_COLS = ["match_uuid", "Game", "Arquetipo", "Salida / Robo", "Ganado", "Turnos",
              "Prowess", "Monjes", "Reportado por"]

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
        r = drive.files().list(q=q, fields='nextPageToken,files(id,name,mimeType)',
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
    """La hoja de Google 'Partidas — <nick>' dentro de la carpeta del jugador."""
    hojas = [f for f in list_children(drive, folder_id)
             if f['mimeType'] == 'application/vnd.google-apps.spreadsheet']
    if not hojas:
        return None
    pref = [f for f in hojas if 'partidas' in key(f['name'])]
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
    'mazo_rival': ['mazo rival (opcional)', 'mazo rival', 'mazo del oponente', 'rival', 'oponente'],
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
        if key(a['notas']).startswith('(ejemplo'):   # fila de ejemplo -> ignorar
            continue
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
def _fila_pareja(m, a, nick):
    mazo = a['mazo_rival'] or m['arquetipo']       # nombre legacy o arquetipo, NUNCA el nick
    return {
        'match_uuid': m['match_uuid'], 'Fecha': m['_fecha'], 'Evento / Liga': a['evento'],
        'Lista': a['lista'], 'Ronda': a['ronda'], 'Mazo del Oponente': mazo,
        'Arquetipo': m['arquetipo'], 'Resultado (W/L)': m['resultado'],
        'Juegos Ganados': m['jg'], 'Juegos Perdidos': m['jp'],
        'Salida / Robo (G1)': m['salida_robo'], 'Mulligans (Yo)': m['mull_local'],
        'Mulligans (Rival)': m['mull_opp'], 'Cartas Clave / MVP': a['mvp'],
        'Notas de Match / Sideboard': a['notas'], 'Reportado por': nick, 'Fuente': 'log',
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
            'Prowess': g['prowess'], 'Monjes': g['monks'], 'Reportado por': nick,
        })
    return filas

def _ronda_int(a):
    try:
        return int(str(a.get('ronda', '')).strip())
    except Exception:
        return 99

def emparejar(matches, apuntes, nick):
    """Empareja apuntes ↔ matches por fecha (Madrid) + orden cronológico.
    Devuelve (registro, games): registro = lista de {'row','sort','uuid'}."""
    for m in matches:
        h = m.get('hora')
        m['_madrid'] = h.astimezone(MADRID) if h else None
        m['_fecha'] = m['_madrid'].strftime('%d/%m/%Y') if m['_madrid'] else norm_fecha(m.get('fecha', ''))

    matches_ord = sorted(matches, key=lambda m: m['_madrid'] or datetime.min.replace(tzinfo=timezone.utc))
    m_by_day, a_by_day = defaultdict(list), defaultdict(list)
    for m in matches_ord:
        m_by_day[m['_fecha']].append(m)
    for a in apuntes:
        a_by_day[a['fecha']].append(a)

    registro, games = [], []
    for day in sorted(set(m_by_day) | set(a_by_day), key=day_key):
        ms = m_by_day.get(day, [])
        aps = a_by_day.get(day, [])
        byes = [a for a in aps if is_bye(a.get('mazo_rival'))]
        reales = [a for a in aps if not is_bye(a.get('mazo_rival'))]
        n = min(len(ms), len(reales))
        for i in range(n):                       # (ii) fila n del día ↔ match n cronológico
            registro.append({'row': _fila_pareja(ms[i], reales[i], nick),
                             'sort': (day_key(day), i), 'uuid': ms[i]['match_uuid']})
            games += _games_de_match(ms[i], nick)
        for j, m in enumerate(ms[n:]):           # (iv) matches de más -> práctica (log)
            registro.append({'row': _fila_practica(m, nick),
                             'sort': (day_key(day), n + j), 'uuid': m['match_uuid']})
            games += _games_de_match(m, nick)
        for a in reales[n:]:                      # (v) apuntes de más -> manual (papel/log perdido)
            registro.append({'row': _fila_manual(a, nick),
                             'sort': (day_key(day), 500 + _ronda_int(a)), 'uuid': ''})
        for a in byes:                            # bye/concede sin log -> manual
            registro.append({'row': _fila_manual(a, nick),
                             'sort': (day_key(day), 900 + _ronda_int(a)), 'uuid': ''})
    return registro, games

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
    registro_all, games_all = [], []

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
    logs = sum(1 for f in filas if f['Fuente'] == 'log')
    manual = sum(1 for f in filas if f['Fuente'] == 'manual')
    print(f"OK: registro.csv -> {len(filas)} filas ({logs} log + {manual} manual) · "
          f"games.csv -> {len(games_all)} games.")

if __name__ == '__main__':
    main()
