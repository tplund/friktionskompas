# Friktionskompasset - System Design & Analyse Kriterier

**Vigtig:** Læs dette dokument ved start af hver ny session for at forstå systemets design decisions og kriterier.

---

## 📊 Analyse Kriterier

### Severity Levels (Friktionsniveauer)
Baseret på score 1-5 (eller 0-100%):

- **Høj friktion (🔴):** Score ≤ 2.5 (≤ 50%)
- **Medium friktion (🟡):** Score 2.5-3.5 (50-70%)
- **Lav friktion (🟢):** Score > 3.5 (> 70%)

### Gap Analysis (Leder vs. Medarbejder)
Forskel mellem lederens vurdering og medarbejdernes oplevelse:

- **Kritisk forskel:** ≥ 1.0 point (≥ 20%) - 🔴 Rød alert
- **Moderat forskel:** 0.6-0.9 point (12-19%) - 🟡 Gul alert
- **Acceptabelt:** < 0.6 point (< 12%) - Ingen alert

**Rationale for threshold:**
- Lederen er ÉN person vs. teamets GENNEMSNIT
- Selv 0.6-0.8 point (12-16%) er betydelig forskel
- 60% vs 76% burde flagges som moderat forskel

**Hvad betyder det:**
- Hvis medarbejder < leder_assess: Lederen undervurderer teamets problemer
- Hvis medarbejder > leder_assess: Lederen overvurderer teamets problemer

### Spredning (Standardafvigelse)
Måler hvor enige teamet er om friktionsniveauet:

- **Lav spredning:** σ < 0.5 - Teamet er enige
- **Medium spredning:** σ 0.5-1.0 - Nogle forskelle
- **Høj spredning:** σ ≥ 1.0 - Meget uensartet oplevelse

**Hvad betyder høj spredning:**
- Potentiel konflikt i teamet
- Ulige arbejdsvilkår
- "Hidden pockets" - nogle har det godt, andre dårligt
- Bør prioriteres højt, da det signalerer intern uenighed

### Blocked Leader (Leder Blokeret)
Lederen kan ikke hjælpe teamet, fordi lederen selv har samme friktioner:

- **Kriterium:** BÅDE team_score < 3.5 OG leader_self_score < 3.5
- **Anbefaling:** Lederen bør først adressere egne friktioner

### Substitution (Kahneman's Bias)
Folk siger "jeg mangler tid", men mener egentlig "jeg er utilfreds":

**Kriterium:**
- `tid_bias ≥ 0.6` OG `underliggende ≥ 3.5`

**Beregning:**
```python
tid_mangel = 6 - item14  # "Jeg har tid nok..."
proc = avg(item19, 6-item20, 6-item21, 6-item22)  # Mekanisk friktion
underliggende = max(item5, item10, item17, item18)  # Substitution items
tid_bias = tid_mangel - proc
```

**Hvad betyder det:**
- De kan ikke skelne mellem reelle tidsproblemer og underliggende utilfredshed
- Adresser MENING/TRYGHED/KAN - IKKE proces-optimering
- Effektivisering vil ikke hjælpe

### Anonymitet Threshold
For at beskytte anonymitet i anonymous mode:

- **Standard minimum:** 5 responses
- **Konfigurerbar** per campaign via `min_responses`
- **Identified mode:** Vises altid (ingen threshold)

---

## 🎯 Prioriteringslogik for KKC Anbefalinger

Systemet kan vise enten **én klar prioritet** eller **liste af ligeværdige friktioner**.

### Single Priority (Vis "Start Her: X")
Vises når der er én klar førsteprioritet:

1. **Severity først:** Høj > Medium > Lav
2. **Hvis ALLE scores er meget tætte (< 0.4 range):**
   - Vis ALLE som ligeværdige (se nedenfor)
3. **Hvis scores er tætte (< 0.3 forskel) inden for severity gruppe:**
   - Prioriter felt med **højest spredning**
   - Rationale: Uensartet oplevelse signalerer konflikt/ulige vilkår
4. **Ellers:**
   - Prioriter **laveste score**

### Multiple Priorities (Vis liste)
Vises når alle friktioner er næsten lige høje (< 0.4 point forskel):

- Alle problematiske felter vises i prioriteret liste
- Sorteret efter: severity → spredning → score
- Brugeren vælger selv rækkefølge baseret på teamets kontekst
- Hver anbefaling kan foldes ud for at se handlinger

**Rationale:**
Når scores er tætte (fx 2.3, 2.4, 2.5, 2.6), er det kunstigt at sige "start med 2.3". I stedet vises alle, så lederen kan vælge baseret på kontekst.

### Eksempler

**Eksempel 1 - Single Priority:**
- MENING: 2.4 (høj severity), spredning: 0.6 (medium)
- TRYGHED: 2.5 (høj severity), spredning: 1.2 (høj)
- Forskel: 0.1 (< 0.3) → Prioriter TRYGHED pga. højest spredning

