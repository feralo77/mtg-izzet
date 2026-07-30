#!/usr/bin/env python3
"""Genera meta/definitiva.json: La 75 Definitiva calculada, no escrita a mano.

Decisión de Fer (2026-07-30): la 75 Definitiva deja de ser un texto que alguien
mantiene y pasa a construirse sola con los datos, actualizándose en cada corrida
del robot.

QUÉ ES DERIVABLE Y QUÉ NO
El consenso del campo y el histórico de Fer dan, objetivamente:
  - la lista media de mtgtop8 (base de partida),
  - dónde se desvían sus versiones y con qué récord,
  - qué matchups pierde y con cuánta muestra.
Lo que los datos NO dicen es QUÉ CARTA RESPONDE A QUÉ MAZO (que Consign to Memory
sirve contra triggers, que Tormod's Crypt para cementerios). Eso es conocimiento de
Magic, no estadística. Así que este generador NO se lo inventa: calcula todo lo
calculable y marca lo que queda como decisión humana, con el dato al lado para que
se decida informado. Inventarlo daría una lista con pinta de autoridad y sin base.

Uso:  python automation/generar_definitiva.py [--out meta/definitiva.json]
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LISTAS = REPO / 'listas'
FETCH = {"Arid Mesa", "Bloodstained Mire", "Scalding Tarn", "Wooded Foothills",
         "Flooded Strand", "Polluted Delta", "Windswept Heath", "Marsh Flats",
         "Verdant Catacombs", "Misty Rainforest"}

# Umbrales, en un solo sitio para poder discutirlos:
MIN_N_MATCHUP = 3      # menos partidas que esto no es un matchup, es una anécdota
WR_MALO = 40           # <=40% con muestra suficiente = agujero real
PCT_CAMPO_ALTO = 70    # el campo lo lleva mayoritariamente
PCT_CAMPO_BAJO = 30    # el campo casi no lo lleva


def cartas_de(path):
    main, side, cur, blank = Counter(), Counter(), None, False
    cur = main
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line:
            blank = True
            continue
        if line.startswith('#'):
            continue
        if line.lower().startswith('sideboard'):
            cur, blank = side, False
            continue
        m = re.match(r'^(\d+)x?\s+(.*)$', line)
        if not m:
            continue
        if blank and cur is main:
            cur = side
        blank = False
        cur[m.group(2).strip()] += int(m.group(1))
    return main, side


def cargar():
    meta = json.loads((REPO / 'meta' / 'prowess.json').read_text(encoding='utf-8'))
    cfg = json.loads((REPO / 'automation' / 'listas.json').read_text(encoding='utf-8'))
    reg = list(csv.DictReader((REPO / 'registro.csv').open(encoding='utf-8')))
    games = list(csv.DictReader((REPO / 'games.csv').open(encoding='utf-8')))
    listas = {p.stem: cartas_de(p) for p in sorted(LISTAS.glob('*.txt'))}
    return meta, cfg, reg, games, listas


def wr(w, n):
    return round(w * 100 / n) if n else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(REPO / 'meta' / 'definitiva.json'))
    ap.add_argument('--date', default=None)
    args = ap.parse_args()
    meta, cfg, reg, games, listas = cargar()

    ref_names = {n.lower() for n in cfg.get('referencia', [])}
    version_de = {l.lower(): v for v, ls in cfg['versiones'].items() for l in ls}
    jugadas = {n: d for n, d in listas.items() if n.lower() not in ref_names}

    # ---- récord por matchup (pondera el sideboard) -------------------------------
    mm = defaultdict(lambda: {'W': 0, 'L': 0})
    for r in reg:
        aq = (r.get('Arquetipo') or '').strip()
        res = (r.get('Resultado (W/L)') or '').strip().upper()
        if not aq or aq.startswith('N/A') or res not in ('W', 'L'):
            continue
        mm[aq]['W' if res == 'W' else 'L'] += 1
    matchups = sorted(
        ({'aq': k, 'W': v['W'], 'L': v['L'], 'n': v['W'] + v['L'],
          'wr': wr(v['W'], v['W'] + v['L'])} for k, v in mm.items()),
        key=lambda x: (-x['n'], x['aq']))

    # ---- récord por lista (para el con/sin de cada carta) ------------------------
    rec_lista = defaultdict(lambda: {'W': 0, 'L': 0})
    for r in reg:
        li = (r.get('Lista') or '').strip()
        res = (r.get('Resultado (W/L)') or '').strip().upper()
        if li and res in ('W', 'L'):
            rec_lista[li.lower()]['W' if res == 'W' else 'L'] += 1

    def con_sin(zona_idx, carta):
        """Récord de Fer y compañía en las partidas jugadas con listas que llevan la
        carta, frente a las que no. Solo cuenta listas con partidas apuntadas."""
        con = {'W': 0, 'L': 0}
        sin = {'W': 0, 'L': 0}
        for nombre, mazo in jugadas.items():
            r = rec_lista.get(nombre.lower())
            if not r:
                continue
            dest = con if mazo[zona_idx].get(carta, 0) > 0 else sin
            dest['W'] += r['W']
            dest['L'] += r['L']
        return ({'W': con['W'], 'L': con['L'], 'n': con['W'] + con['L'],
                 'wr': wr(con['W'], con['W'] + con['L'])},
                {'W': sin['W'], 'L': sin['L'], 'n': sin['W'] + sin['L'],
                 'wr': wr(sin['W'], sin['W'] + sin['L'])})

    # ---- base: el consenso del campo --------------------------------------------
    def base_zona(rows, tope):
        """Consenso: cada carta a sus copias típicas, de más jugada a menos, hasta el
        tope de la zona. Los fetchlands se tratan como un bloque (son intercambiables
        en este mazo) para no llenar el hueco con la que más salga en mtgtop8."""
        out, total = [], 0
        for c in sorted(rows, key=lambda x: (-x['pct'], -x['avg'])):
            if total >= tope:
                break
            q = min(int(c['typical'] or 0), tope - total)
            if q <= 0:
                continue
            out.append({'n': c['n'], 'copias': q, 'pct': c['pct'],
                        'typical': c['typical'], 'min': c['min'], 'max': c['max']})
            total += q
        return out, total

    base_main, n_main = base_zona(meta['main'], 60)
    base_side, n_side = base_zona(meta['side'], 15)

    # ---- desviaciones: donde sus versiones no coinciden con el campo -------------
    def desviaciones(zona_idx, rows, base):
        cons = {c['n']: c for c in rows}
        en_base = {c['n']: c['copias'] for c in base}
        cartas = set(cons) | {c for m in jugadas.values() for c in m[zona_idx]}
        out = []
        for c in sorted(cartas):
            if c in FETCH:
                continue          # bloque intercambiable, no es una desviación real
            suyas = {n: m[zona_idx].get(c, 0) for n, m in jugadas.items()}
            suyas_max = max(suyas.values()) if suyas else 0
            pct = cons.get(c, {}).get('pct', 0)
            base_q = en_base.get(c, 0)
            if suyas_max == base_q and all(v == base_q for v in suyas.values()):
                continue          # coincide con la base en todas sus versiones
            con, sin = con_sin(zona_idx, c)
            tipo = None
            if pct >= PCT_CAMPO_ALTO and suyas_max == 0:
                tipo = 'el campo la lleva y tú no'
            elif pct <= PCT_CAMPO_BAJO and suyas_max > 0:
                tipo = 'la llevas y el campo casi no'
            elif base_q != suyas_max:
                tipo = 'copias distintas del consenso'
            if not tipo:
                continue
            out.append({'n': c, 'tipo': tipo, 'consensoPct': pct,
                        'consensoCopias': cons.get(c, {}).get('typical', 0),
                        'baseCopias': base_q, 'tusVersiones': suyas,
                        'con': con, 'sin': sin})
        # primero las que tienen dato propio con el que decidir
        return sorted(out, key=lambda x: (-(x['con']['n'] or 0), x['n']))

    desv_main = desviaciones(0, meta['main'], base_main)
    desv_side = desviaciones(1, meta['side'], base_side)

    # ---- avisos: solo lo que el dato sostiene -----------------------------------
    avisos = []
    malos = [m for m in matchups if m['n'] >= MIN_N_MATCHUP and m['wr'] <= WR_MALO]
    if malos:
        avisos.append({
            'clave': 'matchups-perdidos',
            'titulo': 'Dónde se te escapan las partidas',
            'texto': ('Con al menos %d partidas jugadas, estos son los mazos contra los '
                      'que vas por debajo del %d%%. El sideboard debería estar ponderado '
                      'a ellos, no al campo global.' % (MIN_N_MATCHUP, WR_MALO)),
            'datos': [{'aq': m['aq'], 'rec': f"{m['W']}-{m['L']}", 'wr': m['wr'], 'n': m['n']}
                      for m in malos],
            'decision': 'humana: qué carta responde a cada uno de estos mazos no sale de los datos',
        })

    # el acantilado de la duración, calculado (no escrito a mano)
    t = [int(g['Turnos']) for g in games if (g.get('Turnos') or '').strip().isdigit()]
    w = [int(g['Turnos']) for g in games
         if (g.get('Turnos') or '').strip().isdigit() and (g.get('Ganado') or '').strip() == '1']
    if t:
        corto = sum(1 for x in t if x <= 5)
        corto_w = sum(1 for x in w if x <= 5)
        largo = len(t) - corto
        largo_w = len(w) - corto_w
        avisos.append({
            'clave': 'ventana-de-victoria',
            'titulo': 'Hasta qué turno ganas',
            'texto': ('Hasta el turno 5 ganas el %d%% (%d games); del 6 en adelante, el %d%% '
                      '(%d). Toda carta que solo aporte a partir del turno 6 está pagando un '
                      'precio en una ventana que casi no juegas.' %
                      (wr(corto_w, corto), corto, wr(largo_w, largo), largo)),
            'datos': [{'tramo': 'T1-T5', 'n': corto, 'wr': wr(corto_w, corto)},
                      {'tramo': 'T6+', 'n': largo, 'wr': wr(largo_w, largo)}],
            'decision': 'humana: qué cartas de la lista son de turno tardío',
        })

    # game 1 por salida/robo (la única medición limpia del efecto de empezar)
    g1 = [g for g in games if (g.get('Game') or '').strip() == '1']
    def _wr_sr(sr):
        a = [g for g in g1 if (g.get('Salida / Robo') or '').strip() == sr]
        ww = sum(1 for g in a if (g.get('Ganado') or '').strip() == '1')
        return {'sr': sr, 'n': len(a), 'W': ww, 'L': len(a) - ww, 'wr': wr(ww, len(a))}
    sal, rob = _wr_sr('Salida'), _wr_sr('Robo')
    if sal['n'] and rob['n']:
        avisos.append({
            'clave': 'game1-salida-robo',
            'titulo': 'El peso de empezar',
            'texto': ('En el game 1, donde la salida la reparte el dado, ganas el %d%% saliendo '
                      'y el %d%% robando: %d puntos. Es la única medición sin sesgo (en el G2/G3 '
                      'elige quien perdió el anterior). Cuanto mayor sea esa brecha, más debe '
                      'pesar en la lista la resiliencia jugando segundo.' %
                      (sal['wr'], rob['wr'], abs(sal['wr'] - rob['wr']))),
            'datos': [sal, rob],
            'decision': 'humana: qué cartas te hacen menos dependiente de la salida',
        })

    out = {
        'generado': args.date or __import__('datetime').date.today().isoformat(),
        'comoSeCalcula': (
            'Base: la lista media de mtgtop8 (cada carta a sus copias típicas, de más '
            'jugada a menos, hasta 60 y 15; los fetchlands como bloque intercambiable). '
            'Encima, las desviaciones de las versiones de Fer con su récord real con y sin '
            'cada carta, y los avisos que el histórico sostiene. Lo que NO se calcula: qué '
            'carta responde a qué mazo — eso es criterio de Magic y va marcado como '
            'decisión humana en cada aviso.'),
        'campo': {'mazos': meta.get('mazos'), 'ventanaDias': meta.get('ventanaDias'),
                  'fuente': meta.get('fuente'), 'generado': meta.get('generado')},
        'tuHistorico': {'partidas': sum(m['n'] for m in matchups), 'games': len(games),
                        'versiones': sorted(set(version_de.get(n.lower(), '') for n in jugadas) - {''})},
        'base': {'main': base_main, 'mainN': n_main, 'side': base_side, 'sideN': n_side},
        'desviaciones': {'main': desv_main, 'side': desv_side},
        'matchups': matchups,
        'avisos': avisos,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n',
                              encoding='utf-8')
    print(f"meta/definitiva.json: main {n_main}/60, side {n_side}/15, "
          f"{len(desv_main)}+{len(desv_side)} desviaciones, {len(avisos)} avisos, "
          f"{len(matchups)} matchups")


if __name__ == '__main__':
    main()
