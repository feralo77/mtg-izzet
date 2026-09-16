#!/usr/bin/env python3
"""Genera la PLANTILLA DE SIDEBOARD: una matriz carta x matchup sobre la 75 REAL de Fer.

Por que existe
--------------
La hoja de sideboard de ethanmtg (Metafy) esta hecha sobre SU 75, que no es la de Fer:
el lleva 2 Assault Strobe donde Fer lleva 2 Meltdown, 1 Spell Pierce donde Fer lleva 2,
3 Consign donde Fer lleva 4. Copiarla tal cual seria apuntar cartas que Fer no tiene.
Esto genera la misma idea pero con SUS cartas y SUS matchups.

Tres fuentes, ninguna a mano:
  meta/mi-75.json    -> las filas (que puede salir y que puede entrar)
  registro.csv       -> las columnas (ordenadas por lo que MAS se cruza) y el record
  meta/guia-sb.json  -> el prerrelleno (los planes que ya estan escritos)

Lo que queda en blanco es justo lo que falta por decidir: son los agujeros, y se ven.

Uso:  python3 scripts/plantilla_sb.py [--out meta/plantilla-sideboard.csv]

La copia que Fer rellena vive en su Drive, dentro de "MTG · Izzet":
https://docs.google.com/spreadsheets/d/1_Q6qhZ6F9ou7QA0rtcYEt-Lz7xHY-ol2-9KvTh8vUm4/edit

OJO al subirla: nada de formulas con separador de argumentos. Su Sheets esta en locale
espanol y usa ';', asi que un IF(a,b,c) importado desde CSV sale como #ERROR!. Por eso la
fila de descuadre es una resta pelada.
"""
import csv, json, sys, collections
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSION_UNICA = "Stock"          # la misma constante que manda en el dashboard
MOTOR = ["Cori-Steel Cutter", "Dragon's Rage Channeler", "Monastery Swiftspear",
         "Mishra's Bauble", "Preordain"]   # nunca salen (reglaGeneral de la guia)

# Columnas que no ha jugado con esta lista pero que SI tienen plan escrito, o que
# conviene tener preparadas. Van al final, despues de las que si se cruza.
EXTRA = ["Ruby Storm", "Amulet Titan", "Living End", "Golgari Yawgmoth", "Hollow One"]
LIBRES = 2                        # columnas en blanco para que Fer meta lo que salga

def leer_75():
    d = json.loads((RAIZ / "meta/mi-75.json").read_text(encoding="utf-8"))
    main = [(c["n"], c["q"]) for c in d["main"] if c["z"] != "tierra"]
    tierras = sum(c["q"] for c in d["main"] if c["z"] == "tierra")
    side = [(c["n"], c["q"]) for c in d["side"]]
    return main, tierras, side, d.get("nombre", "tu 75")

def leer_matchups():
    """Arquetipos ordenados por lo que mas se cruza, con su record. Solo la version unica."""
    filas = [x for x in csv.DictReader((RAIZ / "registro.csv").open(encoding="utf-8"))
             if x["Versión"].strip() == VERSION_UNICA]
    rec = collections.defaultdict(lambda: [0, 0])
    for x in filas:
        aq = x["Arquetipo"].strip()
        # "Desconocido" no es un mazo: es una partida donde no se identifico al rival.
        # Como columna de una plantilla de sideboard no se puede rellenar, asi que fuera.
        if not aq or aq in ("N/A (bye/concede)", "NA", "Desconocido", "Otros (¿?)"):
            continue
        rec[aq][0 if x["Resultado (W/L)"].upper() == "W" else 1] += 1
    orden = sorted(rec.items(), key=lambda kv: (-(kv[1][0] + kv[1][1]), kv[0]))
    return orden, len(filas), rec

