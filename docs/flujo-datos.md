# Flujo de datos — logs, apuntes y multi-usuario

Cómo entran los resultados al dashboard sin teclear dos veces, y cómo se registra **quién**
aporta cada partida. El montaje es **carpeta-céntrico**: la entrada son las carpetas
`Logs_<nick>` del Drive; la salida son `registro.csv` y `games.csv` en el repo.

## Las dos fuentes

| Fuente | Qué aporta | Cómo |
|---|---|---|
| **Logs de MTGO** (parser) | Lo automático: fecha, **mazo detectado**, resultado, games, salida/robo (G1), mulligans, turnos, prowess, monjes, `match_uuid` | `mtgo_gamelog_parser.py` |
| **Apuntes** (hoja "Partidas — <nick>") | Lo que el log NO sabe: **Evento/Liga, Ronda, Lista, Notas** y, opcional, **Mazo rival** | a mano, poco |

Las dos se cruzan por **fecha (hora de Madrid) + orden cronológico**: la fila n de un día
se empareja con la partida n de ese día. Nunca reescribes lo que el log ya trae.

## Multi-usuario: quién reporta

Cargan datos varias personas. Cada fila lleva **`Reportado por`** (el nick de la carpeta) y
todo se **deduplica por `match_uuid`**: si dos personas suben logs que se solapan, cada
partida cuenta **una sola vez**. El dashboard tiene filtro y columna "Reportado por".

## El pipeline

```
  Drive/MTG · Izzet/Logs_<nick>/ :  .dat  +  hoja "Partidas — <nick>"
        │  (GitHub Action diaria · cuenta de servicio SOLO LECTURA)
        ▼
  automation/pipeline.py
   · parser: logs -> partidas (solo las del jugador · dedupe por match_uuid)
   · emparejar apuntes ↔ partidas por fecha (Madrid) + orden cronológico
   · feralo77: el tracker viejo se lee (solo lectura) como apuntes históricos
        │
        ▼
  registro.csv  +  games.csv  (commiteados al repo)  ->  Dashboard (se lee solo)
```

## Reglas de emparejamiento

1. Fechas de logs a **hora de Madrid** antes de cruzar (los `.dat` traen UTC).
2. **Fecha + orden cronológico**: fila n ↔ partida n.
3. "Mazo rival" del apunte desambigua contra el arquetipo detectado.
4. Más partidas que filas → las sobrantes son **práctica** (`Fuente=log`, Evento vacío).
5. Fila sin partida (papel o log perdido) → sale con `Fuente=manual` y nota de revisar
   (aquí entra el bye/concede).
6. Fila de ejemplo (Notas que empieza por "(ejemplo") → se ignora.

## Notas

- El dashboard lee **por nombre de columna**, no por posición: añadir columnas no lo rompe.
- El volcado de logs incluye **partidas de práctica** (no solo Liga). El apunte es donde
  marcas cuáles son de Liga (Evento/Ronda); el filtro "Liga / Evento" del dashboard las separa.
- `match_uuid`, los logs crudos y las hojas con datos personales **no se suben al repo**.
- **Privacidad**: en los ficheros publicados no aparece ningún nick de rival; "Mazo del
  Oponente" lleva el nombre de mazo del apunte o, si no lo hay, el arquetipo detectado.
