# TODO - Friktionskompasset

## 🔥 Høj Prioritet

### Central Beregningsmotor (friction_engine) ✅
- [x] ~~**Opret `friction_engine.py`** - Samlet motor til alle friktionsberegninger~~
  - `calculate_field_scores(responses)` → {MENING: 3.5, TRYGHED: 2.8, ...}
  - `calculate_spread(responses)` → {MENING: 0.8, ...} (std_dev)
  - `calculate_gap(employee_scores, leader_scores)` → {...}
  - `get_warnings(scores, spread, gap)` → [Warning(...), ...]
  - `get_profile_type(scores)` → "travlt_team" | "siloed" | ...
- [x] ~~**Unit tests** for alle beregningsfunktioner~~ (36 tests, alle passerer)
- [ ] **Migrér beregninger fra `analysis.py`** til motoren
- [ ] **Migrér beregninger fra `admin_app.py`** til motoren
- [ ] **Dokumentér mekanik** i `ANALYSELOGIK.md`

**Formål:** Ét sted at opdatere når mekanikken ændres, lettere at teste, konsistens på tværs af alle visninger.

### Privacy by Design - B2C Local Storage 🆕
- [ ] **Analyse af data flow** - Hvad skal gemmes hvor (server vs. local)
- [ ] **LocalStorage implementation** - Gem B2C profiler krypteret i browser
- [ ] **Stateless API** - Server serverer spørgsmål + beregner resultater, gemmer intet
- [ ] **Eksport/import** - Bruger kan downloade/uploade sin profil som JSON
- [ ] **Opt-in server storage** - Valgfrit for brugere der vil have backup
- [ ] **Cookie consent** - Opdater privacy notice for localStorage brug
- [ ] **B2B uændret** - Enterprise kunder gemmer stadig centralt

**Formål:** GDPR compliance, lavere omkostninger, skalerbarhed, brugertillid. B2C data fylder ikke på serveren, ingen privacy-problemer.

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
- [x] ~~**UI/UX test** - Playwright tests af brugerflows~~ (19 tests: login, dropdown navigation, organisation tree, campaigns, backup, responsive)
- [x] ~~**Integration test** - End-to-end test af survey flow~~ (22 tests inkl. superadmin access tests)
- [x] ~~**Data isolation tests** - Verificerer at Herning/Esbjerg data er isoleret korrekt~~ (17 tests - tjekker faktisk HTML content, ikke bare status 200)
- [x] ~~**CI/CD** - GitHub Actions workflow kører tests automatisk ved push~~ (123 tests total)

### ⚠️ VIGTIGT - Dokumentation
- [ ] **Ved ALLE ændringer i analyselogik:** Opdater `ANALYSELOGIK.md`
  - Substitution thresholds (tid_bias ≥ 0.6, underliggende ≥ 3.5)
  - KKC severity levels (høj < 2.5, medium < 3.5)
  - Leder gap threshold (> 1.0 point forskel)
  - Leder blokeret threshold (både team og leder < 3.5)
  - Farvecodning (grøn ≥ 70%, gul ≥ 50%, rød < 50%)

- [ ] **Ved ALLE ændringer i brugerflows:** Opdater `/help` siden (`templates/help.html`)
  - Login flows (password, email-kode, social)
  - Registrering
  - Glemt password
  - FAQ sektion

### Brugerrettet Dokumentation
- [x] ~~**Hjælpeside oprettet** - `/help` med vejledning til oprettelse, login, glemt password~~
- [ ] **Admin dokumentation** - Vejledning til admin-brugere (målinger, organisationer, analyser)
- [ ] **Manager dokumentation** - Vejledning til managers (resultater, rapporter)
- [ ] **Friktionsprofil dokumentation** - Forklaring af tests og resultater til slutbrugere

### Multi-tenant & Auth
- [x] ~~Implementer kunde/tenant isolation i database~~
- [x] ~~Tilføj auth system med Admin og Manager roller~~
- [x] ~~Admin kan se alle kunder, Manager kan kun se egen kunde~~
- [x] ~~Login page med session management~~
- [x] ~~Bcrypt password hashing (sikker)~~
- [x] ~~Secret key fra environment variable~~
- [x] ~~**Superadmin rolle** - Global admin der kan se alle kunder/domæner~~
- [x] ~~**Branding side** - Admin kan redigere branding for egne domæner~~
- [ ] CSRF protection (deferred til produktion)
- [ ] Rate limiting på login (deferred til produktion)

