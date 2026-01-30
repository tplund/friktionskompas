# Friktionskompasset - Claude Code Notes

## Tilgængelige MCP Servere

### Global (alle projekter)
- **github** - Git/GitHub integration (PRs, issues, commits)
- **fetch** - Web fetching og API kald

### Projekt-specifik
- **friktionskompas** - Custom MCP server til projektets API
- **gtm-mcp-server** - Google Tag Manager integration (Stape)

---

## VIGTIGT: Projekt Regler

### TODO-Liste Disciplin (KRITISK!)
- **ALTID** tilføj nye instrukser/opgaver til TODO-listen MED DET SAMME - også midt i en anden opgave
- **ALDRIG** start på en opgave uden at den er på TODO-listen først
- **ALTID** marker opgaver som in_progress før du begynder
- **ALTID** marker opgaver som completed straks de er færdige
- Nye instrukser fra brugeren har højere prioritet end at færdiggøre nuværende opgave
- Ved nye instrukser: Tilføj til TODO → Fortsæt med nuværende opgave ELLER skift til ny opgave

### Dokumentation af Beslutninger (KRITISK!)
- **ALTID** dokumenter vigtige arkitektur-beslutninger i CLAUDE.md MED DET SAMME
- **ALTID** dokumenter refactorings der IKKE må rulles tilbage (fx campaign → assessment)
- **ALTID** dokumenter instrukser der gælder på tværs af sessioner
- Ved store ændringer: Beskriv HVORFOR beslutningen blev taget
- Sessioner kan kollapses/glemmes - CLAUDE.md er den permanente hukommelse
- **UNDGÅ** at rulle ændringer tilbage uden at tjekke CLAUDE.md først!

---

## 🚨 KRITISK: GIT RESET OG DATABASE SIKKERHED

### ALDRIG brug `git reset --hard` uden at beskytte databasen først!

**Hændelse 2025-12-27:** `git reset --hard` overskrev databasen med en gammel version og vi mistede testdata. Databasen ER i git history!

### Sikker rollback procedure:

```bash
# 1. FØRST: Kopier databasen væk
copy friktionskompas_v3.db friktionskompas_v3_BACKUP.db

# 2. Derefter kan du reset
git reset --hard <commit>

# 3. Gendan databasen
copy friktionskompas_v3_BACKUP.db friktionskompas_v3.db
del friktionskompas_v3_BACKUP.db

# 4. Kør migration hvis nødvendigt
python -c "from db_hierarchical import init_db; init_db()"
```

### Alternativ: Brug checkout i stedet for reset

```bash
# Gendan specifikke filer UDEN at røre databasen
git checkout <commit> -- admin_app.py templates/
```

### Hvis data går tabt - regenerer med seed scripts:

```bash
python seed_herning_testdata.py
python seed_esbjerg_canonical.py
```

---

## ⛔ BESLUTNINGS-TJEKLISTE - TJEK INDEN DU STARTER!

Før du laver ændringer i følgende områder, TJEK denne liste:

### 1. Database kolonne-navne
- ✅ **responses.assessment_id** - IKKE campaign_id (refactored)
- ✅ **tokens.assessment_id** - IKKE campaign_id (refactored)
- ✅ **assessments** tabel - IKKE campaigns (refactored)

### 2. Field navne i profil-spørgsmål
- ✅ **KAN** - IKKE MULIGHED (database bruger KAN)
- ✅ Field order: `['TRYGHED', 'MENING', 'KAN', 'BESVÆR']`

### 3. Terminologi i UI
- ✅ Brug "måling" - IKKE "kampagne"
- ✅ Brug "analyse" - IKKE "rapport"
- ✅ Brug "assessment" i kode - IKKE "campaign"

### 4. Arkitektur
- ✅ Database: SQLite med persistent disk på Render `/var/data/`
- ✅ Auth: Session-based med Flask-Login
- ✅ Oversættelser: Database-based (translations table)
- ✅ Logging: Centraliseret struktureret logging (JSON format)
- ✅ **Flask App Factory Pattern** (implementeret 2025-12-22)

### 5. 7-Point Likert Skala (KRITISK!)
Systemet bruger **7-point Likert skala** (1-7), IKKE 5-point!

**Farve-thresholds i templates:**
- **RØD (krise):** `score < 3.5` (under 50%)
- **GUL (advarsel):** `score >= 3.5 AND score < 4.9` (50-70%)
- **GRØN (god):** `score >= 4.9` (over 70%)

**Reverse scoring formel:**
```python
adjusted_score = 8 - raw_score  # IKKE 6 - raw_score!
```

**Bar-bredde beregning:**
```javascript
width = ((score - 1) / 6 * 100) + '%'  // IKKE score/5*100!
```

**Gap thresholds:**
- Signifikant gap: `> 1.4` points
- Moderat gap: `> 0.84` points

### 6. Cross-Customer Data Isolation (KRITISK!)
Når queries bruger `full_path LIKE` til at aggregere børne-enheder, SKAL der også filtreres på `customer_id`:

**FORKERT:**
```sql
LEFT JOIN organizational_units children ON children.full_path LIKE ou.full_path || '%'
```

**KORREKT:**
```sql
LEFT JOIN organizational_units children ON children.full_path LIKE ou.full_path || '%' AND children.customer_id = ou.customer_id
```

**Hvorfor:** Enheder fra forskellige kunder kan have samme `full_path` (fx "Social- og Sundhedsforvaltningen" i både Herning og Esbjerg). Uden `customer_id` filter vil data blandes på tværs af kunder.

---

## Flask App Factory Pattern (2025-12-22)

**Beslutning:** Implementeret Flask app factory pattern for bedre testbarhed og konfiguration.

### Struktur
- **app_factory.py**: Central factory funktion `create_app(config_name)`
  - Config modes: 'development', 'testing', 'production'
  - Håndterer database initialization, extensions, blueprints, middleware
