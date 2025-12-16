# Analyselogik for Friktionskompasset

**VIGTIGT:** Denne fil SKAL opdateres hver gang der laves ændringer i analyselogikken!

Sidste opdatering: 2025-12-16

---

## Central Beregningsmotor

Al beregningslogik er nu centraliseret i **`friction_engine.py`**. Ved ændringer skal KUN denne fil opdateres.

### Arkitektur

```
friction_engine.py     <- Alle beregninger og konstanter
    ↓
analysis.py            <- Database-wrapper funktioner
    ↓
admin_app.py           <- Routes og templates
```

### Konstanter (friction_engine.py)

```python
THRESHOLDS = {
    # Procent-baseret farvecodning
    'percent_green': 70,     # >= 70% = grøn (lav friktion)
    'percent_yellow': 50,    # >= 50% = gul (moderat friktion)

    # Score-baseret severity (1-5 skala)
    'severity_high': 2.5,    # < 2.5 = høj severity
    'severity_medium': 3.5,  # < 3.5 = medium severity

    # Gap mellem leder og medarbejder
    'gap_significant': 1.0,  # > 1.0 = signifikant gap (20%)
    'gap_moderate': 0.6,     # > 0.6 = moderat gap (12%)

    # Leder blokeret
    'leader_blocked': 3.5,   # Både team og leder < 3.5

    # Substitution (Kahneman)
    'tid_bias': 0.6,         # TID_BIAS >= 0.6
    'underliggende': 3.5,    # UNDERLIGGENDE >= 3.5

    # Spredning (standardafvigelse)
    'spread_low': 0.5,       # < 0.5 = lav spredning
    'spread_medium': 1.0,    # < 1.0 = medium spredning
}
```

---

## 1. Substitutionsanalyse (Kahneman)

### Teoretisk grundlag
Baseret på Daniel Kahneman's forskning i kognitiv substitution. Mennesker kan ikke skelne mellem et svært spørgsmål ("Har jeg tidsproblemer?") og et lettere spørgsmål ("Er jeg utilfreds?"). De substituerer derfor det svære spørgsmål med det lette.

### Måleformlen

For hver respondent beregnes (se `friction_engine.py:515`):

```python
TID_MANGEL = 6 - item14  # "Jeg har tid nok..." (reverseret)
PROC = gennemsnit(item19, 6-item20, 6-item21, 6-item22)  # Mekaniske friktioner
UNDERLIGGENDE = max(item5, item10, item17, item18)  # Underliggende tilfredshed
TID_BIAS = TID_MANGEL - PROC
```

### Detektionslogik

En person flagges for substitution hvis **BEGGE** betingelser er opfyldt:

1. **TID_BIAS >= 0.6** - De rapporterer 0.6+ mere tidsmangel end deres faktiske procesfriktioner
2. **UNDERLIGGENDE >= 3.5** - De scorer højt på tilfredshed/kompetence (over 70%)

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
- **Beregning:** `friction_engine.py:515` - `calculate_substitution_for_respondent()`
- **Aggregering:** `friction_engine.py:571` - `calculate_substitution()`
- **Database:** `analysis.py:298` - `calculate_substitution_db()`

---

## 2. KKC Anbefalinger (Kend-Kontekst-Catalyzer)

### Teoretisk grundlag
KKC-modellen identificerer det mest kritiske felt at arbejde med først, baseret på friktionsniveauer og deres indbyrdes sammenhænge.

### Severitetsklassificering

Baseret på gennemsnitsscore (1-5 skala) - se `friction_engine.py:218`:

```python
def get_severity(score: float) -> Severity:
    if score < THRESHOLDS['severity_high']:   # < 2.5
        return Severity.HIGH
    elif score < THRESHOLDS['severity_medium']: # < 3.5
        return Severity.MEDIUM
    return Severity.LOW
```

### "Start Her" Logik

Se `friction_engine.py:693` - `get_start_here_recommendation()`:

Prioriterer felter i rækkefølgen:
1. **MENING** - Altid først hvis under tærskel (hvorfor)
2. **TRYGHED** - Næste prioritet (tør jeg)
3. **KAN** - Tredje prioritet (ved jeg hvordan)
4. **BESVÆR** - Sidste prioritet (mekanisk flow)

**Rationale:** Man skal først have MENING, så TRYGHED, så KAN, og til sidst BESVÆR.

### Tærskelværdier

- **Kritisk (rød):** < 50% (< 2.5/5) = `Severity.HIGH`
- **Problemområde (gul):** 50-70% (2.5-3.5/5) = `Severity.MEDIUM`
- **Acceptabel (grøn):** >= 70% (>= 3.5/5) = `Severity.LOW`

---

## 3. Leder vs. Medarbejder Gap

### Detektionslogik

Se `friction_engine.py:401` - `calculate_gap()`:

```python
gap = abs(employee_score - leader_assess_score)

if gap >= THRESHOLDS['gap_significant']:  # >= 1.0
    gap_severity = 'kritisk'
elif gap >= THRESHOLDS['gap_moderate']:   # >= 0.6
    gap_severity = 'moderat'
else:
    gap_severity = None

has_misalignment = gap >= THRESHOLDS['gap_moderate']
```

### Grænseværdier

- **Kritisk gap:** >= 1.0 point (>= 20%)
- **Moderat gap:** >= 0.6 point (>= 12%)
- **Acceptabelt:** < 0.6 point (< 12%)

### Alert i oversigt

En organisationsenhed vises med ⚠️ gap-alert hvis:
- Der er et gap >= 0.6 i mindst ét felt (MENING, TRYGHED, KAN, eller BESVÆR)

---

## 4. Leder Blokeret

### Teoretisk grundlag
Hvis lederen selv har høje friktioner i samme område som teamet, kan lederen ikke effektivt hjælpe teamet.

### Detektionslogik

Se `friction_engine.py:439` - `check_leader_blocked()`:

```python
def check_leader_blocked(employee_score, leader_self_score) -> bool:
    threshold = THRESHOLDS['leader_blocked']  # 3.5
    return (
        employee_score is not None and
        leader_self_score is not None and
        employee_score < threshold and
        leader_self_score < threshold
    )
```

### Rationale

- **Teamet** har friktioner (< 70%)
- **OG lederen selv** har friktioner (< 70%)
- → Lederen kan ikke hjælpe, da de selv kæmper med samme problem

### Alert i oversigt

En organisationsenhed vises med 🚧 blocked-alert hvis:
- Der findes mindst ét felt hvor både team og leder selv scorer under 3.5

---

## 5. Procent-baseret Farvecodning

### Konvertering

Se `friction_engine.py:160` - `score_to_percent()`:

```python
def score_to_percent(score: float) -> float:
    if score is None or score == 0:
        return 0.0
    return round((score / 5) * 100, 1)
```

### CSS-klasser

Se `friction_engine.py:240` - `get_percent_class()`:

```python
def get_percent_class(percent: float) -> str:
    if percent >= THRESHOLDS['percent_green']:   # >= 70
        return 'score-high'   # Grøn
    elif percent >= THRESHOLDS['percent_yellow']: # >= 50
        return 'score-medium' # Gul
    return 'score-low'        # Rød
```

### Visualisering

- **Grøn (≥70%):** Lav friktion - acceptabel tilstand
- **Gul (50-70%):** Moderat friktion - opmærksomhedsområde
- **Rød (<50%):** Høj friktion - kritisk område

---

## 6. Spredning (Standardafvigelse)

### Beregning

Se `friction_engine.py:284` - `calculate_std_dev()`:

```python
def calculate_std_dev(scores: List[float]) -> float:
    if len(scores) < 2:
        return 0.0
    mean = sum(scores) / len(scores)
    variance = sum((x - mean) ** 2 for x in scores) / len(scores)
    return round(math.sqrt(variance), 2)
```

