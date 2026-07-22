# Automatismo del tracker (se hace solo)

> Guía paso a paso sin tecnicismos para ponerlo en marcha: [`GUIA.md`](GUIA.md).
> Qué hace cada compañero (plantilla + mensaje): [`../docs/instrucciones-companeros.md`](../docs/instrucciones-companeros.md).

Cada día, una **GitHub Action** lee los logs de MTGO del Drive, corre el parser por
jugador y escribe el resultado en la pestaña **`Registro-logs`** del tracker. El
dashboard lee esa pestaña, así que se actualiza solo. Nadie tiene que tocar nada
más que **dejar sus logs en su carpeta del Drive**.

```
Cada jugador deja sus .dat en  Drive/MTG · Izzet/Logs_<nick>/
        │
        ▼   (GitHub Action, cada día)
  pipeline.py  →  parser (solo TUS partidas, dedupe por match_uuid)
        │
        ▼
  pestaña "Registro-logs" del tracker  →  el dashboard se actualiza
```

## Puesta en marcha (una sola vez) — lo que tiene que hacer Fer

Yo no puedo crear credenciales ni tocar secretos; estos pasos son tuyos. Te guío en cada uno.

1. **Cuenta de servicio de Google** (gratis, en console.cloud.google.com):
   - Crea un proyecto, activa **Google Drive API** y **Google Sheets API**.
   - Crea una **Service Account** y genera una **clave JSON** (la descargas).
   - Apunta su email, del tipo `algo@tu-proyecto.iam.gserviceaccount.com`.
2. **Compartir con esa cuenta** (para que pueda leer logs y escribir el tracker):
   - Comparte la carpeta **`MTG · Izzet`** con ese email como **Lector**.
   - Comparte el **tracker** (Google Sheet) con ese email como **Editor**.
3. **Secretos en GitHub** (repo `feralo77/mtg-izzet` → Settings → Secrets → Actions):
   - `GOOGLE_SA_KEY` = el contenido del JSON de la cuenta de servicio.
   - `TRACKER_SHEET_ID` = el id del tracker (el de la URL de la hoja).
   - `MTG_FOLDER_ID` = `16WDaeVHuOtyTaJDrNlVlpgbcN39iVhY6` (la carpeta MTG · Izzet).
4. **Jugadores**: dime los nicks de MTGO de quienes aportarán logs y los añado a
   [`jugadores.json`](jugadores.json). Cada uno deja sus `.dat` en su `Logs_<nick>`.

Cuando esté, se lanza a mano una vez (pestaña **Actions** del repo → "Actualizar
tracker desde los logs" → Run) para validar, y a partir de ahí va solo cada día.

## Notas de diseño
- **De quién es cada partida**: el parser mira quién juega cada match; solo cuenta
  las del jugador de esa carpeta y descarta partidas ajenas/espectadas.
- **Sin duplicados**: todo se deduplica por `match_uuid`, así que si varios suben
  logs solapados, cada partida cuenta una vez.
- **Seguridad**: la clave de la cuenta de servicio vive solo como secreto de GitHub;
  nunca en el repo. Los logs crudos no se suben al repo (los lee la Action y ya).
- **Evento/Liga y Ronda** no vienen en el log: se rellenan aparte (complemento) y se
  cruzan por `match_uuid`. Ver [`../docs/flujo-datos.md`](../docs/flujo-datos.md).
