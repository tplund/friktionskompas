# Analyselogik for Friktionskompasset

**VIGTIGT:** Denne fil SKAL opdateres hver gang der laves ændringer i analyselogikken!

Sidste opdatering: 2025-11-16

---

## 1. Substitutionsanalyse (Kahneman)

### Teoretisk grundlag
Baseret på Daniel Kahneman's forskning i kognitiv substitution. Mennesker kan ikke skelne mellem et svært spørgsmål ("Har jeg tidsproblemer?") og et lettere spørgsmål ("Er jeg utilfreds?"). De substituerer derfor det svære spørgsmål med det lette.

### Måleformlen

For hver respondent beregnes:

```python
TID_MANGEL = 6 - item14  # "Jeg har tid nok..." (reverseret)
PROC = gennemsnit(item19, 6-item20, 6-item21, 6-item22)  # Mekaniske friktioner
UNDERLIGGENDE = max(item5, item10, item17, item18)  # Underliggende tilfredshed
TID_BIAS = TID_MANGEL - PROC
```

### Detektionslogik

En person flagges for substitution hvis **BEGGE** betingelser er opfyldt:

1. **TID_BIAS ≥ 0.6** - De rapporterer 0.6+ mere tidsmangel end deres faktiske procesfriktioner
2. **UNDERLIGGENDE ≥ 3.5** - De scorer højt på tilfredshed/kompetence (over 70%)

### Konkrete spørgsmål

**TID_MANGEL:**
- Item 14: "Jeg har tid nok til at løse mine arbejdsopgaver" (reverse scored)

**PROC - Mekaniske friktioner:**
- Item 19: Dobbeltindtastning (reverse scored)
- Item 20: Let at komme i gang
- Item 21: Ventetid (reverse scored)
- Item 22: Afbrydelser (reverse scored)

**UNDERLIGGENDE:**
- Item 5: Mening - udfoldelse
- Item 10: Tryghed - udskyder pga reaktioner
- Item 17: Kan - ved hvad der forventes
- Item 18: Kan - kender første skridt

### Implementering
Se `analysis.py:262` - funktionen `calculate_substitution()`

---

## 2. KKC Anbefalinger (Kend-Kontekst-Catalyzer)

### Teoretisk grundlag
KKC-modellen identificerer det mest kritiske felt at arbejde med først, baseret på friktionsniveauer og deres indbyrdes sammenhænge.

### Severitetsklassificering

Baseret på gennemsnitsscore (0-5 skala):

```python
if avg_score < 2.5:  # Under 50%
    severity = 'høj'
elif avg_score < 3.5:  # Under 70%
    severity = 'medium'
else:  # Over 70%
    severity = 'lav'
```

### "Start Her" Logik

KKC "Start Her" vises hvis der findes mindst ét felt med severity 'høj' ELLER 'medium':

```python
if rec['severity'] in ['høj', 'medium']:
    return rec  # Vis som "Start Her"
```

### Prioriteringsrækkefølge

1. **MENING** - Altid først hvis under tærskel
2. **TRYGHED** - Næste prioritet
3. **KAN** - Tredje prioritet
4. **BESVÆR** - Sidste prioritet

**Rationale:** Man skal først have MENING (hvorfor), så TRYGHED (tør jeg), så KAN (ved jeg hvordan), og til sidst BESVÆR (mekanisk flow).

### Tærskelværdier

- **Kritisk (rød):** < 50% (< 2.5/5)
- **Problemområde (gul):** 50-70% (2.5-3.5/5)
- **Acceptabel (grøn):** > 70% (> 3.5/5)

### Implementering
Se `analysis.py:627` - funktionen `get_start_here_recommendation()`

---

## 3. Leder vs. Medarbejder Gap

### Detektionslogik

Der er et signifikant gap mellem leder og medarbejdere hvis:

```python
abs(employee_score - leader_assess_score) > 1.0  # Mere end 20% forskel
```

### Grænseværdier

- **Stort gap:** > 1.0 point (> 20%)
- **Acceptabelt:** ≤ 1.0 point (≤ 20%)

### Alert i oversigt

En organisationsenhed vises med ⚠️ gap-alert hvis:
- Der er et gap > 1.0 i mindst ét felt (MENING, TRYGHED, KAN, eller BESVÆR)