### Social Login & SSO (i gang)
- [x] ~~**Database struktur** - `auth_providers` JSON felt på customers/domains, `user_oauth_links` tabel~~
- [x] ~~**OAuth modul** - `oauth.py` med Authlib integration~~
- [x] ~~**Microsoft OAuth** (Azure AD) - routes og callback~~
- [x] ~~**Google OAuth** - routes og callback~~
- [x] ~~**Login-side opdateret** - Viser OAuth buttons baseret på domæne-config~~
- [x] ~~**Admin UI til auth konfiguration** - Konfigurer providers per kunde/domæne (superadmin)~~
- [x] ~~**Domæne-config** - friktionskompasset.dk (alle providers), frictioncompass.com (kun Google)~~
- [x] ~~**Opsæt OAuth credentials på Render** - Opret apps hos Google/Microsoft, sæt env vars~~
- [ ] **Apple Sign-In** - B2C (iOS brugere)
- [ ] **Facebook Login** - B2C
- [ ] **SAML SSO** - Enterprise kunder
- [ ] **OIDC SSO** - Enterprise kunder
- Se detaljeret plan: `PLAN_social_login.md`

### B2C Selvregistrering & Passwordless Login ✅ NY
- [x] ~~**B2C kunde** - Auto-oprettet "B2C Brugere" kunde til selvregistrerede brugere~~
- [x] ~~**User rolle** - Ny 'user' rolle for B2C brugere (kan tage tests, ikke admin adgang)~~
- [x] ~~**Passwordless login** - Login med email-kode (som Canva) - 6-cifret kode, 15 min udløb~~
- [x] ~~**Selvregistrering** - Opret konto med email-verifikation~~
- [x] ~~**Glemt password** - Nulstil password med email-kode~~
- [x] ~~**Email templates** - Flotte HTML emails til login/register/reset koder~~
- [x] ~~**Login-side opdateret** - Links til registrering, glemt password, og email-kode login~~
- [x] ~~**User hjemmeside** - Dedikeret side for B2C brugere med adgang til friktionsprofil tests~~

#### Aktivering af OAuth (kræver miljøvariabler)
```bash
# Microsoft Azure AD
MICROSOFT_CLIENT_ID=xxx
MICROSOFT_CLIENT_SECRET=xxx

# Google
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx
```

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
- [x] ~~**Organiser navigation med undermenuer** - Dashboard først, dropdown-menuer for Målinger, Friktionsprofil, Organisation, Indstillinger~~

### Målingstype-konfiguration ✅ NY
- [x] ~~**Database tabeller** - assessment_types, customer_assessment_types, domain_assessment_types, presets~~
- [x] ~~**7 målingstyper** - screening, profil_fuld, profil_situation, gruppe_friktion, gruppe_leder, kapacitet, baandbredde~~
- [x] ~~**3 presets** - B2C Individuel (default), B2B Standard, Enterprise Full~~
- [x] ~~**Helper funktion** - get_available_assessments() med fallback: domain → customer → preset → alle~~
- [x] ~~**Admin UI** - /admin/assessment-types (superadmin) + per-kunde konfiguration~~
- Se detaljeret plan: `PLAN_maalingstyper.md`

### CSV Import
- [x] ~~Semikolon separator (Excel standard)~~
- [x] ~~UTF-8 BOM encoding~~
- [x] ~~Auto-opret kontakter fra CSV~~
- [x] ~~Bedre fejlhåndtering og preview før import~~ (2-trins flow med drag-drop, hierarki-preview)

---

## 📊 Medium Prioritet

### Rapportering
- [x] ~~Eksporter resultater til PDF~~ (xhtml2pdf med dedikeret PDF template)
- [x] ~~Email notifikationer når måling er færdig~~ (auto-send ved 100% svarprocent, DA/EN templates)
- [x] ~~Dashboard med nøgletal~~ (/admin/noegletal med stats, friktionsfelter, seneste målinger, per-kunde oversigt)

### Data Management
- [ ] Bulk edit af organisationer
- [x] ~~Slet/arkiver gamle kampagner~~ (slet-knap på campaigns_overview med bekræftelse)
- [x] ~~Backup/restore funktionalitet~~ (/admin/backup med download JSON og restore med merge/replace)

### UX
- [x] ~~Loading spinners ved lange operationer~~ (global loading overlay i layout.html)
- [x] ~~Konfirmation dialogs ved sletning~~ (allerede implementeret alle steder)
- [x] ~~Toast notifications i stedet for flash messages~~ (slide-in toasts med auto-dismiss)