- **admin_app.py**: Bruger factory til at skabe app instance
  - Automatisk miljø-detektion (production hvis `/var/data` eksisterer)
  - Registrerer legacy routes (som ikke er i blueprints endnu)

### Konfigurationsmodes
```python
# Development (default lokalt)
app = create_app('development')  # Debug=True, rate limiting enabled

# Testing (pytest)
app = create_app('testing')  # Debug=False, CSRF disabled, rate limiting disabled

# Production (Render)
app = create_app('production')  # Debug=False, seed database, fuld sikkerhed
```

### Tests
- `tests/conftest.py` importerer `admin_app.app` (som bruger factory)
- Tests får automatisk korrekt miljø via `os.environ['TESTING'] = 'true'`
- Alle 461 tests kører korrekt med factory pattern

### Miljø-detektion
Admin_app.py detekterer automatisk miljø:
```python
if os.path.exists('/var/data'):
    app = create_app('production')  # Render
elif os.environ.get('TESTING', '').lower() == 'true':
    app = create_app('testing')     # Pytest
else:
    app = create_app('development')  # Lokal udvikling
```

### Hvad er flyttet til factory
- Flask app creation og config
- Extension initialization (CSRF, rate limiting, CORS, OAuth)
- Blueprint registration
- Middleware (domain detection, security headers)
- Context processors (translations, customers, helpers)
- Error handlers (CSRF, 404, 500)

### Bagudkompatibilitet
- Eksisterende imports virker stadig: `from admin_app import app`
- Routes i admin_app.py registreres automatisk
- Deployment kræver ingen ændringer

### Fremtidige migreringer
Legacy routes i admin_app.py bør gradvist flyttes til blueprints:
- `/admin/my-account` → `blueprints.admin_core`
- `/help` → `blueprints.public`
- `/user` → `blueprints.auth`
- osv.

---

## Struktureret Logging (2025-12-22)

### Arkitektur
Projektet bruger centraliseret struktureret logging via `logging_config.py`:

**Features:**
- JSON formattering for strukturerede logs (production)
- Farvet console output (development)
- Automatisk log rotation (10MB filer, 5 backups)
- Separate log filer: `app.log`, `error.log`, `security.log`
- Request logging middleware med timing
- Automatisk sanitering af sensitive data (passwords, tokens, etc.)
- Context-aware logging (inkluderer request info hvor relevant)

**Log levels:**
- DEBUG: Detaljeret debugging info
- INFO: Normale operationer (requests, database queries)
- WARNING: Potentielle problemer
- ERROR: Fejl der ikke stopper applikationen
- CRITICAL: Alvorlige fejl

**Brug:**
```python
from logging_config import get_logger, log_security_event

logger = get_logger(__name__)

# Normal logging
logger.info("User logged in", extra={'extra_data': {
    'user_id': user_id,
    'email': email
}})

# Security events
log_security_event(logger, 'login_failed', {
    'email': email,
    'ip': request.remote_addr
})

# Error logging with exception
try:
    # code
except Exception as e:
    logger.error("Operation failed", exc_info=True, extra={'extra_data': {
        'context': 'value'
    }})
```

**Log locations:**
- Production (Render): `/var/data/logs/`
- Development: `./logs/`

**Environment variable:**
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)

**VIGTIGT:**
- **ALDRIG** brug `print()` - brug altid `logger.info()`, `logger.error()`, etc.
- Inkluder context via `extra={'extra_data': {...}}` for struktureret søgning
- Sensitive data (passwords, tokens) bliver automatisk saniteret
- Request logging sker automatisk via middleware

---

### Selvstændighed - Gør ting selv når muligt!
- **ALTID** tjek CLAUDE.md for eksisterende API keys/credentials FØR du spørger brugeren
- **ALTID** gem API keys og credentials i CLAUDE.md når brugeren giver dem
- **ALTID** tjek om der findes API endpoints du kan kalde direkte i stedet for at bede brugeren gøre det
- **ALTID** tjek hvilke MCP servers der er tilgængelige før du siger du ikke har adgang
- Brug `curl` til at kalde endpoints på Render efter deployment
- Seed endpoints accepterer GET requests så de kan kaldes via curl
- **Tilgængelige seed endpoints på Render:**
  - `curl https://friktionskompasset.dk/admin/seed-domains` - Seed/opdater domæner
  - `curl https://friktionskompasset.dk/admin/seed-translations` - Seed oversættelser
- Render MCP kan bruges til at opdatere environment variables direkte
- Tjek altid logs og status via MCP før du spørger brugeren

---

## 🔧 Infrastruktur API'er og Adgang

Disse API'er kan bruges direkte fra Claude Code sessioner til at administrere infrastruktur.

### Render (Hosting)
**API Key:** `rnd_3MflEFHakX6sYZVIXxICAti0v5pZ`
**Service ID:** `srv-d4q8t8k9c44c73b8ut60` (friktionskompas-eu)

**Hvad kan jeg gøre:**
- ✅ Liste services og deployments
- ✅ Trigger deploy/restart
- ✅ Læse/skrive environment variables
- ✅ Se logs
- ✅ Tjekke deploy status

```bash
# Liste services
curl -s "https://api.render.com/v1/services" \
  -H "Authorization: Bearer rnd_3MflEFHakX6sYZVIXxICAti0v5pZ"

# Sæt environment variable
curl -s -X PUT "https://api.render.com/v1/services/srv-d4q8t8k9c44c73b8ut60/env-vars/VAR_NAME" \
  -H "Authorization: Bearer rnd_3MflEFHakX6sYZVIXxICAti0v5pZ" \
  -H "Content-Type: application/json" \
  -d '{"value": "VAR_VALUE"}'

# Trigger deploy
curl -s -X POST "https://api.render.com/v1/services/srv-d4q8t8k9c44c73b8ut60/deploys" \
  -H "Authorization: Bearer rnd_3MflEFHakX6sYZVIXxICAti0v5pZ" \
  -H "Content-Type: application/json" \
  -d '{"clearCache": "do_not_clear"}'

# Check deploy status
curl -s "https://api.render.com/v1/services/srv-d4q8t8k9c44c73b8ut60/deploys?limit=1" \
  -H "Authorization: Bearer rnd_3MflEFHakX6sYZVIXxICAti0v5pZ"
```

