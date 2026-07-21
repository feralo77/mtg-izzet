#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — automatismo del tracker.

Corre en GitHub Actions con una CUENTA DE SERVICIO de Google. Sin que nadie toque
nada, cada día:
  1) lee las carpetas Logs_<nick> del Drive (carpeta "MTG · Izzet"),
  2) baja los ficheros Match_GameLog*.dat,
  3) corre el parser por jugador (solo las partidas donde ESE jugador juega),
  4) deduplica por match_uuid y estampa "Reportado por",
  5) escribe el resultado en la pestaña "Registro-logs" del tracker (Sheet).
El dashboard lee esa pestaña -> se actualiza solo.

Variables de entorno (secretos de GitHub):
  GOOGLE_SA_KEY     JSON de la cuenta de servicio
  TRACKER_SHEET_ID  id del Google Sheet del tracker
  MTG_FOLDER_ID     id de la carpeta "MTG · Izzet" (por defecto, la conocida)

Jugadores registrados: automation/jugadores.json  {"players": ["feralo77", ...]}
"""
import os, sys, json, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'parser'))
import mtgo_gamelog_parser as P

TAB = os.environ.get('TRACKER_TAB', 'Registro-logs')
COLS = ["match_uuid","Fecha","Evento / Liga","Lista","Ronda","Mazo del Oponente","Arquetipo",
        "Resultado (W/L)","Juegos Ganados","Juegos Perdidos","Salida / Robo (G1)",
        "Mulligans (Yo)","Mulligans (Rival)","Cartas Clave / MVP","Notas de Match / Sideboard",
        "Reportado por","Fuente"]

def clients():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    info = json.loads(os.environ['GOOGLE_SA_KEY'])
    creds = service_account.Credentials.from_service_account_info(info, scopes=[
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/spreadsheets'])
    return (build('drive', 'v3', credentials=creds, cache_discovery=False),
            build('sheets', 'v4', credentials=creds, cache_discovery=False))

def list_children(drive, parent_id, only_folders=False):
    q = f"'{parent_id}' in parents and trashed=false"
    if only_folders: q += " and mimeType='application/vnd.google-apps.folder'"
    out, tok = [], None
    while True:
        r = drive.files().list(q=q, fields='nextPageToken,files(id,name,mimeType)',
                               pageToken=tok, pageSize=1000).execute()
        out += r.get('files', []); tok = r.get('nextPageToken')
        if not tok: break
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

def download(drive, file_id, dest):
    from googleapiclient.http import MediaIoBaseDownload
    with open(dest, 'wb') as fh:
        dl = MediaIoBaseDownload(fh, drive.files().get_media(fileId=file_id))
        done = False
        while not done: _, done = dl.next_chunk()

def parse_player(logdir, nick):
    """Devuelve los matches donde 'nick' juega (dedupe de ficheros por nombre)."""
    seen, games = set(), []
    for fp in P.find_files(str(logdir)):
        b = os.path.basename(fp)
        if b in seen: continue
        seen.add(b)
        try:
            p = P.parse_gamelog(open(fp, 'rb').read())
        except Exception as e:
            print(f"  ! {b}: {e}"); continue
        if not p: continue
        names = P.detect_names([e['message'] for e in p['entries']])
        if nick not in names: continue        # solo SUS partidas
        opp = next((n for n in names if n != nick), None)
        for gm in P.split_games(p['entries']):
            games.append(P.extract_game(gm, nick, opp, p['match_uuid']))
    out = P.aggregate(games)
    for m in out: m['reported_by'] = nick
    return out

def ensure_tab(sheets, sheet_id):
    meta = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    if not any(s['properties']['title'] == TAB for s in meta['sheets']):
        sheets.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={
            'requests': [{'addSheet': {'properties': {'title': TAB}}}]}).execute()

def write_sheet(sheets, sheet_id, matches):
    ensure_tab(sheets, sheet_id)
    rows = [COLS]
    for m in matches:
        rows.append([m['match_uuid'], m['fecha'], '', 'Stock', '', m['opp'] or '', m['arquetipo'],
                     m['resultado'], m['jg'], m['jp'], m['salida_robo'], m['mull_local'],
                     m['mull_opp'], '', '', m.get('reported_by', ''), 'log'])
    sheets.spreadsheets().values().clear(spreadsheetId=sheet_id, range=f"{TAB}!A:Q").execute()
    sheets.spreadsheets().values().update(spreadsheetId=sheet_id, range=f"{TAB}!A1",
        valueInputOption='RAW', body={'values': rows}).execute()

def main():
    if not os.environ.get('GOOGLE_SA_KEY'):
        print("Sin GOOGLE_SA_KEY: el automatismo aún no está configurado. Saliendo sin error.")
        return
    folder_id = os.environ.get('MTG_FOLDER_ID', '16WDaeVHuOtyTaJDrNlVlpgbcN39iVhY6')
    sheet_id = os.environ['TRACKER_SHEET_ID']
    players = json.loads((HERE / 'jugadores.json').read_text(encoding='utf-8')).get('players', [])
    drive, sheets = clients()

    logs_folders = [f for f in list_children(drive, folder_id, only_folders=True)
                    if f['name'].startswith('Logs_')]
    tmp = Path(tempfile.mkdtemp())
    all_matches = []
    for lf in logs_folders:
        nick = lf['name'][len('Logs_'):]
        if players and nick not in players:
            print(f"- {lf['name']}: nick no registrado en jugadores.json, se ignora"); continue
        pdir = tmp / nick; pdir.mkdir(parents=True, exist_ok=True)
        gl = find_gamelogs(drive, lf['id'])
        for g in gl: download(drive, g['id'], pdir / g['name'])
        ms = parse_player(pdir, nick)
        print(f"- {nick}: {len(gl)} ficheros -> {len(ms)} partidas suyas")
        all_matches += ms

    by = {}
    for m in all_matches:                       # dedupe por match_uuid (solapes entre jugadores)
        by.setdefault(m['match_uuid'], m)
    matches = sorted(by.values(), key=lambda m: (m['hora'] or ''))
    write_sheet(sheets, sheet_id, matches)
    print(f"OK: {len(matches)} partidas escritas en la pestaña '{TAB}' del tracker.")

if __name__ == '__main__':
    main()
