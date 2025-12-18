# Esbjerg Kommune - Kanonisk Testdata

**Status:** KANONISK - DATA MÅ IKKE ÆNDRES UDEN DOKUMENTATION
**Opdateret:** 2025-12-19
**Formål:** Stabil testdata der fanger bugs og edge cases

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
| TRYGHED | 3.5 | 3.6 | Grøn/gul |
| MENING | 3.4 | 3.5 | Grøn/gul |
| KAN | 3.6 | 3.5 | Grøn/gul |
| BESVÆR | 3.3 | 3.4 | Grøn/gul |

**Respondenter:** 9 medarbejdere, 1 leder

---

### 2. Skovbrynet - Succes Case
**Formål:** Teste høje scores, grønne indikatorer
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Forventet |
|------|-------------|-------|-----------|
| TRYGHED | 4.5 | 4.4 | Grøn |
| MENING | 4.6 | 4.5 | Grøn |
| KAN | 4.4 | 4.5 | Grøn |
| BESVÆR | 4.3 | 4.4 | Grøn |

**Respondenter:** 9 medarbejdere, 1 leder

---

### 3. Solhjem - Krise Case
**Formål:** Teste lave scores, røde indikatorer, advarsler
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Forventet |
|------|-------------|-------|-----------|
| TRYGHED | 1.8 | 2.0 | Rød |
| MENING | 1.9 | 2.1 | Rød |
| KAN | 2.0 | 2.2 | Rød |
| BESVÆR | 1.7 | 1.9 | Rød |

**Respondenter:** 9 medarbejdere, 1 leder
**Forventede advarsler:** Krise-indikator

---

### 4. Strandparken - Leader Gap Case
**Formål:** Teste stort gap mellem leder og medarbejder
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Gap | Forventet |
|------|-------------|-------|-----|-----------|
| TRYGHED | 2.5 | 4.5 | 2.0 | Gap-advarsel |
| MENING | 2.6 | 4.4 | 1.8 | Gap-advarsel |
| KAN | 2.4 | 4.6 | 2.2 | Gap-advarsel |
| BESVÆR | 2.5 | 4.5 | 2.0 | Gap-advarsel |

**Respondenter:** 9 medarbejdere, 1 leder
**Forventede advarsler:** Leader-gap ikon

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
| TRYGHED | 3.0 | Normal visning |
| MENING | 4.0 | Normal visning |
| KAN | 2.5 | Lavt |
| BESVÆR | 3.5 | Normal |

**Respondenter:** 1 (kun self-assessment)
**Ingen leder-vurdering**

---

### 7. Minimal Data Test - Edge Case
**Formål:** Teste absolut minimum data
**Assessment type:** individuel_friktion (B2C)

| Felt | Score | Forventet |
|------|-------|-----------|
| TRYGHED | 3.0 | - |
| MENING | 3.0 | - |
| KAN | 3.0 | - |
| BESVÆR | 3.0 | - |

**Respondenter:** 1
**Alle scores identiske - tester variation-håndtering**

---

### 8. Substitution Test - Kahneman
**Formål:** Teste substitutionsanalyse-advarsel
**Assessment type:** gruppe_friktion (B2B)

| Felt | Medarbejder | Leder | Forventet |
|------|-------------|-------|-----------|
| TRYGHED | 4.0 | 4.0 | Høj |
| MENING | 2.0 | 2.0 | LAV - trigger! |
| KAN | 4.0 | 4.0 | Høj |
| BESVÆR | 2.0 | 2.0 | LAV - substitution! |

**Respondenter:** 9 medarbejdere, 1 leder
**Forventede advarsler:** Substitution-ikon (siger tid/besvær, mener mening)

---

## VALIDERINGS-TESTS

Følgende tests SKAL passere:

```python
def test_esbjerg_has_duplicate_name():
    """Både Esbjerg og Herning har 'Social- og Sundhedsforvaltningen'"""

def test_esbjerg_birkebo_normal_scores():
    """Birkebo har gennemsnitlige scores omkring 3.5"""

def test_esbjerg_skovbrynet_high_scores():
    """Skovbrynet har høje scores over 4.0"""

def test_esbjerg_solhjem_crisis_scores():
    """Solhjem har lave scores under 2.5"""

def test_esbjerg_strandparken_leader_gap():
    """Strandparken har gap > 1.5 mellem medarbejder og leder"""

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