### Cloudflare (DNS & CDN)
**API Token:** `36M4rmOrLGb_q69d77RNwwRx77emyXdCM2oCv1lU`

**Zone IDs:**
- frictioncompass.com: `78b1e32c9fcde984f5ca1d088da0db63`
- friktionskompasset.dk: `8fae5ce31f4002c8e2e55935eceacc32`

**Hvad kan jeg gøre:**
- ✅ Oprette/ændre/slette DNS records
- ✅ Konfigurere subdomæner
- ✅ Se zone status og indstillinger
- ✅ Purge cache

```bash
# List DNS records for friktionskompasset.dk
curl -s "https://api.cloudflare.com/client/v4/zones/8fae5ce31f4002c8e2e55935eceacc32/dns_records" \
  -H "Authorization: Bearer 36M4rmOrLGb_q69d77RNwwRx77emyXdCM2oCv1lU"

# Create CNAME record
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records" \
  -H "Authorization: Bearer 36M4rmOrLGb_q69d77RNwwRx77emyXdCM2oCv1lU" \
  -H "Content-Type: application/json" \
  --data '{"type":"CNAME","name":"subdomain","content":"target.com","ttl":1,"proxied":true}'

# Purge cache
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/ZONE_ID/purge_cache" \
  -H "Authorization: Bearer 36M4rmOrLGb_q69d77RNwwRx77emyXdCM2oCv1lU" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}'
```

### Mailjet (Email)
**Primary API Key:** `f470ff0c3a9ab9d2eaa1d080b271f468`
**Primary API Secret:** `ffa9d70fee458d15b77a3b520881a5dd`

**VIGTIGT:** Brug ALTID Primary API key - sub-account keys har ikke validerede sender-adresser!

**Environment variables på Render:**
- `MAILJET_API_KEY` = Primary API key
- `MAILJET_API_SECRET` = Primary API secret
- `FROM_EMAIL` = info@friktionskompasset.dk
- `FROM_NAME` = Friktionskompasset

**Hvad kan jeg gøre:**
- ✅ Sende transaktionelle emails (invitationer, login-koder, etc.)
- ✅ Tjekke email statistik via Mailjet dashboard

### Friktionskompasset Admin API (Applikation)
**API Key:** `w_r0xNlJAzAm7XSKARbo2T4GkKCePxiqXroB2w0o29s`
**Header:** `X-Admin-API-Key`

**Hvad kan jeg gøre:**
- ✅ Seede domæner og oversættelser
- ✅ Rydde caches
- ✅ Tjekke database status

```bash
# Check status
curl https://friktionskompasset.dk/api/admin/status \
  -H "X-Admin-API-Key: w_r0xNlJAzAm7XSKARbo2T4GkKCePxiqXroB2w0o29s"

# Seed efter deployment
curl https://friktionskompasset.dk/admin/seed-domains \
  -H "X-Admin-API-Key: w_r0xNlJAzAm7XSKARbo2T4GkKCePxiqXroB2w0o29s"
curl https://friktionskompasset.dk/admin/seed-translations \
  -H "X-Admin-API-Key: w_r0xNlJAzAm7XSKARbo2T4GkKCePxiqXroB2w0o29s"
```

### MCP Tools (når tilgængelige)
Følgende MCP tools KAN være tilgængelige i sessionen:
- `mcp__friktionskompas__*` - Lokal database queries
- `mcp__render__*` - Render management (ikke altid aktivt)

**Tjek altid med curl først** hvis MCP tools fejler.

### Data Opdatering - Render og Lokal
- **ALTID** opdater data BÅDE lokalt OG på Render når testdata ændres
- **ALTID** ryd cache på Render efter data-opdateringer (brug API endpoint eller Dev Tools)
- Midlertidige API endpoints med secret keys er OK under udvikling
- Cache-rydning endpoint: `curl https://friktionskompasset.dk/api/clear-cache/frik2025cache`
- Data-variation endpoint: `curl https://friktionskompasset.dk/api/vary-testdata/frik2025vary`
- **FJERN midlertidige endpoints før produktion!**
- Lokale Python scripts kan køres direkte for lokal database
- For Render: Opret midlertidigt API endpoint, push, kald via curl, fjern endpoint igen

### Git Disciplin (KRITISK!)
- **ALTID** kør `git status` FØR push for at sikre alle nødvendige filer er committed
- **ALDRIG** push uden at verificere at templates, static filer og Python moduler er med
- **ALTID** tjek at nye filer (templates, JS, CSS) er `git add`'et - de er IKKE automatisk tracked!
- Ved nye features: Tjek ALLE relaterede filer (templates, static, routes) er committed
- Fejl på produktion (404, 502) skyldes ofte manglende filer i git - tjek `git status` først!

**Pre-push tjekliste:**
```bash
# Kør ALTID før push:
git status --short templates/ static/ *.py
# Hvis der er ?? (untracked) eller M (modified) filer der burde med:
git add <filerne>
git commit -m "beskrivelse"
# FØRST DEREFTER:
git push
```

### Udviklings-workflow
- Vi er IKKE i produktion endnu - vi udvikler stadig
- Det er OK at pushe testdata-ændringer via git
- Brug midlertidige endpoints til engangskørsler på Render
- Vær proaktiv - gør tingene selv i stedet for at bede brugeren

