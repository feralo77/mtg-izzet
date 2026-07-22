# Automatismo de datos (se hace solo, carpeta-céntrico)

> Guía paso a paso sin tecnicismos para ponerlo en marcha: [`GUIA.md`](GUIA.md).
> Qué hace cada compañero (plantilla + mensaje): [`../docs/instrucciones-companeros.md`](../docs/instrucciones-companeros.md).

Cada día, una **GitHub Action** lee las carpetas del Drive, empareja tus apuntes con las
partidas de los logs y **regenera dos ficheros en el repo**: `registro.csv` (el detalle de
partidas que ya lee el dashboard) y `games.csv` (una fila por game, para la pestaña "Cómo
juegas"). El dashboard lee esos ficheros, así que se actualiza solo. Nadie tiene que tocar
nada más que **su carpeta del Drive**.

```
Cada jugador, en  Drive/MTG · Izzet/Logs_<nick>/ :
   · deja sus .dat  (Match_GameLog*.dat)
   · rellena su hoja de Google  "Partidas — <nick>"  (Evento/Liga, Ronda, Lista, Notas, Mazo rival)
        │
        ▼   (GitHub Action, cada día · cuenta de servicio de Google SOLO LECTURA)
  automation/pipeline.py
   · parsea los logs (solo TUS partidas · dedupe por match_uuid)
   · empareja apuntes ↔ partidas por fecha (hora de Madrid) + orden cronológico
        │
        ▼
  registro.csv  +  games.csv  (commiteados al repo)  →  el dashboard se actualiza solo
```

## Qué entra y qué sale

- **Entrada: SOLO las carpetas `Logs_<nick>`** de "MTG · Izzet". Cada una lleva los `.dat`
  del jugador y su hoja "Partidas — <nick>" con los apuntes.
- **Salida: `registro.csv` y `games.csv`** en la raíz del repo. El robot **ya no escribe en
  ningún Google Sheet**: solo lee. Por eso ya no hay que compartir el tracker como Editor.
- **Histórico de feralo77**: el tracker viejo (pestaña manual) se lee en **solo lectura** y
  sus filas tecleadas a mano complementan las partidas de los logs (Liga/Ronda/Lista/Notas),
  incluida la del bye/concede sin log. Si una partida está en el tracker y en la hoja nueva,
  manda la hoja nueva.

## Reglas de emparejamiento (apuntes ↔ partidas)

1. Las fechas de los logs se pasan a **hora de Madrid** antes de cruzar (los `.dat` traen
   UTC; una partida de las 00:30 locales caería en el día anterior si no se convierte).
2. Por **fecha + orden cronológico**: la fila n de ese día se empareja con la partida n.
3. Si la fila trae "Mazo rival", ayuda a desambiguar contra el arquetipo detectado.
4. Si un día tiene **más partidas que filas**, las sobrantes salen como **práctica**
   (`Fuente=log`, Evento vacío).
5. Una **fila sin partida** (jugada en papel o log perdido) sale igual con `Fuente=manual`
   y nota de revisar. El **bye/concede** entra por aquí.
6. La **fila de ejemplo** (Notas que empieza por "(ejemplo") se ignora.

## Privacidad

Ningún nick de rival de MTGO aparece en los ficheros publicados. En "Mazo del Oponente" va
el nombre de mazo de tu apunte si lo pusiste; si no, el **arquetipo detectado**. Los logs
crudos no se suben al repo (los lee la Action y ya).

## Puesta en marcha (una sola vez) — lo que tiene que hacer Fer

Yo no puedo crear credenciales ni tocar secretos; estos pasos son tuyos. Te guío en cada uno.

1. **Cuenta de servicio de Google** (gratis, en console.cloud.google.com):
   - Crea un proyecto, activa **Google Drive API** y **Google Sheets API**.
   - Crea una **Service Account** y genera una **clave JSON** (la descargas).
   - Apunta su email, del tipo `algo@tu-proyecto.iam.gserviceaccount.com`.
2. **Compartir con esa cuenta** (basta LECTURA):
   - Comparte la carpeta **`MTG · Izzet`** con ese email como **Lector**.
   - (Solo para el histórico) comparte el **tracker viejo** con ese email como **Lector**.
     Ya **no** hace falta darle permiso de Editor a nada.
3. **Secretos en GitHub** (repo `feralo77/mtg-izzet` → Settings → Secrets → Actions):
   - `GOOGLE_SA_KEY` = el contenido del JSON de la cuenta de servicio.
   - `TRACKER_SHEET_ID` = el id del tracker viejo (para leer el histórico).
   - `MTG_FOLDER_ID` = `16WDaeVHuOtyTaJDrNlVlpgbcN39iVhY6` (la carpeta MTG · Izzet).
4. **Jugadores**: dime los nicks de MTGO de quienes aportarán logs y los añado a
   [`jugadores.json`](jugadores.json). Cada uno deja sus `.dat` y su hoja en su `Logs_<nick>`.

Cuando esté, se lanza a mano una vez (pestaña **Actions** → "Actualizar datos desde las
carpetas" → Run) para validar, y a partir de ahí va solo cada día.

## Notas de diseño
- **De quién es cada partida**: el parser mira quién juega cada match; solo cuenta las del
  jugador de esa carpeta y descarta partidas ajenas/espectadas.
- **Sin duplicados**: todo se deduplica por `match_uuid`; si varios suben logs solapados,
  cada partida cuenta una vez.
- **Seguridad**: la clave de la cuenta de servicio vive solo como secreto de GitHub; nunca
  en el repo.
- **Autotests**: `automation/test_emparejamiento.py` prueba las reglas de emparejamiento con
  fixtures sintéticos (práctica, medianoche/Madrid, papel, ejemplo, bye, privacidad).
