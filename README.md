# Equipo de alabanza · Northwood Worship

Página privada (con contraseña) del liderazgo del equipo de alabanza, con tres pestañas:

- **Participación**: cuántas veces ha servido cada persona en **voces, banda y sonido**, con filtros por equipo, tipo de evento (solo domingos o todos) y periodo. Cada persona cuenta **una vez por evento**, aunque sirva en dos posiciones.
- **Disponibilidad**: los blockout dates de quienes tienen una posición en voces, banda o sonido (calendario por mes, por persona, eventos, "¿Quién está disponible?" y próximas ausencias). No se muestran los motivos.
- **Armar voces**: escoger fecha y voz líder, y armar las voces (5 o 6) buscando balance de rango vocal, armonización, desarrollo vocal y presencia escénica. Los niveles se leen de **tags de persona en Planning Center Services**, en cuatro grupos de tags:
  - Rango Vocal: Bajo, Barítono, Tenor, Alto, Mezzo-Soprano, Soprano
  - Desarrollo Vocal: Bajo, Medio, Alto
  - Armonización: 1ra, +2da, +3ra
  - Presencia Escénica: Bajo, Medio, Alto

Se actualiza sola **cada mañana** desde Planning Center (`.github/workflows/actualizar.yml`). También se puede correr a mano en **Actions → Actualizar participación → Run workflow**.

La página se cifra con StaticCrypt antes de publicarse. **En este repositorio no se guarda ningún dato de personas**: solo el código.

## Configuración (una sola vez)

1. **Settings → Secrets and variables → Actions**: agregar `PCO_APP_ID`, `PCO_SECRET` (token de Planning Center) y `PORTAL_PASSWORD` (la contraseña de la página).
2. **Settings → Pages → Source: GitHub Actions**.

## Archivos

- `build.py`: lee Planning Center (y los eventos del Calendario de Eventos) y genera la página (sin cifrar, solo dentro del runner).
- `template.html`: la página interactiva; los conteos, el calendario y el armado de voces se hacen en el navegador.
