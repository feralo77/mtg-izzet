# Carga diaria automática de datos

El dashboard lee `registro.csv` y `games.csv` (en la raíz del repo). Un único GitHub Action
los regenera solos una vez al día desde las **carpetas del Drive**, para que no tengas que
tocar nada.

## Cómo funciona

1. `.github/workflows/actualizar-tracker.yml` ("Actualizar datos desde las carpetas") se
   ejecuta cada día (06:00 UTC) y también a mano desde la pestaña **Actions** del repo.
2. Llama a `automation/pipeline.py`, que:
   - lee las carpetas `Logs_<nick>` de "MTG · Izzet" (logs `.dat` + hoja "Partidas — <nick>"),
   - parsea los logs (solo las partidas de cada jugador, dedupe por `match_uuid`),
   - empareja tus apuntes con las partidas por fecha (hora de Madrid) + orden cronológico,
   - regenera `registro.csv` y `games.csv`.
3. Si hubo cambios, los commitea. La próxima vez que abras el dashboard, ya salen.

El robot de Google trabaja en **solo lectura**: sus resultados van al repo, no a ningún
Google Sheet. Detalle del montaje y las reglas de emparejamiento en
[`../automation/README.md`](../automation/README.md) y [`../automation/GUIA.md`](../automation/GUIA.md).

Orden de fuentes que usa el dashboard para las partidas: `registro.csv` (auto, sin CORS) →
hoja en vivo (si se configura) → snapshot embebido. Para "Cómo juegas": `games.csv` (fetch) →
array `GAMES` embebido como último recurso.

## Para activarlo (una vez)

No hace falta publicar ninguna hoja: basta con compartir la carpeta "MTG · Izzet" (y el
tracker viejo) con la cuenta de servicio como **Lector**, y tener los tres secretos en
GitHub (`GOOGLE_SA_KEY`, `TRACKER_SHEET_ID`, `MTG_FOLDER_ID`). Pasos guiados en
[`../automation/GUIA.md`](../automation/GUIA.md).

Mientras no esté configurado (sin `GOOGLE_SA_KEY`), **el workflow no falla**: sale con un
mensaje y deja los ficheros como estén. Así no llena tu correo de errores.

## Añadir arquetipos nuevos

El arquetipo del rival lo detecta el parser a partir de las cartas que ve
(`parser/mtgo_gamelog_parser.py`, firmas ponderadas por arquetipo). Cuando aparezca un mazo
que no clasifica bien, se afinan esas firmas. En tu apunte puedes poner el mazo en "Mazo
rival" para que quede fijado en "Mazo del Oponente" aunque el parser dude.
