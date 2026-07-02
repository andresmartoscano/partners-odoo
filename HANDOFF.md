# Handoff — Partners Odoo España

Documento de traspaso del dashboard de partners certificados de Odoo en España.
Resume qué es, cómo funciona y cómo trabajar sobre él sin romperlo.

## Qué es

Dashboard HTML de una sola página con los **89 partners** de Odoo en España,
auto-actualizado y desplegado en GitHub Pages.

- **Web pública:** https://andresmartoscano.github.io/partners-odoo/
- **Repo:** https://github.com/andresmartoscano/partners-odoo
- **Fuente de datos:** páginas públicas de odoo.com (sin autenticación).

### Las cinco pestañas

| Pestaña | Contenido |
|---|---|
| **Listado de Partners** | Tabla de los partners: nivel, referencias, retención, proyecto medio/grande, expertos certificados, sectores. Ordenable, filtrable por nivel, con búsqueda. Botón **Exportar ▾** (CSV / Excel .xlsx). |
| **Referencias por Partner** | Panel dividido. Al seleccionar un partner: desglose por sector + listado completo de sus clientes (nombre y sector) con buscador. Exporta CSV. |
| **Clientes** | Búsqueda inversa: todos los clientes con su partner asociado. Mismo botón Exportar y enlaces con hover que el Listado. |
| **Posibles duplicados** | Referencias posiblemente duplicadas dentro de cada partner (contención de nombres o similitud Jaro-Winkler ≥ 90 %). Solo JS, no toca el scraper. |
| **Cambios de partner** | Historial de clientes que cambian de partner, detectado comparando snapshots sucesivos del scraper. Fecha orientativa (cuándo se detectó). |

## Arquitectura

```
github/
├── index.html                   ← dashboard generado (lo sirve GitHub Pages)
├── scraper/
│   ├── scraper.py               ← scraper de odoo.com
│   ├── template.html            ← index.html con placeholders de datos
│   ├── partner_changes.py       ← lógica de diff de cambios de partner
│   ├── backfill_changes.py      ← reconstruye changes.json desde git (idempotente)
│   ├── changes.json             ← historial persistente de cambios de partner
│   └── requirements.txt
├── .github/workflows/update.yml ← GitHub Action cada 4 h
├── README.md
└── HANDOFF.md                   ← este documento
```

### Cómo se generan los datos

1. **`scraper.py`** trabaja en dos fases:
   - **Listado:** pagina `odoo.com/es_ES/partners/country/spain-67`. Cada tarjeta
     ya trae todos los stats numéricos (nivel, retención, usuarios, referencias,
     expertos) → se leen ahí. Los partners se localizan por el anchor
     `aria-label="Ir al distribuidor"`.
   - **Detalle:** visita la página de cada partner solo para la **lista de
     clientes** (anchors `/es_ES/customers/...`) y los **sectores del partner**.
2. **Cambios de partner:** antes de sobreescribir `index.html`, `update_changes()`
   extrae el REFS del index anterior, lo diffea contra los datos nuevos
   (cliente que desaparece del partner A y aparece en B = cambio; altas y bajas
   puras no cuentan) y acumula los cambios en `scraper/changes.json`.
3. Rellena `template.html` (placeholders `__PARTNERS_DATA__`, `__REFS_DATA__` y
   `__CHANGES_DATA__`) y escribe `index.html`.

### Actualización automática

`.github/workflows/update.yml` ejecuta el scraper **cada 4 horas**
(`cron: '0 */4 * * *'`) y hace commit/push de `index.html` y
`scraper/changes.json` **solo si el scraper termina con éxito**
(`if: steps.scraper.outcome == 'success'`). También se puede lanzar a mano:
Actions → "Update Partner Dashboard" → Run workflow.

## Cómo hacer cambios sin romper nada

> ⚠️ **`index.html` y `scraper/template.html` deben mantenerse en SYNC.**
> El template es `index.html` con los bloques de datos sustituidos por
> placeholders. Si cambias UI o JS, hazlo en `index.html` y **regenera el
> template** (sustituye `const PARTNERS = [...]` por `__PARTNERS_DATA__`,
> `const REFS={...}` por `__REFS_DATA__` y `const CHANGES=[...]` por
> `__CHANGES_DATA__`). Si solo tocas el template, el próximo run del scraper
> sobrescribe `index.html` y se pierden tus cambios.

### Cambios de UI / JS
1. `git pull` (la Action commitea cada 4 h — no trabajes sobre datos viejos).
2. Edita `index.html`.
3. **Valida el JavaScript antes de publicar** (ver pitfalls). Un solo error de
   sintaxis deja la web entera en blanco.
4. Regenera `template.html` desde el `index.html` actualizado.
5. `git add index.html scraper/template.html && git commit && git pull --no-edit && git push`.

### Regenerar datos a mano
```bash
cd scraper
python scraper.py        # ~4-6 min (delays anti-rate-limit)
```
Luego valida y commitea `index.html` + `scraper/changes.json` (+ `scraper.py`
si lo cambiaste).

## Pitfalls conocidos (ya resueltos — no reintroducir)

1. **Web en blanco por error de JS.** Un `});` huérfano de código muerto rompía
   el `<script>` entero → tablas vacías y botones muertos. **Siempre valida el JS
   antes de publicar.** No hay Node en el equipo; usar el parser de Python:
   ```bash
   pip install esprima
   ```
   esprima no soporta `??` ni `?.` (el código sí los usa y los navegadores
   también) — para validar la estructura, neutralízalos antes: `?.[`→`[`,
   `?.`→`.`, `??`→`||`, y luego `esprima.parseScript(js)`.

2. **Datos basura del scraper.** El regex de slugs capturaba enlaces de filtro
   (`/partners/country/`, `/partners/grade/`) en vez de partners → 171 entradas
   vacías. Resuelto usando los anchors `aria-label="Ir al distribuidor"`.

3. **Off-by-one en referencias.** Antes se extraían los clientes desde los logos
   (`avatar_128`); un cliente sin logo se perdía. Resuelto extrayendo desde los
   anchors `/es_ES/customers/...`. El sector de cliente se distingue del sector
   del partner por el modificador de clase `ms-1`.

4. **El scraper sobrescribe el index.html bueno.** Si el template está
   desactualizado, el run automático regenera un `index.html` sin tus mejoras.
   Mantén el template en sync (ver arriba).

5. **Falsos positivos en cambios de partner.** Un fallo de scrapeo de la página
   de un partner solo produce bajas o altas puras (nunca el par baja+alta que
   define un cambio), así que no genera falsos movimientos. Además, un snapshot
   con menos de 30 partners en REFS se descarta sin diffear
   (`MIN_PARTNERS_FOR_DIFF`).

## Estado actual (jul 2026)

- 89 partners con datos embebidos (≈9 Gold / 33 Silver / resto Ready).
- 5 pestañas operativas; historial de cambios de partner con backfill desde el
  26 jun 2026 (4 cambios iniciales).
- Auto-actualización cada 4 h operativa (commitea index.html + changes.json).
