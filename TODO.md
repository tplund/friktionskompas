# TODO - Friktionskompasset

## 🔥 Høj Prioritet

### 🔍 GO-LIVE AUDIT ✅ KOMPLET (2025-12-18)
Grundig gennemgang af hele systemet før go-live.

**Status:** Gennemført af Claude Code. Se AUDIT_*.md filer for detaljer.

#### 1. Test Coverage ✅
- [x] Kør fuld test suite - 282/296 tests passerer (95.3%)
- [x] Verificer at CI/CD stadig fungerer
- Se: `AUDIT_TEST_COVERAGE.md`

#### 2. Sikkerhed ✅
- [x] Fjernet debug endpoints med hardcoded secrets
- [x] Fixet SQL injection i backup restore og MCP server
- [x] Implementeret CSRF protection (Flask-WTF)
- [x] Implementeret rate limiting (Flask-Limiter)
- [x] Fixet hardcoded secret key i profil_app.py
- Se: `AUDIT_SECURITY_RESULTS.md`

#### 3. Kode Kvalitet ✅
- [x] Slettet 15 outdated Python scripts + old/ folder
- [x] Fjernet sikkerhedsrisiko (update_admin_password.py)
- [x] Fixed hardcoded sprog i survey_app.py
- Se: `AUDIT_CODE_QUALITY.md`

#### 4. UI Konsistens ✅
- [x] Terminologi OK ("måling" konsistent i UI)
- [x] Navigation OK (dropdowns)
- [x] Loading states OK
- [x] Mobile responsive OK
- Se: `AUDIT_UI_CONSISTENCY.md`

#### 5. Data & Performance ✅
- [x] Database indexes OK (20+)
- [x] Foreign keys OK (CASCADE DELETE)
- [x] Caching OK (TTL-baseret)
- Se: `AUDIT_DATA_PERFORMANCE.md`

#### 6. Dokumentation ✅
- [x] CLAUDE.md opdateret
- [x] TODO.md konsistent
- [x] ANALYSELOGIK.md korrekt
- Se: `AUDIT_DOCUMENTATION.md`

**Resultat:** Systemet er klar til go-live.

### 📝 Spørgsmåls-kvalitet (Sproglig + Videnskabelig Review)
Grundig gennemgang af alle spørgsmål i Friktionsprofilen.

**Baggrund:** Nogle spørgsmål har uklar formulering, f.eks.:
- "Jeg får hurtigt retning, når jeg tænker over noget"
- "Jeg reagerer hurtigt fysisk, når noget virker uforudsigeligt"

**Opgaver:**
- [ ] **Sproglig review** - Gennemgå alle 40 spørgsmål for klarhed, naturligt dansk, entydighed
- [ ] **Videnskabelig review** - Verificer at spørgsmål måler det intenderede (konstruktvaliditet)
- [ ] **Reverse-scored konsistens** - Tjek at reverse-scored spørgsmål er intuitive at besvare
- [ ] **Pilot-test** - Test med 5-10 brugere for forståelighed
- [ ] **Dokumenter ændringer** - Opdater ANALYSELOGIK.md med begrundelser

**Filer:**
- `db_profil.py` - `_insert_legacy_questions()` funktion
- `templates/profil/survey.html` - Visning af spørgsmål

**Prioritet:** Medium (efter go-live, før bred udrulning)

### Central Beregningsmotor (friction_engine) ✅ FÆRDIG
- [x] ~~**Opret `friction_engine.py`** - Samlet motor til alle friktionsberegninger~~
  - `calculate_field_scores(responses)` → {MENING: 3.5, TRYGHED: 2.8, ...}
  - `calculate_spread(responses)` → {MENING: 0.8, ...} (std_dev)
  - `calculate_gap(employee_scores, leader_scores)` → {...}
  - `get_warnings(scores, spread, gap)` → [Warning(...), ...]
  - `get_profile_type(scores)` → "travlt_team" | "siloed" | ...
