# TODO - Friktionskompasset

## 🔥 Høj Prioritet

### Flersproget Support (Oversættelser)
- [x] ~~**Database ændringer** - `language` på users, `translations` tabel~~
- [x] ~~**Translation modul** - `translations.py` med `t()` funktion~~
- [x] ~~**Flask integration** - Context processor, `/set-language` route~~
- [x] ~~**Sprogvælger i nav** - DA/EN skifter i header~~
- [x] ~~**Template migrering (delvis)** - login, layout, home, tree_node, customers, analyser, org_dashboard~~
- [x] ~~**Seed oversættelser** - 147 oversættelser seedet til database (DA/EN)~~
- [x] ~~**Template migrering (resterende)** - new_unit, view_unit, new_campaign konverteret til layout.html + t()~~
- [x] ~~**Spørgsmålsoversættelse** - 24 friktionsanalyse + 30 profil spørgsmål oversat til engelsk~~
- [x] ~~**Email templates** - Alle 3 email types (invitation, reminder, profil) med DA/EN templates~~
- Se detaljeret plan: `PLAN_flersproget.md`

### Automatiseret Test
- [x] ~~**Test framework** - pytest opsætning med fixtures~~
- [x] ~~**Database test** - CRUD, constraints, cascade delete (8 tests)~~
- [x] ~~**Auth test** - Login, logout, authorization (8 tests)~~
- [x] ~~**Route test** - Alle endpoints, navigation, 404 håndtering (21 tests)~~
- [x] ~~**Sikkerhedstest** - SQL injection, XSS, auth bypass, session hijacking (12 tests)~~
- [ ] **UI/UX test** - Selenium/Playwright tests af brugerflows
- [ ] **Integration test** - End-to-end test af survey flow
- [x] ~~**CI/CD** - GitHub Actions workflow kører 55 tests automatisk ved push~~

### ⚠️ VIGTIGT - Dokumentation
- [ ] **Ved ALLE ændringer i analyselogik:** Opdater `ANALYSELOGIK.md`
  - Substitution thresholds (tid_bias ≥ 0.6, underliggende ≥ 3.5)
  - KKC severity levels (høj < 2.5, medium < 3.5)
  - Leder gap threshold (> 1.0 point forskel)
  - Leder blokeret threshold (både team og leder < 3.5)
  - Farvecodning (grøn ≥ 70%, gul ≥ 50%, rød < 50%)

### Multi-tenant & Auth
- [x] ~~Implementer kunde/tenant isolation i database~~
- [x] ~~Tilføj auth system med Admin og Manager roller~~
- [x] ~~Admin kan se alle kunder, Manager kan kun se egen kunde~~
- [x] ~~Login page med session management~~
- [x] ~~Bcrypt password hashing (sikker)~~
- [x] ~~Secret key fra environment variable~~
- [ ] CSRF protection (deferred til produktion)
- [ ] Rate limiting på login (deferred til produktion)

### UI Forbedringer
- [x] ~~Vis organisationer som træ-struktur (ikke flat liste)~~
- [x] ~~Navigation menu i admin interface~~
- [x] ~~Customer dropdown for admin~~
- [x] ~~Breadcrumbs i alle admin views~~
- [x] ~~Organisations-dashboard med drill-down (Organisation → Forvaltning → Område → Enhed)~~
- [x] ~~Customer dropdown bevarer nuværende side ved skift~~
- [x] ~~Terminologi: "kampagne" → "måling"~~
- [x] ~~Favicon: Kompas-nål design~~
- [x] ~~**Slet toplevel organisationer** - Mulighed for at slette kunder/toplevel fra organisationsoversigten~~

### CSV Import
- [x] ~~Semikolon separator (Excel standard)~~
- [x] ~~UTF-8 BOM encoding~~
- [x] ~~Auto-opret kontakter fra CSV~~
- [x] ~~Bedre fejlhåndtering og preview før import~~ (2-trins flow med drag-drop, hierarki-preview)

---

## 📊 Medium Prioritet

### Rapportering
- [ ] Eksporter resultater til PDF
- [ ] Email notifikationer når kampagne er færdig
- [ ] Dashboard med nøgletal

### Data Management
- [ ] Bulk edit af organisationer
- [ ] Slet/arkiver gamle kampagner
- [ ] Backup/restore funktionalitet

