#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mtgo_gamelog_parser.py  (v4 — extracción máxima + clasificador con confianza)
Decodifica los *Match_GameLog*.dat binarios de Magic Online, PARTE cada match en sus
games y extrae el máximo de datos por game: turnos, tu curva de hechizos, disparos de
prowess, fichas de Monje (Cori-Steel Cutter), objetivos de tu removal, manos, mulligans,
descartes y la lista COMPLETA del rival (para clasificar el arquetipo mucho mejor).

Novedad v4 — clasificador de arquetipo con CONFIANZA (idea tomada del cliente
open-source de MyMTGO, reimplementada aquí; NO es su código): cada arquetipo tiene
firmas PONDERADAS (cartas casi únicas pesan más que las de reparto). El clasificador
puntúa por (fuerza de la señal + cobertura de las cartas clave), penaliza cuando dos
arquetipos empatan (ambigüedad) y baja la confianza si viste pocas cartas del rival
(evidencia fina). Devuelve arquetipo + confianza 0-1 + alternativas; por debajo del
umbral marca '¿? (revisar)' en vez de arriesgar una etiqueta dudosa.

Genera 4 ficheros:
  1) <out>            -> CSV del Registro (match, compatible con el tracker/dashboard)
  2) <out>.matches    -> detalle por MATCH (agregados ricos + confianza/alternativas)
  3) <out>.games      -> detalle por GAME (la granularidad más fina)
  4) <out>.scouting   -> informe de scouting por arquetipo (récord + cartas más vistas)

Cada .dat suele contener el MATCH ENTERO (todos los games). Agrupamos por match_uuid.
Basado en el formato del cliente open-source de MyMTGO (github.com/mymtgo/client).

Uso:
  python3 mtgo_gamelog_parser.py --dir "<carpeta con .dat>" --user <usuario_MTGO> --out registro.csv
  python3 mtgo_gamelog_parser.py --selftest