### TODO.md Vedligeholdelse (KRITISK!)
**TODO.md er den autoritative kilde til projektets status!**

**Ved feature-completion:**
- **ALTID** marker opgaver som ✅ FÆRDIG i TODO.md STRAKS de er implementeret og testet
- **ALTID** tilføj dato for completion (fx "✅ FÆRDIG (2025-01-15)")
- **ALTID** opdater TODO.md INDEN sessionen afsluttes
- Ved delvist færdige features: Marker som "✅ DELVIST FÆRDIG" og beskriv hvad der mangler

**Ved session-start:**
- **ALTID** verificer at TODO.md matcher virkeligheden
- Tjek om features markeret som "pending" faktisk allerede er implementeret
- Ret eventuelle uoverensstemmelser FØR du starter nyt arbejde

**Ved nye opgaver:**
- **ALTID** tilføj nye features/bugs til TODO.md MED DET SAMME
- Brug konsistent formatering: `- [ ]` for pending, `- [x]` eller ✅ for færdig
- Inkluder prioritet hvis relevant (fx "🔴 KRITISK", "🟡 VIGTIG", "🟢 NICE-TO-HAVE")

**Typiske fejl at undgå:**
- ❌ Implementere en feature uden at opdatere TODO.md bagefter
- ❌ Starte en session uden at verificere TODO.md er korrekt
- ❌ Antage at TODO.md er opdateret - TJEK det altid

### UI Navigation
- **ALTID** tilføj links til nye sider i admin navigation (`templates/admin/layout.html`)
- Nye features skal være tilgængelige fra UI - brugerne skal kunne finde dem
- Brug `target="_blank"` og ↗ ikon for links der åbner i nyt vindue

### Automatiseret Test & CI/CD

#### Git Pre-Push Hook (KRITISK!)
**En git hook kører tests automatisk FØR push - forhindrer at broken kode pushes!**

Hook lokation: `.git/hooks/pre-push`

**Hvad sker der:**
1. Du kører `git push`
2. Hook kører `pytest tests/test_routes.py` automatisk
3. Hvis tests fejler → push afbrydes med fejlbesked
4. Hvis tests passerer → push fortsætter

**Bypass (KUN i nødstilfælde):**
```bash
git push --no-verify  # Springer hook over - BRUG MED FORSIGTIGHED!
```

**Hvis hook mangler (ny clone):**
Hook-filen er i `.git/hooks/` som ikke er i git. Opret manuelt:
```bash
# Opret .git/hooks/pre-push med indhold fra CLAUDE.md eller bed Claude om det
```

#### GitHub Actions (CI)
- **55 tests kører automatisk** ved hvert push til `main`
- Se status: https://github.com/tplund/friktionskompas/actions
- Workflow fil: `.github/workflows/test.yml`
- Tests kører på Ubuntu med Python 3.10
- Coverage threshold: 50%
- **VIGTIGT:** Selvom pre-push hook fanger de fleste fejl, tjek ALTID GitHub Actions efter push!

#### Hvornår køre tests LOKALT
- Pre-push hook kører tests automatisk - du behøver ikke køre manuelt
- Men ved store ændringer: `python -m pytest tests/ -v --tb=short`
- Hvis tests fejler, ret fejlen før commit

#### Hvornår OPDATERE tests
- **ALTID** tilføj tests til nye features
- **ALTID** tilføj regression test når du fikser bugs
- **ALTID** opdater tests hvis du ændrer eksisterende API/funktionalitet
- Placer tests i `tests/` mappen, navngivet `test_*.py`

### Bug Fix Dokumentation (AUTOMATISK!)
Når en bug fikses skal følgende ALTID ske UDEN at brugeren skal bede om det:

1. **Tilføj regressionstest** - test der ville have fanget buggen
2. **Opdater CLAUDE.md** hvis buggen relaterer til en arkitektur-beslutning
3. **Tilføj til KENDTE BUGS FIKSET** sektionen nedenfor
4. **Commit message skal forklare** hvad buggen var og hvordan den blev fikset

Dette gælder for ALLE bugs - ikke kun dem brugeren specifikt beder om dokumentation for!

#### Test kommandoer
```bash
# Kør alle tests (quick)
python -m pytest tests/ -q

# Kør med coverage
python -m pytest tests/ --cov=. --cov-report=term-missing

# Kør specifik test fil
python -m pytest tests/test_auth.py -v

# Kør tests der matcher et navn
python -m pytest tests/ -k "login" -v
```

#### Test struktur
- `tests/test_auth.py` - Login, logout, authorization (8 tests)
- `tests/test_database.py` - CRUD, constraints, cascade (8 tests)
- `tests/test_routes.py` - Alle endpoints, navigation (21 tests)
- `tests/test_security.py` - SQL injection, XSS, CSRF (12 tests)

### Planer og Dokumentation
- Store features skal have en `PLAN_*.md` fil før implementation
- Ved ændringer i analyselogik: Opdater `ANALYSELOGIK.md`
- Hold `CLAUDE.md` opdateret med nye patterns og løsninger

### Brugerdokumentation (VIGTIGT!)
- **Ved ændringer i login/registrering/auth flows:** Opdater `/help` siden (`templates/help.html`)
- Hjælpesiden skal altid afspejle de faktiske brugerflows
- Hold FAQ sektionen opdateret med nye spørgsmål
- Dokumentationen er brugerrettet - skriv til ikke-tekniske brugere

### Terminologi
- Brug "måling" (ikke "kampagne") i brugersynlige tekster
- Brug "analyse" for resultater/rapporter
- Interne variabelnavne må gerne være engelske