### UX
- [x] ~~Loading spinners ved lange operationer~~ (global loading overlay i layout.html)
- [x] ~~Konfirmation dialogs ved sletning~~ (allerede implementeret alle steder)
- [x] ~~Toast notifications i stedet for flash messages~~ (slide-in toasts med auto-dismiss)

---

## 🔮 Lav Prioritet / Future

### Friktionsprofil V2 (i gang)
- [x] Dokumentation opdateret (FRIKTIONSPROFIL_V2.md)
- [x] 8 nye kapacitets-spørgsmål ("tage sig sammen"-mekanikken)
- [x] 2 båndbredde-spørgsmål (løfte pres opad)
- [x] 6 screening-spørgsmål (hurtig vurdering)
- [x] Database udvidet med question_type og state_text_da
- [x] Profil vs Situations versioner (tekster klar)
- [ ] **Admin interface til spørgsmålsredigering og versionering**
  - Liste alle spørgsmål med felt, lag, type
  - Rediger tekst (profil + situation), scoring, sequence
  - Tilføj/fjern spørgsmål
  - Versionering af spørgsmålssæt
  - Intro/outro tekster per version

### Features
- [ ] Drag-and-drop reorganisering af units
- [ ] Custom spørgsmål per organisation
- [ ] Scheduled campaigns (send automatisk)
- [ ] API for integration med andre systemer

### Analytics
- [ ] Trend analyse (sammenlign kampagner over tid)
- [ ] Benchmarking på tværs af brancher
- [ ] AI-baseret indsigter fra fritekst kommentarer

### Performance
- [ ] Caching af aggregerede data
- [ ] Pagination i lange lister
- [ ] Database indexes optimering

---

## 🎯 STOR OPGAVE: Validering af spørgsmål

### Mål
Sikre at spørgsmålene præcist måler det teorien beskriver.

### Problem
- Når man beskriver adfærd til en chatbot med teorien som baggrund → præcist svar
- Når man tager testen med nuværende spørgsmål → mindre præcist svar
- Spørgsmålene fanger måske ikke nuancerne godt nok

### Tilgang
1. [ ] **Opdater teori-dokumentation** (Thomas arbejder på dette)
2. [ ] **Agentbaseret validering**
   - Beskriv personas med specifik adfærd
   - Lad agent svare på spørgsmål som persona
   - Sammenlign resultat med forventet teoretisk score
3. [ ] **Spørgsmåls-gennemgang**
   - Gennemgå hvert spørgsmål mod teorien
   - Vurder om det måler det rigtige felt/lag
   - Identificer manglende nuancer
4. [ ] **Brugertest**
   - Få rigtige brugere til at teste og give feedback

### Status
⏳ Afventer opdateret teori-dokumentation

---

## 🐛 Bugs & Issues

_Ingen kendte bugs pt._

---

## 🚀 Deploy & Hosting
- [x] Git repository opsat
- [x] GitHub push
- [x] Render deployment
- [x] Persistent disk konfigureret
- [x] Email tracking og templates
- [ ] **GDPR: Flyt Render service til EU (Frankfurt)**
- [ ] **Køb domain (friktionskompas.dk)**

---

## ✅ Færdige Features

### Core Features
- [x] Hierarkisk organisationsstruktur med `//` separator
- [x] CSV bulk upload med brugerinfo
- [x] Kampagne system med token generation
- [x] Aggregeret data visning på alle niveauer
- [x] Admin interface til styring
- [x] Test data generator

### Multi-tenant & Sikkerhed
- [x] Customer isolation i database
- [x] Login system med Admin/Manager roller
- [x] Customer dropdown og impersonation for admin
- [x] Bcrypt password hashing
- [x] Secret key fra environment variable

### KKC-Integration (Anders Trillingsgaard)
- [x] Mapping fra friktioner til KKC-elementer (MENING→KURS, TRYGHED/MULIGHED→KOORDINERING, BESVÆR→COMMITMENT)
- [x] KKC-anbefalinger med konkrete handlinger i `analysis.py`
- [x] KKC-badges i dashboard med gradient styling
- [x] KKC-reference til Anders Trillingsgaard i anbefalinger
- [x] Prioritering af anbefalinger efter severity