### Klassificering

Se `friction_engine.py:262` - `get_spread_level()`:

```python
def get_spread_level(std_dev: float) -> SpreadLevel:
    if std_dev < THRESHOLDS['spread_low']:     # < 0.5
        return SpreadLevel.LOW
    elif std_dev < THRESHOLDS['spread_medium']: # < 1.0
        return SpreadLevel.MEDIUM
    return SpreadLevel.HIGH
```

- **Lav spredning (<0.5):** Teamet er enige
- **Medium spredning (0.5-1.0):** Nogen variation
- **Høj spredning (>=1.0):** Stor uenighed - undersøg forskelle

---

## 7. Lagdeling (Ydre vs. Indre)

Se `friction_engine.py:38` - `QUESTION_LAYERS`:

### MENING
- **All:** Items 1, 2, 3, 4, 5 (ingen lagdeling)

### TRYGHED
- **Ydre (social):** Items 6, 7, 8
- **Indre (emotionel):** Items 9, 10

### KAN
- **Ydre (rammer):** Items 11, 13, 14, 15, 16, 17
- **Indre (evne):** Items 12, 18

### BESVÆR
- **Mekanisk:** Items 19, 21, 22
- **Oplevet/flow:** Items 20, 23, 24

---

## 8. Reverse Scoring

### Koncept

Se `friction_engine.py:196` - `adjust_score()`:

```python
def adjust_score(raw_score: int, reverse_scored: bool = False) -> int:
    if reverse_scored:
        return 6 - raw_score
    return raw_score
```

### Eksempel
Item 14: "Jeg har tid nok..." er reverse scored:
- Hvis respondent svarer 5 (meget enig) → adjusted = 1 (lav friktion)
- Hvis respondent svarer 1 (meget uenig) → adjusted = 5 (høj friktion)

---

## 9. Profiltyper

Se `friction_engine.py:719` - `get_profile_type()`:

Baseret på friktionsmønster:

| Laveste score | Profiltype |
|---------------|------------|
| MENING < 2.5 | `retningsløst_team` |
| TRYGHED < 2.5 | `utrygt_team` |
| KAN < 2.5 | `inkompetent_team` |
| BESVÆR < 2.5 | `bøvlet_team` |
| Stor forskel (>1.5) | `ubalanceret_team` |
| Alle < 3.5 | `udviklingspotentiale` |
| Alle >= 4.0 | `højtydende_team` |
| Alle >= 3.5 | `velfungerende_team` |

---

## Opdateringsprocedure

Når du ændrer analyselogik:

1. ✅ Opdater `friction_engine.py` (KUN denne fil for beregninger)
2. ✅ Opdater denne fil (ANALYSELOGIK.md) med nye grænseværdier/formler
3. ✅ Kør tests: `python -m pytest tests/test_friction_engine.py -v`
4. ✅ Test import: `python -c "from friction_engine import *; print('OK')"`
5. ✅ Dokumenter ændringen i commit besked

---

## Filer og ansvar

| Fil | Ansvar |
|-----|--------|
| `friction_engine.py` | AL beregningslogik, konstanter, dataklasser |
| `analysis.py` | Database-wrapper, caching, trend-analyse |
| `admin_app.py` | Routes, templates, UI-logik |
| `tests/test_friction_engine.py` | Unit tests for beregninger |

---

## Unit Tests

36 tests dækker alle beregningsfunktioner:

```bash
python -m pytest tests/test_friction_engine.py -v
```

Testdækning:
- Score konvertering
- Severity klassificering
- Gap beregning
- Leder blokeret
- Substitutionsanalyse
- Spredning
- Warnings
- Profiltyper
- Start Her anbefaling

---

**Husk:** Konsistens er nøglen! Ved ændringer:
1. Opdater `friction_engine.py`
2. Opdater denne dokumentation
3. Kør tests