---

## 🌐 Multi-Domain Setup ✅ FÆRDIG

### Implementeret
- [x] Database: `domains` tabel med mapping (sprog, kunde, branding)
- [x] Middleware: `before_request` detecter domæne → sætter sprog/kunde/branding
- [x] Admin UI: `/admin/domains` CRUD interface
- [x] Render: Custom domains via API (frictioncompass.com, herning.frictioncompass.com)
- [x] DNS: Cloudflare konfigureret med SSL, HSTS, proxy
- [x] Domæner live:
  - `frictioncompass.com` (primær, engelsk)
  - `herning.frictioncompass.com` (kunde-subdomain)
  - `friktionskompasset.dk` (dansk)

---

## 🔮 Lav Prioritet / Future

### B2C Freemium & Public Access ⏸️ AFVENTER BUSINESS ANALYSE
- [ ] **Business analyse** - prissætning, freemium-struktur, målgruppe
- [ ] **Betalingsintegration** - Stripe (eller MobilePay DK)
- [ ] **Flere OAuth providers** - Apple Sign-In, Facebook Login
- [ ] **Feature gating** - "Upgrade to unlock" UI
- [ ] **Marketing tracking** - Facebook Pixel, GA4, LinkedIn Insight
- [ ] **SoMe ads automation** - Guardrails, budget-styring, A/B test
- Se detaljeret plan: `PLAN_freemium_b2c.md`

### B2C Friktionsprofil-produkter (Idéer til automatiseret markedsføring)

> 💡 **Idé**: Bruge Facebook/Instagram annoncer til at drive trafik til gratis friktionsprofil-tests. Målgrupper med høj søgevolumen.

#### Produkt 1: Parforhold-profil
- [ ] **Landing page** - "Test dit parforhold" / "Er I på samme side?"
- [ ] **Invitation flow** - Bruger tager test → inviterer partner via email/SMS
- [ ] **Par-sammenligning** - Vis begges profiler side om side
- [ ] **Gap-analyse** - Hvor er I uenige? Hvor supplerer I hinanden?
- [ ] **Facebook annoncering** - Målret par, nyforlovede, samboende
- [ ] **Automatiseret A/B test** - Forskellige hooks ("kommunikation", "stress", "prioriteter")

#### Produkt 2: ADHD Friktionsprofil
- [ ] **Landing page** - "Har du ADHD-friktion?" / "Hvorfor føles alting svært?"
- [ ] **Tilpassede spørgsmål** - Fokus på executive function, tidsstyring, prioritering
- [ ] **Resultat-fortolkning** - ADHD-venlig forklaring af friktionspunkter
- [ ] **Handlingsplan** - Konkrete tips baseret på profil
- [ ] **Facebook/Google Ads** - Høj søgevolumen på ADHD-relaterede termer
- [ ] **SEO indhold** - Blog posts om ADHD og friktion

#### Produkt 3: Karriere/Job-profil
- [ ] **Landing page** - "Passer dit job til dig?" / "Hvorfor er du udbrændt?"
- [ ] **Arbejdsplads-fokus** - Mening, tryghed, kapacitet i job-kontekst
- [ ] **Karrierevejledning** - Anbefalinger baseret på profil
- [ ] **LinkedIn annoncering** - Målret jobsøgende, utilfredse medarbejdere

#### Fælles infrastruktur
- [ ] **Automatiseret annoncering** - Budget-styring, auto-pause ved dårlig ROI
- [ ] **Conversion tracking** - Facebook Pixel, GA4 events
- [ ] **A/B test framework** - Landing pages, annoncetekster, CTA'er
- [ ] **Email sequences** - Nurture flow efter gratis test
- [ ] **Upsell til betalt** - Premium rapport, coaching, etc.

### Friktionsprofil V2 (i gang)
- [x] Dokumentation opdateret (FRIKTIONSPROFIL_V2.md)
- [x] 8 nye kapacitets-spørgsmål ("tage sig sammen"-mekanikken)
- [x] 2 båndbredde-spørgsmål (løfte pres opad)
- [x] 6 screening-spørgsmål (hurtig vurdering)
- [x] Database udvidet med question_type og state_text_da
- [x] Profil vs Situations versioner (tekster klar)
- [ ] **Admin interface til spørgsmålsredigering og versionering** ⏸️ VENTER
  - ⏸️ Afventer: Teorigrundlaget forventes at ændre sig
  - Liste alle spørgsmål med felt, lag, type
  - Rediger tekst (profil + situation), scoring, sequence
  - Tilføj/fjern spørgsmål
  - Versionering af spørgsmålssæt
  - Intro/outro tekster per version