- [x] ~~**Unit tests** for alle beregningsfunktioner~~ (36 tests, alle passerer)
- [x] ~~**Migrér beregninger fra `analysis.py`** til motoren~~
- [x] ~~**Migrér beregninger fra `admin_app.py`** til motoren~~
- [x] ~~**Dokumentér mekanik** i `ANALYSELOGIK.md`~~

**Formål:** Ét sted at opdatere når mekanikken ændres, lettere at teste, konsistens på tværs af alle visninger.

### Privacy by Design - B2C Local Storage ✅ FÆRDIG
- [x] ~~**Analyse af data flow** - Hvad skal gemmes hvor (server vs. local)~~
- [x] ~~**LocalStorage implementation** - Gem B2C profiler i browser (`static/js/profil-storage.js`)~~
- [x] ~~**Stateless API** - `/profil/api/questions` + `/profil/api/calculate` (gemmer intet)~~
- [x] ~~**Eksport/import** - JSON fil eksport/import i profil-storage.js~~
- [x] ~~**Client-side UI** - `/profil/local` med fuld survey + historik~~
- [x] ~~**Storage mode konfiguration** - `storage_mode` kolonne på assessment_types (local/server/both)~~
- [x] ~~**Admin UI** - Viser storage mode i /admin/assessment-types~~
- [ ] **Opt-in server storage** - Valgfrit for brugere der vil have backup (fremtidig)
- [x] ~~**Cookie consent** - Google Consent Mode v2 med privacy notice~~ (2025-12-22)
- [x] ~~**B2B uændret** - Enterprise kunder gemmer stadig centralt~~

**Storage modes:**
- `local` = Data gemmes KUN i browser (B2C: screening, profil_fuld, profil_situation, kapacitet)
- `server` = Data gemmes centralt (B2B: gruppe_friktion, gruppe_leder, baandbredde)
- `both` = Bruger vælger

**Formål:** GDPR compliance, lavere omkostninger, skalerbarhed, brugertillid. B2C data fylder ikke på serveren, ingen privacy-problemer.
**Se plan:** `PLAN_privacy_localStorage.md`

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
- [x] ~~**Route test** - Alle endpoints, navigation, 404 håndtering (38 tests)~~
- [x] ~~**Sikkerhedstest** - SQL injection, XSS, auth bypass, session hijacking (12 tests)~~
- [x] ~~**UI/UX test** - Playwright tests af brugerflows~~ (27 tests: login, navigation, localStorage profil, responsive)
- [x] ~~**Integration test** - End-to-end test af survey flow~~ (22 tests inkl. superadmin access tests)
- [x] ~~**Data isolation tests** - Verificerer at Herning/Esbjerg data er isoleret korrekt~~ (17 tests)
- [x] ~~**localStorage API tests** - Stateless API endpoints og storage_mode~~ (21 tests)
- [x] ~~**CI/CD** - GitHub Actions workflow kører tests automatisk ved push~~

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

### Brugerrettet Dokumentation ✅ FÆRDIG
- [x] ~~**Hjælpeside oprettet** - `/help` med vejledning til oprettelse, login, glemt password~~
- [x] ~~**Admin dokumentation** - Vejledning til admin-brugere~~ (`docs/ADMIN_VEJLEDNING.md`)
- [x] ~~**Manager dokumentation** - Vejledning til managers~~ (`docs/MANAGER_VEJLEDNING.md`)
- [x] ~~**Friktionsprofil dokumentation** - Forklaring af tests og resultater~~ (`FRIKTIONSPROFIL_V2.md`)
- [x] ~~**MCP Server dokumentation** - Dokumentation af Claude Code integration~~ (`MCP_SERVER.md`)

