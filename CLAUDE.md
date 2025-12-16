# Friktionskompasset - Claude Code Notes

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

## ⛔ BESLUTNINGS-TJEKLISTE - TJEK INDEN DU STARTER!

Før du laver ændringer i følgende områder, TJEK denne liste:

### 1. Database kolonne-navne
- ✅ **responses.assessment_id** - IKKE campaign_id (refactored)
- ✅ **tokens.assessment_id** - IKKE campaign_id (refactored)
- ✅ **assessments** tabel - IKKE campaigns (refactored)

### 2. Field navne i profil-spørgsmål
- ✅ **KAN** - IKKE MULIGHED (database bruger KAN)
- ✅ Field order: `['MENING', 'TRYGHED', 'KAN', 'BESVÆR']`

### 3. Terminologi i UI
- ✅ Brug "måling" - IKKE "kampagne"
- ✅ Brug "analyse" - IKKE "rapport"
- ✅ Brug "assessment" i kode - IKKE "campaign"

### 4. Arkitektur
- ✅ Database: SQLite med persistent disk på Render `/var/data/`
- ✅ Auth: Session-based med Flask-Login
- ✅ Oversættelser: Database-based (translations table)

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

### API Keys og Credentials (FORTROLIGT)
Disse keys er til brug i Claude Code sessioner - spørg IKKE brugeren om dem igen!

**Cloudflare:**
- API Token (Bred access): `36M4rmOrLGb_q69d77RNwwRx77emyXdCM2oCv1lU`
- Zone ID for frictioncompass.com: `78b1e32c9fcde984f5ca1d088da0db63`
- Zone ID for friktionskompasset.dk: `8fae5ce31f4002c8e2e55935eceacc32`

**Cloudflare DNS eksempler:**
```bash
# List DNS records
curl -s "https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records" \
  -H "Authorization: Bearer 36M4rmOrLGb_q69d77RNwwRx77emyXdCM2oCv1lU"

# Create CNAME record
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records" \
  -H "Authorization: Bearer 36M4rmOrLGb_q69d77RNwwRx77emyXdCM2oCv1lU" \
  -H "Content-Type: application/json" \
  --data '{"type":"CNAME","name":"subdomain","content":"target.com","ttl":1,"proxied":false}'
```

**Render:** Konfigureret via MCP (mcp__render__*)

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

### TODO.md Vedligeholdelse
- **ALTID** opdater `TODO.md` når nye opgaver identificeres
- **ALTID** marker opgaver som færdige når de er implementeret
- Hold TODO.md som den centrale kilde til projektets status
- Nye features, bugs, og teknisk gæld skal tilføjes til TODO.md

### UI Navigation
- **ALTID** tilføj links til nye sider i admin navigation (`templates/admin/layout.html`)
- Nye features skal være tilgængelige fra UI - brugerne skal kunne finde dem
- Brug `target="_blank"` og ↗ ikon for links der åbner i nyt vindue

### Automatiseret Test & CI/CD

#### GitHub Actions (CI)
- **55 tests kører automatisk** ved hvert push til `main`
- Se status: https://github.com/tplund/friktionskompas/actions
- Workflow fil: `.github/workflows/test.yml`
- Tests kører på Ubuntu med Python 3.10
- Coverage threshold: 50%

#### Hvornår køre tests LOKALT
- **KØR ALTID LOKALT FØR COMMIT** - tests skal være grønne før push
- Kommando: `python -m pytest tests/ -v --tb=short`
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

## Testdata: Herning Kommune (Kanonisk Test-Kunde)

### Hvorfor Herning Kommune?
Herning Kommune (`cust-0nlG8ldxSYU`) er den kanoniske test-kunde med komplet testdata for alle scenarier.
Al ny testdata skal tilføjes til Herning Kommune for at sikre konsistens.

### Testdata Scenarier
| Scenarie | Unit | Formål |
|----------|------|--------|
| **Normal B2B** | Birk Skole, Aktivitetscentret Midt | Trend-data (Q1-Q4 2025) |
| **B2C** | Individuel Screening, Par-profiler, Karrierevejledning | Uden leder-vurdering |
| **Edge Cases** | Se nedenfor | Test af advarsels-scenarier |

### Edge Case Tests (under "Edge Case Tests" unit)
| Test | Formål | Karakteristik |
|------|--------|---------------|
| Gap Test - Kritisk Forskel | Stort gap mellem medarbejder og leder | Medarbejdere ~2.5, Ledere ~4.0 |
| Krise Test - Alt er Galt | Alle scores kritisk lave | Alle felter < 2.0 |
| Succes Test - Høj Trivsel | Alle scores høje | Alle felter > 4.0 |
| Spredning Test - Stor Uenighed | Høj varians i svar | Std.dev > 1.2 |
| Tryghed Test - Kun Psykologisk Sikkerhed | Ét felt markant lavere | TRYGHED ~2.0, andre ~4.0 |

### Realistiske Profil-Arketyper
| Arketype | MENING | TRYGHED | KAN | BESVÆR | Beskrivelse |
|----------|--------|---------|-----|--------|-------------|
| Travlt Team | 3.8 | 3.2 | 4.2 | 2.0 | Høj kapacitet, lav besvær |
| Demotiveret Team | 2.2 | 3.5 | 3.0 | 3.2 | Lav mening, OK tryghed |
| Siloed Team | 3.5 | 2.0 | 4.0 | 3.5 | Lav tryghed, høj kunnen |
| Overbelastet Team | 3.0 | 2.8 | 2.3 | 1.5 | Lav kapacitet og besvær |
| Balanceret Team | 3.5 | 3.5 | 3.5 | 3.5 | Jævn profil |

### Seed Scripts
```bash
# Lokalt: Regenerer al testdata
python seed_herning_testdata.py
python seed_edge_cases.py

# Render: Seed assessments fra JSON
curl https://friktionskompasset.dk/admin/seed-assessments
```

### Data Flow (under udvikling)
1. **Lokal udvikling** → Data i `seed_*.py` scripts
2. **Eksporter** → `python -c "..."` (se nedenfor)
3. **Git** → `seed_assessments.json` + responses
4. **Render** → `/admin/seed-assessments` endpoint

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
