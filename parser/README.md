# Parser de game logs de MTGO → tu tracker

Convierte los logs de partida de Magic Online en filas del **Registro** del tracker, sin apuntar a mano. **Validado con logs reales** de `feralo77` (v3 — extracción máxima).

## Qué hace
Lee los ficheros binarios `*Match_GameLog*.dat` que MTGO escribe automáticamente, **parte cada match en sus games** y extrae el máximo:

- **Por match**: resultado (W/L), games, salida/robo (G1), mulligans, `match_uuid`, y la **lista COMPLETA del rival** (clasifica el arquetipo mucho mejor que con 4 cartas).
- **Por game**: turnos que duró, tu mano y la del rival, tus hechizos lanzados (tu curva), disparos de **prowess**, fichas de **Monje** (Cori-Steel Cutter), activaciones, descartes y los **objetivos de tu removal** (a qué apunta cada Bolt/Heat).

Cada fichero `.dat` contiene la partida entera. Está basado en el cliente open-source de MyMTGO (formato binario y regex verificados contra su código).

> **Solo tus partidas.** El volcado de MTGO puede traer partidas ajenas (espectadas o de otra persona en ese cliente). El parser **descarta los matches donde tu `--user` no juega** y avisa de cuántos. En el volcado de prueba: 29 ficheros → 9 ajenos descartados → **20 partidas tuyas** (récord 10-10, que cuadra con tu histórico).

## Dónde están los logs (Windows, el PC de MTGO)
MTGO es una app ClickOnce; los logs viven en `%USERPROFILE%\AppData\Local\Apps\2.0\Data` y contienen `Match_GameLog` en el nombre. No hay que activar nada. (En Mac/wrapper la ruta cambia; se localiza la carpeta equivalente.)

## Uso
```bash
# 1) Comprobar el decodificador (no necesita logs)
python3 mtgo_gamelog_parser.py --selftest

# 2) Procesar tus logs
python3 mtgo_gamelog_parser.py --dir "<carpeta con los .dat>" --out registro_mtgo.csv
```
- `--user` (por defecto `feralo77`): tu nick de MTGO, para saber cuál de los dos jugadores eres. **Importante**: sin el usuario correcto, el parser puede confundirte con el rival.
- `--reported-by` (por defecto, el `--user`): quién reporta estas partidas. Va en la columna `Reportado por` (ver multi-usuario abajo).
- `--lista` (por defecto `Stock`): nombre de lista en cada fila.

Genera **3 ficheros**: `<out>` (Registro, para el tracker/dashboard), `<out>.matches.csv` (detalle rico por match) y `<out>.games.csv` (detalle por game).

## Clasificación del mazo rival
El arquetipo no viene en el log: se deduce de las cartas vistas (`classify`, firmas por cartas). Cubre el meta de Modern actual (incluye Boros Ponza, Neoform, Broodscale, Goryo's, etc.). Si solo se ven 1-2 cartas, deja `¿? (revisar)` — es falta de datos, no un fallo.

## Lo que el log NO sabe → el complemento
**Evento/Liga y Ronda** no están en el game log. En vez de teclearlos a mano cada vez, se rellenan una vez en una hoja de **complemento** por `match_uuid` y se fusionan con `merge_registro.py`. Ver [`../docs/flujo-datos.md`](../docs/flujo-datos.md).

```bash
python3 merge_registro.py --logs registro_mtgo.csv --complemento complemento.csv --out registro_completo.csv
```
Plantilla: [`plantilla_complemento.csv`](plantilla_complemento.csv).

## Multi-usuario
Cargaremos datos varias personas. Cada volcado se estampa con `Reportado por`, y todo se **deduplica por `match_uuid`**: si dos personas suben logs solapados, cada partida cuenta una vez. El dashboard filtra por "Reportado por".