### Oversættelser (i18n)
- Oversættelser gemmes i **databasen** (translations table), IKKE kun i Python-koden
- `translations.py` indeholder `INITIAL_TRANSLATIONS` dict med alle oversættelser
- **VIGTIGT**: Når du tilføjer/ændrer oversættelser i `INITIAL_TRANSLATIONS`:
  1. Opdater `translations.py` med de nye keys
  2. Commit og push til GitHub
  3. Efter deployment: Kald `POST /admin/seed-translations` for at opdatere databasen
  4. Alternativt: Besøg `/admin/db-status` og klik "Seed Translations" knappen
- `seed_translations()` kaldes automatisk ved app start, men oversættelser opdateres KUN hvis de ikke allerede eksisterer
- For at tvinge opdatering: Kald endpoint manuelt efter deployment
- **Husk**: Tilføj oversættelser til BÅDE 'da' og 'en' sprog

```bash
# Seed translations på Render (efter deployment)
curl -X POST https://friktionskompas-eu.onrender.com/admin/seed-translations
```

---

## ✅ KENDTE BUGS FIKSET (Reference)

### Bug: vary_testdata() ignorerede reverse_scored (2025-12-15)
**Symptom:** Hammerum Skole viste 57% i stedet for ~80%
**Årsag:** `vary_testdata()` genererede høje scores (4.0-4.8) for ALLE spørgsmål baseret på profiler, men `reverse_scored` spørgsmål kræver LAVE raw scores for at give høje adjusted scores.

**Teknisk forklaring:**
- Profilen sagde: "Hammerum Skole skal have høje scores (4.0-4.8)"
- For normale spørgsmål: raw=4.5 → adjusted=4.5 ✅
- For reverse spørgsmål: raw=4.5 → adjusted=6-4.5=1.5 ❌ (dårligt!)
- Korrekt for reverse: raw=1.5 → adjusted=6-1.5=4.5 ✅

**Fix:**
```python
# I vary_testdata():
if r['reverse_scored'] == 1:
    new_score = 6 - target_score  # Invert for reverse
else:
    new_score = target_score
```

**Regressionstest:** `test_vary_testdata_must_invert_reverse_scored()` i `tests/test_analysis.py`

### Bug: Trend-chart Y-akse max:5 i stedet for max:7 (2026-01-30)
**Symptom:** Trend-grafer på `/admin` og `/admin/analyser` viste tomt indhold
**Årsag:** Chart.js Y-akse var konfigureret med `max: 5` (gammel 5-point skala), men systemet bruger 7-point skala. Scores over 5 blev renderet udenfor grafen.

**Fix:** Rettet `max: 5` → `max: 7` i tre templates:
- `templates/admin/analyser.html`
- `templates/admin/dashboard_v2.html`
- `templates/admin/trend.html`

**HUSK:** Ved tilføjelse af nye Chart.js-grafer, brug ALTID `max: 7` for score-akser!

### Bug: Password hash brugte scrypt i stedet for bcrypt (2026-01-30)
**Symptom:** Login med korrekt password gav "Forkert brugernavn eller password"
**Årsag:** Bruger blev oprettet med `werkzeug.security.generate_password_hash()` (scrypt), men `verify_password()` i `db_multitenant.py` bruger `bcrypt.checkpw()`.
**Fix:** Generér altid password-hashes med `bcrypt.hashpw()`, IKKE `werkzeug.security.generate_password_hash()`.

**VIGTIGT:** Systemet bruger **bcrypt** til password-hashing:
```python
import bcrypt
pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
```
Brug ALDRIG `werkzeug.security.generate_password_hash()` - det genererer scrypt-hashes som `verify_password()` ikke kan verificere!

### Bug: Render restore-db-from-backup finder ikke backup-filen (2026-01-30)
**Symptom:** `restore-db-from-backup` endpoint returnerer 404 selvom `db_backup.b64` er committed
**Årsag:** Render builder kopierer repo-filer til build-mappen, men persistent disk er mounted separat på `/var/data`. Filen ligger i build-dir, men endpoint leder i forkert sti.
**Workaround:** Brug midlertidige API-endpoints til at ændre data direkte på Render i stedet for DB-restore.

---

## 🔄 FREMTIDIG MIGRERING: Render → Azure (PARKERET)

**Status:** Parkeret (2026-01-30). Demo virker, ingen ændringer planlagt. Genoptag ved traction.

**Baggrund:** Render har følgende begrænsninger med SQLite + persistent disk:
1. **DB-synkronisering** kræver workarounds (base64 via git, midlertidige endpoints)
2. **502 Bad Gateway** under deploys (2-3 min cold start)
3. **Ingen direkte DB-adgang** - kan ikke SSH ind og køre SQL
4. **Persistent disk** er bundet til én instans, ingen automatisk backup

**Azure App Service plan (når det bliver aktuelt):**
- App Service B1: ~$13/måned
- Azure Database for PostgreSQL Flexible (Burstable B1ms): ~$13/måned
- **Total: ~$25-30/måned** (vs Render ~$8/måned)

**Migrering kræver:**
1. SQLite → PostgreSQL migrering (schema + data)
2. Ændre `get_db()` til PostgreSQL connection pool (psycopg2/asyncpg)
3. Tilpasse SQL-queries (SQLite-specifikke ting som `||` for concat, `PRAGMA`, etc.)
4. Azure App Service setup med GitHub Actions deploy
5. DNS-ændring i Cloudflare (CNAME til Azure)
6. Environment variables flyttes til Azure App Configuration

**Fordele ved Azure:**
- Managed PostgreSQL med automatisk backup og point-in-time restore
- Zero-downtime deploys (deployment slots)
- SSH direkte til container
- Bedre logging og monitoring
- Ingen persistent disk-problemer

**Beslutning:** Vent til der er traction. Demo fungerer fint på Render. Migrer når:
- Der kommer betalende kunder
- DB-synkronisering bliver et dagligt problem
- Performance krav stiger

