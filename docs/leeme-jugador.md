# Plantilla: LEEME de la carpeta de cada jugador

> Al dar de alta a un jugador (operación `alta-jugador.md` en HQ), se crea en su carpeta
> `Logs_<NICK>` un Google Doc llamado **"LEEME — empieza aquí (<NICK>)"** con este texto,
> sustituyendo `<NICK>` por su nick de MTGO. Es lo primero que ve al abrir su carpeta.

---

```
LEEME — EMPIEZA AQUÍ (carpeta Logs_<NICK>)
Actualizado: <FECHA>

QUÉ ES ESTO
Esta carpeta conecta tus partidas de Magic Online con el dashboard de la liga:
https://feralo77.github.io/mtg-izzet/
Un robot la lee cada mañana (~08:00). Nadie teclea resultados: salen solos de tus
logs. Tú solo subes ficheros y apuntas en qué liga y ronda jugaste cada partida.

TU RUTINA DESPUÉS DE JUGAR (5 MINUTOS)

1) SUBE TUS LOGS
   En tu PC (Windows), los logs de MTGO están en esta ruta:
   C:\Users\TU_USUARIO\AppData\Local\Apps\2.0\Data
   (pégala en la barra del Explorador de Windows y busca "Match_GameLog";
   ordena por fecha y copia los del día)
   Copia esos ficheros a ESTA carpeta de Drive.
   Repetir ficheros no pasa nada: ninguna partida se duplica.

2) APUNTA CADA PARTIDA en la hoja "Partidas — <NICK>" (está en esta carpeta)
   Una fila por partida, con estas columnas:
   - Fecha ............ 22/07/2026
   - Evento / Liga .... Liga 5
   - Ronda ............ 3
   - Lista ............ el nombre de tu mazo (o de la versión que juegues)
   - Rival ............ el NICK EXACTO de tu oponente en MTGO (con él, el robot
                        casa tu apunte con la partida correcta aunque juegues
                        varias ese día)
   - Mazo rival ....... opcional: si lo dejas vacío, el robot detecta su mazo
                        por las cartas que le viste
   - Notas ............ lo que quieras
   La primera fila es un EJEMPLO: bórrala cuando apuntes la primera de verdad.
   ¿Partida en papel (sin MTGO)? Apúntala igual y en Notas: "papel: 2-1 contra <mazo>".

QUÉ OBTIENES
Tus estadísticas en el dashboard (elige tu nick en el filtro de arriba a la derecha):
win rate por mazo rival, salida vs robo, manos iniciales, mulligans, duración de tus
games... y el scouting compartido de rivales de toda la liga.

PRIVACIDAD
- Esta carpeta solo la veis tú, Fer y el robot (que solo LEE, nunca escribe aquí).
- Tu hoja de apuntes no se publica: al dashboard solo llegan resultados y mazos.
- El robot descarta partidas donde tu nick no juega (espectadas o de otra persona).

Dudas: Fer (feralo77).
```