### Multi-tenant & Auth
- [x] ~~Implementer kunde/tenant isolation i database~~
- [x] ~~Tilføj auth system med Admin og Manager roller~~
- [x] ~~Admin kan se alle kunder, Manager kan kun se egen kunde~~
- [x] ~~Login page med session management~~
- [x] ~~Bcrypt password hashing (sikker)~~
- [x] ~~Secret key fra environment variable~~
- [x] ~~**Superadmin rolle** - Global admin der kan se alle kunder/domæner~~
- [x] ~~**Branding side** - Admin kan redigere branding for egne domæner~~
- [x] ~~CSRF protection~~ (Flask-WTF implementeret 2025-12-22)
- [x] ~~Rate limiting på login~~ (Flask-Limiter implementeret 2025-12-22)

### Admin API ✅ FÆRDIG
- [x] ~~**Intern Admin API** - API endpoints til automatiserede admin-operationer~~
  - `X-Admin-API-Key` header authentication
  - `/api/admin/status` - Database status og aktive domæner
  - `/admin/seed-domains` - Seed standard domæner
  - `/admin/seed-translations` - Seed oversættelser
  - `/api/admin/clear-cache` - Ryd alle caches
- [x] ~~**Dokumentation i CLAUDE.md** - API brug og eksempler~~
- [x] ~~**API sikkerhed** - Beskyttelse mod brute force og misbrug~~ (2025-12-22)
  - [x] Rate limiting på API endpoints (100/min GET, 20/min POST)
  - [x] Security headers (CSP, HSTS, X-Frame-Options, etc.)
  - [x] CORS konfiguration
  - [x] Secure session cookies
  - [ ] API key rotation UI (fremtidig)
  - [ ] IP whitelist option for enterprise (fremtidig)

### Kunde API ✅ FÆRDIG
- [x] ~~**Kunde-facing REST API** - Giv enterprise-kunder mulighed for at integrere med egne systemer~~
  - Autentifikation via API keys per kunde
  - GET `/api/v1/assessments` - Liste over målinger
  - GET `/api/v1/assessments/{id}` - Enkelt måling
  - GET `/api/v1/assessments/{id}/results` - Resultater for en måling
  - GET `/api/v1/units` - Organisationsoversigt
  - POST `/api/v1/assessments` - Opret ny måling
- [x] ~~**API key management** - Admin UI til oprettelse/rotation af API keys~~ (`/admin/api-keys`)
- [x] ~~**API dokumentation**~~ - OpenAPI spec + Swagger UI (`/api/docs`) + `API_DOCUMENTATION.md` (2025-12-22)
- [ ] **Webhook support** - Notifikationer ved events (fremtidig)

**Formål:** Enterprise-kunder kan integrere Friktionskompasset med deres HR-systemer, Power BI dashboards, etc.

### Situationsmåling ✅ FÆRDIG
Mål friktion for specifikke **handlinger** i specifikke **opgaver** - ikke personprofiler.
Bruges til udvikling af e-læring, kommunikation og adfærdsdesign.

- [x] ~~**Database udvidelse** - `tasks`, `actions`, `situation_assessments`, `situation_tokens`, `situation_responses` tabeller~~
- [x] ~~**Handlingsbaseret struktur** - Én opgave → 2-5 konkrete handlinger → måling per handling~~
- [x] ~~**Indirekte spørgsmål** - Undgå substitution (Kahneman-problemet)~~
  - Tryghed: "Hvor ubehageligt ville det være at lave en fejl her?"
  - Mening: "Hvor tydeligt kan du se, hvem handlingen hjælper?"
  - Kan: "Hvor sikkert ved du, hvad første skridt er?"
  - Besvær: "Hvor mange mentale stop er der typisk?"
- [x] ~~**Admin UI** - Opret opgaver og handlinger (CRUD med navigation)~~
- [x] ~~**Email-integration** - Mailjet invitationer til respondenter~~
- [x] ~~**Respondent flow** - 4 spørgsmål per handling, token-baseret adgang~~
- [x] ~~**Resultat-visning** - Prioriteret friktionsliste per handling med anbefalinger~~
- Se detaljeret plan: `PLAN_situationsmaaling.md`

**Formål:** Målrettet udvikling af læring og kommunikation. Svar på "hvad skal adresseres først?"