---

## ⚠️ KENDTE PROBLEMER - TJEK FØR DEPLOY

### Problem 1: Lokal database != Produktion database
**Symptom:** Ændringer vises ikke på produktion efter push
**Årsag:** Testdata/ændringer er kun i lokal SQLite, ikke på Render

**Løsning:**
1. Database er IKKE i git (med vilje for nu under udvikling)
2. Efter seed/data-ændringer lokalt: HUSK at køre seed på produktion
3. Brug `/admin/seed-testdata` til at køre scripts på produktion
4. Eller brug `/admin/backup` til at uploade database

**Tjek:** Hvis data ser anderledes ud lokalt vs. produktion:
- Kør `curl https://friktionskompasset.dk/admin/db-status`
- Sammenlign med lokal database stats

### Problem 2: Render deployment trigger delay
**Symptom:** Push til GitHub, men Render deployer ikke
**Årsag:** Render tjekker kun hvert 5. minut for nye commits

**Løsning:**
- Vent 5-10 minutter
- Tjek Render dashboard: https://dashboard.render.com
- Tjek via MCP: `mcp__render__list_deploys`

### Problem 3: Integration tests passer lokalt men fejler i produktion
**Symptom:** Tests grønne lokalt, men data mangler på produktion
**Årsag:** Tests kører mod lokal database med testdata

**Løsning:**
- Tests er for lokal udvikling
- Produktion skal have data seeded separat
- Herning Kommune er kanonisk test-kunde - brug `seed_herning_testdata.py`

### Problem 4: Customer filter virker ikke
**Symptom:** Superadmin med filter ser stadig alle kunders data
**Årsag:** Endpoint bruger ikke `get_customer_filter()` korrekt

**Tjek ved nye endpoints:**
1. Kald `get_customer_filter()` tidligt i funktionen
2. Brug returneret `(where_clause, params)` i SQL queries
3. Test med superadmin + customer_filter sat

---

## KRITISK: Database Konfiguration

### Render Persistent Disk
- Render har persistent disk på `/var/data`
- Database path: `/var/data/friktionskompas_v3.db`
- Konfigureret i både `db_hierarchical.py` og `db_multitenant.py`

### Foreign Keys (CASCADE DELETE)
- **VIGTIGT**: SQLite har foreign keys DISABLED by default!
- Skal aktiveres med `PRAGMA foreign_keys=ON` ved HVER connection
- Implementeret i `get_db()` i begge database filer
- Uden dette virker CASCADE DELETE IKKE

### Database Filer
- Lokal: `friktionskompas_v3.db`
- Render: `/var/data/friktionskompas_v3.db`

### Database Synkronisering (Lokal → Render)
Når lokale data-ændringer ikke reflekteres på Render (pga. persistent disk), kan databasen pushes via git:

**Metode: Push database som base64 via git**
```bash
# 1. Eksporter lokal database som base64
python -c "import base64; open('db_backup.b64','w').write(base64.b64encode(open('friktionskompas_v3.db','rb').read()).decode())"

# 2. Commit og push
git add db_backup.b64
git commit -m "Database backup for Render sync"
git push

# 3. Efter deployment, kald restore endpoint:
curl -X POST https://friktionskompasset.dk/admin/restore-db-from-backup

# 4. Slet backup fil fra git (valgfrit)
git rm db_backup.b64
git commit -m "Remove db backup"
git push
```

**Alternativ: JSON import/export** (se nedenfor)

## Data Import/Export

### Eksporter lokal data
```python
# Kør fra C:\_proj\Friktionskompasset
python -c "
import sqlite3, json
conn = sqlite3.connect('friktionskompas_v3.db')
conn.row_factory = sqlite3.Row
data = {
    'organizational_units': [dict(r) for r in conn.execute('SELECT * FROM organizational_units').fetchall()],
    'campaigns': [dict(r) for r in conn.execute('SELECT * FROM campaigns').fetchall()],
    'responses': [dict(r) for r in conn.execute('SELECT * FROM responses').fetchall()],
    'customers': [dict(r) for r in conn.execute('SELECT * FROM customers').fetchall()],
}
with open('local_data_export.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
"
```

### Importer på Render
URL: `/admin/cleanup-empty` (kræver admin login)

## Kendte Problemer og Løsninger

### VIGTIG REFACTORING: campaign → assessment (DONE - MÅ IKKE RULLES TILBAGE!)
**Besluttet tidligt i projektet - fuldt implementeret**

- **Hvorfor**: "Campaign" lyder marketing-agtigt. "Assessment" / "Måling" er mere HR/læring-agtigt
- **Database**: Kolonnen hedder `assessment_id` (ikke `campaign_id`)
- **Kode**: Alle queries bruger `r.assessment_id`
- **UI**: Bruger "måling" (dansk) i stedet for "kampagne"

**ALDRIG rul tilbage til campaign_id!** Migrationsscripts i `db_hierarchical.py` konverterede automatisk:
- `tokens.campaign_id` → `tokens.assessment_id`
- `responses.campaign_id` → `responses.assessment_id`
- Tabellen `campaigns` → `assessments`

**Ved fremtidige ændringer:**
- Brug altid `assessment_id` i SQL queries
- Brug "måling" i brugersynlig tekst (ikke "kampagne")
- Variabelnavne: `assessment_id`, `assessment`, `assessments`

### Problem: Data forsvinder på Render
- **Årsag**: Ephemeral storage eller persistent disk ikke mounted
- **Løsning**: Tjek at `/var/data` eksisterer på Render og at DB_PATH peger dertil

### Problem: CASCADE DELETE virker ikke
- **Årsag**: Foreign keys ikke aktiveret
- **Løsning**: `PRAGMA foreign_keys=ON` i get_db()

