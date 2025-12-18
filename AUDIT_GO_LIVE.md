# GO-LIVE AUDIT - Friktionskompasset

**Oprettet:** 2025-12-18
**Formål:** Grundig gennemgang før lancering

---

## 🎯 Audit Områder

### 1. TEST COVERAGE
**Mål:** Sikre at alle nye features er testet

**Nye features der skal have tests:**
- [ ] Situationsmåling (tasks, actions, situation_assessments)
- [ ] B2C LocalStorage profil (`/profil/local`, `/profil/api/*`)
- [ ] Social login (Microsoft, Google OAuth)
- [ ] Passwordless email-login
- [ ] Selvregistrering
- [ ] Glemt password flow
- [ ] GA4 event tracking (dataLayer pushes)

**Eksisterende test filer:**
- `tests/test_auth.py` - Login, logout, authorization
- `tests/test_database.py` - CRUD, constraints, cascade
- `tests/test_routes.py` - Endpoints, navigation
- `tests/test_security.py` - SQL injection, XSS, CSRF
- `tests/test_ui.py` - Playwright UI tests
- `tests/test_integration.py` - End-to-end flows
- `tests/test_integration_data.py` - Data isolation
- `tests/test_localstorage_api.py` - LocalStorage API

**Actions:**
- [ ] Kør `pytest tests/ -v --tb=short` og noter fejl
- [ ] Tjek coverage: `pytest tests/ --cov=. --cov-report=term-missing`
- [ ] Tilføj tests for manglende areas

---

### 2. SIKKERHED
**Mål:** Verificer at systemet er sikkert

**OWASP Top 10 checklist:**
- [ ] **Injection** - SQL injection i alle database queries
- [ ] **Broken Auth** - Session management, password hashing
- [ ] **Sensitive Data** - Kryptering, HTTPS, secrets management
- [ ] **XXE** - XML parsing (hvis relevant)
- [ ] **Broken Access Control** - Customer isolation, role-based access
- [ ] **Security Misconfig** - Debug mode, default credentials
- [ ] **XSS** - Output encoding, CSP headers
- [ ] **Insecure Deserialization** - Pickle, JSON handling
- [ ] **Vulnerable Components** - Outdated dependencies
- [ ] **Insufficient Logging** - Audit trail

**Specifikt for Friktionskompasset:**
- [ ] Multi-tenant isolation (customer_id filter på ALLE queries)
- [ ] Token-baseret survey access (kan tokens gættes?)
- [ ] OAuth state parameter validation
- [ ] Session timeout og refresh
- [ ] Rate limiting på login/register
- [ ] CSRF tokens på forms

**Debug/test endpoints der skal fjernes:**
- [ ] `/api/fix-testdata-trends/<secret>`
- [ ] `/api/list-assessments/<secret>`
- [ ] `/api/vary-testdata/<secret>`
- [ ] `/api/clear-cache/<secret>`
- [ ] Andre midlertidige endpoints?

---

### 3. DOKUMENTATION
**Mål:** Opdater al dokumentation

**Filer der skal gennemgås:**
- [ ] `CLAUDE.md` - Er alle beslutninger dokumenteret?
- [ ] `TODO.md` - Er det konsistent med virkeligheden?
- [ ] `ANALYSELOGIK.md` - Er beregninger korrekt beskrevet?
- [ ] `templates/help.html` - Er brugerflows opdateret?
- [ ] `FRIKTIONSPROFIL_V2.md` - Er spørgsmål dokumenteret?

**Nye ting der skal dokumenteres:**
- [ ] Situationsmåling flow
- [ ] B2C LocalStorage arkitektur
- [ ] OAuth setup og konfiguration
- [ ] GA4 event tracking

---

### 4. UI KONSISTENS
**Mål:** Strømlin brugeroplevelsen

**Terminologi (skal være konsistent):**
- "Måling" (brugervendt) vs "Assessment" (kode)
- "Profil" vs "Screening" vs "Test"
- "Enhed" vs "Organisation" vs "Afdeling"

**Målings-typer (for mange special cases?):**
- `gruppe_friktion` - Standard gruppe-måling
- `gruppe_leder` - Med leder-vurdering
- `individuel_profil` - B2C profiler
- `screening` - Kort screening
- `kapacitet` - Kapacitetsmåling
- `baandbredde` - Båndbreddemåling
- `edge_case_test` - Test data

**UI elementer der skal tjekkes:**
- [ ] Navigation - Er den konsistent?
- [ ] Forms - Samme styling overalt?
- [ ] Buttons - Konsistent farver/størrelser?
- [ ] Loading states - Vises de korrekt?
- [ ] Fejlbeskeder - Konsistente og hjælpsomme?
- [ ] Mobile responsiveness - Virker på telefon?

---

### 5. KODE KVALITET
**Mål:** Ryd op i teknisk gæld

**Dead code:**
- [ ] Søg efter ubrugte funktioner
- [ ] Søg efter udkommenteret kode
- [ ] Søg efter TODO/FIXME kommentarer

**Duplikeret logik:**
- [ ] Er `friction_engine.py` brugt overalt?
- [ ] Er der duplikerede SQL queries?
- [ ] Er der duplikerede templates?

**Filstruktur:**
- [ ] Er Python filer organiseret logisk?
- [ ] Er templates organiseret?
- [ ] Er der filer der kan slettes?

---

### 6. DATA & PERFORMANCE
**Mål:** Sikre god performance

**Database:**
- [ ] Er indexes korrekte? (tjek `db_hierarchical.py`)
- [ ] Er der N+1 query problemer?
- [ ] Er foreign keys sat korrekt op?

**Caching:**
- [ ] Virker cache invalidation?
- [ ] Er TTL passende?

**Testdata på produktion:**
- [ ] Skal Herning Kommune testdata fjernes?
- [ ] Skal edge case tests fjernes?
- [ ] Er der "fake" brugere der skal slettes?

---

## 🔧 WORK SETUP REVIEW

### CLAUDE.md Best Practices
- [ ] Er reglerne klare og nemme at følge?
- [ ] Er der modstridende instruktioner?
- [ ] Mangler der vigtige patterns?
- [ ] Er credentials håndteret sikkert?

### Vibe Coding Optimering
- [ ] Er TODO-disciplin for streng/løs?
- [ ] Er dokumentationskrav passende?
- [ ] Er test-krav passende?
- [ ] Er commit-flow optimalt?

### Kode Best Practices
- [ ] Python style guide (PEP 8)
- [ ] SQL query patterns
- [ ] Error handling patterns
- [ ] Logging patterns

---

## 📋 Prioriteret Rækkefølge

1. **Sikkerhed** - Kritisk før go-live
2. **Tests** - Fang fejl før brugere
3. **UI Konsistens** - Professionelt indtryk
4. **Dokumentation** - Vedligeholdelse
5. **Kode Kvalitet** - Teknisk gæld
6. **Performance** - Kan vente til der er load

---

## 🚀 Sådan Starter Du Audit i Ny Claude Session

```
Start en ny Claude Code session og sig:

"Jeg vil gerne lave en go-live audit af Friktionskompasset.
Læs AUDIT_GO_LIVE.md for den fulde plan.
Start med [OMRÅDE] og giv mig konkrete fund og fixes."

Erstat [OMRÅDE] med: sikkerhed, tests, UI, docs, kode, eller performance.
```

---

## Noter
- GTM er publiceret og virker (verificeret 2025-12-18)
- GA4 events trackes: profile_start, profile_complete, sign_up, login, cta_click, scroll_depth
- Python 3.10 → 3.12 opgradering er på TODO (ikke kritisk for go-live)