### Data Import/Export & Research ✅ DELVIST FÆRDIG (2025-12-20)
Bulk data håndtering til forskning, analyse og integration.

- [x] ~~**Bulk eksport** - JSON/CSV med fuld metadata~~ (`/admin/bulk-export`)
  - Måledata (svar, scores, timestamps)
  - Spørgeskema-definition
  - Felt-mapping (TRYGHED, MENING, KAN, BESVÆR)
  - Organisationsstruktur (valgfrit)
- [x] ~~**Anonymisering** - Irreversibel anonymisering til research~~ (fuld, pseudonymiseret, ingen)
- [x] ~~**Pseudonymisering** - Respondent-UUID som default~~ (SHA256-baseret UUID)
- [x] ~~**API eksport** - `/api/v1/export` for programmatisk adgang~~
- [ ] **Import** - Mapping-interface for eksterne data (Excel, Qualtrics, etc.) (fremtidig)
- [ ] **Research mode** - Særlig datatilstand uden personhenførbarhed (fremtidig)

**Formål:** Muliggør forskning, benchmarking og brug af data uden lock-in.

### GDPR & DPO-overblik ✅ FÆRDIG (2025-12-22)
Compliance-features der gør det nemt for kunder at dokumentere.

- [x] ~~**DPO Dashboard** - Samlet overblik for Data Protection Officers~~ (`/admin/gdpr`)
  - Dataoversigt (antal kunder, brugere, målinger, respondenter)
  - Data per kunde visning
  - Datatyper og formål
- [x] ~~**Sletning som feature** - Admin kan slette kundedata komplet~~ (GDPR sletning)
- [x] ~~**Auto-DPA** - Generer databehandleraftale med kundeinfo~~ (`/admin/dpa/<customer_id>`) (2025-12-22)
- [x] ~~**Underdatabehandlere** - Live liste med formål, datatyper, region~~ (i DPA template) (2025-12-22)
- [x] ~~**Retention-regler** - Auto-sletning efter X måneder~~ (`data_retention.py`, daglig cleanup) (2025-12-22)
- [x] ~~**Bruger-initieret sletning** - Self-service sletning med eksport~~ (`/my-data/export`, `/admin/my-account/delete`) (2025-12-22)
- [x] ~~**Privacy policy** - GDPR-compliant privacy side~~ (`/privacy`) (2025-12-22)
- [x] ~~**Email unsubscribe** - List-Unsubscribe headers og opt-out~~ (2025-12-22)

**Formål:** Compliance uden friktion. DPO'er kan dokumentere alt på 5 minutter.

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

### Preskriptiv Læring / Friktionsstyret Indhold (Fremtidsvision)
Brug friktionsmåling **før** læring til automatisk at matche indholdstype.

- [ ] **Indholdstype-mapping** - Knyt indholdstyper til friktionsfelter
  - TRYGHED/MENING friktion → Social proof, videoer med rigtige mennesker
  - KAN friktion → Instruktion, eksempler, step-by-step (tekst er ofte nok)
  - BESVÆR friktion → Tjeklister, links, overblik
- [ ] **Automatisk match** - Logik der vælger indhold baseret på måling
- [ ] **LMS integration** - Hooks til eksisterende læringssystemer
- [ ] **Illusorisk kunnen-detektion** - Sammenlign "oplevet kunnen" vs "faktisk usikkerhed"

**Hvorfor bedre end klassiske adaptive systemer:**
- Klassisk: Tester viden → giver næste opgave → antager viden er problemet
- Friktionsbaseret: Tester modstand → matcher indhold til barrieren → accepterer at adfærd stopper før viden

**Formål:** Giv kun instruktion når det er problemet. Motivér kun når det er problemet. Reducer når det er problemet.

Se detaljeret plan: `PLAN_situationsmaaling.md`

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
- [x] ~~**Mobile responsiveness** - Test og forbedring af mobilvisning~~
  - Admin layout.html: responsive nav, submenu scroll, stacked elements
  - Profil local.html: responsive tabs, questions, result grid
  - Breakpoints: mobile (<768px), tablet (768-1024px), desktop