def leer_planes():
    """{arquetipo -> {'in': {carta: n}, 'out': {carta: n}, 'rol': str}} desde la guia.

    La guia mapea varios arquetipos del registro a un mismo plan (campo `aq`), asi que
    se indexa por cada uno de ellos.
    """
    d = json.loads((RAIZ / "meta/guia-sb.json").read_text(encoding="utf-8"))
    def parsea(lst):
        out = {}
        for s in lst or []:
            n, _, carta = s.partition(" ")
            out[carta.strip()] = int(n)
        return out
    planes = {}
    for m in d["matchups"]:
        p = {"in": parsea(m.get("in")), "out": parsea(m.get("out")),
             "rol": m.get("rol", ""), "mazo": m["mazo"]}
        for aq in (m.get("aq") or [m["mazo"]]):
            planes[aq] = p
        planes.setdefault(m["mazo"], p)
    return planes

def adapta(plan, cartas_75):
    """La guia puede nombrar cartas que ya no estan en la 75 (se escribio con otra).

    En vez de dejarlas pasar en silencio -que es como se cuela un plan con una carta que
    no tienes-, se traducen las equivalencias conocidas y lo demas se marca para revisar.
    """
    EQUIV = {"Tormod's Crypt": "Surgical Extraction"}   # mismo hueco: odio a cementerio
    avisos = []
    for zona in ("in", "out"):
        nuevo = {}
        for carta, n in plan[zona].items():
            destino = carta if carta in cartas_75 else EQUIV.get(carta)
            if destino is None:
                avisos.append(f"{plan['mazo']}: '{carta}' no esta en tu 75, se quita del plan")
                continue
            if destino != carta:
                avisos.append(f"{plan['mazo']}: '{carta}' -> '{destino}' (ya no llevas la primera)")
            tope = cartas_75[destino]
            if n > tope:
                avisos.append(f"{plan['mazo']}: {n} {destino} pero solo llevas {tope}, se ajusta")
                n = tope
            nuevo[destino] = nuevo.get(destino, 0) + n
        plan[zona] = nuevo
    return plan, avisos

