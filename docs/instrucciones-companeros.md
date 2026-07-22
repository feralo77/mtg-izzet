# Carga de datos: alta y rutina de cada compañero

Cómo se da de alta a un compañero de la Liga y qué hace él después de cada jornada.
El alta la ejecuta el orquestador (proceso en `HQ/proyectos/mtg-izzet/operaciones/alta-jugador.md`);
aquí queda lo esencial para entender el sistema.

## El alta (una sola vez por jugador)

1. Fer consigue su **nick exacto de MTGO** y su mail.
2. El orquestador crea en Drive (carpeta "MTG · Izzet") la subcarpeta **`Logs_<nick>`** con la
   hoja **"Partidas — <nick>"** dentro (columnas: Fecha, Evento / Liga, Ronda, Lista, **Rival**
   —el nick de MTGO del oponente—, **Mazo rival** y Notas), y registra el nick en
   [`../automation/jugadores.json`](../automation/jugadores.json)
   — sin ese registro, el robot ignora la carpeta.
3. Fer comparte `Logs_<nick>` con el mail del jugador como **Editor** (un solo share cubre la
   carpeta y la hoja) y le reenvía el mensaje de bienvenida (plantilla en la operación de alta).

## La rutina del jugador (5 min por jornada)

1. **Subir sus logs**: copiar los ficheros `Match_GameLog*.dat` de su PC
   (`%USERPROFILE%\AppData\Local\Apps\2.0\Data`) a su carpeta `Logs_<nick>` del Drive.
   Repetir ficheros no pasa nada: todo se deduplica por partida.
2. **Apuntar por partida** en su hoja "Partidas — <nick>": Fecha, Liga, Ronda y el **Rival**
   (su nick exacto de MTGO — con él el robot cuelga el apunte de la partida correcta aunque ese
   día haya jugado varias). El resto (resultado, marcador, salida/robo, mulligans) lo saca el
   robot de los logs.
   - "Rival" = el NICK del oponente; "Mazo rival" = el nombre de su mazo (opcional: si se deja
     vacío, el robot pone el arquetipo que detecta por las cartas).
   - Partida en papel (sin log): apuntarla igual con `papel: resultado X-Y contra <mazo>` en
     Notas; saldrá marcada para revisión manual. (La plantilla completa
     [`Plantilla_Partidas_Liga.xlsx`](Plantilla_Partidas_Liga.xlsx) queda de reserva por si el
     papel se vuelve frecuente.)

## Por qué así

- **Los logs son la fuente buena**: nadie teclea resultados. La hoja solo aporta lo que el log
  no sabe (qué Liga y qué ronda).
- **Privacidad**: cada jugador solo ve su carpeta. El robot descarta las partidas donde su nick
  no juega (espectadas o de otra persona en su cliente) y todo se deduplica por partida.
- **Su hoja no se publica**: la lee el robot en privado con su cuenta de servicio.