- [x] ~~**Bedre fejlbeskeder** - Mere informative fejlbeskeder ved validation errors~~
  - FormValidation JS objekt med inline errors
  - CSS styling for has-error/has-success states
  - Danske fejlbeskeder
- [x] ~~**Loading states** - Tydeligere loading-indikatorer på lange operationer~~ (allerede implementeret)
- [x] ~~**Keyboard navigation** - Tab-navigation og Enter-submit på forms~~
  - Enter submitter fra sidste felt/password
  - Escape lukker dropdowns
  - Focus-visible styling

### Dokumentation
- [ ] **Admin dokumentation** - Vejledning til admin-brugere (målinger, organisationer, analyser)
- [ ] **Manager dokumentation** - Vejledning til managers (resultater, rapporter)
- [ ] **Friktionsprofil dokumentation** - Forklaring af tests og resultater til slutbrugere

### Teknisk
- [x] ~~**Session timeout** - Auto-logout efter 8 timers inaktivitet~~
  - PERMANENT_SESSION_LIFETIME = 8 timer
  - SESSION_REFRESH_EACH_REQUEST = True
  - session.permanent = True på alle login paths
- [x] ~~**Audit log** - Logning af vigtige handlinger (sletninger, ændringer)~~ (`audit.py` + `/admin/audit-log` UI)
- [ ] **Database vacuum** - Automatisk cleanup af slettet data

### SEO & Tilgængelighed
- [x] ~~**Webtilgængelighed (a11y)**~~
  - Skip-link til hovedindhold
  - ARIA roles og labels på navigation, formularer, toasts
  - Focus-visible styling for keyboard navigation
  - Dynamisk lang attribut baseret på brugerens sprog
- [x] ~~**Teknisk SEO**~~
  - robots.txt med Disallow for admin/auth
  - Dynamisk sitemap.xml
  - Meta descriptions på offentlige sider
  - Open Graph + Twitter Card meta tags
  - Canonical URLs
  - OG image (SVG)
- [x] ~~**Cookie consent med Google Consent Mode v2**~~
  - GDPR-compliant cookie banner
  - 4 kategorier: nødvendige, funktionelle, statistik, marketing
  - Google Consent Mode v2 integration (alle 7 consent signals)
  - DataLayer events for GTM triggers

### Marketing & Analytics
- [x] ~~**Google Tag Manager (GTM)**~~
  - [x] ~~Opret GTM containere~~ (GTM-KRM92FXQ for .dk, GTM-P7J74JZZ for .com)
  - [x] ~~Implementer domæne-baseret GTM~~ (`templates/macros/gtm.html`)
  - [x] ~~Integrer i alle public templates~~ (10 templates opdateret)
  - [ ] Opsæt GA4 tag i GTM (med consent mode)
  - [ ] Opsæt conversion events (profil startet, profil færdig, registrering)
- [x] ~~**Google Analytics 4 (GA4)**~~
  - [x] ~~Opret GA4 property~~ (G-FTWM9JK2FW)
  - [ ] Konfigurer GA4 tag i GTM
  - [ ] Opsæt key events/conversions
  - [ ] Dashboard til B2C trafik og funnel
- [ ] **Google Search Console**
  - [ ] Verificer friktionskompasset.dk
  - [ ] Verificer frictioncompass.com
  - [ ] Submit sitemaps
  - [ ] Overvåg indeksering og søgeperformance
- [ ] **Performance tracking**
  - [ ] Core Web Vitals monitoring
  - [ ] PageSpeed Insights baseline
  - [ ] Bounce rate og session duration analyse
- [x] ~~**GTM MCP Server**~~ - Tilføjet til .mcp.json for AI-styret GTM konfiguration

### B2C Forberedelse
- [x] ~~**Landing page**~~ - `/landing` med hero, features, privacy sektion, CTA
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

