# NW HQ · Northwood Worship

Página privada (con contraseña) del liderazgo del equipo de alabanza, con tres pestañas:

- **Participación**: cuántas veces ha servido cada persona en **voces, banda y sonido**, con filtros por equipo, tipo de evento (solo domingos o todos) y periodo. Cada persona cuenta **una vez por evento**, aunque sirva en dos posiciones.
- **Disponibilidad**: los blockout dates de quienes tienen una posición en voces, banda o sonido (calendario por mes, por persona, eventos, "¿Quién está disponible?" y próximas ausencias). No se muestran los motivos.
- **Plan del mes**: matriz de voces × domingos del mes para armar todas las semanas a la vez. La meta es que cada voz sirva 2 veces (0–1 en blanco, 2 en teal, 3 en naranja, 4 o más en rojo). Comparte los equipos con Armar voces.
- **Armar voces**: escoger fecha y voz líder, y armar las voces (5 o 6) buscando balance de rango vocal, armonización, desarrollo vocal y presencia escénica. Solo cuentan las voces con su tag de Vocals - Range (las voces invitadas quedan fuera). Los niveles se leen de **tags de persona en Planning Center Services**:
  - Vocals - Range: Bass, Baritone, Tenor, Alto, Mezzo Soprano, Soprano
  - Vocals - Level: In Progress, Good, Strong
  - Vocals - Stage Presence: In Progress, Good, Strong
  - Vocals - Harmony (selección múltiple): First, Second, Third

Se actualiza sola **cada mañana** desde Planning Center (`.github/workflows/actualizar.yml`). También se puede correr a mano en **Actions → Actualizar participación → Run workflow**.

La página se cifra con StaticCrypt antes de publicarse. **En este repositorio no se guarda ningún dato de personas**: solo el código.

## Configuración (una sola vez)

1. **Settings → Secrets and variables → Actions**: agregar `PCO_APP_ID`, `PCO_SECRET` (token de Planning Center) y `PORTAL_PASSWORD` (la contraseña de la página).
2. **Settings → Pages → Source: GitHub Actions**.

## Archivos

- `build.py`: lee Planning Center (y los eventos del Calendario de Eventos) y genera la página (sin cifrar, solo dentro del runner).
- `template.html`: la página interactiva; los conteos, el calendario y el armado de voces se hacen en el navegador.
