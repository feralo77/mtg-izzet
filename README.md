# MTG · Izzet Prowess — Centro de mando

Dashboard de estadísticas y estrategia para el mazo **Izzet Prowess** (Modern, jugado en Magic Online) de [@feralo77](https://github.com/feralo77), más un **lector de logs de MTGO** que convierte los ficheros de partida en datos del tracker sin apuntar a mano.

## El dashboard

`index.html` es una página autónoma (HTML + [Chart.js](https://www.chartjs.org/)). Se publica en **GitHub Pages** y muestra:

- Estadísticas de partidas: win rate en salida vs. robo, por matchup, evolución por liga.
- Las listas analizadas con enlaces, y la comparativa de slots flexibles.
- Plan de sideboard por matchup (con tu win rate real).
- La "75 Definitiva" y su plan de sideboard.
- **Logs MTGO**: demo del lector de partidas (parser).

### De dónde saca los datos

1. **Google Sheet publicado** (automático): pega la URL de tu hoja publicada como CSV en la constante `SHEET_CSV_URL` (dentro de `index.html`). El dashboard la lee cada vez que se abre.
2. **CSV manual** (respaldo): botón "⟳ Cargar datos (CSV)".

Si no hay Sheet configurado, usa un snapshot de datos incrustado.

## El parser de logs (`parser/`)

`mtgo_gamelog_parser.py` decodifica los ficheros binarios `*Match_GameLog*.dat` que MTGO escribe solo, y genera el CSV del Registro: resultado, games, salida/robo (game 1), mulligans, cartas del rival y una **clasificación automática del mazo rival** por esas cartas.

```bash
# Comprobar que va bien (no necesita logs)
python3 parser/mtgo_gamelog_parser.py --selftest

# Procesar tus logs → CSV
python3 parser/mtgo_gamelog_parser.py --dir "<carpeta con los .dat>" --out registro.csv
```

Usuario MTGO por defecto: `feralo77` (cámbialo con `--user`). Detalle en [`parser/README.md`](parser/README.md).

## Datos y logs (no están en el repo)

Los logs de MTGO, las hojas de cálculo y las notas de traspaso viven en `data/` y están **excluidos del repo** (`.gitignore`): contienen chat, nombres de terceros y datos personales. La fuente de verdad de las partidas es el Google Sheet del Drive.

## Estructura

```
mtg-izzet/
├─ index.html            # dashboard (GitHub Pages)
├─ parser/               # lector de logs de MTGO
│  ├─ mtgo_gamelog_parser.py
│  └─ README.md
├─ docs/                 # cuadernos de estrategia del mazo
└─ data/                 # (gitignored) logs, hojas, notas — local
```