## 🔧 Teknisk Gæld (Audit 2025-12-20)

Baseret på fuld teknisk audit. Se `docs/AUDIT_2025-12-20.md` for detaljer.

### ✅ Kritisk - Fikset
- [x] ~~**23 bare except-klausuler** - Tilføjet specifik exception handling~~ (fikset 2025-12-20)
- [x] ~~**Manglende database indexes** - Tilføjet composite index på responses~~ (fikset 2025-12-20)
- [x] ~~**survey_app.py dead code** - Fjernet ubrugt fil~~ (fikset 2025-12-20)

### 🟡 Gør Snart (inden 1 måned)
- [x] ~~**Opdel admin_app.py i blueprints**~~ ✅ FÆRDIG (2025-12-22)
  - [x] auth_helpers.py - Shared auth decorators
  - [x] template_helpers.py - Shared template helpers
  - [x] blueprints/public.py - Landing, robots.txt, sitemap
  - [x] blueprints/api_admin.py - Admin API endpoints
  - [x] blueprints/api_customer.py - Customer REST API
  - [x] blueprints/auth.py - Login, logout, OAuth, register
  - [x] blueprints/admin_core.py - Dashboard, GDPR, audit log
  - [x] blueprints/assessments.py - Assessment CRUD
  - [x] blueprints/units.py - Unit management
  - [x] blueprints/customers.py - Customer/domain management
  - [x] blueprints/export.py - Backup/export
  - [x] blueprints/dev_tools.py - Development tools
- [x] ~~**Centralisér get_db() i db.py**~~ ✅ FÆRDIG - Ny `db.py` med get_db() og get_db_connection() (2025-12-22)
- [x] ~~**Fix N+1 query i get_assessment_overview()**~~ ✅ FÆRDIG - Optimized with CTEs (2025-12-22)
- [x] ~~**Tilføj caching til get_detailed_breakdown()**~~ ✅ FÆRDIG - @cached(ttl=300) decorator (2025-12-22)
- [x] ~~**Opret DEPLOYMENT_GUIDE.md**~~ ✅ FÆRDIG - `DEPLOYMENT_CHECKLIST.md` (2025-12-22)
- [x] ~~**Opret API_DOCUMENTATION.md**~~ ✅ FÆRDIG (2025-12-22)
- [x] ~~**Erstat xhtml2pdf med WeasyPrint**~~ ✅ FÆRDIG - Replaced deprecated library (2025-12-22)

### 🟢 Kan Vente (inden 3 måneder)
- [x] ~~**Implementér struktureret logging**~~ ✅ FÆRDIG - `logging_config.py` med JSON format, file rotation, security logging (2025-12-22)
- [ ] **Konsolidér profil-systemer** - Anbefales IKKE (de er to forskellige målesystemer)
- [x] ~~**App factory pattern**~~ ✅ FÆRDIG - `app_factory.py` med create_app() (2025-12-22)
- [x] ~~**Øg test coverage**~~ ✅ FÆRDIG - Fra 6% til 39% med 1000+ nye tests (2025-12-22)
- [x] ~~**Opret DATABASE_SCHEMA.md**~~ ✅ FÆRDIG - Komplet med ER-diagram og tabelbeskrivelser (2025-12-22)
- [ ] **Planlæg Python 3.11 upgrade** - 3.10 end-of-life jan 2026

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
- [ ] **Uptime monitoring** - Opsæt uptimerobot.com for alle produktions-sites
  - friktionskompasset.dk
  - frictioncompass.com
  - herning.friktionskompasset.dk (når aktiv)
- [ ] **Python 3.12+ opgradering** - Nuværende 3.10 EOL oktober 2026
  - Lokal: Installer Python 3.12 eller 3.13
  - Render: Opdater `runtime.txt` til `python-3.12.x`
  - Test alle dependencies med ny version
  - Opdater GitHub Actions workflow
  - Bemærk: 3.13 har bedre performance, 3.12 er mere stabil

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
