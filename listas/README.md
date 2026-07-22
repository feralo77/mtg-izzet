# Listas de los jugadores

Aquí vive la **lista real y completa de 75 cartas** de cada jugador, para poder
compararlas carta a carta. Los logs de MTGO solo enseñan las cartas que
aparecieron en juego, nunca el mazo entero — por eso hace falta que cada jugador
deje aquí su lista.

## Cómo añadir una lista

1. Abre tu mazo en MTGO / Arena / mtggoldfish y dale a **Export** (o cópialo).
2. Crea un fichero de texto con el **nick del jugador** como nombre:
   `feralo77.txt`, `4c_PolG.txt`, `Inkmaster.txt`.
3. Pega dentro el export tal cual. Formato (una carta por línea):

   ```
   # feralo77 — La 75 Definitiva      ← opcional: la 1ª línea con # es el título
   4 Monastery Swiftspear
   4 Dragon's Rage Channeler
   ...
   3 Mountain

   Sideboard
   4 Consign to Memory
   ...
   ```

Vale cualquiera de estos formatos para separar el sideboard:
- una línea con `Sideboard` (o `SB`),
- líneas que empiecen por `SB:` (ej. `SB: 2 Tormod's Crypt`),
- o simplemente **una línea en blanco** entre el mazo principal y el sideboard.

Se ignoran las líneas que empiezan por `#` (comentarios) y los sufijos de edición
que meten algunos exports (`4 Monastery Swiftspear (MID) 143` cuenta igual).

## Qué pasa después

El script `scripts/comparar_listas.mjs` lee todas las listas de esta carpeta y
genera `listas/comparativa.json`: la comparación carta a carta entre jugadores,
frente a **La 75 Definitiva** (`meta/mi-75.json`) y frente al **consenso del meta**
(`meta/prowess.json`). El dashboard lo muestra en la pestaña **Listas**.

Para regenerar la comparación tras añadir o cambiar una lista:

```
node scripts/comparar_listas.mjs --date AAAA-MM-DD
```

> La lista de referencia (contra la que se calculan las diferencias) es la 75 de
> Fer en `meta/mi-75.json`, no un fichero de esta carpeta. `feralo77.txt` está aquí
> como ejemplo y para que aparezca en el comparador junto al resto.