### Problem: Kan ikke logge ind
- **Årsag**: Bruger eksisterer ikke eller forkert password hash
- **Løsning**: Opret midlertidig reset route (HUSK AT FJERNE!)

### Problem: Render deployment fejler med "ModuleNotFoundError"
- **Årsag**: Ny Python-fil oprettet lokalt men IKKE committed til git
- **Løsning**:
  1. Kør `git status` for at se untracked filer
  2. `git add <filnavn>.py` og commit
  3. Tjek også at dependencies er i `requirements.txt`
- **VIGTIGT**: Når du opretter nye .py filer, ALTID commit dem med det samme!

### Problem: Oversættelser viser [key.name] i stedet for tekst
- **Årsag**: Oversættelser mangler i databasen (translations table)
- **Løsning**:
  1. Tilføj oversættelser til `INITIAL_TRANSLATIONS` i `translations.py`
  2. Push til GitHub og vent på deployment
  3. Kald `POST /admin/seed-translations` for at opdatere databasen
- **Alternativ**: Besøg `/admin/db-status` og klik "Seed Translations"

## Blueprint Struktur

Applikationen bruger Flask blueprints til at organisere routes modular. Alle blueprints registreres i `admin_app.py` og bruges til at gruppere relaterede endpoints.

### De 10 Blueprints

| Blueprint | Fil | Formål | Antimekanisme |
|-----------|-----|--------|---------------|
| **public** | `blueprints/public.py` | Offentlige sider: landing page, robots.txt, sitemap | Ingen auth kraves |
| **auth** | `blueprints/auth.py` | Login, logout, registrering, OAuth, password reset, email login | `@limiter` på login (10/min) |
| **admin_core** | `blueprints/admin_core.py` | Dashboard, KPIs, trends, analyser - hovedoversigt | `@login_required`, `@admin_required` |
| **api_admin** | `blueprints/api_admin.py` | Admin API endpoints: status, cache clearing, dokumentation | `@api_or_admin_required`, `X-Admin-API-Key` header |
| **api_customer** | `blueprints/api_customer.py` | REST API v1 for enterprise kunder: assessments, units, export | `@customer_api_required` med API keys |
| **assessments** | `blueprints/assessments.py` | Assessment CRUD: opret, vis, slet, analyser, PDF export, assessment types | `@login_required`, `@admin_required` |
| **units** | `blueprints/units.py` | Enhed management: opret unit, bulk upload, move, kontakter, dashboard | `@login_required`, `@admin_required` |
| **customers** | `blueprints/customers.py` | Kunde management: opret kunde, domæner, API-nøgler, auth konfiguration | `@admin_required`, `@superadmin_required` |
| **export** | `blueprints/export.py` | Backup, restore, bulk export med anonymisering | `@admin_required`, `@api_or_admin_required` |
| **dev_tools** | `blueprints/dev_tools.py` | Seed data, migrering, database status, dev debugging | `@admin_required` |
| **friktionsprofil** | `friktionsprofil_routes.py` | Screening og dybdeprofil: survey, resultater, sammenligning | Ingen auth (B2C) |

### Route Gruppering

**Offentlige routes (ingen auth):**
- `public` - Landing page
- `friktionsprofil` - Screening/dyb måling (B2C)

**Bruger auth (login kraves):**
- `admin_core` - Dashboard og analyser
- `assessments` - Assessment management
- `units` - Enhed management

**Admin routes (admin_required):**
- `customers` - Kunde og domæne konfiguration
- `export` - Backup og bulk export
- `dev_tools` - Seed data og migrering

**API routes (API key kraves):**
- `api_admin` - Admin API med `X-Admin-API-Key` header
- `api_customer` - Customer REST API v1 med customer API-nøgler

**Auth routes:**
- `auth` - Login flows med rate limiting

### Hvordan Tilføjer Man Nye Routes?

**1. Velg rigtig blueprint baseret på formål:**
- **Dashboard/oversigt?** → `admin_core`
- **CRUD på assessments?** → `assessments`
- **CRUD på units?** → `units`
- **Kunde-/domæne-konfiguration?** → `customers`
- **Backup/export?** → `export`
- **Dev tools/seed data?** → `dev_tools`
- **API endpoint?** → `api_admin` eller `api_customer`
- **Public sider?** → `public`
- **Auth flows?** → `auth`

**2. Opret route med rigtig sikkerhed:**
```python
# I f.eks. assessments.py
@assessments_bp.route('/admin/min-nye-side', methods=['GET', 'POST'])
@login_required  # For bruger-authenticated routes
@admin_required  # For admin-only routes
def min_nye_route():
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
    # Implementation...
    return render_template('...')
```

**3. Tilføj template og static filer:**
- Templates: `templates/path/page.html`
- JavaScript: `static/js/script.js`
- CSS: `static/css/style.css`
- **VIGTIGT**: Commit alle template/static filer eksplicit!

**4. Tilføj navigation link i admin layout** (`templates/admin/layout.html`):
```html
<a href="{{ url_for('blueprint_name.route_function') }}">Min side</a>
```

**5. Tilføj tests** i `tests/test_routes.py`:
```python
def test_ny_route():
    with client.session_transaction() as sess:
        sess['user'] = {'id': 1, 'role': 'admin', 'customer_id': 'xyz'}
    response = client.get('/admin/min-nye-side')
    assert response.status_code == 200
```

**6. Commit til git FØR push:**
```bash
git add blueprints/assessments.py templates/path/page.html static/
git commit -m "feat: Add new assessment feature"
git push
```

---

## Domæner og OAuth

### Domæne-konfiguration
Domæner konfigureres i `admin_seed_domains()` i `admin_app.py`:

| Domæne | Sprog | Microsoft | Google | Email/Password | Formål |
|--------|-------|-----------|--------|----------------|--------|
| friktionskompasset.dk | da | ✅ | ✅ | ✅ | Generisk DK |
| frictioncompass.com | en | ✅ | ✅ | ✅ | Generisk EN |
| herning.friktionskompasset.dk | da | ✅ | ❌ | ❌ | Enterprise |

### OAuth Credentials
- Gemmes som environment variables på Render
- Microsoft: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID`
- Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- Opdater via Render MCP: `mcp__render__update_environment_variables`

### Tilføj nyt enterprise-domæne
1. Tilføj domænet til `domains_config` i `admin_app.py`
2. Push til GitHub
3. Kald `curl https://friktionskompasset.dk/admin/seed-domains`
4. Tilføj redirect URI i Azure/Google Console hvis OAuth skal bruges

## Worktrees
- Main repo: `C:\_proj\Friktionskompasset`
- Worktrees: `C:\Users\tplun\.claude-worktrees\Friktionskompasset\*`
- **VIGTIGT**: Hver worktree har sin egen database!

## MCP Server
- Fil: `mcp_server.py`
- Version: 2.1 med sikkerhed og debug
- Features: Rate limiting, audit logging, SQL validation
- Config: `.mcp.json`

## Testdata Strategi: To Kunder

### KRITISK: 7-Point Skala (Opdateret 2026-01-04)
**AL data bruger nu 7-point Likert skala (1-7), IKKE 5-point!**

Farve-thresholds for 7-point skala:
- **GRØN (high):** score >= 4.9 (70% eller højere)
- **GUL (medium):** score >= 3.5 (50-70%)
- **RØD (low):** score < 3.5 (under 50%)

Reverse scoring: `8 - score` (IKKE `6 - score`)

### Oversigt
| Kunde | Formål | Data |
|-------|--------|------|
| **Herning Kommune** | Demo/showcase | Meget data, kan ændres frit |
| **Esbjerg Kommune** | Kanonisk test | STABIL data, MÅ IKKE ændres! |

---

### Esbjerg Kommune - Kanonisk Testdata (KRITISK!)
**ID:** `cust-SHKIi10cOe8`
**Dokumentation:** `ESBJERG_TESTDATA.md`

**REGLER:**
1. **ALDRIG** ændr Esbjerg-data uden at opdatere ESBJERG_TESTDATA.md
2. **ALTID** kør `pytest tests/test_esbjerg_canonical.py` efter ændringer
3. Esbjerg-data er designet til at fange specifikke bugs
4. Inkluderer `leader_self` responses for gap-analyse

**Esbjerg Test-Scenarier (7-point skala):**
| Unit | Test Case | Score Range | Forventet Farve |
|------|-----------|-------------|-----------------|
| Birkebo | Normal scores | 4.5-4.9 | GUL (borderline GRØN) |
| Skovbrynet | Høje scores | 6.0-6.4 | GRØN |
| Solhjem | Krise scores | 2.1-2.8 | RØD |
| Strandparken | Leader gap | 3.3 vs 6.3 | Gap-advarsel |
| Handicapområdet | Tom enhed | - | Ingen crash |
| Individuel Profil | B2C, 1 respondent | - | Korrekt visning |
| Minimal Data | Identiske scores | 4.0 | Ingen division-by-zero |
| Substitution Test | Kahneman pattern | 5.5/2.5 | Substitution-ikon |

**Seed Esbjerg:**
```bash
python seed_esbjerg_canonical.py
pytest tests/test_esbjerg_canonical.py -v
```

---

### Herning Kommune - Demo Data
**ID:** `cust-0nlG8ldxSYU`

Herning Kommune bruges til demo og showcase. Data kan ændres frit.

**Demo Scenarier:**
| Scenarie | Unit | Formål |
|----------|------|--------|
| **Trend Data** | Birk Skole, Aktivitetscentret Midt | Q1-Q4 2025 |
| **B2C** | Individuel Screening, Par-profiler | Uden leder |
| **Variation** | Forskellige skoler | Forskellige farver |

**Tilføj Variation til Herning (efter seed):**
Dev Tools har en "Vary Testdata" funktion der tilføjer realistisk variation:
- Birk Skole: GRØN (høje scores)
- Hammerum Skole: GRØN (høje scores)
- Gødstrup Skole: RØD (lave scores)
- Andre: GUL (middel scores)

Lokalt kan du køre variation via Python (se `blueprints/dev_tools.py:vary_testdata`).

**Seed Herning:**
```bash
python seed_herning_testdata.py
python seed_edge_cases.py
```

---

### Synkronisering til Render
```bash
# 1. Eksporter database
python -c "import base64; open('db_backup.b64','w').write(base64.b64encode(open('friktionskompas_v3.db','rb').read()).decode())"

# 2. Push til git
git add db_backup.b64 && git commit -m "DB sync" && git push

# 3. Vent på deployment, derefter restore
curl -X POST https://friktionskompasset.dk/admin/restore-db-from-backup \
     -H "X-Admin-API-Key: w_r0xNlJAzAm7XSKARbo2T4GkKCePxiqXroB2w0o29s"

# 4. Fjern backup fra git
git rm db_backup.b64 && git commit -m "Remove backup" && git push
```

## Deploy Checklist
1. ~~Test lokalt først~~ (CI klarer det nu, medmindre store ændringer)
2. Commit og push til GitHub
3. **Tjek GitHub Actions** - vent på grønt flueben: https://github.com/tplund/friktionskompas/actions
4. Render deployer automatisk (1-2 min)
5. Verificer på https://friktionskompas.onrender.com

## Token-besparelse i Claude Code sessioner
- **UNDGÅ** at køre alle 55 tests rutinemæssigt - CI gør det
- **KØR KUN** relevante tests ved specifikke ændringer
- **STOL PÅ** GitHub Actions til at fange fejl
- Ved tvivl: Push og tjek CI i stedet for at køre lokalt
