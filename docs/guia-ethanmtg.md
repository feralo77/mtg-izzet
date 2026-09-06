# La guía de ethanmtg — cómo se mantiene al día

La guía premium de **ethanmtg** en Metafy (*Izzet Prowess Complete Guide*) es la referencia
externa del proyecto. Fer la tiene comprada; el contenido **es de pago y no se sube al repo**.

- Original: https://metafy.gg/guides/view/izzet-prowess-complete-guide-rcl7z0OsEGi
- Copia local de Fer: `guia.pages` (raíz del repo, gitignored)
- Traducción al español: pestaña **Guía** del dashboard (`index.html`, sección `v-guia`)
- Patrones por matchup, dentro de tu propio plan: campo `patrones` de `meta/guia-sb.json`

## Por qué esto necesita mantenimiento

Es un documento vivo: el autor la actualiza y avisa a los compradores ("this guide will be
constantly updated"). Además publica cada 2 semanas planes de sideboard nuevos como guías
aparte. La foto que hay volcada aquí es la del **26-jul-2026**.

## Cómo actualizarla (proceso)

1. **Fer** abre la guía en Metafy con su cuenta y la trae al repo. Vale cualquiera de las dos
   vías: guardar el documento como `guia.pages`, o **copiar y pegar** el texto en un
   documento nuevo y dejarlo como `.rtf` o `.txt`. (Sin este paso no hay nada que hacer: la
   web pide compra y Claude no puede leerla.)
2. Sacar el texto y compararlo con la foto anterior:

   ```
   python3 scripts/extraer_guia.py                       # guia.pages -> data/guia-texto.txt
   python3 scripts/extraer_guia.py pegado.rtf data/guia-texto.txt   # o desde un pegado
   diff data/guia-texto-2026-09-06.txt data/guia-texto.txt
   ```

   El `diff` enseña **solo lo que cambió**, en vez de obligar a releer 11.000 palabras.
   (Si las dos copias vienen de vías distintas, los saltos de línea no coinciden y el `diff`
   crudo mete ruido: en ese caso se comparan las frases sueltas de cada fichero, que es lo
   que se hizo el 6-sep.)
3. Volcar lo nuevo a la pestaña Guía (traducido, marcando lo nuevo con una etiqueta de fecha)
   y, si toca patrones de juego, al campo `patrones` del matchup correspondiente en
   `meta/guia-sb.json`.
4. Guardar la foto nueva como referencia para la siguiente vez:
   `cp data/guia-texto.txt data/guia-texto-<fecha>.txt`

> El script existe porque un `.pages` es un zip con protobuf comprimido: sin él, la única
> forma de leer la guía era abrir Pages a mano y copiar. Todo lo que produce va a `data/`,
> que está gitignored.

## Fotos guardadas

| Fecha | Fichero | Cómo llegó |
|---|---|---|
| 26-jul-2026 | `data/guia-texto-2026-07-26.txt` | de `guia.pages` |
| 6-sep-2026 | `data/guia-texto-2026-09-06.txt` | pegado de Fer (`data/guia-original-2026-09-06.rtf`) |

**Alcance de la revisión del 6-sep**: el autor tocó el capítulo principal (*Individual Card
Choices*, *Play Pattern Guide*, *Play Pattern Deep-Dives* y *Matchup Guide*), que es
exactamente lo que trajo el pegado de Fer. **Decklists**, **Other Prowess Variants**,
**Mulligan Guide** y **Sideboard Guide** los dejó igual, así que la versión de julio que hay
volcada en el dashboard sigue vigente: no hay nada que copiar de ellos.

## Qué cambió el 6-sep-2026

- **ESPER BLINK**: matchup nuevo, no existía en julio. Favorable preboard.
- **NECRODOMINANCE**: entrada abierta pero vacía (*coming soon*).
- **GORYO'S**: el que más cambia. Pasa de "desfavorable" a "ligeramente desfavorable, depende
  de tu build", y añade un bloque entero de cómo leerle la mano al rival. Cambia el
  tratamiento del Psychic Frog: antes "difícil de matar, presiona por otro lado"; ahora
  **Spell Snare es la respuesta y atacar contra el Frog es fuerte**.
- **BROODSCALE**: reescrito. "Corre, pero respetando el combo", atacar a través del Writhing
  Chrysalis, matar siempre al Glaring Fleshraker como jugada de tempo, y la versión
  mono-verde marcada como más favorable.
- **LIVING END**: cambia el veredicto a **desfavorable**; añade su lista de interacción
  completa y el papel de Endurance (apaga el delirium en mitad del combate).
- **NEOFORM**: desaparece el "intenta esquivarlo"; entra quemar al Griselbrand, el reparto
  Spell Pierce/Spell Snare y el aviso de Endurance.
- **Cartas nuevas fichadas**: Prismatic Ending, Soul-Guide Lantern (con la comparativa contra
  Tormod's Crypt) e Island, que en julio estaba pendiente.
- **Sección nueva de patrones**: *la fetchland como recurso* — cuándo NO romperla.
- Retoques de veredicto en **Affinity** (manda quien esté en la jugada), **Boros Ponza**
  (positivo preboard, más igualado post-side), **Burn** (protege la vida, busca solo básicas)
  y **Belcher** (Into the Flood Maw es su mejor jugada de control).

## Estado del cruce con tu plan de sideboard

El encargo de Fer del 27-jul era cruzar la guía de ethanmtg contra su propio plan
(`meta/guia-sb.json`), matchup a matchup, y quedarse con lo que aporte.

- **12-ago**: cruzados mirror y Esper Goryo's.
- **5-sep**: cruzados los **14 restantes**. Los 16 matchups tienen ya su campo `patrones`.
- **6-sep**: actualizados los cuatro que el autor reescribió (Goryo's, Broodscale, Living End
  y Neoform). Cada uno arranca con una línea que dice qué cambió respecto a julio. Esper
  Blink **no** se añade a esta guía: es de la pestaña Guía, pero no aparece ni una vez en el
  censo de rivales de la liga (`scouting.csv`).

Dos avisos honestos de ese cruce:

- **Hollow One** no tiene sección en la guía (no está en el meta del autor). Su entrada lo
  dice explícitamente: ahí el plan es solo de Fer.
- **Grixis Reanimator** tampoco tiene sección propia; hereda la de Goryo's, que comparte
  esqueleto (reanimar barato y temprano). También queda marcado en la propia entrada.

**Lo que NO se toca del cruce**: los IN/OUT de Fer. Ya se comprobó el 12-ago que ethanmtg
juega otro banquillo (Soul-Guide Lantern, sin Consign/Crypt/Snare a 2), así que sus cambios
no son trasladables tal cual. Lo que migra son los **patrones de juego**, que no dependen de
la lista.

## Lo que dice la guía sobre decisiones abiertas del proyecto

Recogido aquí porque son las líneas que tocan pendientes de `estado.md`:

- **Mirror, Murktide vs Abhorrent Oculus**: el autor dice que "los sideboards de Prowess se
  están alejando de Murktide Regent". Su comparación: Oculus a 3 manas es más difícil de
  justificar que Murktide a 2 (y Murktide se come menos cementerio); Oculus es carta de
  late game y cuesta más combinarla con otro hechizo el mismo turno; **mejor que Murktide
  contra Archon of Cruelty y notablemente mala contra el Murktide del rival**. Su propia
  línea de prueba es 2 Oculus como plan de late game. No zanja la decisión de Fer, pero
  ordena el porqué.
- **Manabase**: la 2ª Fiery Islet le ha rendido mejor que la 10ª fetchland.
- **Mulligan** (el leak nº 1 de Fer, 53% con siete cartas vs 29% con mulligan): la guía tiene
  14 manos comentadas en la pestaña **Manos iniciales**. La regla que más se repite: mulligan
  a cualquier mano **sin interacción ni amenaza**, y a las que "necesitan demasiadas cosas"
  (amenazas *y* respuestas). Contra Yawgmoth y Amulet, criatura de 1 en el turno 1 o mulligan.
