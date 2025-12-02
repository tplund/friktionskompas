# TODO - Friktionskompasset

## 🔥 Høj Prioritet

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
- [ ] "Slet alle data" knap (kun synlig for Admin rolle) - REMOVED (dangerous)
- [x] ~~Breadcrumbs i alle admin views~~

### CSV Import
- [x] ~~Semikolon separator (Excel standard)~~
- [x] ~~UTF-8 BOM encoding~~
- [x] ~~Auto-opret kontakter fra CSV~~
- [ ] Bedre fejlhåndtering og preview før import

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
- [ ] Loading spinners ved lange operationer
- [ ] Konfirmation dialogs ved sletning
- [ ] Toast notifications i stedet for flash messages

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
