#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mtgo_gamelog_parser.py  (v2)
Decodifica los *Match_GameLog*.dat binarios de Magic Online y los agrupa en MATCHES,
generando un CSV compatible con la pestaña Registro del tracker Izzet.

MTGO escribe UN FICHERO POR GAME. Cada fichero comparte el mismo match_uuid en su
cabecera, así que agrupamos por match_uuid y sumamos los games para obtener el match.

Basado en el cliente open-source de MyMTGO (github.com/mymtgo/client):
  - ParseGameLogBinary.php (formato binario)  - ExtractGameResults.php (regex)

Uso:
  python3 mtgo_gamelog_parser.py --dir "<carpeta con .dat>" --user <tu_usuario_MTGO> --out registro.csv
  python3 mtgo_gamelog_parser.py --selftest
Ruta por defecto (Windows, MTGO ClickOnce):  %USERPROFILE%\\AppData\\Local\\Apps\\2.0\\Data
"""
import os, re, csv, sys, struct, argparse
from datetime import datetime, timezone
from collections import defaultdict, Counter

DOTNET_EPOCH_OFFSET = 621355968000000000
PLAYER = r'[A-Za-z0-9_-]+'

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
    version = raw[pos]; pos += 1; pos += 1
    ulen = raw[pos]; pos += 1
    if pos + ulen > length: return None
    match_uuid = raw[pos:pos+ulen].decode('latin-1','replace'); pos += ulen
    mtype = raw[pos]; pos += 1; pos += 1
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

# ---------- Extracción por GAME ----------
def extract_game(parsed, local_user=None):
    msgs = [e['message'] for e in parsed['entries']]
    names = []
    for m in msgs:
        for rx in (rf'^@P({PLAYER}) chooses to play', rf'^@P({PLAYER}) wins the game',
                   rf'^@P({PLAYER}) rolled a \d', rf'^@P@P({PLAYER}) joined the game',
                   rf'^@P({PLAYER}) (?:leads|wins) the match'):
            g = re.match(rx, m)
            if g and g.group(1) not in names: names.append(g.group(1))
    local = local_user if (local_user and local_user in names) else (names[0] if names else None)
    opp = next((n for n in names if n != local), None)

    salida_robo = None
    for m in msgs:
        g = re.match(rf'^@P({PLAYER}) chooses to play (first|second)', m)
        if g:
            if local:
                if g.group(1) == local: salida_robo = 'Salida' if g.group(2)=='first' else 'Robo'
                else:                    salida_robo = 'Robo' if g.group(2)=='first' else 'Salida'
            break

    winner = None
    for m in msgs:
        g = re.match(rf'^@P({PLAYER}) wins the game', m)
        if g: winner = g.group(1)
        c = re.match(rf'^@P({PLAYER}) has conceded from the game', m)
        if c: winner = (opp if c.group(1)==local else local)

    # score de match explícito ("leads/wins the match D-D") desde la perspectiva del que lo dice
    match_score = None
    for m in msgs:
        g = re.match(rf'^@P({PLAYER}) (?:leads|wins) the match (\d+)-(\d+)', m)
        if g:
            a, b = int(g.group(2)), int(g.group(3))
            match_score = (a, b) if g.group(1)==local else (b, a)

    # mulligans: nº de líneas "mulligans to" por jugador
    mull = Counter()
    for m in msgs:
        g = re.match(rf'^@P({PLAYER}) mulligans to', m)
        if g: mull[g.group(1)] += 1

    opp_cards = []
    if opp:
        for m in msgs:
            for g in re.finditer(rf'@P{re.escape(opp)} casts @\[([^@]+)@:', m):
                c = g.group(1).strip()
                if c and c not in opp_cards: opp_cards.append(c)

    ts = next((e['ts'] for e in parsed['entries'] if e['ts']), None)
    return {'match_uuid': parsed['match_uuid'], 'local': local, 'opp': opp,
            'salida_robo': salida_robo, 'winner': winner, 'match_score': match_score,
            'mull_local': mull.get(local,0), 'mull_opp': mull.get(opp,0),
            'opp_cards': opp_cards, 'ts': ts}

# ---------- Clasificador de arquetipo por cartas del rival ----------
SIG = [
    ('Broodscale', ['Basking Broodscale','Blade of the Bloodchief',"Kozilek's Command"]),
    ("Esper Goryo's", ["Goryo's Vengeance",'Atraxa','Ephemerate']),
    ('Grixis Reanimator', ['Persist','Archon of Cruelty','Abhorrent Oculus']),
    ('Dimir Frog', ['Psychic Frog']),
    ('Boros Energy', ['Guide of Souls','Ocelot Pride','Ajani, Nacatl Pariah','Galvanic Discharge']),
    ('Izzet Affinity', ['Kappa Cannoneer',"Urza's Saga",'Thought Monitor','Pinnacle Emissary','Mox Opal']),
    ('Eldrazi', ['Thought-Knot Seer','Ugin','Chalice of the Void',"Kozilek, the Broodmother",'Devourer of Destiny']),
    ('Amulet Titan', ['Amulet of Vigor','Primeval Titan']),
    ('Golgari Yawgmoth', ['Yawgmoth, Thran Physician',"Agatha's Soul Cauldron"]),
    ('Ruby Storm', ['Ruby Medallion','Grapeshot','Past in Flames']),
    ('Living End', ['Living End','Shardless Agent']),
    ('Tameshi Belcher', ['Goblin Charbelcher']),
    ('Boros Ponza', ['High Noon','Erode','Demolition Field','Cleansing Wildfire','Magus of the Moon','Price of Freedom']),
    ('Neoform', ['Neoform','Allosaurus Rider',"Summoner's Pact"]),
    ('Izzet Prowess', ['Slickshot Show-Off','Cori-Steel Cutter','Monastery Swiftspear']),
    ('Azorius Control', ['Counterspell','Wrath of the Skies','Teferi, Time Raveler']),
]
def classify(cards):
    cset = set(cards); best=None; bestn=0
    for name, sigs in SIG:
        n = sum(1 for s in sigs if s in cset)
        if n > bestn: best, bestn = name, n
    # matices Frog: Psychic Frog + señales de reanimación => Grixis
    if best == 'Dimir Frog' and (('Unearth' in cset) or ('Persist' in cset)):
        return 'Grixis Frog/Reanimator'
    return best or '¿? (revisar)'

# ---------- Agregar games -> matches ----------
def aggregate(games):
    by = defaultdict(list)
    for g in games:
        if g and g['match_uuid']: by[g['match_uuid']].append(g)
    matches = []
    for mid, gs in by.items():
        gs.sort(key=lambda x: x['ts'] or datetime.min.replace(tzinfo=timezone.utc))
        local = next((g['local'] for g in gs if g['local']), None)
        opp = Counter(g['opp'] for g in gs if g['opp']).most_common(1)
        opp = opp[0][0] if opp else None
        jg = sum(1 for g in gs if g['winner'] and g['winner']==local)
        jp = sum(1 for g in gs if g['winner'] and g['winner']==opp)
        # override con el score de match más alto encontrado
        best = None
        for g in gs:
            if g['match_score']:
                if best is None or sum(g['match_score'])>sum(best): best = g['match_score']
        if best and sum(best) >= jg+jp: jg, jp = best
        salida_robo = next((g['salida_robo'] for g in gs if g['salida_robo']), '')
        mull_local = gs[0]['mull_local'] if gs else 0
        mull_opp = gs[0]['mull_opp'] if gs else 0
        cards = []
        for g in gs:
            for c in g['opp_cards']:
                if c not in cards: cards.append(c)
        fecha = next((g['ts'].strftime('%d/%m/%Y') for g in gs if g['ts']), '')
        hora = next((g['ts'] for g in gs if g['ts']), None)
        resultado = 'W' if jg>jp else ('L' if jp>jg else 'D')
        matches.append({'match_uuid':mid,'fecha':fecha,'hora':hora,'local':local,'opp':opp,'resultado':resultado,
                        'jg':jg,'jp':jp,'salida_robo':salida_robo,'mull_local':mull_local,
                        'mull_opp':mull_opp,'arquetipo':classify(cards),'opp_cards':cards,
                        'games':len(gs)})
    matches.sort(key=lambda m: m['hora'] or datetime.min.replace(tzinfo=timezone.utc))
    return matches

# ---------- CLI ----------
def find_files(directory):
    out=[]
    for root,_d,files in os.walk(directory):
        for f in files:
            if 'Match_GameLog' in f: out.append(os.path.join(root,f))
    return out

def run_dir(directory, user, out_csv, lista, reported_by):
    files = find_files(directory)
    if not files:
        print(f"No encontré *Match_GameLog* en: {directory}", file=sys.stderr); return 1
    # dedupe por nombre (ClickOnce duplica ficheros idénticos)
    seen=set(); uniq=[]
    for fp in files:
        b=os.path.basename(fp)
        if b not in seen: seen.add(b); uniq.append(fp)
    games=[]
    for fp in uniq:
        try:
            with open(fp,'rb') as fh: p=parse_gamelog(fh.read())
            if p: games.append(extract_game(p, user))
        except Exception as e:
            print(f"  ! {os.path.basename(fp)}: {e}", file=sys.stderr)
    matches = aggregate(games)
    cols=["match_uuid","Fecha","Evento / Liga","Lista","Ronda","Mazo del Oponente","Arquetipo",
          "Resultado (W/L)","Juegos Ganados","Juegos Perdidos","Salida / Robo (G1)",
          "Mulligans (Yo)","Mulligans (Rival)","Cartas Clave / MVP","Notas de Match / Sideboard",
          "Reportado por","Fuente"]
    with open(out_csv,'w',newline='',encoding='utf-8') as fh:
        w=csv.writer(fh); w.writerow(cols)
        for m in matches:
            notas=f"rival={m['opp'] or '?'}"
            if m['opp_cards']: notas+=" | cartas: "+", ".join(m['opp_cards'][:10])
            w.writerow([m['match_uuid'],m['fecha'],'',lista,'', m['opp'] or '', m['arquetipo'],
                        m['resultado'],m['jg'],m['jp'],m['salida_robo'],
                        m['mull_local'],m['mull_opp'],'',notas,reported_by,'log'])
    print(f"OK: {len(games)} games -> {len(matches)} matches -> {out_csv}\n")
    print(f"{'Fecha':<11}{'Rival':<14}{'Arquetipo':<24}{'Res':<4}{'G':<5}{'G1':<7}Cartas rival")
    for m in matches:
        print(f"{m['fecha']:<11}{(m['opp'] or '?')[:13]:<14}{m['arquetipo'][:23]:<24}"
              f"{m['resultado']:<4}{str(m['jg'])+'-'+str(m['jp']):<5}{m['salida_robo']:<7}"
              f"{', '.join(m['opp_cards'][:4])}")
    return 0

# ---------- Autotest ----------
def selftest():
    def wv(n):
        o=bytearray()
        while True:
            b=n&0x7F; n>>=7; o.append(b|(0x80 if n else 0))
            if not n: break
        return bytes(o)
    def ent(msg):
        r=bytearray(); r+=struct.pack('<Q', DOTNET_EPOCH_OFFSET+int(1_700_000_000*10_000_000))
        r+=b'\x00'; mb=msg.encode(); r+=wv(len(mb))+mb; return bytes(r)
    def game(mu, gu, lines):
        b=bytearray(); b+=bytes([2,0,len(mu)])+mu+bytes([1,0,len(gu)])+gu
        for m in lines: b+=ent(m)
        if len(b)<20: b+=b'\x00'*(20-len(b))
        return bytes(b)
    mu=b'match-1'
    g1=game(mu,b'game-1',["@Prival rolled a 3.","@Pfernando rolled a 6.",
        "@Prival chooses to play first.","@Prival mulligans to six cards.",
        "@Pfernando begins the game with seven cards in hand.",
        "@Prival casts @[Psychic Frog@:1,2:@].","@Prival casts @[Unearth@:3,4:@].",
        "@Pfernando wins the game.","@Pfernando leads the match 1-0."])
    g2=game(mu,b'game-2',["@Pfernando chooses to play first.",
        "@Prival wins the game.","@Prival leads the match 1-1."])
    g3=game(mu,b'game-3',["@Pfernando chooses to play first.",
        "@Pfernando wins the game.","@Pfernando wins the match 2-1."])
    games=[extract_game(parse_gamelog(g),'fernando') for g in (g1,g2,g3)]
    m=aggregate(games)[0]
    print("Autotest -> match agregado:")
    for k in ('local','opp','resultado','jg','jp','salida_robo','mull_local','mull_opp','arquetipo','games'):
        print(f"  {k}: {m[k]}")
    assert m['resultado']=='W' and m['jg']==2 and m['jp']==1, m
    assert m['salida_robo']=='Robo'          # G1: rival juega primero -> yo al robo
    assert m['mull_opp']==1 and m['mull_local']==0
    assert m['arquetipo']=='Grixis Frog/Reanimator'
    print("Aserciones OK ✓")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dir'); ap.add_argument('--user',default='feralo77'); ap.add_argument('--out',default='registro_mtgo.csv')
    ap.add_argument('--lista',default='Stock'); ap.add_argument('--reported-by',dest='reported_by',default=None,
                    help='quién reporta estas partidas (por defecto, el --user)')
    ap.add_argument('--selftest',action='store_true')
    a=ap.parse_args()
    if a.selftest: selftest(); return
    directory=a.dir or os.path.join(os.environ.get('USERPROFILE',os.path.expanduser('~')),
                                    'AppData','Local','Apps','2.0','Data')
    sys.exit(run_dir(directory, a.user, a.out, a.lista, a.reported_by or a.user))

if __name__=='__main__':
    main()
