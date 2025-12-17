# Plan: Situationsmåling & Friktionsstyret Læring

## Executive Summary
Friktionskompasset udvides fra profilmålinger til **situationsmålinger** - korte, handlingsbundne målinger der identificerer friktion i forhold til specifikke opgaver. Dette muliggør:
1. Udvikling af målrettet e-læring og kommunikation
2. Preskriptiv levering af indhold baseret på friktionstype
3. Research og benchmarking med proper datahandling

---

## 1. Kernekonceptet: Situationsmåling

### Hvad er forskellen fra profilmåling?

| Profilmåling | Situationsmåling |
|--------------|------------------|
| "Hvordan har du det generelt?" | "Når du skal gøre X i situation Y - hvor strammer det?" |
| Personprofil | Opgave/handlingsprofil |
| 20-30 spørgsmål | 5-8 spørgsmål |
| Én gang / sjældent | Før hvert læringsforløb |

### Struktur
```
Opgave (1)
  └── Handling (2-5)
        └── Friktionsmåling per handling (4-5 spørgsmål)
```

**Eksempel: Sygefraværshåndtering**
- Opgave: "Håndtering af sygefravær korrekt og ordentligt"
- Handlinger:
  1. Ringe til medarbejderen på første sygedag
  2. Tale om forventet varighed
  3. Følge op på dag 5/14
  4. Dokumentere samtalen korrekt

---

## 2. Spørgsmålsdesign: Undgå Substitution

### Kahneman-problemet
Folk svarer på det nemme spørgsmål i stedet for det svære:
- "Jeg kan ikke" → dække for "jeg tør ikke"
- "Det giver ikke mening" → dække for "jeg gider ikke"
- "Det er besværligt" → dække for "jeg føler mig usikker"

### Løsning: Indirekte spørgsmål
I stedet for at spørge direkte om friktion, spørg om oplevelse i handling.

**TRYGHED** (ikke "føler du dig tryg?"):
- "Hvor ubehageligt ville det være at lave en fejl her?"
- "Hvor tydeligt ved du, hvad der sker, hvis noget går galt?"
- "Hvor meget holder du igen, når du udfører handlingen?"

**MENING** (ikke "giver det mening?"):
- "Hvis handlingen forsvandt i morgen, hvor meget ville det påvirke dit arbejde?"
- "Hvor tydeligt kan du se, hvem handlingen hjælper?"
- "Hvor ofte føles handlingen som noget, der bare skal overstås?"

**KAN** (ikke "kan du?"):
- "Når du står med opgaven, hvor sikkert ved du, hvad første skridt er?"
- "Hvis du skulle forklare handlingen til en kollega, hvor nemt ville det være?"
- "Hvor ofte stopper du op midt i handlingen, fordi du er i tvivl?"

**BESVÆR** (ikke "er det besværligt?"):
- "Hvor mange mentale stop er der typisk i handlingen?"
- "Hvor ofte kræver handlingen, at du skifter system, vindue eller fokus?"
- "Hvor meget ekstra energi kræver handlingen sammenlignet med lignende?"

### Vigtigt designprincip
- **Aldrig** lad brugeren vælge primær friktionstype
- Beregn friktionen fra svarene
- Spørgsmål på samme skala for sammenlignelighed

---

## 3. Interface: Handlingsbaseret Måling

### Admin/Designer-flow
1. Opret opgave (fx "Sygefraværshåndtering")
2. Tilføj 2-5 konkrete handlinger
3. Vælg målingstype (quick/deep)
4. Generer link til målgruppe

### Respondent-flow
1. Modtag link
2. Se opgave-kontekst
3. For hver handling: svar på 4-5 spørgsmål
4. Færdig (2-3 minutter total)

### Output
- Friktionsscore per handling per felt
- Prioriteret liste: "Her strammer det mest"
- Anbefalet indholdsstrategi

---

## 4. Datatilstande & Målingstyper

### Tre datatilstande
| Tilstand | Beskrivelse | Identitet | Retention |
|----------|-------------|-----------|-----------|
| **Almindelig drift** | Standard B2B brug | Pseudonymiseret | Kundevalg |
| **Analyse** | Intern analyse | Pseudonym-ID | Valgfri |
| **Research/Anonym** | Forskning/benchmark | Ingen | Permanent |

### Målingstyper med defaults
| Type | Spørgsmål | Identitet | Default retention |
|------|-----------|-----------|-------------------|
| **Opgavefriktion - hurtig** | 5-6 | Pseudo | 12 mdr |
| **Opgavefriktion - dyb** | 12-15 | Pseudo | 12 mdr |
| **Før/efter måling** | 5-6 x 2 | Pseudo | 24 mdr |
| **Research/benchmark** | 5-6 | Anonym | Permanent |

### Designprincip
- **Målingstypen** bestemmer datatilstand
- Brugeren vælger **ikke** GDPR-konsekvenser
- Alt håndteres i baggrunden

---

## 5. Data Import/Export