**Eksempel 2 - Multiple Priorities:**
- MENING: 2.3 (høj severity), spredning: 0.5
- TRYGHED: 2.4 (høj severity), spredning: 0.8
- KAN: 2.5 (høj severity), spredning: 1.2
- BESVÆR: 2.6 (medium severity), spredning: 0.6
- Range: 0.3 (< 0.4) → Vis alle som liste
- Rækkefølge: TRYGHED (høj sev + høj spread), MENING (høj sev), KAN (høj sev), BESVÆR (medium sev)

---

## 🗺️ KKC Framework Integration

Anders Trillingsgaard's Kurs-Koordinering-Commitment framework:

| Friktionsfelt | KKC Element | Betydning |
|---------------|-------------|-----------|
| MENING | KURS | "Hvorfor gør vi det?" - retning og formål |
| TRYGHED | KOORDINERING | "Hvem gør hvad?" - samarbejde og åbenhed |
| KAN | KOORDINERING | Både evner (indre) og ressourcer (ydre) |
| BESVÆR | COMMITMENT | "Kan vi levere det vi siger ja til?" - system matcher virkelighed |

---

## 📋 Spørgsmålsstruktur (v1.4)

### Totalt: 24 spørgsmål fordelt på 4 felter

#### MENING (Spørgsmål 1-5)
- Item 1: "Opgaver føles som spild af tid" (reverse)
- Item 2: "Forstår hvordan arbejdet hjælper borger/kunde"
- Item 3: "Der er ting jeg ville lade være med" (reverse)
- Item 4: Situationsbaseret MENING
- Item 5: **Substitution item** - Generelt utilfredshed

**Lagdeling:** Ingen (alle items behandles ens)

#### TRYGHED (Spørgsmål 6-10)
**Ydre lag (Social tryghed):** Items 6, 7, 8
- Item 6: "Holder ting for mig selv" (reverse)
- Item 7: "Kritik bliver taget seriøst"
- Item 8: "Opfølgning uden straf"

**Indre lag (Emotionel robusthed):** Items 9, 10
- Item 9: "Usikkerhed uden at spørge" (reverse)
- Item 10: **Substitution item** - Udsætter pga. reaktioner (reverse)

#### KAN/MULIGHED (Spørgsmål 11-18)
**Ydre lag (Rammer):** Items 11, 13, 14, 15, 16, 17
- Item 11: "Har de værktøjer jeg skal bruge"
- Item 13: "Ved hvor jeg kan få hjælp"
- Item 14: **TID ITEM** - "Har tid nok" (bruges i substitution)
- Item 15: "Klare beslutninger når jeg har brug"
- Item 16: "Cues til korrekt adfærd"
- Item 17: **Substitution item** - Regler vs. virkelighed

**Indre lag (Evne):** Items 12, 18
- Item 12: "Ved ikke præcist hvordan" (reverse)
- Item 18: **Substitution item** - Kender ikke første skridt (reverse)

#### BESVÆR (Spørgsmål 19-24)
**Mekanisk friktion:** Items 19, 21, 22
- Item 19: "Dobbeltindtastning og unødige registreringer" (reverse)
- Item 21: "Ventetid og afhængigheder" (reverse)
- Item 22: "Afbrydelser" (reverse)

**Oplevet flow:** Items 20, 23, 24
- Item 20: "Let at komme i gang"
- Item 23: **Substitution item** - Udsætter selvom tid (reverse)
- Item 24: "Rimelig indsats vs. resultat"

---

## 👥 Respondent Types

### employee
- Standard medarbejderbesvarelse
- Bruges til hovedanalyse
- Kan være anonymous eller identified

### leader_assess
- Lederens vurdering af teamets friktioner
- "Hvordan tror du dit team oplever...?"
- Sammenlignes med employee for gap-analyse

### leader_self
- Lederens egne friktioner
- "Hvordan oplever DU...?"
- Bruges til "blocked leader" analyse

---

## 🏗️ Database Struktur

### Multi-tenant
- `customers` - Kunder/organisationer
- `users` - Med role: 'admin' eller 'manager'
- `customer_id` på organizational_units for isolation

### Hierarkisk Organisation
- `organizational_units` - Træstruktur med parent_id
- `full_path` - "Virksomhed//Afdeling//Team"
- `level` - Dybde i træet (0 = root)
- Leaf units = enheder uden børn (hvor medarbejdere er)

### Campaigns & Responses
- `campaigns` - Målinger/kampagner
  - `target_unit_id` - Rammer alle leaf units under denne
  - `mode` - 'anonymous' eller 'identified'
  - `min_responses` - Anonymitetstærskel
  - `include_leader_assessment`, `include_leader_self`
- `tokens` - Unikke adgangskoder
  - `respondent_type` - employee/leader_assess/leader_self
  - `respondent_name` - For identified mode
- `responses` - Svar
  - `score` - 1-5
  - `comment` - Fritekst
  - `respondent_type`

### Reverse Scoring
Nogle spørgsmål er reverse scored (negativt formuleret):
- Hvis `reverse_scored = 1`: Actual score = `6 - raw_score`
- Dette gør at høj score altid = lav friktion

