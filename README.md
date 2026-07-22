# MTG · Izzet Prowess — Centro de mando

Dashboard de estadísticas para el mazo **Izzet Prowess** (Modern, Magic Online) de [@feralo77](https://github.com/feralo77) y sus compañeros de la Liga Modern de Lleida. Nadie teclea resultados: un **robot diario** lee los logs de MTGO y los apuntes de cada jugador desde Drive y publica los datos aquí.

**Dashboard en vivo:** https://feralo77.github.io/mtg-izzet/

## Cómo fluye todo

```
Drive: Logs_<nick>/            GitHub Actions                    GitHub Pages
  ficheros .dat de MTGO   →    robot diario (~08:00)      →      dashboard
  hoja "Partidas — <nick>"     parsea + empareja + commitea      index.html
  (apuntes del jugador)        registro.csv · games.csv          (8 pestañas)
                               scouting.csv
```

- El robot es de **solo lectura** en Google (cuenta de servicio; nunca escribe ni borra en Drive).
- Corre solo cada mañana y **a demanda**: botón "Actualizar datos" del dashboard → `Run workflow` (~1 min).
- El emparejamiento apunte ↔ partida usa el **Rival (nick de MTGO)** como llave, con fecha ±1 día y resultado como apoyo (robusto a sesiones de madrugada y partidas de práctica intercaladas).

## El dashboard (`index.html`)

Página autónoma (HTML + Chart.js, design system Blockprint) con filtro global por jugador:

| Pestaña | Qué muestra |
|---|---|
| Estadísticas | KPIs, salida vs robo, WR por mazo rival, evolución por liga, detalle de partidas |
| Cómo juegas | Análisis game a game de los logs: manos iniciales, mulligans, robos, tierras, tempo (primera amenaza, turno del Cutter), motor de prowess |
| Listas | Tus versiones de mazo con récord real y Lista × mazo rival |
| Scouting | Rival a rival: enfrentamientos, récord, mazos y cartas vistas |
| Comparativa | Jugadores y mazos frente a frente |
| La 75 Definitiva | La lista de referencia, carta a carta y su porqué |
| Plan SB | Plan de sideboard por matchup con tu WR real |
| Meta · mtgtop8 | Lista media del arquetipo (se refresca cada 2 días), deltas vs tu 75 y lectura del coach |

Fuentes de datos (mismo origen, sin CORS): `registro.csv` (partidas), `games.csv` (games), `scouting.csv` (rivales), `meta/prowess.json` (meta del arquetipo). Con todo caído, la página cae a un snapshot incrustado.

## Rutas del repo

```
mtg-izzet/
├─ index.html                  # dashboard (GitHub Pages)
├─ registro.csv                # partidas — lo escribe el robot
├─ games.csv                   # detalle por game — lo escribe el robot
├─ scouting.csv                # scouting por rival — lo escribe el robot
├─ automation/
│  ├─ pipeline.py              # el robot: Drive → parsear → emparejar → CSVs
│  ├─ test_emparejamiento.py   # autotests del emparejamiento (sin tocar Google)
│  ├─ jugadores.json           # nicks dados de alta (sin esto, el robot ignora la carpeta)
│  └─ GUIA.md                  # cómo se montó la cuenta robot y los secretos
├─ parser/
│  ├─ mtgo_gamelog_parser.py   # decodifica los .dat de MTGO (con --selftest)
│  └─ README.md
├─ scripts/
│  └─ meta_mtgtop8.mjs         # recolector del meta (mtgtop8) → meta/prowess.json
├─ meta/                       # mi-75.json (tu lista de referencia) + prowess.json (campo)
├─ .github/workflows/
│  ├─ actualizar-tracker.yml   # robot de datos: diario + manual (Run workflow)
│  └─ actualizar-meta.yml      # meta mtgtop8: cada 2 días + manual
├─ docs/                       # cuadernos de estrategia + instrucciones de jugadores
│  ├─ leeme-jugador.md         # plantilla del LEEME de cada carpeta de jugador
│  └─ instrucciones-companeros.md
└─ data/                       # (gitignored) material local sensible
```

## Para un jugador nuevo

1. Fer pide el alta (operación en su HQ): se crea en Drive la carpeta `Logs_<nick>` con su hoja **"Partidas — <nick>"** y su **LEEME** (plantilla en [`docs/leeme-jugador.md`](docs/leeme-jugador.md)), y se registra el nick en [`automation/jugadores.json`](automation/jugadores.json).
2. El jugador solo hace dos cosas después de jugar: **subir sus `.dat`** (están en `C:\Users\<usuario>\AppData\Local\Apps\2.0\Data`) y **apuntar Fecha, Liga, Ronda y Rival** en su hoja. Detalle en [`docs/instrucciones-companeros.md`](docs/instrucciones-companeros.md).

## Desarrollo

```bash
python3 parser/mtgo_gamelog_parser.py --selftest   # parser sin necesitar logs
python3 automation/test_emparejamiento.py          # emparejamiento con fixtures
python3 -m http.server 8000                        # dashboard en local
```

Los nicks de rivales son públicos por decisión del propietario (2026-07-22); las hojas de apuntes de los jugadores no se publican nunca.
