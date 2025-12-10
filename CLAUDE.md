# Friktionskompasset - Claude Code Notes

## VIGTIGT: Projekt Regler

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

## Worktrees
- Main repo: `C:\_proj\Friktionskompasset`
- Worktrees: `C:\Users\tplun\.claude-worktrees\Friktionskompasset\*`
- **VIGTIGT**: Hver worktree har sin egen database!

## MCP Server
- Fil: `mcp_server.py`
- Version: 2.1 med sikkerhed og debug
- Features: Rate limiting, audit logging, SQL validation
- Config: `.mcp.json`

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
