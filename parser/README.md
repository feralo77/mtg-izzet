# Parser de game logs de MTGO → tu tracker

Convierte los logs de partida de Magic Online en filas del **Registro** del tracker, sin apuntar a mano.

## Qué hace
Lee los ficheros binarios `*Match_GameLog*.dat` que MTGO escribe automáticamente y extrae, por cada match: **resultado (W/L), games ganados/perdidos, salida/robo (G1), mulligans (tú y rival) y las cartas vistas del rival**. Genera un `CSV` con las columnas exactas del Registro para cargarlo en el dashboard (botón "⟳ Cargar datos (CSV)") o pegarlo en el Excel.

Está basado en el cliente open-source de MyMTGO (formato binario y regex de resultados verificados contra su código).

## Dónde están los logs (Windows, el PC de MTGO)
MTGO es una app ClickOnce; los logs viven en:
```
%USERPROFILE%\AppData\Local\Apps\2.0\Data
```
y los ficheros contienen `Match_GameLog` en el nombre. No hay que "activar" nada especial: MTGO los escribe solo. (En Mac/wrapper la ruta cambia; localizamos la carpeta equivalente.)

## Uso
```bash
# 1) Comprobar que el decodificador va bien (no necesita logs)
python3 mtgo_gamelog_parser.py --selftest

# 2) Procesar tus logs
python3 mtgo_gamelog_parser.py --dir "C:\Users\<tu>\AppData\Local\Apps\2.0\Data" --user <tu_usuario_MTGO> --out registro_mtgo.csv
```
- `--user` es tu nick de MTGO: sirve para saber cuál de los dos jugadores eres tú.
- `--lista` (opcional) pone el nombre de lista en cada fila (por defecto "Stock").

Luego, en el dashboard: **⟳ Cargar datos (CSV)** → eliges `registro_mtgo.csv` y se actualiza todo.

## Qué NO saca (aún) y siguiente paso
- El **arquetipo del rival** no está en el log: se deja en blanco y se listan las cartas vistas del rival en "Notas" para clasificarlo (podemos añadir un auto-clasificador por cartas).
- **Evento/Liga y Ronda** no están en el game log (van en otros mensajes de torneo): de momento se dejan en blanco para que los rellenes, o los inferimos por fecha/hora en una v2.

**Para afinarlo al 100%:** súbeme UN `.dat` real tuyo y valido la extracción contra él (nombres, salida/robo, mulligans) y ajusto lo que haga falta.
