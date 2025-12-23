# Esbjerg Kommune - Kanonisk Testdata

**Status:** KANONISK - DATA MÅ IKKE ÆNDRES UDEN DOKUMENTATION
**Opdateret:** 2025-12-23
**Formål:** Stabil testdata der fanger bugs og edge cases
**Skala:** 7-point Likert (1-7)

---

## VIGTIGE REGLER

1. **ALDRIG** ændr Esbjerg-data uden at opdatere denne fil
2. **ALDRIG** slet eller tilføj enheder/målinger uden godkendelse
3. **ALTID** kør `test_esbjerg_canonical.py` efter ændringer
4. Esbjerg er til TEST - Herning er til DEMO

---

## STRUKTUR OVERSIGT

```
Esbjerg Kommune (cust-SHKIi10cOe8) - 13 enheder total
│
├── Social- og Sundhedsforvaltningen     ← SAMME NAVN som Herning! (tester duplikering)
│   │
│   ├── Ældreplejen
│   │   ├── Birkebo                      ← Normal case: gennemsnitlige scores
│   │   ├── Skovbrynet                   ← Høje scores (succes-case)
│   │   ├── Solhjem                      ← Lave scores (krise-case)
│   │   └── Strandparken                 ← Stort leader-gap
│   │
│   └── Handicapområdet                  ← Tom enhed (ingen målinger)
│
├── Børn og Kultur                       ← B2C testdata
│   ├── Individuel Profil Test           ← B2C: Kun 1 respondent
│   └── Minimal Data Test                ← B2C: Edge case med minimal data
│
└── Teknisk Forvaltning                  ← Substitution test
    └── Driftsafdelingen
        └── Substitution Test            ← Kahneman: Siger tid, mener utilfreds
```

---

## DETALJERET TESTDATA SPECIFIKATION

### 1. Birkebo - Normal Case
**Formål:** Baseline for sammenligning, gennemsnitlige scores
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Forventet |
|------|-------------|-------|-----------|
| TRYGHED | 4.8 | 4.9 | Grøn/gul |
| MENING | 4.6 | 4.8 | Grøn/gul |
| KAN | 4.9 | 4.8 | Grøn/gul |
| BESVÆR | 4.5 | 4.6 | Grøn/gul |

**Respondenter:** 9 medarbejdere, 1 leder

---

### 2. Skovbrynet - Succes Case
**Formål:** Teste høje scores, grønne indikatorer
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Forventet |
|------|-------------|-------|-----------|
| TRYGHED | 6.3 | 6.1 | Grøn |
| MENING | 6.4 | 6.3 | Grøn |
| KAN | 6.1 | 6.3 | Grøn |
| BESVÆR | 6.0 | 6.1 | Grøn |

**Respondenter:** 9 medarbejdere, 1 leder

---

### 3. Solhjem - Krise Case
**Formål:** Teste lave scores, røde indikatorer, advarsler
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Forventet |
|------|-------------|-------|-----------|
| TRYGHED | 2.2 | 2.5 | Rød |
| MENING | 2.4 | 2.7 | Rød |
| KAN | 2.5 | 2.8 | Rød |
| BESVÆR | 2.1 | 2.4 | Rød |

**Respondenter:** 9 medarbejdere, 1 leder
**Forventede advarsler:** Krise-indikator (score < 3.5)

---

### 4. Strandparken - Leader Gap Case
**Formål:** Teste stort gap mellem leder og medarbejder
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Gap | Forventet |
|------|-------------|-------|-----|-----------|
| TRYGHED | 3.3 | 6.3 | 3.0 | Gap-advarsel |
| MENING | 3.4 | 6.1 | 2.7 | Gap-advarsel |
| KAN | 3.1 | 6.4 | 3.3 | Gap-advarsel |
| BESVÆR | 3.3 | 6.3 | 3.0 | Gap-advarsel |

**Respondenter:** 9 medarbejdere, 1 leder
**Forventede advarsler:** Leader-gap ikon (gap > 1.4)

---

### 5. Handicapområdet - Tom Enhed
**Formål:** Teste håndtering af enheder uden data
**Assessment type:** Ingen

**Forventet adfærd:**
- Vises i organisationstræ
- Viser "-" eller "Ingen data" i analyser
- Må IKKE crashe eller give fejl

---

### 6. Individuel Profil Test - B2C Minimal
**Formål:** Teste B2C flow med kun 1 respondent
**Assessment type:** individuel_friktion (B2C)

| Felt | Score | Forventet |
|------|-------|-----------|
| TRYGHED | 4.0 | Normal visning |
| MENING | 5.5 | Normal visning |
| KAN | 3.3 | Lavt |
| BESVÆR | 4.8 | Normal |

**Respondenter:** 1 (kun self-assessment)
**Ingen leder-vurdering**

---

### 7. Minimal Data Test - Edge Case
**Formål:** Teste absolut minimum data
**Assessment type:** individuel_friktion (B2C)

| Felt | Score | Forventet |
|------|-------|-----------|
| TRYGHED | 4.0 | - |
| MENING | 4.0 | - |
| KAN | 4.0 | - |
| BESVÆR | 4.0 | - |

**Respondenter:** 1
**Alle scores identiske - tester variation-håndtering**

---

### 8. Substitution Test - Kahneman
**Formål:** Teste substitutionsanalyse-advarsel
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Forventet |
|------|-------------|-------|-----------|
| TRYGHED | 5.5 | 5.5 | Høj |
| MENING | 2.5 | 2.5 | LAV - trigger! |
| KAN | 5.5 | 5.5 | Høj |
| BESVÆR | 2.5 | 2.5 | LAV - substitution! |

**Respondenter:** 9 medarbejdere, 1 leder
**Forventede advarsler:** Substitution-ikon (siger tid/besvær, mener mening)

---

## 7-POINT SKALA THRESHOLDS

| Indikator | Threshold | Beskrivelse |
|-----------|-----------|-------------|
| Krise (Rød) | < 3.5 | Under 50% på 7-point skala |
| Advarsel (Gul) | < 4.9 | Under 70% på 7-point skala |
| God (Grøn) | >= 4.9 | Over 70% på 7-point skala |
| Gap signifikant | > 1.4 | Over 20% forskel |
| Gap moderat | > 0.84 | Over 12% forskel |

---

## VALIDERINGS-TESTS

Følgende tests SKAL passere:

```python
def test_esbjerg_has_duplicate_name():
    """Både Esbjerg og Herning har 'Social- og Sundhedsforvaltningen'"""

def test_esbjerg_birkebo_normal_scores():
    """Birkebo har gennemsnitlige scores omkring 4.7 (7-point)"""

def test_esbjerg_skovbrynet_high_scores():
    """Skovbrynet har høje scores over 6.0"""

def test_esbjerg_solhjem_crisis_scores():
    """Solhjem har lave scores under 3.5 (krise-threshold)"""

def test_esbjerg_strandparken_leader_gap():
    """Strandparken har gap > 1.4 mellem medarbejder og leder"""

def test_esbjerg_handicap_empty_unit():
    """Handicapområdet eksisterer men har ingen målinger"""

def test_esbjerg_b2c_one_respondent():
    """Individuel Profil Test har præcis 1 respondent"""

def test_esbjerg_substitution_pattern():
    """Substitution Test trigger substitution-advarsel"""
```

---

## ÆNDRINGSLOG

| Dato | Ændring | Godkendt af |
|------|---------|-------------|
| 2025-12-19 | Initial design | Claude Code |
| 2025-12-23 | Opdateret til 7-point Likert skala | Claude Code |

