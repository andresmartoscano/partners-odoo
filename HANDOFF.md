# Handoff — Partners Odoo España

Documento de traspaso del dashboard de partners certificados de Odoo en España.
Resume qué es, cómo funciona y cómo trabajar sobre él sin romperlo.

## Qué es

Dashboard HTML de una sola página con los **90 partners** de Odoo en España,
auto-actualizado y desplegado en GitHub Pages.

- **Web pública:** https://andresmartoscano.github.io/partners-odoo/
- **Repo:** https://github.com/andresmartoscano/partners-odoo
- **Fuente de datos:** páginas públicas de odoo.com (sin autenticación).

### Las tres pestañas

| Pestaña | Contenido |
|---|---|
| **Listado de Partners** | Tabla de los 90 partners: nivel, referencias, retención, proyecto medio/grande, expertos certificados, sectores. Ordenable, filtrable por nivel, con búsqueda. Botón **Exportar ▾** (CSV / Excel .xlsx). |
| **Referencias por Partner** | Panel dividido. Al seleccionar un partner: desglose por sector + listado completo de sus clientes (nombre y sector) con buscador. Exporta CSV. |
| **Clientes** | Búsqueda inversa: todos los clientes con su partner asociado. Mismo botón Exportar y enlaces con hover que el Listado. |

## Arquitectura

```
github/
├── index.html                  ← dashboard generado (lo sirve GitHub Pages)
├── scraper/
│   ├── scraper.py              ← scraper de odoo.com
│   ├── template.html           ← index.html con placeholders de datos
│   └── requirements.txt
├── .github/workflows/update.yml ← GitHub Action cada 4 h
├── README.md
└── HANDOFF.md                  ← este documento
```

### Cómo se generan los datos

1. **`scraper.py`** trabaja en dos fases:
   - **Listado:** pagina `odoo.com/es_ES/partners/country/spain-67`. Cada tarjeta
     ya trae todos los stats numéricos (nivel, retención, usuarios, referencias,
     expertos) → se leen ahí. Los partners se localizan por el anchor
     `aria-label="Ir al distribuidor"`.
   - **Detalle:** visita la página de cada partner solo para la **lista de
     clientes** (anchors `/es_ES/customers/...`) y los **sectores del partner**.
2. Rellena `template.html` (placeholders `__PARTNERS_DATA__` y `__REFS_DATA__`)
   y escribe `index.html`.

### Actualización automática

`.github/workflows/update.yml` ejecuta el scraper **cada 4 horas**
(`cron: '0 */4 * * *'`) y hace commit/push de `index.html` **solo si el scraper
termina con éxito** (`if: steps.scraper.outcome == 'success'`) **y solo si
`index.html` cambió** (`git diff --cached --quiet || git commit`). Por eso puede
haber horas sin commits aunque la Action corra: significa que no hubo cambios de
datos. También se puede lanzar a mano: Actions → "Update Partner Dashboard" → Run
workflow.

> 🩺 **Diagnosticar la Action sin `gh`.** `gh` no está instalado y
> `gh auth login` es interactivo (no se puede lanzar desde un shell no
> interactivo). El repo es **público**, así que basta la API REST pública:
> ```bash
> curl -s "https://api.github.com/repos/andresmartoscano/partners-odoo/actions/runs?per_page=15"
> ```
> Mira `status`/`conclusion`/`event`/`created_at`. "Sin commits recientes" NO
> equivale a "Action rota": puede ser simplemente que no hubo cambios de datos.

> 📸 **Artifact ≠ web.** La **web** (GitHub Pages) se auto-actualiza vía Action.
> El **Artifact** es una foto manual: solo cambia cuando se republica a mano. No
> uses el Artifact para consultar cifras al día (envejece); es el entorno de
> pruebas de diseño/UX. Antes de publicar el Artifact, `git pull` para no
> retratar datos viejos.

## Cómo hacer cambios sin romper nada

> 🔄 **PRIMERO: `git pull`.** La Action auto-commitea a `main` cada 4h
> ("chore: update partners data"), así que tu clon local envejece solo. Empieza
> SIEMPRE con `git fetch origin && git log --oneline HEAD..origin/main`; si estás
> detrás, `git pull` (o `git reset --hard origin/main` si tienes basura local).
> Editar/publicar sin actualizar = trabajar sobre datos viejos y arriesgar un
> merge sucio o pushear cifras obsoletas.

> ⚠️ **`index.html` y `scraper/template.html` deben mantenerse en SYNC.**
> El template es `index.html` con los bloques de datos sustituidos por
> placeholders. Si cambias UI o JS, hazlo en `index.html` y **regenera el
> template** (sustituye `const PARTNERS = [...]` por `__PARTNERS_DATA__` y
> `const REFS={...}` por `__REFS_DATA__`). Si solo tocas el template, el próximo
> run del scraper sobrescribe `index.html` y se pierden tus cambios.

### Cambios de UI / JS
1. Edita `index.html`.
2. **Valida el JavaScript antes de publicar** (ver pitfalls). Un solo error de
   sintaxis deja la web entera en blanco.
3. Regenera `template.html` desde el `index.html` actualizado.
4. **Publica primero en el Artifact privado para revisión** (NO hacer push aún).
   El Artifact es privado (solo lo ve el usuario) y hace de **entorno de pruebas**
   — no hay otro. URL fija del proyecto:
   `https://claude.ai/code/artifact/9c0ff10d-008d-4313-b835-f948dbf0c6c2`
   (republicar siempre sobre esa misma URL, no crear enlaces nuevos).
5. **Espera el OK del usuario.** Solo cuando confirme que se ve bien:
   `git add index.html scraper/template.html && git commit && git pull --no-edit && git push`
   → GitHub Pages es **público**, por eso el push va siempre después de la
   aprobación en el Artifact.

### Regenerar datos a mano
```bash
cd scraper
python scraper.py        # ~4-6 min (delays anti-rate-limit)
```
Luego valida y commitea `index.html` (+ `scraper.py` si lo cambiaste).

## Pitfalls conocidos (ya resueltos — no reintroducir)

1. **Web en blanco por error de JS.** Un `});` huérfano de código muerto rompía
   el `<script>` entero → tablas vacías y botones muertos. **Siempre valida el JS
   antes de publicar.** No hay Node en el equipo; usar el parser de Python:
   ```bash
   pip install esprima
   ```
   esprima no soporta `??` ni `?.` (el código sí los usa y los navegadores
   también) — para validar la estructura, neutralízalos antes: `?.[`→`  [`,
   `?.`→`. `, `??`→`||`, y luego `esprima.parseScript(js)`.

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

## Estado actual (jun 2026)

- 90 partners · 9 Gold / 33 Silver / 48 Ready.
- 0 discrepancias entre el contador de referencias y la lista mostrada.
- Auto-actualización cada 4 h operativa.