### Datatyper (fast katalog)
| Type | Indhold | Kan eksporteres | Kan slettes separat |
|------|---------|-----------------|---------------------|
| **Måledata** | Svar, scores, timestamps | Ja | Ja |
| **Metadata** | Spørgeskema, version, felt-mapping | Ja (med måledata) | Nej |
| **Persondata** | Navn, mail, rolle | Kun til DPO | Ja |

### Eksport-format
```json
{
  "export_version": "1.0",
  "export_date": "2025-12-17T10:00:00Z",
  "dataset": {
    "task_id": "task-xxx",
    "task_name": "Sygefraværshåndtering",
    "measurement_type": "task_friction_quick",
    "anonymization_level": "pseudonymized"
  },
  "schema": {
    "questions": [...],
    "fields": ["TRYGHED", "MENING", "KAN", "BESVAER"],
    "scale": "1-5"
  },
  "responses": [
    {
      "respondent_id": "resp-xxx",
      "action_id": "action-1",
      "answers": {...},
      "timestamp": "2025-12-15T14:30:00Z"
    }
  ]
}
```

### Import-mapping
- Eksternt spørgsmål → vores felt
- Ekstern skala → vores skala
- Ekstern opgave → vores opgave

---

## 6. GDPR & DPO-overblik

### DPA (Databehandleraftale)
- Auto-genereret PDF med kundeinfo
- Versioneret
- Download → Underskriv → Upload (eller digital accept)

### DPO-overblik (dashboard)
**Sektioner:**
1. **Aftaler** - Aktiv DPA, tidligere versioner, underskriftsstatus
2. **Datatilstande** - Hvad gemmes, hvad gemmes ikke, kan føres tilbage?
3. **Regler** - Opbevaringstid, auto-sletning, opsigelse
4. **Underdatabehandlere** - Live liste med formål, datatyper, region
5. **Dataoverblik** - Antal målinger, respondenter, aktivitet

### Underdatabehandlere (eksempel)
| Leverandør | Formål | Datatyper | Region |
|------------|--------|-----------|--------|
| Render | Hosting | Alle | EU |
| Cloudflare | CDN/DNS | Request logs | EU |
| Mailjet | Email | Email, navn | EU |

---

## 7. Preskriptiv Læring (Fremtidsvision)

### Konceptet
Friktionsmåling **før** læring - ikke kun som analyse.

### Indholdsmatch baseret på friktionstype
| Primær friktion | Anbefalet indhold |
|-----------------|-------------------|
| **TRYGHED/MENING** | Social proof, videoer med rigtige mennesker, normalisering |
| **KAN** | Instruktion, eksempler, step-by-step (tekst er ofte nok) |
| **BESVÆR** | Tjeklister, links, overblik, "hvad gør jeg nu?" |

### Logik
```
IF friktion.MENING > threshold THEN
  → Vis først HVORFOR (social proof, cases)

IF friktion.KAN > threshold AND friktion.MENING < threshold THEN
  → Vis HVORDAN (instruktion, eksempler)

IF friktion.BESVAER > threshold THEN
  → Vis VÆRKTØJER (tjeklister, quick refs)
```

### Håndtering af "illusorisk kunnen"
Problem: Erfarne medarbejdere tror de kan, men gør det ikke.

Løsning: Sammenlign to spørgsmål:
- "Hvor sikkert ved du, hvad du skal gøre?" (oplevet kunnen)
- "Hvor ofte stopper du midt i handlingen?" (faktisk usikkerhed)

Når de ikke matcher → reality-check før instruktion.

---

## 8. Implementeringsrækkefølge

### Fase 1: Fundament
- [ ] Database: actions tabel, action_responses
- [ ] API: CRUD for opgaver og handlinger
- [ ] UI: Admin interface til at definere opgaver/handlinger
- [ ] Spørgsmålsdesign: 4-5 indirekte spørgsmål per felt

### Fase 2: Måling
- [ ] Respondent UI: Situationsmåling flow
- [ ] Beregningsmotor: Friktionsscore per handling
- [ ] Resultat-visning: Prioriteret friktionsliste

### Fase 3: Data & Compliance
- [ ] Export: JSON/CSV med metadata
- [ ] Import: Mapping-interface
- [ ] DPA: Auto-generering
- [ ] DPO-overblik: Dashboard

### Fase 4: Preskriptiv (Fremtidig)
- [ ] Indholdstyper: Mapping til friktionsfelter
- [ ] Logik: Automatisk match
- [ ] Integration: LMS hooks

---

## 9. Beslutningspunkter til møde

1. **Er situationsmåling kernen fremadrettet?** (vs. kun profilmåling)
2. **Hvor mange handlinger max per opgave?** (anbefaling: 5)
3. **Hvor mange spørgsmål per handling?** (anbefaling: 4-5)
4. **Hvilke datatilstande fra start?** (anbefaling: pseudo + anonym)
5. **DPO-overblik som separat feature eller del af admin?**
6. **Preskriptiv læring: MVP eller fremtid?**

---

## Referencer
- Kahneman: Thinking, Fast and Slow (substitution)
- Friktionskompasset: ANALYSELOGIK.md (beregningsmekanik)
- GDPR: Databehandleraftale-krav
