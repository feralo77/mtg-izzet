# Flujo de datos — logs, complemento y multi-usuario

Cómo entran los resultados al dashboard sin teclear dos veces, y cómo se registra **quién** aporta cada partida.

## Las dos fuentes

| Fuente | Qué aporta | Cómo |
|---|---|---|
| **Logs de MTGO** (parser) | Lo automático: fecha, rival, **mazo detectado**, resultado, games, salida/robo (G1), mulligans, `match_uuid` | `mtgo_gamelog_parser.py` |
| **Complemento** (hoja/Excel) | Lo que el log NO sabe: **Evento/Liga, Ronda, Lista, MVP, Notas** (y arquetipo corregido si hace falta) | a mano, poco |

La clave que las une es **`match_uuid`**: el identificador único de cada partida que MTGO escribe en el log. Rellenas la metadata una vez por `match_uuid` y la fusión la pega a la fila automática. **Nunca reescribes lo que el log ya trae.**

## Multi-usuario: quién reporta

Cargaremos datos varias personas. Por eso cada fila lleva **`Reportado por`**:

- El parser estampa quién corre el volcado: `--reported-by <nombre>` (por defecto, el `--user`).
- El dashboard tiene un **filtro "Reportado por"** y una **columna** en el detalle.
- **Anti-duplicados:** todo se **deduplica por `match_uuid`**. Si dos personas suben logs que se solapan, cada partida cuenta **una sola vez** (tanto en la fusión como en el dashboard).

## El pipeline

```
   Logs .dat (MTGO)                Complemento (hoja)
        │  parser                       │  a mano
        ▼                               ▼
  registro_mtgo.csv  ── merge_registro.py (por match_uuid) ──►  registro_completo.csv
        (auto + match_uuid + Reportado por)                          │
                                                                     ▼
                                                     Google Sheet publicado (CSV)
                                                                     │
                                                                     ▼
                                                          Dashboard (se lee solo)
```

## Paso a paso

1. **Volcar tus logs** (cada persona, sus logs):
   ```bash
   python3 parser/mtgo_gamelog_parser.py --dir "<carpeta .dat>" --reported-by feralo77 --out registro_mtgo.csv
   ```
   Sale un CSV con `match_uuid` y `Reportado por`.

2. **Rellenar el complemento** (`parser/plantilla_complemento.csv`): por cada `match_uuid`, pon solo Evento/Liga, Ronda, Lista, MVP, Notas. Para partidas **en papel** (sin log), deja `match_uuid` vacío y rellena la fila entera.

3. **Fusionar**:
   ```bash
   python3 parser/merge_registro.py --logs registro_mtgo.csv --complemento complemento.csv --out registro_completo.csv
   ```

4. **Publicar**: vuelca `registro_completo.csv` a la hoja de Google que el dashboard lee (o cárgalo con el botón "Cargar CSV"). El dashboard se actualiza solo.

## Notas

- El dashboard lee **por nombre de columna**, no por posición: añadir columnas nuevas no lo rompe.
- El volcado de logs incluye **partidas de práctica** (no solo Liga). El complemento es donde marcas cuáles son de Liga (Evento/Ronda); el filtro "Liga / Evento" del dashboard separa lo uno de lo otro.
- `match_uuid`, los logs y las hojas con datos personales **no se suben al repo** (van en `data/`, gitignored).
