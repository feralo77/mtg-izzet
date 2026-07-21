# Carga diaria automática de resultados

El dashboard lee `registro.csv` (en la raíz del repo). Un GitHub Action lo refresca solo una vez al día desde tu hoja del Drive, para que no tengas que tocar nada.

## Cómo funciona

1. `.github/workflows/actualizar-datos.yml` se ejecuta cada día (06:00 UTC) y también a mano desde la pestaña **Actions** del repo.
2. Llama a `scripts/actualizar_registro.mjs`, que baja el CSV de tu hoja, le añade la columna **Arquetipo** (mapeando el mazo del oponente a un nombre limpio) y **Reportado por**, y reescribe `registro.csv`.
3. Si hubo cambios, los commitea. La próxima vez que abras el dashboard, ya salen.

Orden de fuentes que usa el dashboard: `registro.csv` (auto, sin CORS) → hoja en vivo → snapshot embebido.

## Para activarlo (una vez)

La hoja tiene que ser accesible sin login. La forma más limpia:

1. En la hoja: **Archivo → Compartir → Publicar en la web → CSV** (elige la pestaña *Registro*). Copia la URL.
2. En GitHub: **Settings → Secrets and variables → Actions → Variables → New repository variable**
   - Nombre: `SHEET_CSV_URL`
   - Valor: la URL del paso 1.
3. (Opcional) Pega también esa URL en `SHEET_CSV_URL` dentro de `index.html` para que el navegador la use en vivo.

Mientras no esté configurado, **el workflow no falla**: baja los brazos con un mensaje y deja `registro.csv` como esté. Así no llena tu correo de errores.

## Añadir arquetipos nuevos

Cuando aparezca un mazo de oponente que no estaba, edita el diccionario `ARQUETIPOS` en `scripts/actualizar_registro.mjs`. Si no está mapeado, no se pierde: se conserva el texto tal cual lo apuntaste.
