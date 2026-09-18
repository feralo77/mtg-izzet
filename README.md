# MTG · Izzet Prowess — Centro de mando

Dashboard de estadísticas para el mazo **Izzet Prowess** (Modern) de [@feralo77](https://github.com/feralo77) en las **ligas de Magic Online**. Nadie teclea resultados: un **robot diario** lee los logs de MTGO y los apuntes desde Drive y publica los datos aquí.

> ### El enfoque (15-sep-2026)
> El dashboard analiza **un solo jugador, Fer**, y abre en **una sola versión del mazo, la Stock**.
>
> - Las partidas de los compañeros de liga **no se han borrado**: viven enteras en [`archivo/`](archivo/) y el robot las sigue guardando cada día. Basta con sacar un nick de `archivados` en [`automation/jugadores.json`](automation/jugadores.json) para que vuelvan.
> - Las versiones Aggro y Basics siguen en los datos y en los desplegables, a un clic. Lo que cambia es por dónde **abre** el dashboard.
> - **Con menos datos, más honestidad**: la muestra pasó de 190 partidas a 32 (Stock). Todos los cortes llevan su `n` a la vista, las barras que no llegan a muestra salen en **gris** y los textos describen sin concluir cuando el dato no da. La regla está escrita en el propio dashboard, no solo en el código.

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

Página autónoma (HTML + Chart.js, design system Blockprint). En la cabecera hay un **chip de muestra** permanente que dice, desde cualquier pestaña, sobre cuántas partidas y games está calculado lo que estás viendo, y se pone ámbar cuando la muestra es corta.

| Pestaña | Qué muestra |
|---|---|
| Estadísticas | KPIs, salida vs robo, WR por mazo rival, evolución por liga, detalle de partidas |
| Cómo juegas | Análisis game a game de los logs: manos iniciales, mulligans, robos, tierras, tempo (primera amenaza, turno del Cutter), motor de prowess |
| Listas | Tus versiones de mazo con récord real y versión × mazo rival |
| Scouting | Rival a rival: enfrentamientos, mazos y cartas vistas (la única tabla que sigue incluyendo lo que vieron los compañeros — es una base de datos de rivales, no de jugadores) |
| Comparativa | Versiones, mazos rivales y salida/robo frente a frente (la dimensión "Jugador" se retiró con el cambio de enfoque) |
| La 75 Definitiva | La lista de referencia carta a carta, y la guía de sideboard de 16 matchups con tu récord y tu frecuencia recalculados en vivo |
| Meta · mtgtop8 | Lista media del arquetipo (se refresca cada 2 días), deltas vs tu 75 y lectura del coach |

Fuentes de datos (mismo origen, sin CORS): `registro.csv` (partidas), `games.csv` (games), `scouting.csv` (rivales), `meta/prowess.json` (meta del arquetipo). Con todo caído, la página cae a un snapshot incrustado.

## Rutas del repo

```
mtg-izzet/
├─ index.html                  # dashboard (GitHub Pages)
├─ registro.csv                # TUS partidas — lo escribe el robot
├─ games.csv                   # detalle por game (tuyo) — lo escribe el robot
├─ scouting.csv                # scouting por rival, de todos los logs — lo escribe el robot
├─ archivo/                    # partidas de los compañeros: guardadas, fuera del análisis
│  └─ README.md                # qué hay, por qué, y cómo devolverlas a la raíz
├─ automation/
│  ├─ pipeline.py              # el robot: Drive → parsear → emparejar → CSVs
│  ├─ test_emparejamiento.py   # autotests del emparejamiento (sin tocar Google)
│  ├─ jugadores.json           # nicks de alta + quién es el 'principal' y quién está 'archivado'
│  ├─ anuladas.json            # ligas y rondas que no cuentan (p. ej. la que se cortó por un cuelgue)
│  └─ GUIA.md                  # cómo se montó la cuenta robot y los secretos
├─ parser/
│  ├─ mtgo_gamelog_parser.py   # decodifica los .dat de MTGO (con --selftest)
│  └─ README.md
├─ scripts/
│  ├─ meta_mtgtop8.mjs         # recolector del meta (mtgtop8) → meta/prowess.json
│  └─ extraer_guia.py          # guia.pages (guía premium de ethanmtg) → texto plano, para ver qué cambió
├─ meta/                       # mi-75.json (tu lista de referencia) + prowess.json (campo)
├─ .github/workflows/
│  ├─ actualizar-tracker.yml   # robot de datos: diario + manual (Run workflow)
│  └─ actualizar-meta.yml      # meta mtgtop8: cada 2 días + manual
├─ docs/                       # cuadernos de estrategia + instrucciones de jugadores
│  ├─ guia-ethanmtg.md         # cómo se mantiene al día la guía premium (proceso de actualización)
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

## Umbrales de lectura

Están en `index.html` y son la línea a partir de la cual el dashboard se atreve a concluir. No son estadística fina: son el acuerdo de hasta dónde se puede leer un dato.

| Constante | Valor | Qué controla |
|---|---|---|
| `VERSION_FOCO` | `Stock` | la versión que queda marcada de salida en los filtros |
| `MUESTRA_CORTA` | 40 partidas | por debajo, el chip de muestra se pone ámbar |
| `N_MIN` | 10 partidas | mínimo por grupo para **afirmar** una diferencia (si no, se describe) |
| `DIF_MIN` | 12 puntos | diferencia de WR a partir de la cual se llama señal y no ruido |
| `N_GAME_MIN` | 8 games | por debajo, la barra sale en gris en vez de verde/rojo |
| `N_MATCHUP` | 3 partidas | por debajo, el matchup sale en gris y marcado "muestra mínima" |

`MIN_BASE` (30 partidas por mitad) vive en `scripts/radar_meta.mjs` y gobierna si el radar se atreve a hablar de **tendencia** en la liga de Fer. Con solo sus partidas no se cumple todavía, y **no se baja el listón para encenderla**: el radar lo dice y sigue avisando por frecuencia y récord, que sí son fiables.
