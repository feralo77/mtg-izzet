# Guía: dejar los datos en automático (paso a paso)

Objetivo: que los logs de MTGO y tus apuntes se conviertan solos en los datos del
dashboard, sin que nadie toque nada más que su carpeta del Drive. Lo montas UNA vez
(unos 15-20 min) y ya funciona cada día.

No hace falta saber programar. Sigue los pasos en orden. Si algo no cuadra, para y me
lo dices.

---

## Antes de empezar: qué necesitas tener a mano
- Tu cuenta de Google (la de tu Magic: `falonso2089`).
- Acceso al repo de GitHub `feralo77/mtg-izzet` (tu cuenta `feralo77`).
- Estos identificadores (cópialos cuando toque):
  - **Carpeta MTG · Izzet**: `16WDaeVHuOtyTaJDrNlVlpgbcN39iVhY6`
  - **Tracker viejo (Google Sheet)**: su id lo copias de la barra del navegador con el
    tracker abierto — es la ristra larga de la URL, entre `/d/` y `/edit`. Solo se usa
    para leer tu histórico.

---

## Paso 1 — Crear la "cuenta robot" de Google (cuenta de servicio)

Es una cuenta especial que actúa sola, sin persona detrás. Gratis.

1. Entra en **console.cloud.google.com** con tu cuenta.
2. Arriba, en el selector de proyectos, **Nuevo proyecto** → nombre `mtg-izzet` → Crear.
   Asegúrate de que queda seleccionado ese proyecto (arriba a la izquierda).
3. Activa las dos APIs que hacen falta. Busca cada una en la barra de arriba y pulsa **Habilitar**:
   - **Google Drive API**
   - **Google Sheets API**
4. Menú (☰) → **APIs y servicios** → **Credenciales** → **Crear credenciales** →
   **Cuenta de servicio**.
   - Nombre: `robot-tracker`. **Crear y continuar** → **Listo** (sin roles, no hacen falta).
5. En la lista de cuentas de servicio, entra en la que acabas de crear. Copia su
   **correo electrónico** (algo tipo `robot-tracker@mtg-izzet-xxxx.iam.gserviceaccount.com`).
   **Apúntalo**, lo usas en el Paso 2.
6. Pestaña **Claves** → **Agregar clave** → **Crear clave nueva** → tipo **JSON** → Crear.
   Se te descarga un fichero `.json`. **Guárdalo, es la contraseña del robot** (no lo
   compartas ni lo subas a ningún sitio; solo va al secreto de GitHub del Paso 3).

---

## Paso 2 — Dar permiso al robot (compartir, SOLO lectura)

El robot solo necesita **LEER**. No escribe en ningún sitio de Google: sus resultados van
al repo de GitHub. Le das permiso compartiendo, igual que con una persona, usando el correo
del robot del Paso 1.

1. En Drive, botón derecho sobre la carpeta **MTG · Izzet** → **Compartir** → pega el
   correo del robot → rol **Lector** → Enviar.
2. (Solo para tu histórico) abre el **tracker viejo** → **Compartir** → pega el correo del
   robot → rol **Lector** → Enviar. **Ya no hace falta darle Editor a nada.**

---

## Paso 3 — Guardar los secretos en GitHub

Aquí le dices al automatismo quién es el robot y dónde leer. Los "secretos" están cifrados;
nadie los ve.

1. Ve a **github.com/feralo77/mtg-izzet** → **Settings** (Ajustes) → menú izquierdo
   **Secrets and variables** → **Actions** → botón **New repository secret**.
2. Crea estos tres (Name exactamente así, y en Secret pegas el valor):
   - Name: `GOOGLE_SA_KEY` · Secret: **todo el contenido** del fichero `.json` del Paso 1.
   - Name: `TRACKER_SHEET_ID` · Secret: el id del tracker viejo (la ristra larga de su URL,
     entre `/d/` y `/edit`).
   - Name: `MTG_FOLDER_ID` · Secret: `16WDaeVHuOtyTaJDrNlVlpgbcN39iVhY6`

---

## Paso 4 — Dar de alta a los compañeros

Por cada compañero que vaya a aportar datos (el tuyo ya está: `feralo77`):

1. Pídele su **nick de MTGO** y pásamelo: lo añado a la lista de jugadores.
2. En Drive, dentro de **MTG · Izzet**, crea la subcarpeta **`Logs_<sunick>`** (nick exacto)
   y compártela **solo con él**, como **Editor**. Dentro, crea su hoja de Google
   **"Partidas — <sunick>"** con las columnas: Fecha · Evento / Liga · Ronda · Lista ·
   Notas · Mazo rival (opcional).
3. Envíale el mensaje que tienes listo en
   [`../docs/instrucciones-companeros.md`](../docs/instrucciones-companeros.md): que deje
   sus `.dat` en la carpeta y rellene una fila por partida en su hoja.

---

## Paso 5 — Encender y comprobar

1. En **github.com/feralo77/mtg-izzet** → pestaña **Actions** → en la izquierda
   "Actualizar datos desde las carpetas" → botón **Run workflow** → Run.
2. Espera un minuto y ábrelo: si sale verde, el repo tendrá `registro.csv` y `games.csv`
   actualizados (los verás en un commit automático). El dashboard ya los muestra.
3. A partir de ahí va **solo cada día**. Cuando quieras forzarlo, repites el Run.

Si el Run sale en rojo, entra en él, copia el mensaje de error y me lo pegas: casi siempre
es un permiso del Paso 2 o un secreto mal pegado del Paso 3. Lo afinamos.

---

## Qué NO tienes que hacer
- No subas nunca el `.json` del robot al repo ni a Drive: solo va al secreto de GitHub.
- No hace falta tocar código. Si algún día cambian los jugadores, me dices los nicks.

Resumen de la tubería, por si lo quieres tener claro:

```
Cada jugador, en  Drive/MTG · Izzet/Logs_<nick>/ :  .dat  +  hoja "Partidas — <nick>"
      │  (GitHub Action, cada día, con el "robot" de Google en SOLO LECTURA)
      ▼
  parser (solo TUS partidas · sin duplicados)  +  emparejar con tus apuntes
      │
      ▼
  registro.csv  +  games.csv  (commiteados al repo)  →  el dashboard se actualiza solo
```
