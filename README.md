# Partners Odoo España

Dashboard interactivo con los partners certificados de Odoo en España.  
Se actualiza automáticamente cada 4 horas mediante GitHub Actions.

## Dashboard

👉 **[Ver dashboard](https://andresmartoscano.github.io/partners-odoo/)**

## Datos

- Fuente: [odoo.com/es_ES/partners/country/spain-67](https://www.odoo.com/es_ES/partners/country/spain-67)
- Actualización: cada 4 horas
- Contenido: nivel, referencias, retención, expertos certificados y listado de clientes por partner

## Pestañas

1. **Listado de Partners** — tabla ordenable y filtrable con export CSV/Excel
2. **Referencias por Partner** — desglose sectorial y clientes de cada partner
3. **Clientes** — búsqueda inversa cliente → partner
4. **Posibles duplicados** — referencias posiblemente duplicadas dentro de cada partner
5. **Cambios de partner** — historial de clientes que cambian de partner (fecha orientativa; se detecta comparando snapshots sucesivos, historial en `scraper/changes.json`)

Ver `HANDOFF.md` para arquitectura, flujo de trabajo y pitfalls conocidos.

## Actualización manual

Actions → "Update Partner Dashboard" → Run workflow