def main():
    salida = RAIZ / (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
                     else "meta/plantilla-sideboard.csv")
    main75, tierras, side75, nombre = leer_75()
    orden, total, rec = leer_matchups()
    planes = leer_planes()
    cartas_75 = {**dict(main75), **{n: q for n, q in side75}}
    # Unholy Heat esta en main (1) y en banquillo (3): el tope real para un plan es la suma.
    for n, q in main75:
        for m, qq in side75:
            if m == n:
                cartas_75[n] = q + qq

    cols = [a for a, _ in orden] + [e for e in EXTRA if e not in dict(orden)]
    avisos = []

    motor = [(n, q) for n, q in main75 if n in MOTOR]
    flex  = [(n, q) for n, q in main75 if n not in MOTOR]

    # --- filas ---
    R = []
    R.append([f"IZZET PROWESS — PLANTILLA DE SIDEBOARD"])
    R.append([f"{nombre}. Columnas ordenadas por lo que MAS te cruzas ({total} partidas con esta lista)."])
    R.append(["Cada celda = cuantas copias. En el bloque de arriba, las que SALEN; abajo, las que ENTRAN. La fila 'DESCUADRE' tiene que dar 0: si da otra cosa, no salen las mismas cartas que entran."])
    R.append(["Lo que esta en blanco es lo que falta por decidir. Generado por scripts/plantilla_sb.py — no se edita a mano en el repo, se rellena en la copia de Drive."])
    R.append([])
    R.append(["CARTA", "Nº"] + cols)
    R.append(["TU RECORD", ""] + [f"{rec[c][0]}-{rec[c][1]}" if c in rec else "sin partidas" for c in cols])
    R.append(["% DE LO QUE TE CRUZAS", ""] + [f"{round(100*(rec[c][0]+rec[c][1])/total)}%" if c in rec else "—" for c in cols])
    R.append(["TU PAPEL", ""] + [planes[c]["rol"] if c in planes else "" for c in cols])
    R.append([])

    fila_motor_ini = len(R) + 2
    R.append([f"EL MOTOR — no sale nunca", ""])
    for n, q in motor:
        R.append([n, q] + [""] * len(cols))
    R.append(["Tierras", tierras] + [""] * len(cols))
    fila_motor_fin = len(R)
    R.append([])

    fila_flex_ini = len(R) + 2
    R.append([f"QUE SALE — los {sum(q for _, q in flex)} flexibles", ""])
    for n, q in flex:
        p = planes.get(n)  # no aplica; se rellena por columna abajo
        R.append([n, q] + [""] * len(cols))
    fila_flex_fin = len(R)
    R.append([])

    fila_side_ini = len(R) + 2
    R.append([f"QUE ENTRA — banquillo ({sum(q for _, q in side75)})", ""])
    for n, q in side75:
        R.append([n, q] + [""] * len(cols))
    fila_side_fin = len(R)
    R.append([])

    # --- prerrelleno desde la guia ---
    idx_flex = {n: fila_flex_ini + i for i, (n, _) in enumerate(flex)}
    idx_side = {n: fila_side_ini + i for i, (n, _) in enumerate(side75)}
    for j, c in enumerate(cols):
        if c not in planes:
            continue
        plan, av = adapta(dict(planes[c]), cartas_75)
        avisos += av
        for carta, n in plan["out"].items():
            if carta in idx_flex:
                R[idx_flex[carta] - 1][2 + j] = n
            else:
                avisos.append(f"{c}: sale '{carta}', que es motor o tierra — no se pinta")
        for carta, n in plan["in"].items():
            if carta in idx_side:
                R[idx_side[carta] - 1][2 + j] = n
            else:
                avisos.append(f"{c}: entra '{carta}', que no esta en tu banquillo — no se pinta")

    # --- totales con formula viva ---
    def col_letra(i):
        s = ""
        while True:
            s = chr(ord("A") + i % 26) + s
            i = i // 26 - 1
            if i < 0:
                return s
    def fila_formula(etiqueta, plantilla):
        return [etiqueta, ""] + [plantilla.format(L=col_letra(2 + j)) for j in range(len(cols))]

    f_fuera = len(R) + 1
    R.append(fila_formula("FUERA (total)",
             f"=SUM({{L}}{fila_motor_ini}:{{L}}{fila_motor_fin})+SUM({{L}}{fila_flex_ini}:{{L}}{fila_flex_fin})"))
    f_dentro = len(R) + 1
    R.append(fila_formula("DENTRO (total)", f"=SUM({{L}}{fila_side_ini}:{{L}}{fila_side_fin})"))
    # OJO con esta formula: NADA de separadores de argumentos. El Sheets de Fer esta en
    # locale espanol y usa ';' en vez de ',', asi que cualquier IF(a,b,c) subido desde un CSV
    # le revienta con #ERROR!. Una resta no tiene separadores y funciona en cualquier idioma,
    # y ademas dice mejor lo que pasa: cuantas cartas te sobran o te faltan.
    R.append(fila_formula("DESCUADRE (0 = bien)", f"={{L}}{f_dentro}-{{L}}{f_fuera}"))
    R.append([])
    R.append(["QUE CAMBIA EN EL ROBO", ""] + [""] * len(cols))
    R.append(["NOTAS / POR QUE", ""] + [""] * len(cols))

    # Columnas en blanco al final, con su cabecera, para el mazo que salga manana.
    ancho = 2 + len(cols)
    for fila in R:
        if len(fila) >= ancho:
            fila.extend([""] * LIBRES)
    for k in range(LIBRES):
        R[5][ancho + k] = f"(libre {k + 1})"

    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(R)

    print(f"Escrito {salida.relative_to(RAIZ)}: {len(cols)+LIBRES} columnas, "
          f"{sum(1 for n,_ in main75+side75)} cartas.")
    con_plan = sum(1 for c in cols if c in planes)
    print(f"Prerrellenadas {con_plan} de {len(cols)} columnas; {len(cols)-con_plan} en blanco (los agujeros).")
    for a in dict.fromkeys(avisos):
        print("  aviso:", a)

if __name__ == "__main__":
    main()