---

## 🎨 UI/UX Conventions

### Alerts i tabeller
- **⚠️ Gap** - Stor forskel mellem leder og medarbejdere (> 20%)
- **🚧 Blocked** - Leder blokeret af egne friktioner
- **📊 Spredning** - Høj spredning = uensartet oplevelse (σ ≥ 1.0)
- **Tom celle** - Ingen alerts = ingen problemer (IKKE vist som ✓ eller tekst)

**Designprincip:** Vis kun alerts når der ER problemer. Tom celle = OK.

### Farvekodning
- **🟢 Grøn:** Lav friktion (godt) - > 70%
- **🟡 Gul:** Medium friktion (ok) - 50-70%
- **🔴 Rød:** Høj friktion (problematisk) - < 50%

### Spredning (Standardafvigelse) Farvekodning
- **🟢 Grøn:** Lav spredning (< 0.5) - teamet er enige
- **🟡 Orange:** Medium (0.5-1.0) - nogle forskelle
- **🔴 Rød:** Høj (≥ 1.0) - meget uensartet oplevelse

### Procent vs. Score
- **Score:** 1-5 skala (brugt internt)
- **Procent:** (score / 5) * 100% (brugt i UI)
- Eksempel: 3.5/5 = 70%

---

## 🔄 Når Kriterier Ændres

**VIGTIG PROCES:**

1. Opdater relevant kode (`analysis.py`, templates, osv.)
2. **Opdater DENNE fil** med de nye værdier
3. Dokumenter rationale for ændringen
4. Test med eksisterende data for at se impact

**Eksempel på ændring:**
```markdown
## Ændringslog

### 2025-01-17: Spredning threshold justeret
- **Før:** Høj spredning = σ > 1.2
- **Nu:** Høj spredning = σ ≥ 1.0
- **Rationale:** For mange teams havde 1.0-1.2 uden at få flagget
```

---

## 📖 Læs Dette Ved Session Start

Når du starter en ny session med Claude, bed den læse:
```
Læs venligst SYSTEM_DESIGN.md for at forstå analyse-kriterierne og design decisions.
```

Dette sikrer:
- Konsistente kriterier på tværs af ændringer
- Ingen breaking changes uden opdatering
- Single source of truth for alle værdier

---

## Ændringslog

### 2025-01-17: Multiple recommendations når scores er tætte
- **Ændring:** KKC anbefalinger kan nu vise enten én prioritet ELLER liste af ligeværdige
- **Trigger:** Hvis alle problematiske scores har < 0.4 range → vis alle som liste
- **Rationale:** Når scores er tætte (fx 2.3, 2.4, 2.5), er det kunstigt at prioritere én. Leder vælger selv rækkefølge.
- **UI:** "🎯 Prioriterede Anbefalinger" med fold-ud detaljer per anbefaling
- **Kode:** `analysis.py::get_start_here_recommendation()` returnerer nu dict med `single: bool`

### 2025-01-17: Spredning tilføjet til analyse
- **Tilføjet:** Standardafvigelse (σ) beregnes per friktionsfelt
- **UI:** Ny kolonne "Spredning" i sammenligningstabel
- **Alert:** "📊 Spredning" når σ ≥ 1.0
- **Farvekodning:** Grøn < 0.5, Orange 0.5-1.0, Rød ≥ 1.0
- **Prioritering:** Høj spredning prioriteres ved tætte scores
- **Kode:** `analysis.py::get_unit_stats_with_layers()` returnerer nu `std_dev` og `spread`

### 2025-01-17: Fjernet "✓ OK" i alerts
- **Før:** Viste "✓ OK" når ingen alerts
- **Nu:** Tom celle når ingen alerts
- **Rationale:** Mindre visuelt støj - tom = godt

### 2025-01-17: Gap threshold sænket
- **Før:** Kritisk gap > 1.0 point (20%)
- **Nu:** Moderat gap ≥ 0.6 point (12%), Kritisk gap ≥ 1.0 point (20%)
- **Rationale:** Leder er ÉN person vs. team GENNEMSNIT. 60% vs 76% (16pp) burde flagges.
- **UI:** To farver: Gul (moderat) og Rød (kritisk)
- **Kode:** `analysis.py::get_comparison_by_respondent_type()` returnerer nu `gap_severity`

### 2025-01-17: Sprogbrug - Engelske udtryk oversætanvt
- **Ændret:** Gap → Forskel, Logout → Log ud, Login → Log ind, Bulk Upload → Upload CSV
- **Behold:** Upload, Download, CSV (alment udbredt i dansk)
- **Regel:** Brug dansk medmindre engelsk er naturligt i daglig dansk
- **Dokumenteret:** `.clinerules` indeholder nu sprogregler

### 2025-01-17: Login-side farver opdateret
- **Før:** Lilla gradient (#667eea → #764ba2)
- **Nu:** Teal/grøn gradient (#0f766e → #134e4a)
- **Rationale:** Brugerens præference - mindre lilla