### Features
- [x] ~~Drag-and-drop reorganisering af units~~ (Flyt-mode med visuel feedback)
- [ ] Custom spørgsmål per organisation
- [x] ~~Scheduled campaigns (send automatisk)~~ (Planlæg målinger til fremtidigt tidspunkt, baggrunds-scheduler, admin UI)
- [ ] API for integration med andre systemer

### Analytics
- [x] ~~Trend analyse~~ (sammenlign kampagner over tid, Chart.js grafer, filter per enhed)
- [ ] Benchmarking på tværs af brancher (lav prioritet)
- [ ] AI-baseret indsigter fra fritekst kommentarer (fremtidig overvejelse)
  - ⚠️ **Note**: Nogle kunder kan være skeptiske over for AI-brug - overvej opt-in model

### Performance
- [x] ~~Caching af aggregerede data~~ (cache.py modul med TTL, @cached decorator på analyse-funktioner)
- [x] ~~Pagination helper~~ (Pagination klasse i cache.py, klar til brug)
- [x] ~~Database indexes optimering~~ (nye indexes: campaigns_target_unit, campaigns_created_at, campaigns_status, responses_created_at)

---

## 🔧 Små Forbedringer (Nice-to-have)

### UX/UI
- [ ] **Mobile responsiveness** - Test og forbedring af mobilvisning
- [ ] **Bedre fejlbeskeder** - Mere informative fejlbeskeder ved validation errors
- [ ] **Loading states** - Tydeligere loading-indikatorer på lange operationer
- [ ] **Keyboard navigation** - Tab-navigation og Enter-submit på forms

### Dokumentation
- [ ] **Admin dokumentation** - Vejledning til admin-brugere (målinger, organisationer, analyser)
- [ ] **Manager dokumentation** - Vejledning til managers (resultater, rapporter)
- [ ] **Friktionsprofil dokumentation** - Forklaring af tests og resultater til slutbrugere

### Teknisk
- [ ] **Session timeout** - Auto-logout efter inaktivitet
- [x] ~~**Audit log** - Logning af vigtige handlinger (sletninger, ændringer)~~ (`audit.py` + `/admin/audit-log` UI)
- [ ] **Database vacuum** - Automatisk cleanup af slettet data

### B2C Forberedelse
- [ ] **Landing page** - Public info-side om Friktionskompasset
- [ ] **Prøveresultat** - Teaser-visning af resultater før betaling
- [ ] **Email capture** - Nyhedsbrev signup på landing page

---

## 🎯 STOR OPGAVE: Validering af spørgsmål ⏸️ VENTER

> ⚠️ **VIGTIGT**: Denne opgave er sat på pause. Teorigrundlaget forventes at ændre sig.

### Mål
Sikre at spørgsmålene præcist måler det teorien beskriver.

### Problem
- Når man beskriver adfærd til en chatbot med teorien som baggrund → præcist svar
- Når man tager testen med nuværende spørgsmål → mindre præcist svar
- Spørgsmålene fanger måske ikke nuancerne godt nok

### Forudsætninger
- [ ] Frankfurt-migrering gennemført (GDPR compliance)
- [ ] Agentic system opsat (til automatiseret testning)
- [ ] Opdateret teori-dokumentation fra Thomas

### Tilgang
1. [ ] **Opsæt agentic system til test-validering**
   - System der kan simulere besvarelser baseret på personas
   - Automatiseret sammenligning af forventet vs. faktisk score
   - Regression testing ved spørgsmålsændringer
2. [ ] **Opdater teori-dokumentation** (Thomas arbejder på dette)
3. [ ] **Agentbaseret validering**
   - Beskriv personas med specifik adfærd
   - Lad agent svare på spørgsmål som persona
   - Sammenlign resultat med forventet teoretisk score
4. [ ] **Spørgsmåls-gennemgang**
   - Gennemgå hvert spørgsmål mod teorien
   - Vurder om det måler det rigtige felt/lag
   - Identificer manglende nuancer
5. [ ] **Brugertest**
   - Få rigtige brugere til at teste og give feedback

### Status
⏳ Venter på: Frankfurt-migrering + agentic system opsætning

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
- [x] **GDPR: Render service i EU (Frankfurt)** ✅
- [x] **Domæner: frictioncompass.com + friktionskompasset.dk** ✅

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