"""
import os, re, csv, sys, struct, argparse
from datetime import datetime, timezone
from collections import defaultdict, Counter

DOTNET_EPOCH_OFFSET = 621355968000000000
PLAYER = r'[A-Za-z0-9_-]+'
CARD = r'@\[([^@]+)@:[^\]]*\]'          # @[Nombre@:id:@] -> Nombre
NUMWORD = {'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,
           'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12}

# ---------- Decodificador binario (replica ParseGameLogBinary::run) ----------
def read_varint(raw, pos):
    val = 0; shift = 0
    while True:
        if pos >= len(raw): return None, pos
        b = raw[pos]; pos += 1
        val |= (b & 0x7F) << shift; shift += 7
        if not (b & 0x80): break
    return val, pos

def parse_gamelog(raw):
    length = len(raw)
    if length < 20: return None
    pos = 0
    _ver = raw[pos]; pos += 2
    ulen = raw[pos]; pos += 1
    if pos + ulen > length: return None
    match_uuid = raw[pos:pos+ulen].decode('latin-1','replace'); pos += ulen
    pos += 2
    ulen2 = raw[pos]; pos += 1
    if pos + ulen2 > length: return None
    game_uuid = raw[pos:pos+ulen2].decode('latin-1','replace'); pos += ulen2
    entries = []
    while pos + 10 <= length:
        start = pos
        ticks = struct.unpack_from('<Q', raw, pos)[0]; pos += 8
        pos += 1
        msglen, pos = read_varint(raw, pos)
        if msglen is None or pos + msglen > length:
            pos = start; break
        message = raw[pos:pos+msglen].decode('utf-8','replace'); pos += msglen
        unix = (ticks - DOTNET_EPOCH_OFFSET) / 10_000_000
        try: ts = datetime.fromtimestamp(unix, tz=timezone.utc)
        except Exception: ts = None
        entries.append({'ts': ts, 'message': message})
    return {'match_uuid': match_uuid, 'game_uuid': game_uuid, 'entries': entries}

# ---------- Nombres de jugadores ----------
def detect_names(msgs):
    names = []
    for m in msgs:
        for rx in (rf'^@P({PLAYER}) chooses to play', rf'^@P({PLAYER}) wins the game',
                   rf'^@P({PLAYER}) rolled a \d', rf'^@P@P?({PLAYER}) joined the game',
                   rf'^@P({PLAYER}) (?:leads|wins) the match', rf'^@P({PLAYER}) draws a card',
                   rf'^@P({PLAYER}) casts '):
            g = re.match(rx, m)
            if g and g.group(1) not in names: names.append(g.group(1))
    return names

# ---------- Partir un match en games ----------
def _has_content(buf):
    # un game "de verdad" tiene decisión de salida, hechizos o turnos
    return any(re.search(r'chooses to play|casts @\[|@PTurn \d', e['message']) for e in buf)

def split_games(entries):
    games, cur = [], []
    for e in entries:
        cur.append(e)
        m = e['message']
        end = re.match(rf'^@P{PLAYER} wins the game', m) or re.match(rf'^@P{PLAYER} has conceded from the game', m)
        # cerrar SOLO si el buffer tiene juego real: así el par "X se rinde"+"Y gana"
        # (dos líneas del mismo game) no crea un game fantasma
        if end and _has_content(cur):
            games.append(cur); cur = []
    if cur and _has_content(cur):
        games.append(cur)
    return games

# ---------- Extracción RICA por game ----------
def extract_game(entries, local, opp, match_uuid):
    msgs = [e['message'] for e in entries]
    ts = next((e['ts'] for e in entries if e['ts']), None)

    turns = 0
    for m in msgs:
        g = re.match(r'@PTurn (\d+):', m)
        if g: turns = max(turns, int(g.group(1)))

    local_on_play = None
    for m in msgs:
        g = re.match(rf'@P({PLAYER}) chooses to play (first|second)', m)
        if g:
            p, which = g.group(1), g.group(2)
            first = p if which == 'first' else (opp if p == local else local)
            local_on_play = (first == local); break

    winner = None
    for m in msgs:
        g = re.match(rf'@P({PLAYER}) wins the game', m)
        if g: winner = 'local' if g.group(1) == local else 'opp'
        c = re.match(rf'@P({PLAYER}) has conceded from the game', m)
        if c: winner = 'opp' if c.group(1) == local else 'local'

    match_score = None
    for m in msgs:
        g = re.match(rf'@P({PLAYER}) (?:leads|wins) the match (\d+)-(\d+)', m)
        if g:
            a, b = int(g.group(2)), int(g.group(3))
            match_score = (a, b) if g.group(1) == local else (b, a)

    mull = Counter(); hand = {}; casts = {local: [], opp: []}
    prowess = monks = activ = 0; removal = []; disc = Counter()
    for m in msgs:
        g = re.match(rf'@P({PLAYER}) mulligans to', m)
        if g: mull[g.group(1)] += 1; continue
        g = re.match(rf'@P({PLAYER}).*?begins the game with (\w+) cards? in hand', m)
        if g: hand[g.group(1)] = NUMWORD.get(g.group(2), 0); continue
        g = re.match(rf'@P({PLAYER}) casts {CARD}', m)
        if g:
            p, card = g.group(1), g.group(2).strip()
            if p in casts: casts[p].append(card)
            t = re.search(rf'casts {CARD} targeting {CARD}', m)
            if p == local and t: removal.append(f"{card}->{t.group(2).strip()}")
            continue
        g = re.match(rf'@P({PLAYER}) puts a triggered ability from {CARD} onto the stack \(Prowess\)', m)
        if g and g.group(1) == local: prowess += 1; continue
        g = re.match(rf"@P({PLAYER})'s {CARD} creates a Monk Token", m)
        if g and g.group(1) == local: monks += 1; continue
        g = re.match(rf'@P({PLAYER}) activates an ability', m)
        if g and g.group(1) == local: activ += 1; continue
        g = re.match(rf'@P({PLAYER}) discards {CARD}', m)
        if g: disc[g.group(1)] += 1; continue

    return {'match_uuid': match_uuid, 'ts': ts, 'local': local, 'opp': opp,
            'turns': turns, 'local_on_play': local_on_play, 'winner': winner,
            'match_score': match_score, 'mull_local': mull.get(local, 0), 'mull_opp': mull.get(opp, 0),
            'hand_local': hand.get(local, 7), 'hand_opp': hand.get(opp, 7),
            'my_casts': casts[local], 'opp_casts': casts[opp],
            'prowess': prowess, 'monks': monks, 'activ': activ,
            'removal': removal, 'disc_local': disc.get(local, 0), 'disc_opp': disc.get(opp, 0)}

# ---------- Clasificador de arquetipo por cartas del rival (con confianza) ----------
# Firmas PONDERADAS por arquetipo: (carta, peso). El peso mide cuánto DISCRIMINA la
# carta a favor de ESE arquetipo, no lo buena que es:
#   3 = casi única del arquetipo (verla casi lo confirma; p.ej. Goblin Charbelcher)
#   2 = indicador fuerte (a veces se salpica en otros mazos)
#   1 = de reparto (aparece aquí pero también en otros arquetipos)
# Cartas ubicuas (Lightning Bolt, Fatal Push...) NO se listan: no discriminan, así que
# el modelo por firmas las ignora solo.
SIG = [
    ('Broodscale', [('Basking Broodscale',3),('Blade of the Bloodchief',2),("Kozilek's Command",1)]),
    ("Esper Goryo's", [("Goryo's Vengeance",3),('Atraxa',2),('Ephemerate',2)]),
    ('Grixis Reanimator', [('Persist',3),('Archon of Cruelty',2),('Abhorrent Oculus',2)]),
    ('Dimir Frog', [('Psychic Frog',3)]),
    ('Boros Energy', [('Guide of Souls',2),('Ocelot Pride',3),('Ajani, Nacatl Pariah',3),('Galvanic Discharge',2)]),
    ('Izzet Affinity', [('Kappa Cannoneer',3),("Urza's Saga",1),('Thought Monitor',2),('Pinnacle Emissary',2),('Mox Opal',2)]),
    ('Eldrazi', [('Thought-Knot Seer',2),('Ugin',1),('Chalice of the Void',1),("Kozilek, the Broodmother",2),('Devourer of Destiny',2)]),
    ('Amulet Titan', [('Amulet of Vigor',3),('Primeval Titan',2)]),
    ('Golgari Yawgmoth', [('Yawgmoth, Thran Physician',3),("Agatha's Soul Cauldron",2)]),
    ('Ruby Storm', [('Ruby Medallion',3),('Grapeshot',2),('Past in Flames',2)]),
    ('Living End', [('Living End',3),('Shardless Agent',2)]),
    ('Tameshi Belcher', [('Goblin Charbelcher',3)]),
    ('Boros Ponza', [('High Noon',2),('Erode',2),('Demolition Field',1),('Cleansing Wildfire',2),('Magus of the Moon',2),('Price of Freedom',2)]),
    ('Neoform', [('Neoform',3),('Allosaurus Rider',2),("Summoner's Pact",2)]),
    ('Izzet Prowess', [('Slickshot Show-Off',2),('Cori-Steel Cutter',2),('Monastery Swiftspear',2)]),
    ('Azorius Control', [('Counterspell',1),('Wrath of the Skies',2),('Teferi, Time Raveler',2)]),
]

# Parámetros del scoring (mismo espíritu que MyMTGO EstimateArchetypeLocally):
SATURATION = 4.0        # peso de firma a partir del cual la señal satura a 1.0
AMBIGUITY_GAP = 1.0     # si el 2º arquetipo (distinto) queda a menos de esto -> penalización
AMBIGUITY_PENALTY = 0.7 # factor cuando hay empate ambiguo
MIN_OBSERVED = 4        # cartas distintas del rival para evidencia plena
LOW_CONFIDENCE = 0.35   # por debajo -> '¿? (revisar)' en vez de arriesgar etiqueta

def classify_scored(cards):
    """Devuelve (arquetipo, confianza 0-1, [(alternativa, confianza), ...])."""
    cset = set(cards)
    scored = []
    for name, sigs in SIG:
        matched_w = sum(w for c, w in sigs if c in cset)
        if matched_w > 0:
            total_w = sum(w for _c, w in sigs)
            scored.append({'name': name, 'w': matched_w, 'total': total_w})
    if not scored:
        return '¿? (revisar)', 0.0, []
    scored.sort(key=lambda s: s['w'], reverse=True)
    best = scored[0]

    signal = min(1.0, best['w'] / SATURATION)          # fuerza absoluta de la evidencia
    coverage = best['w'] / best['total']               # cuánto de las cartas clave vimos
    base = 0.75 * signal + 0.25 * coverage

    # Ambigüedad: dos arquetipos DISTINTOS casi empatados -> menos confianza
    for s in scored[1:]:
        if s['name'] != best['name']:
            if best['w'] - s['w'] < AMBIGUITY_GAP:
                base *= AMBIGUITY_PENALTY
            break

    # Evidencia: si viste pocas cartas del rival, baja la confianza; salvo que hayas
    # visto una firma casi única (peso>=3), que se sostiene sola.
    evidence = min(1.0, len(cset) / MIN_OBSERVED)
    if best['w'] >= 3:
        evidence = max(evidence, 0.8)
    conf = round(base * evidence, 2)

    name = best['name']
    if name == 'Dimir Frog' and (('Unearth' in cset) or ('Persist' in cset)):
        name = 'Grixis Frog/Reanimator'
    alts = [(s['name'], round(min(1.0, s['w'] / SATURATION), 2))
            for s in scored[1:3] if s['name'] != best['name']]
    if conf < LOW_CONFIDENCE:
        return '¿? (revisar)', conf, alts
    return name, conf, alts

def classify(cards):
    """Compatibilidad: solo el nombre del arquetipo (usa classify_scored por dentro)."""
    return classify_scored(cards)[0]

# ---------- Agregar games -> matches ----------
def aggregate(games):
    by = defaultdict(list)
    for g in games:
        if g and g['match_uuid']: by[g['match_uuid']].append(g)
    matches = []
    for mid, gs in by.items():
        gs.sort(key=lambda x: x['ts'] or datetime.min.replace(tzinfo=timezone.utc))
        for i, g in enumerate(gs, 1): g['game_idx'] = i
        local = next((g['local'] for g in gs if g['local']), None)
        opp = Counter(g['opp'] for g in gs if g['opp']).most_common(1)
        opp = opp[0][0] if opp else None
        jg = sum(1 for g in gs if g['winner'] == 'local')
        jp = sum(1 for g in gs if g['winner'] == 'opp')
        best = None
        for g in gs:
            if g['match_score'] and (best is None or sum(g['match_score']) > sum(best)): best = g['match_score']
        if best and sum(best) >= jg + jp: jg, jp = best
        sr = ''
        if gs and gs[0]['local_on_play'] is not None: sr = 'Salida' if gs[0]['local_on_play'] else 'Robo'
        turns = [g['turns'] for g in gs if g['turns']]
        opp_cards, my_cards = [], []
        for g in gs:
            for c in g['opp_casts']:
                if c not in opp_cards: opp_cards.append(c)
            my_cards += g['my_casts']
        fecha = next((g['ts'].strftime('%d/%m/%Y') for g in gs if g['ts']), '')
        hora = next((g['ts'] for g in gs if g['ts']), None)
        resultado = 'W' if jg > jp else ('L' if jp > jg else 'D')
        arquetipo, confianza, alternativas = classify_scored(opp_cards)
        matches.append({'match_uuid': mid, 'fecha': fecha, 'hora': hora, 'local': local, 'opp': opp,
            'resultado': resultado, 'jg': jg, 'jp': jp, 'salida_robo': sr, 'games_list': gs,
            'ngames': len(gs), 'turns_tot': sum(turns), 'turns_avg': round(sum(turns)/len(turns), 1) if turns else 0,
            'turns_min': min(turns) if turns else 0, 'turns_max': max(turns) if turns else 0,
            'mull_local': gs[0]['mull_local'] if gs else 0, 'mull_opp': gs[0]['mull_opp'] if gs else 0,
            'mull_local_tot': sum(g['mull_local'] for g in gs), 'mull_opp_tot': sum(g['mull_opp'] for g in gs),
            'arquetipo': arquetipo, 'confianza': confianza, 'alternativas': alternativas,
            'opp_cards': opp_cards, 'my_cards': Counter(my_cards),
            'prowess': sum(g['prowess'] for g in gs), 'monks': sum(g['monks'] for g in gs),
            'activ': sum(g['activ'] for g in gs), 'removal': [r for g in gs for r in g['removal']]})
    matches.sort(key=lambda m: m['hora'] or datetime.min.replace(tzinfo=timezone.utc))
    return matches

# ---------- Scouting: agregar cartas del rival por arquetipo ----------
def scouting_report(matches):
    """Por arquetipo: nº de matches, récord tuyo, turnos medios, confianza media y las
    cartas del rival más vistas. Alimenta el panel de 'scouting de rivales' del dashboard.
    (Idea tomada de AggregateGameLogCardStats de MyMTGO, reimplementada.)"""
    by = defaultdict(lambda: {'matches': 0, 'w': 0, 'l': 0, 'd': 0, 'turns': [],
                              'conf': [], 'cards': Counter()})
    for m in matches:
        r = by[m['arquetipo']]
        r['matches'] += 1
        r['w'] += 1 if m['resultado'] == 'W' else 0
        r['l'] += 1 if m['resultado'] == 'L' else 0
        r['d'] += 1 if m['resultado'] == 'D' else 0
        if m['turns_avg']: r['turns'].append(m['turns_avg'])
        r['conf'].append(m.get('confianza', 0))
        for c in m['opp_cards']: r['cards'][c] += 1
    rows = []
    for arq, r in by.items():
        rows.append({'arquetipo': arq, 'matches': r['matches'],
            'record': f"{r['w']}-{r['l']}" + (f"-{r['d']}" if r['d'] else ''),
            'wr': round(100 * r['w'] / (r['w'] + r['l']), 0) if (r['w'] + r['l']) else 0,
            'turns_avg': round(sum(r['turns']) / len(r['turns']), 1) if r['turns'] else 0,
            'conf_avg': round(sum(r['conf']) / len(r['conf']), 2) if r['conf'] else 0,
            'top_cards': r['cards']})
    rows.sort(key=lambda x: x['matches'], reverse=True)
    return rows

# ---------- CLI ----------
def find_files(directory):
    out = []
    for root, _d, files in os.walk(directory):
        for f in files:
            if 'Match_GameLog' in f: out.append(os.path.join(root, f))
    return out

def top_cards(counter, n=8):
    return ", ".join(f"{c} x{k}" if k > 1 else c for c, k in counter.most_common(n))

def run_dir(directory, user, out_csv, lista, reported_by):
    files = find_files(directory)
    if not files:
        print(f"No encontré *Match_GameLog* en: {directory}", file=sys.stderr); return 1
    seen = set(); uniq = []
    for fp in files:
        b = os.path.basename(fp)
        if b not in seen: seen.add(b); uniq.append(fp)
    games = []; ajenos = []
    for fp in uniq:
        try:
            with open(fp, 'rb') as fh: p = parse_gamelog(fh.read())
            if not p: continue
            msgs = [e['message'] for e in p['entries']]
            names = detect_names(msgs)
            # SOLO tus partidas: si pasas --user y no estás en el match, se descarta
            # (el volcado puede traer partidas espectadas o de otra persona)
            if user and names and user not in names:
                ajenos.append(sorted(names)); continue
            local = user if (user and user in names) else (names[0] if names else None)
            opp = next((n for n in names if n != local), None)
            for gm in split_games(p['entries']):
                games.append(extract_game(gm, local, opp, p['match_uuid']))
        except Exception as e:
            print(f"  ! {os.path.basename(fp)}: {e}", file=sys.stderr)
    if ajenos:
        print(f"Descartados {len(ajenos)} match(es) donde '{user}' NO juega "
              f"(partidas ajenas/espectadas). Ejemplos: "
              + "; ".join(" vs ".join(a) for a in ajenos[:5]) + "\n", file=sys.stderr)
    matches = aggregate(games)

    # 1) Registro (compatible con el tracker/dashboard)
    cols = ["match_uuid","Fecha","Evento / Liga","Lista","Ronda","Mazo del Oponente","Arquetipo",
            "Resultado (W/L)","Juegos Ganados","Juegos Perdidos","Salida / Robo (G1)",
            "Mulligans (Yo)","Mulligans (Rival)","Cartas Clave / MVP","Notas de Match / Sideboard",
            "Reportado por","Fuente"]
    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh); w.writerow(cols)
        for m in matches:
            w.writerow([m['match_uuid'], m['fecha'], '', lista, '', m['opp'] or '', m['arquetipo'],
                        m['resultado'], m['jg'], m['jp'], m['salida_robo'],
                        m['mull_local'], m['mull_opp'], '', '', reported_by, 'log'])

    # 2) Detalle por MATCH (agregados ricos + confianza/alternativas del arquetipo)
    mcols = ["match_uuid","Fecha","Rival","Arquetipo","Confianza","Alternativas","Resultado","Games","Salida/Robo G1",
             "Turnos total","Turnos/game","Turno min","Turno max","Mulls yo","Mulls rival",
             "Prowess (yo)","Monje tokens (yo)","Activaciones (yo)","Removal (objetivos)",
             "Mis cartas (top)","Cartas rival (todas)","Reportado por"]
    with open(out_csv + ".matches.csv", 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh); w.writerow(mcols)
        for m in matches:
            alts = "; ".join(f"{n} ({int(c*100)}%)" for n, c in m['alternativas'])
            w.writerow([m['match_uuid'], m['fecha'], m['opp'] or '', m['arquetipo'],
                        f"{int(m['confianza']*100)}%", alts,
                        f"{m['jg']}-{m['jp']} {m['resultado']}", m['ngames'], m['salida_robo'],
                        m['turns_tot'], m['turns_avg'], m['turns_min'], m['turns_max'],
                        m['mull_local_tot'], m['mull_opp_tot'], m['prowess'], m['monks'], m['activ'],
                        " | ".join(m['removal'][:12]), top_cards(m['my_cards'], 10),
                        ", ".join(m['opp_cards'][:20]), reported_by])

    # 3) Detalle por GAME (granularidad fina)
    gcols = ["match_uuid","Game","Salida/Robo","Ganado","Turnos","Mulls yo","Mulls rival",
             "Mano yo","Mano rival","Prowess yo","Monje yo","Activ yo","Descartes yo",
             "Mis hechizos","Removal (objetivos)","Cartas rival"]
    with open(out_csv + ".games.csv", 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh); w.writerow(gcols)
        for m in matches:
            for g in m['games_list']:
                sr = 'Salida' if g['local_on_play'] else ('Robo' if g['local_on_play'] is not None else '')
                w.writerow([m['match_uuid'], g['game_idx'], sr,
                            'Sí' if g['winner'] == 'local' else ('No' if g['winner'] == 'opp' else '?'),
                            g['turns'], g['mull_local'], g['mull_opp'], g['hand_local'], g['hand_opp'],
                            g['prowess'], g['monks'], g['activ'], g['disc_local'],
                            ", ".join(g['my_casts']), " | ".join(g['removal']),
                            ", ".join(dict.fromkeys(g['opp_casts']))])

    # 4) Scouting por arquetipo (récord + cartas del rival más vistas)
    scout = scouting_report(matches)
    scols = ["Arquetipo","Matches","Récord","WR %","Turnos medios","Confianza media","Cartas del rival más vistas"]
    with open(out_csv + ".scouting.csv", 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh); w.writerow(scols)
        for r in scout:
            w.writerow([r['arquetipo'], r['matches'], r['record'], f"{int(r['wr'])}%",
                        r['turns_avg'], f"{int(r['conf_avg']*100)}%", top_cards(r['top_cards'], 12)])

    ng = sum(m['ngames'] for m in matches)
    print(f"OK: {len(uniq)} ficheros -> {len(matches)} matches / {ng} games")
    print(f"   -> {out_csv}  (+ .matches.csv  + .games.csv  + .scouting.csv)\n")
    print(f"{'Fecha':<11}{'Rival':<15}{'Arquetipo':<22}{'Conf':<6}{'Res':<5}{'G1':<7}{'Turns':<7}{'Prow':<6}{'Monk':<5}")
    for m in matches:
        print(f"{m['fecha']:<11}{(m['opp'] or '?')[:14]:<15}{m['arquetipo'][:21]:<22}"
              f"{str(int(m['confianza']*100))+'%':<6}{m['jg']}-{m['jp']:<3}{m['salida_robo']:<7}"
              f"{m['turns_avg']:<7}{m['prowess']:<6}{m['monks']:<5}")
    print(f"\nScouting por arquetipo (top {min(len(scout),8)}):")
    for r in scout[:8]:
        print(f"  {r['arquetipo'][:24]:<26}{r['matches']} match(es)  récord {r['record']:<8}"
              f"conf.media {int(r['conf_avg']*100)}%  -> {top_cards(r['top_cards'], 5)}")
    return 0

# ---------- Autotest ----------
def selftest():
    def wv(n):
        o = bytearray()
        while True:
            b = n & 0x7F; n >>= 7; o.append(b | (0x80 if n else 0))
            if not n: break
        return bytes(o)
    def ent(msg):
        r = bytearray(); r += struct.pack('<Q', DOTNET_EPOCH_OFFSET + int(1_700_000_000 * 10_000_000))
        r += b'\x00'; mb = msg.encode(); r += wv(len(mb)) + mb; return bytes(r)
    def match_file(mu, lines):
        b = bytearray(); b += bytes([2, 0, len(mu)]) + mu + bytes([1, 0, len(mu)]) + mu
        for m in lines: b += ent(m)
        if len(b) < 20: b += b'\x00' * (20 - len(b))
        return bytes(b)
    # UN fichero = match entero (3 games)
    lines = [
      "@Prival rolled a 3.", "@Pfernando rolled a 6.", "@Prival joined the game.", "@Pfernando joined the game.",
      # game 1
      "@Prival chooses to play first.", "@Prival mulligans to six cards.",
      "@Prival puts a card on the bottom of their library and begins the game with six cards in hand.",
      "@Pfernando begins the game with seven cards in hand.",
      "@PTurn 1: rival", "@PTurn 1: fernando",
      "@Pfernando casts @[Monastery Swiftspear@:1,2:@].",
      "@Pfernando casts @[Lightning Bolt@:3,4:@] targeting @[Psychic Frog@:5,6:@].",
      "@Pfernando puts a triggered ability from @[Monastery Swiftspear@:1,2:@] onto the stack (Prowess).",
      "@Pfernando's @[Cori-Steel Cutter@:7,8:@] creates a Monk Token.",
      "@Prival casts @[Psychic Frog@:5,6:@].", "@Prival casts @[Unearth@:9,10:@].",
      "@PTurn 2: rival", "@PTurn 2: fernando", "@PTurn 3: fernando",
      "@Pfernando wins the game.", "@Pfernando leads the match 1-0.",
      # game 2
      "@Pfernando chooses to play first.", "@Prival wins the game.", "@Prival leads the match 1-1.",
      # game 3
      "@Pfernando chooses to play first.", "@PTurn 1: fernando", "@PTurn 2: fernando",
      "@Pfernando wins the game.", "@Pfernando wins the match 2-1.",
    ]
    p = parse_gamelog(match_file(b'match-1', lines))
    names = detect_names([e['message'] for e in p['entries']])
    local = 'fernando'; opp = next(n for n in names if n != local)
    gs = [extract_game(gm, local, opp, p['match_uuid']) for gm in split_games(p['entries'])]
    m = aggregate(gs)[0]
    print("Autotest -> match agregado:")
    for k in ('resultado','jg','jp','salida_robo','ngames','turns_max','prowess','monks','arquetipo','confianza','mull_opp_tot'):
        print(f"  {k}: {m[k]}")
    print("  mis cartas:", top_cards(m['my_cards']))
    assert m['ngames'] == 3, m['ngames']
    assert m['resultado'] == 'W' and m['jg'] == 2 and m['jp'] == 1, m
    assert m['salida_robo'] == 'Robo'            # G1: rival juega primero -> yo al robo
    assert m['turns_max'] == 3, m['turns_max']
    assert m['prowess'] == 1 and m['monks'] == 1, (m['prowess'], m['monks'])
    assert m['mull_opp_tot'] == 1 and m['mull_local_tot'] == 0
    assert m['arquetipo'] == 'Grixis Frog/Reanimator'
    assert 0.0 < m['confianza'] <= 1.0, m['confianza']
    assert m['games_list'][0]['hand_opp'] == 6      # rival mulligan a 6
    assert 'Lightning Bolt->Psychic Frog' in m['removal']

    # --- Clasificador con confianza ---
    # (a) firma casi única (peso 3) se sostiene sola, con confianza decente
    arq, conf, _ = classify_scored(['Goblin Charbelcher'])
    assert arq == 'Tameshi Belcher' and conf >= LOW_CONFIDENCE, (arq, conf)
    # (b) evidencia nula -> '¿? (revisar)'
    arq0, conf0, _ = classify_scored(['Lightning Bolt', 'Fatal Push'])
    assert arq0 == '¿? (revisar)' and conf0 == 0.0, (arq0, conf0)
    # (c) muchas firmas fuertes -> confianza alta y sin ambigüedad
    arqh, confh, altsh = classify_scored(['Ocelot Pride','Ajani, Nacatl Pariah','Guide of Souls','Galvanic Discharge'])
    assert arqh == 'Boros Energy' and confh >= 0.85, (arqh, confh)
    # (d) señal fuerte de un arquetipo con roce de otro -> gana el fuerte, baja algo la confianza
    arqa, confa, altsa = classify_scored(['Amulet of Vigor','Primeval Titan','Counterspell'])
    assert arqa == 'Amulet Titan', (arqa, altsa)

    # --- Scouting ---
    scout = scouting_report([m])
    assert scout and scout[0]['arquetipo'] == 'Grixis Frog/Reanimator'
    assert scout[0]['matches'] == 1 and scout[0]['record'] == '1-0'
    assert 'Psychic Frog' in scout[0]['top_cards']
    print("Aserciones OK")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir'); ap.add_argument('--user', default='feralo77'); ap.add_argument('--out', default='registro_mtgo.csv')
    ap.add_argument('--lista', default='Stock')
    ap.add_argument('--reported-by', dest='reported_by', default=None, help='quién reporta (por defecto, el --user)')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest: selftest(); return
    directory = a.dir or os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')),
                                      'AppData', 'Local', 'Apps', '2.0', 'Data')
    sys.exit(run_dir(directory, a.user, a.out, a.lista, a.reported_by or a.user))

if __name__ == '__main__':
    main()
