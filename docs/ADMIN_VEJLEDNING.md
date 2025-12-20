# Administrator Vejledning - Friktionskompasset

Denne vejledning er til administratorer (admin/superadmin) der skal opsætte og administrere Friktionskompasset.

---

## Indhold

1. [Overblik](#1-overblik)
2. [Dashboard](#2-dashboard)
3. [Organisationer](#3-organisationer)
4. [Målinger](#4-målinger)
5. [Analyser](#5-analyser)
6. [Friktionsprofil](#6-friktionsprofil)
7. [Situationsmåling](#7-situationsmåling)
8. [Brugere og Kunder](#8-brugere-og-kunder)
9. [Indstillinger](#9-indstillinger)
10. [Fejlfinding](#10-fejlfinding)

---

## 1. Overblik

### Roller

| Rolle | Rettigheder |
|-------|-------------|
| **Superadmin** | Fuld adgang til alle kunder og systemindstillinger |
| **Admin** | Fuld adgang til én kundes data |
| **Manager** | Kan se resultater for tildelte enheder |
| **User** | Kan tage friktionsprofil tests (B2C) |

### Navigation

Menuen er organiseret i dropdown-grupper:
- **Dashboard** - Samlet overblik med KPIs og advarsler
- **Målinger** - Opret og administrer målinger
- **Situationsmålinger** - Opgave-baserede målinger
- **Friktionsprofil** - Individuelle profiler
- **Organisation** - Organisationstræ og kunder
- **Indstillinger** - Branding, email, backup

---

## 2. Dashboard

**URL:** `/admin`

Dashboard v2 viser:

### Friktionsoversigt
Fire kort med gennemsnitlig score for hver friktionsdimension:
- **TRYGHED** - Psykologisk tryghed
- **MENING** - Oplevet mening og formål
- **KAN** - Oplevelse af kompetence
- **BESVÆR** - Oplevelse af unødvendig friktion

**Farvekoder:**
- Grøn (≥ 3.5): Lav friktion
- Gul (2.5-3.5): Moderat friktion
- Rød (< 2.5): Høj friktion

### Analyse per enhed
Hierarkisk visning med scores for hver organisationsenhed. Klik på en enhed for at drill-down.

### Sidebar
- **Mini-stats**: Antal enheder, målinger, svar
- **Advarsler**: Enheder med kritisk lave scores
- **Trend**: Graf over tid (filtrer per enhed)
- **Seneste målinger**: Hurtig adgang

---

## 3. Organisationer

**URL:** `/admin/units`

### Opret organisation
1. Klik **"Opret"** eller **"+"** ved en eksisterende enhed
2. Udfyld:
   - **Navn**: Organisationens navn
   - **Overordnet**: Vælg parent-enhed (eller ingen for toplevel)
   - **Antal medarbejdere**: Til anonymitetsberegning

### Hierarki
Organisationer vises som træstruktur med niveauer:
```
Herning Kommune (toplevel)
  └── Teknik (forvaltning)
      └── IT Afdelingen (område)
          └── Support Team (enhed)
```

### Flyt enheder
1. Klik **"⇅ Flyt"** for at aktivere flyt-mode
2. Træk enheder til ny placering
3. Klik **"⇅ Afslut flyt"** når færdig

### Bulk-sletning
1. Klik **"Vælg flere"**
2. Vælg enheder (checkboxes)
3. Klik **"Slet valgte"**

### CSV Import
1. Klik **"Upload CSV"**
2. Upload fil med semikolon-separator og UTF-8 encoding
3. Bekræft preview og importer

**CSV Format:**
```csv
navn;overordnet;email;medarbejdere
IT Afdelingen;Teknik;chef@firma.dk;25
```

---

## 4. Målinger

**URL:** `/admin/assessments-overview`

### Opret ny måling
1. Gå til **Målinger → Ny måling**
2. Udfyld:
   - **Navn**: Beskrivende navn (fx "Q4 2025 Måling")
   - **Periode**: Valgfri (fx "Q4 2025")
   - **Målgruppe**: Vælg organisationsenhed
   - **Anonym**: Ja/nej (minimum 5 svar for anonymitet)
3. Klik **"Opret måling"**

### Send invitationer
1. Åbn målingen
2. Klik **"Send invitationer"**
3. Vælg kontakter eller indtast emails
4. Klik **"Send"**

### Planlagte målinger
1. Gå til **Målinger → Planlagte**
2. Klik **"Ny planlagt måling"**
3. Vælg dato/tid for afsendelse
4. Systemet sender automatisk når tiden kommer

### Påmindelser
1. Åbn en aktiv måling
2. Klik **"Send påmindelse"**
3. Kun respondenter der ikke har svaret modtager påmindelse

---

## 5. Analyser

**URL:** `/admin/analyser`

### Detaljeret analyse
Viser for hver enhed:
- **Friktionsscores** per dimension (TRYGHED, MENING, KAN, BESVÆR)
- **Medarbejder vs. Leder** gap-analyse
- **Spredning** (standardafvigelse)
- **Substitution** (Kahneman-detektion)
- **KKC-anbefalinger** (Kurs, Koordinering, Commitment)

### Ikoner og advarsler

| Ikon | Betydning |
|------|-----------|
| 🔴 | Kritisk lav score (< 2.5) |
| 🟡 | Moderat score (2.5-3.5) |
| 🟢 | God score (≥ 3.5) |
| ⚠️ | Høj spredning eller gap |
| 🔄 | Substitution detekteret |
| 🔒 | Leder blokeret |

### Eksporter til PDF
1. Åbn en måling
2. Klik **"Eksporter PDF"**
3. Download genereret rapport

---

## 6. Friktionsprofil

**URL:** `/admin/profiler`

### Typer

| Type | Beskrivelse | Storage |
|------|-------------|---------|
| **Screening** | Hurtig 6-spørgsmåls test | LocalStorage |
| **Fuld profil** | 30+ spørgsmål | LocalStorage |
| **Situation** | Kontekst-specifik | LocalStorage |

### Inviter til profil
1. Gå til **Friktionsprofil → Alle profiler**
2. Klik **"Inviter"**
3. Indtast email og vælg profiltype
4. Klik **"Send invitation"**

### B2C (Lokal profil)
Brugere kan tage profiler uden server-lagring:
- URL: `/profil/local`
- Data gemmes kun i brugerens browser
- Eksport/import som JSON-fil

---

## 7. Situationsmåling

**URL:** `/admin/tasks`

Situationsmåling måler friktion for specifikke **handlinger** i specifikke **opgaver**.

### Opret opgave
1. Gå til **Situationsmålinger → Ny opgave**
2. Udfyld:
   - **Opgavenavn**: Fx "Indberetning af ferie"
   - **Beskrivelse**: Kontekst for respondenter
3. Tilføj 2-5 handlinger:
   - Fx "Log ind i HR-systemet"
   - Fx "Find ferieformularen"
   - Fx "Udfyld og indsend"

### Send situationsmåling
1. Åbn opgaven
2. Klik **"Send til respondenter"**
3. Vælg emails eller organisationsenhed
4. Respondenter modtager 4 spørgsmål per handling

### Resultater
Viser friktionsniveau per handling med anbefalinger:
- Høj TRYGHED-friktion → Behov for social proof
- Høj KAN-friktion → Behov for instruktion
- Høj BESVÆR-friktion → Behov for forenkling

---

## 8. Brugere og Kunder

### Kunder (Superadmin)
**URL:** `/admin/customers`

1. Klik **"Ny kunde"**
2. Udfyld navn og kontaktinfo
3. Tildel domæner og branding

### Brugere
1. Gå til **Organisation → Kunder & brugere**
2. Klik **"Ny bruger"**
3. Udfyld:
   - Email
   - Navn
   - Rolle (admin/manager/user)
   - Kunde-tilknytning

### Impersonering (Superadmin)
1. Gå til **Indstillinger → Impersoner bruger**
2. Vælg bruger
3. Du ser nu systemet som den valgte bruger
4. Klik **"Stop impersonering"** for at vende tilbage

---

## 9. Indstillinger

### Branding
**URL:** `/admin/my-branding`
- Logo upload
- Primær farve
- Virksomhedsnavn

### Email Templates
**URL:** `/admin/email-templates`
- Tilpas invitation, påmindelse, og notifikationstekster
- Dansk og engelsk versioner

### Email Status
**URL:** `/admin/email-stats`
- Se sendte emails og leveringsstatus
- Fejlrapporter

### Backup & Restore
**URL:** `/admin/backup`
1. **Download backup**: Eksporter al data som JSON
2. **Restore**: Upload backup-fil med valg om merge eller replace

### Audit Log
**URL:** `/admin/audit-log`
- Se alle handlinger udført i systemet
- Hvem, hvad, hvornår

### GDPR
**URL:** `/admin/gdpr`
- Dataoversigt
- Sletningsanmodninger

---

## 10. Fejlfinding

### Bruger kan ikke logge ind
1. Tjek at brugeren eksisterer
2. Prøv "Glemt password" flow
3. Tjek at domænet har korrekte auth-indstillinger

### Emails modtages ikke
1. Tjek spam-mappe
2. Tjek `/admin/email-stats` for fejl
3. Verificer afsender-domæne i Mailjet

### Data vises ikke
1. Tjek at målingen har svar (minimum 1)
2. For anonyme målinger: minimum 5 svar
3. Tjek customer-filter (superadmin)

### Langsom performance
1. Ryd cache: `/admin/dev-tools` → Clear Cache
2. Tjek database størrelse i backup
3. Kontakt support ved vedvarende problemer

---

## Support

- **Email:** support@friktionskompasset.dk
- **Hjælpeside:** `/help`

---

*Sidst opdateret: 2025-12-20*