### Implementering
Se `admin_app.py:555-612` - loop der beregner `has_leader_gap`

---

## 4. Leder Blokeret

### Teoretisk grundlag
Hvis lederen selv har høje friktioner i samme område som teamet, kan lederen ikke effektivt hjælpe teamet.

### Detektionslogik

Leder er blokeret hvis **BEGGE** betingelser er opfyldt i samme felt:

```python
if employee_score < 3.5 AND leader_self_score < 3.5:
    leader_blocked = True
```

### Rationale

- **Teamet** har friktioner (< 70%)
- **OG lederen selv** har friktioner (< 70%)
- → Lederen kan ikke hjælpe, da de selv kæmper med samme problem

### Alert i oversigt

En organisationsenhed vises med 🚧 blocked-alert hvis:
- Der findes mindst ét felt hvor både team og leder selv scorer under 3.5

### Implementering
Se `admin_app.py:555-612` - loop der beregner `has_leader_blocked`

---

## 5. Procent-baseret Farvecodning

### Grænseværdier

UI'et viser scores i procent (0-100%) med farvecodning:

```python
percent = (score / 5) * 100

if percent >= 70:
    class = 'score-high'  # Grøn
elif percent >= 50:
    class = 'score-medium'  # Gul
else:
    class = 'score-low'  # Rød
```

### Visualisering

- **Grøn (≥70%):** Lav friktion - acceptabel tilstand
- **Gul (50-70%):** Moderat friktion - opmærksomhedsområde
- **Rød (<50%):** Høj friktion - kritisk område

### Implementering
Se `admin_app.py` - helper funktioner `to_percent()` og `get_percent_class()`

---

## 6. Lagdeling (Ydre vs. Indre)

### TRYGHED
- **Ydre (social):** Items 6, 7, 8
- **Indre (emotionel):** Items 9, 10

### KAN
- **Ydre (rammer):** Items 11, 13, 14, 15, 16, 17
- **Indre (evne):** Items 12, 18

### BESVÆR
- **Mekanisk:** Items 19, 21, 22
- **Oplevet/flow:** Items 20, 23, 24

### Implementering
Se `analysis.py:13-36` - konstanten `QUESTION_LAYERS`

---

## 7. Reverse Scoring

### Koncept
Nogle spørgsmål er formuleret positivt og skal inverteres for at måle friktion:

```python
if reverse_scored == 1:
    adjusted_score = 6 - raw_score
else:
    adjusted_score = raw_score
```

### Eksempel
Item 14: "Jeg har tid nok..." er reverse scored:
- Hvis respondent svarer 5 (meget enig) → adjusted = 1 (lav friktion)
- Hvis respondent svarer 1 (meget uenig) → adjusted = 5 (høj friktion)

### Implementering
Alle queries i `analysis.py` anvender reverse scoring automatisk

---

## Opdateringsprocedure

Når du ændrer analyselogik:

1. ✅ Opdater koden (f.eks. `analysis.py` eller `admin_app.py`)
2. ✅ Opdater DENNE fil med nye grænseværdier/formler
3. ✅ Opdater eventuelle UI-beskrivelser i templates
4. ✅ Test med `create_realistic_testdata.py`
5. ✅ Dokumenter ændringen i en commit besked

---

## Filer at opdatere ved logikændringer

| Analyselogik | Python kode | Template visning | Test data |
|--------------|-------------|------------------|-----------|
| Substitution | `analysis.py:262` | `campaign_detailed.html:389+` | `create_realistic_testdata.py` |
| KKC | `analysis.py:627` | `campaign_detailed.html:151+` | `create_realistic_testdata.py` |
| Leder gap | `admin_app.py:555+` | `hr_overview.html:349+`, `campaign_detailed.html:276+` | - |
| Leder blokeret | `admin_app.py:555+` | `hr_overview.html:349+`, `campaign_detailed.html:276+` | - |
| Farvecodning | `admin_app.py` | `hr_overview.html`, `campaign_detailed.html` | - |

---

**Husk:** Konsistens er nøglen! Alle tre lag (backend, frontend, dokumentation) skal altid være synkroniseret.
