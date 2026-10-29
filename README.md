# Participación · Northwood Worship

Página privada (con contraseña) que muestra cuántas veces ha servido cada persona en **voces, banda y sonido**, con filtros por equipo, tipo de evento (solo domingos o todos) y periodo.

- Se actualiza sola cada lunes temprano desde Planning Center (`.github/workflows/actualizar.yml`). También se puede correr a mano en **Actions → Actualizar participación → Run workflow**.
- Cada persona cuenta **una vez por evento**, aunque sirva en dos posiciones.
- La página se cifra con StaticCrypt antes de publicarse. **En este repositorio no se guarda ningún dato de personas**: solo el código.

## Configuración (una sola vez)

1. **Settings → Secrets and variables → Actions**: agregar `PCO_APP_ID`, `PCO_SECRET` (token de Planning Center) y `PORTAL_PASSWORD` (la contraseña de la página).
2. **Settings → Pages → Source: GitHub Actions**.

## Archivos

- `build.py`: lee Planning Center y genera la página (sin cifrar, solo dentro del runner).
- `template.html`: la página interactiva; los conteos se hacen en el navegador.
