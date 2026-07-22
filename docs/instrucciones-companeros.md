# Carga de datos: qué hace cada compañero

Cómo se da de alta a un compañero de la Liga y qué le pides que haga. La plantilla
que se les envía es [`Plantilla_Partidas_Liga.xlsx`](Plantilla_Partidas_Liga.xlsx)
(sus instrucciones van dentro, en la primera hoja).

## Lo que haces tú (Fer) por cada compañero, una sola vez

1. Pídele su **nick de MTGO** y pásamelo: lo doy de alta en
   [`../automation/jugadores.json`](../automation/jugadores.json). Sin ese alta, sus
   logs se ignoran (el automatismo solo procesa a los jugadores registrados).
2. En Drive, dentro de la carpeta **MTG · Izzet**, crea la subcarpeta
   **`Logs_<sunick>`** (con el nick exacto de MTGO) y compártela **solo con él**,
   como **Editor**. Así cada uno ve su carpeta y no las del resto.
3. Envíale la plantilla `Plantilla_Partidas_Liga.xlsx` y el mensaje de abajo.

## Mensaje para enviar (copiar y pegar, rellena lo que va entre <>)

---

Hola. Para llevar las estadísticas de la Liga necesito dos cosas tuyas después de
cada jornada. Son 5 minutos.

1) Tus logs de MTGO (si jugaste online):
- En tu PC, abre el Explorador de archivos y pega esto en la barra de arriba:
  %USERPROFILE%\AppData\Local\Apps\2.0\Data
- En el buscador de esa carpeta (arriba a la derecha) escribe: Match_GameLog
- Copia todos los ficheros que salgan a la carpeta de Drive que te he compartido
  (se llama Logs_<tunick>).
- No pasa nada por copiar ficheros repetidos: el sistema no duplica partidas.

2) El Excel que te he pasado (Plantilla_Partidas_Liga.xlsx):
- Una fila por partida, en la hoja "Partidas".
- Si la partida fue en MTGO y has subido los logs: rellena solo Fecha, Evento/Liga
  y Ronda. El resto lo saca el sistema de tus logs.
- Si fue en papel: rellena la fila entera.
- Pon tu nick de MTGO en "Reportado por".
- Al acabar, mándamelo o déjalo en tu carpeta de Drive.

La primera vez, dime tu nick exacto de MTGO para darte de alta.

---

## Por qué así

- **Los logs son la fuente buena**: el sistema saca de ellos rival, mazo, resultado,
  games, mulligans y salida/robo sin que nadie teclee. El Excel solo aporta lo que
  el log no sabe (qué Liga y qué ronda) y las partidas en papel.
- **Privacidad**: cada uno solo ve su carpeta. El automatismo descarta las partidas
  donde ese jugador no juega (espectadas o de otra persona en su cliente), y todo
  se deduplica por partida, así que nada cuenta dos veces.
