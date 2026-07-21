#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_registro.py — Une la salida del parser (logs de MTGO) con una hoja de COMPLEMENTO,
cruzando por `match_uuid`, para NO teclear dos veces lo que el log ya sabe.

Idea:
  - El LOG aporta lo automático: fecha, rival, arquetipo, resultado, games, salida/robo, mulligans.
  - El COMPLEMENTO aporta lo que el log NO puede saber: Evento/Liga, Ronda, Lista, MVP, Notas
    (y, si quieres, un arquetipo corregido). Se rellena por `match_uuid`.
  - Las partidas SIN log (en papel) van en el mismo complemento con `match_uuid` vacío y todos
    sus campos; se añaden como filas manuales.

Uso:
  python3 merge_registro.py --logs registro_mtgo.csv --complemento complemento.csv --out registro_completo.csv
  python3 merge_registro.py --logs registro_mtgo.csv                                # sin complemento: copia y dedup
"""
import csv, argparse, sys

COLS = ["match_uuid","Fecha","Evento / Liga","Lista","Ronda","Mazo del Oponente","Arquetipo",
        "Resultado (W/L)","Juegos Ganados","Juegos Perdidos","Salida / Robo (G1)","Mulligans (Yo)",
        "Mulligans (Rival)","Cartas Clave / MVP","Notas de Match / Sideboard","Reportado por","Fuente"]
# Campos que el complemento puede rellenar/corregir sobre una fila de log:
META = ["Evento / Liga","Lista","Ronda","Cartas Clave / MVP","Notas de Match / Sideboard","Arquetipo","Reportado por"]

def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def get(row, *names):
    for n in names:
        if n in row and (row[n] or "").strip():
            return row[n].strip()
    return ""

def main():
    ap = argparse.ArgumentParser(description="Une logs del parser + complemento por match_uuid")
    ap.add_argument("--logs", required=True, help="CSV del parser (con columna match_uuid)")
    ap.add_argument("--complemento", help="CSV con metadatos por match_uuid (y/o partidas manuales)")
    ap.add_argument("--out", default="registro_completo.csv")
    a = ap.parse_args()

    logs = read(a.logs)
    comp = read(a.complemento) if a.complemento else []
    comp_by = {get(r, "match_uuid"): r for r in comp if get(r, "match_uuid")}
    manual = [r for r in comp if not get(r, "match_uuid") and get(r, "Resultado (W/L)", "Resultado")]

    out, seen = [], set()
    for r in logs:
        uid = get(r, "match_uuid")
        if uid and uid in seen:      # dedup: mismo match subido por varios -> una vez
            continue
        if uid:
            seen.add(uid)
        row = {c: (r.get(c, "") or "") for c in COLS}
        m = comp_by.get(uid)
        if m:                        # el complemento rellena/corrige la metadata
            for k in META:
                v = get(m, k)
                if v:
                    row[k] = v
        out.append(row)

    for m in manual:                 # partidas sin log (papel) -> tal cual
        row = {c: (m.get(c, "") or "") for c in COLS}
        if not row["Fuente"]:
            row["Fuente"] = "manual"
        out.append(row)

    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    print(f"OK: {len(logs)} log + {len(comp)} complemento ({len(manual)} manuales) "
          f"-> {len(out)} filas -> {a.out}")

if __name__ == "__main__":
    main()
