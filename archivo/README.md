# archivo/ — las partidas que ya no se analizan (pero no se borran)

Desde el **15-sep-2026** el tracker analiza a **un solo jugador: `feralo77`**, y la
lista que mira de salida es la **Stock**. Decisión de Fer.

Lo que hay aquí son las partidas de los **compañeros de liga** (`4c_PolG`; `Inkmaster`
nunca llegó a aportar ninguna). **No se ha borrado nada**: están enteras, con las mismas
columnas de siempre, y el robot las sigue escribiendo cada día.

| Fichero | Qué es | Filas (15-sep-2026) |
|---|---|---|
| `registro.csv` | una fila por partida | 138 |
| `games.csv` | una fila por game | 346 |
| `esperando.json` | rondas apuntadas a las que aún les falta el `.dat` | 9 |

En la raíz del repo quedan los mismos ficheros con **solo lo de Fer** (52 partidas,
123 games). El dashboard lee la raíz y **nunca** mira aquí.

## Lo que NO se movió

`scouting.csv` se queda **entero y en la raíz**. Es una base de datos de **rivales**, no
de jugadores: de los 181 nicks fichados, **129 solo los vio el archivo**, y siguen siendo
scouting útil para cuando a Fer le toque uno de ellos. La columna `Visto por` dice de
quién salió cada avistamiento.

Las **listas** (`listas/*.txt`) tampoco se movieron: son material de referencia para el
comparador carta a carta, no partidas.

## Cómo volver atrás

Todo el reparto lo decide `automation/jugadores.json`:

```json
{ "principal": "feralo77", "archivados": ["4c_PolG", "Inkmaster"] }
```

Sacar un nick de `archivados` y volver a lanzar el robot devuelve sus partidas a la raíz.
No hay que tocar código.
