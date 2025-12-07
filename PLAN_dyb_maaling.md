# Friktionsprofil System - Komplet Dokumentation

Dette dokument beskriver **to målesystemer**:

1. **Screening** (13 items) - Hurtig kortlægning til at spotte mønstre
2. **Dyb Måling** (88 items) - Fuldt profileringsværktøj

---

# DEL 1: SCREENING (13 items)

## Formål

Hurtig identificering af:
- Hvilket **felt** (Tryghed/Mening/Kan/Besvær) er tungest?
- Hvor **knækker kæden opad**?
- Hvilket **manifestationslag** bruges under pres?

Nok til at:
- Spotte tydelige friktionsprofiler
- Vælge hvem der bør have den lange test
- Have noget konkret at tale ud fra

## Spørgsmål (13 items)

### Svarskala
```
1 = Slet ikke typisk for mig
2 = Sjældent typisk for mig
3 = Lidt typisk for mig
4 = Hverken/eller
5 = Noget typisk for mig
6 = Ofte typisk for mig
7 = Meget typisk for mig
```

### Sektion A: Felter (4 items)

| ID | Spørgsmål | Felt |
|----|-----------|------|
| S1 | Jeg føler mig ofte på vagt, også når andre virker rolige. | Tryghed |
| S2 | Jeg mister hurtigt lysten, hvis jeg ikke selv kan se meningen med det, jeg skal. | Mening |
| S3 | Jeg tvivler tit på, om jeg kan løse de opgaver, jeg står med. | Kan |
| S4 | Jeg udskyder ofte opgaver, selvom jeg godt ved, de er vigtige. | Besvær |

### Sektion B: Opad-kæden (4 items)

| ID | Spørgsmål | Overgang | Problem |
|----|-----------|----------|---------|
| S5 | Når jeg har det svært, ved jeg sjældent, hvad jeg egentlig har brug for. | Emo→Indre | Følelse bliver ikke til "mig" |
| S6 | Når noget rammer mig personligt, mister jeg let overblikket. | Indre→Kog | Selvoplevelse bliver ikke til forståelse |
| S7 | Jeg ved tit godt, hvad jeg burde gøre, men får det alligevel ikke gjort. | Kog→Ekstern | Forståelse bliver ikke til handling |
| S8 | Min krop reagerer (fx uro/spænding), før jeg ved, hvad jeg føler. | Bio→Emo | Kropssignal bliver ikke til følelsesbevidsthed |

### Sektion C: Manifestation & Regulering (5 items)

| ID | Spørgsmål | Lag |
|----|-----------|-----|
| S9 | Når jeg er presset, mærker jeg det først i kroppen (søvn, mave, spænding, hovedpine). | Biologi |
| S10 | Når jeg er presset, bliver jeg meget følelsesstyret. | Emotion |
| S11 | Når jeg er presset, går jeg hurtigt i selvkritik eller føler mig forkert. | Indre |
| S12 | Når jeg er presset, går jeg mest op i at tænke/analysere i stedet for at handle. | Kognition |
| S13 | Når jeg er presset, prøver jeg mest at ændre på omgivelserne (aflyse, skifte, undgå, lave om på rammerne). | Ekstern |

## Scoring (Screening)

### 1. Felt-mønster (S1-S4)
```python
felt_tryghed = S1
felt_mening = S2
felt_kan = S3
felt_besvaer = S4

primaert_felt = max(S1, S2, S3, S4)  # Det felt med højest score
```

**Fortolkning:**
- Høj S1 → Tryghed er tungest
- Høj S2 → Meningsfriktion
- Høj S3 → Kan-friktion
- Høj S4 → Besværsfriktion
- Flere høje → Blandet profil

### 2. Opad-mønster (S5-S8)
```python
opad_emo_indre = S5      # Emotion → Indre
opad_indre_kog = S6      # Indre → Kognition
opad_kog_ekstern = S7    # Kognition → Ekstern
opad_bio_emo = S8        # Biologi → Emotion

stop_punkt = max(S5, S6, S7, S8)  # Hvor kæden typisk knækker
```

**Fortolkning:**
- Høj S5 → Følelser bliver ikke til selvfornemmelse/klare behov
- Høj S6 → Selvoplevelse kan ikke blive til forståelse
- Høj S7 → Handlingsbrud, freeze/prokrastination
- Høj S8 → Kroppen larmer uden følelsessprog

### 3. Manifestationslag (S9-S13)
```python
manifest_biologi = S9
manifest_emotion = S10
manifest_indre = S11
manifest_kognition = S12
manifest_ekstern = S13

primaert_lag = max(S9, S10, S11, S12, S13)  # Hvor presset lander
```

**Fortolkning:**
- Høj S9 → Kroppen tager regningen (symptomer, spænding, søvn)
- Høj S10 → Følelser tager regningen (udbrud, meltdown)
- Høj S11 → Indre lag tager regningen (skam, selvkritik, "jeg er forkert")
- Høj S12 → Kognition tager regningen (overanalyse, grublen, kontrol)
- Høj S13 → Omgivelserne tager regningen (skift, undgåelse)

## Screening-rapport

### Eksempel på output

```
┌─────────────────────────────────────────────────────────────┐
│                    FRIKTIONSPROFIL                          │
│                      (Screening)                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FELT-MØNSTER                                               │
│  ───────────────────────────────────────                    │
│  Tryghed   ████████░░ 4.0                                   │
│  Mening    ██████████ 5.0  ← Primært felt                   │
│  Kan       ██████░░░░ 3.0                                   │
│  Besvær    ████████░░ 4.0                                   │
│                                                             │
│  → Din største friktion ligger i MENING-feltet.             │
│    Du bruger energi på at finde formål og engagement.       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  OPAD-KÆDE (hvor knækker det?)                              │
│  ───────────────────────────────────────                    │
│                                                             │
│  EKSTERN ─────────────────────────────                      │
│      ↑ Kog→Ekstern: ████████████ 6.0  ← STOP               │
│  KOGNITION ───────────────────────────                      │
│      ↑ Indre→Kog:   ██████░░░░░░ 3.0                        │
│  INDRE ───────────────────────────────                      │
│      ↑ Emo→Indre:   ████████░░░░ 4.0                        │
│  EMOTION ─────────────────────────────                      │
│      ↑ Bio→Emo:     ██████░░░░░░ 3.0                        │
│  BIOLOGI ─────────────────────────────                      │
│                                                             │
│  → Din kæde stopper typisk ved KOGNITION→EKSTERN.           │
│    Du forstår hvad du skal gøre, men får det ikke gjort.    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  MANIFESTATIONSLAG                                          │
│  ───────────────────────────────────────                    │
│  Biologi   ████░░░░░░ 2.0                                   │
│  Emotion   ██████░░░░ 3.0                                   │
│  Indre     ████████░░ 4.0                                   │
│  Kognition ██████████ 5.0  ← Primært lag                    │
│  Ekstern   ██████░░░░ 3.0                                   │
│                                                             │
│  → Under pres går du mest i KOGNITION-laget.                │
│    Du analyserer, tænker, planlægger - men handler ikke.    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SAMMENFATNING                                              │
│  ───────────────────────────────────────                    │
│                                                             │
│  Du har primært meningsfriktion, og din kæde stopper        │
│  typisk ved overgangen fra tanke til handling. Under pres   │
│  går du i overanalyse og grublen.                           │
│                                                             │
│  Dette mønster ses ofte hos mennesker der:                  │
│  • Har mange gode ideer men får dem ikke eksekveret         │
│  • Prokrastinerer trods god selvindsigt                     │
│  • Bruger analyse som regulering (i stedet for handling)    │
│                                                             │
│  Anbefaling: Overvej en Dyb Måling for mere detaljeret      │
│  kortlægning af dit reguleringssystem.                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema (Screening)

```sql
-- Spørgsmål til screening
CREATE TABLE profil_questions_screening (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL UNIQUE,  -- 'S1', 'S2', ... 'S13'
    text_da TEXT NOT NULL,
    text_en TEXT,
    section TEXT NOT NULL,             -- 'felt', 'opad', 'manifest'
    target TEXT NOT NULL,              -- 'tryghed', 'emo_indre', 'biologi' etc.
    sort_order INTEGER
);

-- Svar på screening
CREATE TABLE profil_responses_screening (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    respondent_token TEXT,
    question_id TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 7),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);

-- Beregnede screening-profiler
CREATE TABLE profil_scores_screening (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    respondent_token TEXT,

    -- Felter
    felt_tryghed INTEGER,
    felt_mening INTEGER,
    felt_kan INTEGER,
    felt_besvaer INTEGER,
    primaert_felt TEXT,

    -- Opad
    opad_bio_emo INTEGER,
    opad_emo_indre INTEGER,
    opad_indre_kog INTEGER,
    opad_kog_ekstern INTEGER,
    stop_punkt TEXT,

    -- Manifestation
    manifest_biologi INTEGER,
    manifest_emotion INTEGER,
    manifest_indre INTEGER,
    manifest_kognition INTEGER,
    manifest_ekstern INTEGER,
    primaert_lag TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);
```

---

# DEL 2: DYB MÅLING (88 items)

## Formål

Dette dokument beskriver det **fulde målesystem** for Friktionskompasset - en "dyb måling" der kortlægger:

1. **Baseline-friktion** i de 4 felter (Tryghed, Mening, Kan, Besvær)
2. **Opad-båndbredde** - hvor godt kan pres bevæge sig op gennem lagene?
3. **Nedad-ruter** - hvor falder pres ned, og hvilke strategier bruges?
4. **Stop-punkter** - hvor i søjlen "hopper kæden af"?
5. **Ubrudte vs brudte søjler** - kan hele kæden bære pres?

---

## Systemarkitektur

```
                    EKSTERN (Adfærd/Omgivelser)
                           ↑↓
                    KOGNITION (Tanker/Forståelse)
                           ↑↓
                    INDRE (Selvoplevelse/Identitet)
                           ↑↓
                    EMOTION (Følelser)
                           ↑↓
                    BIOLOGI (Krop/Fysiologi)
```

### De 4 Felter (hvor friktion opstår)
- **Tryghed**: Grundlæggende sikkerhed og ro
- **Mening**: Oplevelse af formål og engagement
- **Kan**: Oplevet handleevne og kompetence
- **Besvær**: Evne til at håndtere praktiske forhindringer

### De 5 Lag (hvor pres manifesterer sig)
- **Biologi**: Krop, søvn, spænding, somatiske symptomer
- **Emotion**: Følelser, affekt, emotionel reaktion
- **Indre**: Selvoplevelse, identitet, værdighed, skam
- **Kognition**: Tanker, analyse, forståelse, planlægning
- **Ekstern**: Adfærd, handlinger, omgivelser

### De 8 Overgange (båndbredde mellem lag)

**Opad (fra krop til handling):**
1. Biologi → Emotion
2. Emotion → Indre
3. Indre → Kognition
4. Kognition → Ekstern

**Nedad (fra omverden til krop):**
5. Ekstern → Kognition
6. Kognition → Indre
7. Indre → Emotion
8. Emotion → Biologi

---

## Spørgeskema-struktur (70 items)

### Svarskala (alle items)
```
1 = Slet ikke typisk for mig
2 = Sjældent typisk for mig
3 = Lidt typisk for mig
4 = Hverken/eller
5 = Noget typisk for mig
6 = Ofte typisk for mig
7 = Meget typisk for mig
```

### Sektion A: Felter - Baseline-friktion (16 items)

#### Tryghed (A1-A4)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| A1 | Jeg føler mig ofte på vagt, selv når der objektivt ikke er noget galt. | Direkte |
| A2 | Jeg bliver hurtigt urolig i kroppen, når jeg er sammen med andre. | Direkte |
| A3 | Kritik eller negative kommentarer sidder længe i mig. | Direkte |
| A4 | Jeg har let ved at føle mig tryg, også i nye situationer. | **Omvendt** |

#### Mening (A5-A8)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| A5 | Jeg mister hurtigt engagementet, hvis jeg ikke kan se meningen med det, jeg skal. | Direkte |
| A6 | Jeg bliver irriteret eller modstanderisk, når andre vil bestemme retningen for mig. | Direkte |
| A7 | Jeg kan godt motivere mig selv, selvom jeg ikke helt kan se pointen. | **Omvendt** |
| A8 | Jeg føler mig ofte tom eller ligeglad i forhold til det, jeg laver. | Direkte |

#### Kan (A9-A12)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| A9 | Jeg tvivler ofte på, om jeg kan løse de opgaver, jeg står med. | Direkte |
| A10 | Jeg mister nemt modet, hvis jeg ikke hurtigt kan se, hvordan jeg skal gribe noget an. | Direkte |
| A11 | Jeg føler mig som udgangspunkt kompetent i det meste af det, jeg laver. | **Omvendt** |
| A12 | Hvis noget er vigtigt, men svært, tænker jeg ofte: "Det kan jeg nok ikke." | Direkte |

#### Besvær (A13-A16)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| A13 | Jeg udskyder ofte opgaver, selv når jeg godt ved, de er vigtige. | Direkte |
| A14 | Jeg bliver hurtigt drænet af praktiske trin, struktur og systemer. | Direkte |
| A15 | Jeg går som regel bare i gang, selvom noget virker lidt bøvlet. | **Omvendt** |
| A16 | Når en opgave virker omfattende, mister jeg ofte lysten til at gå i gang. | Direkte |

---

### Sektion B: Båndbredde-problemer (32 items)

Måler hvor **svært** det er at få pres igennem hver overgang.
**Høj score = lav båndbredde = problem**

#### B1-B4: Biologi → Emotion (opad)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| B1 | Min krop reagerer (hjerte, mave, spænding), før jeg ved, hvad jeg føler. | Direkte |
| B2 | Jeg har svært ved at skelne mellem kropslige signaler (fx sult, træthed, angst). | Direkte |
| B3 | Jeg opdager ofte først mine følelser ved at mærke kroppen. | Direkte |
| B4 | Når min krop reagerer, ved jeg som regel ret hurtigt, hvad følelsen handler om. | **Omvendt** |

#### B5-B8: Emotion → Indre (opad)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| B5 | Jeg bliver følelsesmæssigt overvældet uden at kunne sætte ord på hvorfor. | Direkte |
| B6 | Når jeg har det svært, er det svært at mærke, hvad det betyder for mig som person. | Direkte |
| B7 | Jeg ved sjældent, hvad jeg har brug for, når jeg er følelsesmæssigt presset. | Direkte |
| B8 | Når jeg føler noget stærkt, kan jeg tydeligt mærke, hvad det siger om mig og mine grænser. | **Omvendt** |

#### B9-B12: Indre → Kognition (opad)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| B9 | Når noget rammer mig personligt, mister jeg let overblikket. | Direkte |
| B10 | Jeg kan have det meget stærkt med noget, uden at kunne forklare det for andre. | Direkte |
| B11 | Jeg kan som regel godt tænke klart, selv når noget betyder meget for mig. | **Omvendt** |
| B12 | Jeg har svært ved at forstå mig selv i situationer, hvor jeg bliver ramt på min værdighed. | Direkte |

#### B13-B16: Kognition → Ekstern (opad)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| B13 | Jeg ved præcis, hvad jeg burde gøre, men får det alligevel ikke gjort. | Direkte |
| B14 | Jeg kan lave detaljerede planer, som jeg bagefter ikke får fulgt. | Direkte |
| B15 | Når jeg først har besluttet mig, er jeg god til at omsætte det til handling. | **Omvendt** |
| B16 | Jeg fryser eller går i stå, når jeg skal udføre noget, der betyder noget for mig. | Direkte |

#### B17-B20: Ekstern → Kognition (nedad)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| B17 | Når andre forklarer mig noget vigtigt, lukker jeg nemt ned indeni. | Direkte |
| B18 | Jeg bliver ofte mere forvirret end hjulpet af andres instruktioner eller råd. | Direkte |
| B19 | Jeg kan typisk nemt omsætte input udefra til noget, jeg forstår og kan bruge. | **Omvendt** |
| B20 | Når nogen giver mig feedback, har jeg svært ved at integrere det, selv hvis jeg er enig. | Direkte |

#### B21-B24: Kognition → Indre (nedad)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| B21 | Jeg kan rationelt forstå noget, uden at det føles sandt for mig. | Direkte |
| B22 | Jeg ved godt, at noget "bare er sådan", men min indre reaktion ændrer sig ikke. | Direkte |
| B23 | Når jeg har forstået noget vigtigt, kan jeg som regel mærke det som en ændring i mig. | **Omvendt** |
| B24 | Jeg kan ofte forklare noget klogt, som overhovedet ikke ændrer, hvordan jeg har det. | Direkte |

#### B25-B28: Indre → Emotion (nedad)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| B25 | Jeg ved godt, hvad jeg står for, men følelsesmæssigt føles det nogle gange fladt. | Direkte |
| B26 | Jeg kan opleve, at jeg "burde føle noget", men ikke rigtig kan. | Direkte |
| B27 | Når noget er vigtigt for mig, kan jeg tydeligt mærke følelsen, der hører til. | **Omvendt** |
| B28 | Jeg kan have en stærk holdning uden at mærke nogen særlig følelse for den. | Direkte |

#### B29-B32: Emotion → Biologi (nedad)
| ID | Spørgsmål | Retning |
|----|-----------|---------|
| B29 | Når jeg bliver følelsesmæssigt presset, kan jeg ikke få kroppen til at falde ned igen. | Direkte |
| B30 | Følelsesmæssigt pres sætter sig hurtigt som kropslige spændinger eller symptomer. | Direkte |
| B31 | Når jeg får det bedre følelsesmæssigt, kan min krop også let slippe spændingen. | **Omvendt** |
| B32 | Jeg kan holde stærke følelser inde længe, indtil kroppen "eksploderer". | Direkte |

---

### Sektion C: Manifestationslag (10 items)

**Instruktion**: "Tænk på situationer, hvor du er presset."

| ID | Spørgsmål | Lag |
|----|-----------|-----|
| C1 | Det første, jeg lægger mærke til, er kroppen (søvn, mave, spænding, hovedpine). | Biologi |
| C2 | Det første, jeg lægger mærke til, er stærke følelser (vrede, tristhed, opgivenhed). | Emotion |
| C3 | Det første, jeg lægger mærke til, er at jeg begynder at tænke hårdt eller køre i ring. | Kognition |
| C4 | Det første, jeg lægger mærke til, er skam, selvkritik eller følelsen af at være forkert. | Indre |
| C5 | Det første, jeg lægger mærke til, er at jeg ændrer på min adfærd (trækker mig, overspiser, flygter, arbejder mere). | Ekstern |
| C6 | Under pres får jeg oftest fysiske symptomer. | Biologi |
| C7 | Under pres reagerer jeg mest følelsesmæssigt. | Emotion |
| C8 | Under pres går jeg mest i mit eget hoved. | Kognition |
| C9 | Under pres bliver jeg hård ved mig selv. | Indre |
| C10 | Under pres ændrer jeg helst på omgivelserne (aflyser, skifter opgave, skifter relation, laver rod/orden). | Ekstern |

---

### Sektion D: Reguleringsstrategier (12 items)

| ID | Spørgsmål | Strategi |
|----|-----------|----------|
| D1 | Når jeg skal berolige mig selv, gør jeg typisk noget med min krop (spiser, bevæger mig, lægger mig, skærm osv.). | Kropslig |
| D2 | Når jeg får det svært, reagerer jeg mest gennem følelser (gråd, vrede, følelsesudbrud eller følelseslukning). | Emotionel |
| D3 | Når jeg får det svært, går jeg mest i selvfortællinger om, hvem jeg er ("jeg er dum", "jeg skal tage mig sammen", "jeg dur ikke"). | Indre |
| D4 | Når jeg får det svært, prøver jeg at få styr på det ved at analysere, forstå og planlægge. | Kognitiv |
| D5 | Når jeg får det svært, ændrer jeg ofte på mine omgivelser (skifter opgave, rydder op/roder, flytter mig, skifter relation). | Ekstern |
| D6 | Jeg søger ofte lindring gennem mad, nikotin, alkohol, skærm eller lignende. | Kropslig |
| D7 | Jeg søger ofte lindring ved at tale med nogen om, hvordan jeg har det. | Emotionel |
| D8 | Jeg søger ofte lindring ved at trække mig og være alene. | Indre |
| D9 | Jeg søger ofte lindring ved at arbejde mere eller gøre mig ekstra umage. | Kognitiv |
| D10 | Jeg søger ofte lindring ved at ignorere det og "køre videre". | Ekstern |
| D11 | Jeg har mindst én strategi, der næsten altid hjælper mig lidt. | **Omvendt** (Robusthed) |
| D12 | Når jeg er meget presset, føles det, som om ingen strategier rigtig virker. | Direkte |

---

### Sektion E: Opad-kapacitet (8 items) - NY

Måler hvor **godt** pres kan bevæge sig op gennem lagene.
**Høj score = høj kapacitet = ubrudt søjle**

| ID | Spørgsmål | Overgang | Retning |
|----|-----------|----------|---------|
| E1 | Jeg kan mærke ret tydeligt, hvad min krop prøver at fortælle mig følelsesmæssigt. | Bio→Emo | Direkte |
| E2 | Når jeg føler noget stærkt, kan jeg hurtigt mærke, hvad det betyder for mig som person. | Emo→Indre | Direkte |
| E3 | Selv når noget rammer mig dybt, kan jeg normalt forstå mig selv og sætte ord på det. | Indre→Kog | Direkte |
| E4 | Når jeg først har besluttet mig, er jeg god til at omsætte det til konkret handling. | Kog→Ekstern | Direkte |
| E5 | Jeg kan typisk tage imod input/feedback fra andre og gøre det til noget, jeg forstår og kan bruge. | Ekstern→Kog | Direkte |
| E6 | Når jeg virkelig forstår noget vigtigt, kan jeg mærke, at det forandrer noget i mig. | Kog→Indre | Direkte |
| E7 | Når noget stemmer med mine værdier, kan jeg mærke en tydelig følelsesmæssig resonans. | Indre→Emo | Direkte |
| E8 | Når jeg har stærke følelser, kan min krop godt få dem til at falde ned igen (fx via åndedræt, bevægelse, ro). | Emo→Bio | Direkte |

---

## Scoring

### 1. Reverse Scoring

For items markeret som **Omvendt**, beregnes:
```
omvendt_score = 8 - original_score
```

**Omvendte items:**
- Sektion A: A4, A7, A11, A15
- Sektion B: B4, B8, B11, B15, B19, B23, B27, B31
- Sektion D: D11

### 2. Skala-beregning

#### Felter (gennemsnit, 1-7, høj = mere friktion)
```python
tryghed = mean(A1, A2, A3, A4_R)
mening = mean(A5, A6, A7_R, A8)
kan = mean(A9, A10, A11_R, A12)
besvaer = mean(A13, A14, A15_R, A16)
```

#### Båndbredde-problem (gennemsnit, 1-7, høj = mere problem)
```python
# Opad
bio_emo_problem = mean(B1, B2, B3, B4_R)
emo_indre_problem = mean(B5, B6, B7, B8_R)
indre_kog_problem = mean(B9, B10, B11_R, B12)
kog_ekstern_problem = mean(B13, B14, B15_R, B16)

# Nedad
ekstern_kog_problem = mean(B17, B18, B19_R, B20)
kog_indre_problem = mean(B21, B22, B23_R, B24)
indre_emo_problem = mean(B25, B26, B27_R, B28)
emo_bio_problem = mean(B29, B30, B31_R, B32)
```

#### Opad-kapacitet (enkelt item, 1-7, høj = god kapacitet)
```python
bio_emo_kapacitet = E1
emo_indre_kapacitet = E2
indre_kog_kapacitet = E3
kog_ekstern_kapacitet = E4
ekstern_kog_kapacitet = E5
kog_indre_kapacitet = E6
indre_emo_kapacitet = E7
emo_bio_kapacitet = E8
```

#### Kombineret Opad-Index (1-7, høj = god båndbredde)
```python
def opad_index(kapacitet, problem):
    return (kapacitet + (8 - problem)) / 2

bio_emo_index = opad_index(E1, bio_emo_problem)
emo_indre_index = opad_index(E2, emo_indre_problem)
# ... osv for alle 8 overgange
```

#### Manifestationslag (gennemsnit, 1-7)
```python
manifest_biologi = mean(C1, C6)
manifest_emotion = mean(C2, C7)
manifest_kognition = mean(C3, C8)
manifest_indre = mean(C4, C9)
manifest_ekstern = mean(C5, C10)
```

#### Reguleringsstrategier (gennemsnit, 1-7)
```python
reg_kropslig = mean(D1, D6)
reg_emotionel = mean(D2, D7)
reg_indre = mean(D3, D8)
reg_kognitiv = mean(D4, D9)
reg_ekstern = mean(D5, D10)
robusthed = mean(D11_R, D12)  # Høj = lav robusthed
```

---

## Profil-analyse

### 1. Baseline-friktion (Felter)

Identificer det/de felter med højest score:
- Score > 5: **Høj friktion** i feltet
- Score 3.5-5: **Moderat friktion**
- Score < 3.5: **Lav friktion**

### 2. Søjle-analyse (Opad-båndbredde)

For hver af de 4 opad-overgange, beregn opad_index:

```
Ubrudt søjle: Alle opad_index > 4.5
Delvist brudt: Mindst én opad_index < 3.5
Brudt søjle: Mindst én opad_index < 2.5
```

**Stop-punkt** = den overgang med lavest opad_index

### 3. Nedad-analyse

Kombinér manifestationslag + reguleringsstrategi:

```
Primært manifestationslag = lag med højest manifest_* score
Sekundært manifestationslag = lag med næsthøjest score

Primær reguleringsstrategi = strategi med højest reg_* score
```

### 4. Kæde-hop identifikation

En "kæde hopper af" når:
1. Høj manifestationsscore i et lag (> 5)
2. Lavt opad_index i overgangen op fra det lag (< 3.5)
3. Høj reguleringsstrategi i samme eller lavere lag

**Eksempel:**
- Høj manifest_emotion (5.5)
- Lavt emo_indre_index (2.8)
- Høj reg_emotionel (5.2)
→ "Kæden hopper af ved emotion-laget, pres kan ikke komme op til indre/kognition"

---

## Profiltyper (eksempler)

### Type A: Somatisering
- Høj bio_emo_problem
- Lav bio_emo_kapacitet
- Høj manifest_biologi
- Høj reg_kropslig
→ "Kroppen larmer, følelser uklare, regulerer via krop"

### Type B: Emotionel overload
- Høj emo_indre_problem
- Høj manifest_emotion
- Høj reg_emotionel
→ "Følelser overvælder, kan ikke blive til mening/identitet"

### Type C: Kognitiv freeze
- Høj kog_ekstern_problem
- Høj manifest_kognition
- Høj reg_kognitiv
→ "Forstår alt, kan ikke handle, overanalyse"

### Type D: Identitets-kollaps
- Høj indre_kog_problem
- Høj manifest_indre
- Høj reg_indre (selvkritik)
→ "Ramt på værdighed, skam, selvangreb"

### Type E: Ekstern flugt
- Høj manifest_ekstern
- Høj reg_ekstern
→ "Ændrer omgivelser i stedet for intern regulering"

---

## Database Schema

```sql
-- Spørgsmål til dyb måling
CREATE TABLE profil_questions_deep (
    id TEXT PRIMARY KEY,
    section TEXT NOT NULL,           -- 'A', 'B', 'C', 'D', 'E'
    question_number INTEGER NOT NULL, -- 1-16 for A, 1-32 for B, etc.
    question_id TEXT NOT NULL,        -- 'A1', 'B15', 'E3' etc.
    text_da TEXT NOT NULL,
    text_en TEXT,
    is_reverse INTEGER DEFAULT 0,     -- 1 = skal vendes
    field TEXT,                       -- For A: 'tryghed', 'mening', 'kan', 'besvaer'
    layer TEXT,                       -- For C/D: 'biologi', 'emotion', 'indre', 'kognition', 'ekstern'
    transition TEXT,                  -- For B/E: 'bio_emo', 'emo_indre', etc.
    direction TEXT,                   -- For B/E: 'up', 'down'
    sort_order INTEGER
);

-- Svar på dyb måling
CREATE TABLE profil_responses_deep (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    respondent_token TEXT,
    question_id TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 7),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES profil_questions_deep(id)
);

-- Beregnede profiler
CREATE TABLE profil_scores_deep (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    respondent_token TEXT,

    -- Felter
    field_tryghed REAL,
    field_mening REAL,
    field_kan REAL,
    field_besvaer REAL,

    -- Båndbredde-problemer (opad)
    problem_bio_emo REAL,
    problem_emo_indre REAL,
    problem_indre_kog REAL,
    problem_kog_ekstern REAL,

    -- Båndbredde-problemer (nedad)
    problem_ekstern_kog REAL,
    problem_kog_indre REAL,
    problem_indre_emo REAL,
    problem_emo_bio REAL,

    -- Opad-kapacitet
    kapacitet_bio_emo REAL,
    kapacitet_emo_indre REAL,
    kapacitet_indre_kog REAL,
    kapacitet_kog_ekstern REAL,
    kapacitet_ekstern_kog REAL,
    kapacitet_kog_indre REAL,
    kapacitet_indre_emo REAL,
    kapacitet_emo_bio REAL,

    -- Kombineret index
    index_bio_emo REAL,
    index_emo_indre REAL,
    index_indre_kog REAL,
    index_kog_ekstern REAL,
    index_ekstern_kog REAL,
    index_kog_indre REAL,
    index_indre_emo REAL,
    index_emo_bio REAL,

    -- Manifestation
    manifest_biologi REAL,
    manifest_emotion REAL,
    manifest_kognition REAL,
    manifest_indre REAL,
    manifest_ekstern REAL,

    -- Regulering
    reg_kropslig REAL,
    reg_emotionel REAL,
    reg_indre REAL,
    reg_kognitiv REAL,
    reg_ekstern REAL,
    reg_robusthed REAL,

    -- Meta-analyse
    primary_field TEXT,           -- Felt med højest friktion
    stop_point TEXT,              -- Overgang med lavest index
    primary_manifest TEXT,        -- Primært manifestationslag
    primary_regulation TEXT,      -- Primær reguleringsstrategi
    chain_status TEXT,            -- 'intact', 'partial', 'broken'

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);
```

---

## Visualisering

### 1. Felt-diagram (4 søjler)
```
Tryghed  ████████░░ 4.2
Mening   ██████████ 5.1  ← Højest
Kan      ██████░░░░ 3.1
Besvær   ███████░░░ 3.8
```

### 2. Søjle-diagram (vertikal kæde)
```
         OPAD                    NEDAD

EKSTERN ─────────────────────── EKSTERN
    ↑ [4.8] ██████████          ↓ [3.2] ██████░░░░
KOGNITION ───────────────────── KOGNITION
    ↑ [2.1] ████░░░░░░ STOP!    ↓ [4.5] █████████░
INDRE ─────────────────────────── INDRE
    ↑ [3.5] ███████░░░          ↓ [5.2] ██████████
EMOTION ─────────────────────── EMOTION
    ↑ [4.2] ████████░░          ↓ [3.8] ████████░░
BIOLOGI ─────────────────────── BIOLOGI
```

### 3. Manifestation + Regulering
```
MANIFESTATION           REGULERING
Biologi   ████░░ 2.1    Kropslig  ██████ 3.2
Emotion   ██████ 3.4    Emotionel █████░ 2.8
Indre     ████████ 4.2  Indre     ████████ 4.5 ←
Kognition ██████████ 5.1 ← Kognitiv ██████ 3.1
Ekstern   ████░░ 2.3    Ekstern   ████░░ 2.2
```

---

## Implementation Plan

### Fase 1: Database
1. [ ] Opret tabeller til dyb måling
2. [ ] Seed alle 78 spørgsmål (A16 + B32 + C10 + D12 + E8)
3. [ ] Tilføj både dansk og engelsk tekst

### Fase 2: Survey Flow
4. [ ] Ny kampagnetype: "Dyb måling"
5. [ ] Survey-side med alle sektioner
6. [ ] Progress-indikator (5 sektioner)
7. [ ] Gem svar i profil_responses_deep

### Fase 3: Scoring
8. [ ] Scoring-funktion med reverse-scoring
9. [ ] Beregn alle skalaer
10. [ ] Beregn kombinerede indeks
11. [ ] Identificer stop-punkter og kæde-status
12. [ ] Gem i profil_scores_deep

### Fase 4: Visualisering
13. [ ] Felt-diagram
14. [ ] Søjle-diagram (opad/nedad)
15. [ ] Manifestation/regulering-diagram
16. [ ] Profil-rapport med fortolkning

### Fase 5: Rapport
17. [ ] Tekstuel profil-beskrivelse
18. [ ] Anbefalinger baseret på profiltype
19. [ ] PDF-eksport

---

## Appendix: Alle Items (Komplet Liste)

### Sektion A (16 items)
A1-A4: Tryghed
A5-A8: Mening
A9-A12: Kan
A13-A16: Besvær

### Sektion B (32 items)
B1-B4: Bio→Emo (opad)
B5-B8: Emo→Indre (opad)
B9-B12: Indre→Kog (opad)
B13-B16: Kog→Ekstern (opad)
B17-B20: Ekstern→Kog (nedad)
B21-B24: Kog→Indre (nedad)
B25-B28: Indre→Emo (nedad)
B29-B32: Emo→Bio (nedad)

### Sektion C (10 items)
C1, C6: Biologi
C2, C7: Emotion
C3, C8: Kognition
C4, C9: Indre
C5, C10: Ekstern

### Sektion D (12 items)
D1, D6: Kropslig
D2, D7: Emotionel
D3, D8: Indre
D4, D9: Kognitiv
D5, D10: Ekstern
D11, D12: Robusthed

### Sektion E (8 items)
E1: Bio→Emo kapacitet
E2: Emo→Indre kapacitet
E3: Indre→Kog kapacitet
E4: Kog→Ekstern kapacitet
E5: Ekstern→Kog kapacitet
E6: Kog→Indre kapacitet
E7: Indre→Emo kapacitet
E8: Emo→Bio kapacitet

### Sektion F (10 items) - NY
F1-F7: Forbrugshyppighed (frekvens-skala)
F8-F10: Forbrugsafhængighed (Likert)

**Total: 88 items**

---

## Sektion F: Forbrugsmønstre (10 items) - NY

Denne sektion måler **kropslig selvmedicinering** - hvor meget personen bruger
eksterne stoffer/adfærd til at regulere indre tilstande. Dette er en stærk
indikator for hvor i systemet reguleringen sidder.

### Hyppigheds-items (F1-F7)

**Instruktion**: "Hvor ofte bruger du følgende til at regulere dit humør, stress eller indre uro?"

**Svarskala**:
```
1 = Aldrig
2 = Sjældent (få gange om året)
3 = Månedligt
4 = Ugentligt
5 = Flere gange om ugen
6 = Dagligt
7 = Flere gange dagligt
```

| ID | Spørgsmål | Type |
|----|-----------|------|
| F1 | Alkohol (øl, vin, spiritus) | Stof |
| F2 | Nikotin (cigaretter, snus, vape) | Stof |
| F3 | Koffein (kaffe, energidrik) for at regulere humør/energi | Stof |
| F4 | Mad som trøst eller belønning (udover sult) | Adfærd |
| F5 | Skærm/gaming/scrolling for at koble af eller flygte | Adfærd |
| F6 | Shopping eller køb af ting for at føle dig bedre | Adfærd |
| F7 | Søvn/ligge i sengen for at undgå noget | Adfærd |

### Afhængigheds-items (F8-F10)

**Svarskala**: Standard 1-7 Likert

| ID | Spørgsmål | Retning |
|----|-----------|---------|
| F8 | Jeg har brug for "noget" (mad, skærm, alkohol, rygning el.lign.) for at falde ned efter en hård dag. | Direkte |
| F9 | Uden mine vaner ville jeg have svært ved at fungere i hverdagen. | Direkte |
| F10 | Jeg ved godt, at nogle af mine vaner ikke er gode for mig, men jeg kan ikke stoppe. | Direkte |

### Scoring

#### Forbrugsprofil (F1-F7)
Beregn gennemsnit for hver kategori:
```python
forbrug_stof = mean(F1, F2, F3)      # Stof-baseret regulering
forbrug_adfaerd = mean(F4, F5, F6, F7)  # Adfærds-baseret regulering
forbrug_total = mean(F1-F7)          # Samlet forbrugsniveau
```

#### Afhængighedsgrad (F8-F10)
```python
afhaengighed = mean(F8, F9, F10)     # Høj = høj afhængighed
```

#### Fortolkning

| Score | Niveau | Betydning |
|-------|--------|-----------|
| 1-2 | Lavt | Minimal brug af ekstern regulering |
| 3-4 | Moderat | Noget brug, men ikke problematisk |
| 5-6 | Højt | Hyppig brug, mulig afhængighed |
| 7 | Kritisk | Daglig/flere gange dagligt, stærk afhængighed |

### Sammenhæng med resten af systemet

Høj forbrug + høj afhængighed korrelerer typisk med:
- Høj `reg_kropslig` (D1, D6)
- Høj `manifest_biologi` (C1, C6)
- Lav `bio_emo_index` (pres kan ikke komme op fra krop til følelser)
- Høj friktion i et eller flere felter

**Profiltype: "Kropslig afhængighed"**
- Høj forbrug_total (> 4)
- Høj afhaengighed (> 5)
- Høj reg_kropslig
- Lav opad-kapacitet i bio→emo
→ "Regulerer næsten udelukkende via kroppen, pres når sjældent op til bevidst bearbejdning"

### Database-udvidelse

```sql
-- Tilføj til profil_scores_deep
ALTER TABLE profil_scores_deep ADD COLUMN forbrug_stof REAL;
ALTER TABLE profil_scores_deep ADD COLUMN forbrug_adfaerd REAL;
ALTER TABLE profil_scores_deep ADD COLUMN forbrug_total REAL;
ALTER TABLE profil_scores_deep ADD COLUMN afhaengighed REAL;
```

### Visualisering

```
FORBRUGSMØNSTRE

Stoffer                    Adfærd
Alkohol    ████████░░ 4.2   Mad      ██████████ 5.5 ←
Nikotin    ██░░░░░░░░ 1.5   Skærm    ████████░░ 4.0
Koffein    ██████░░░░ 3.2   Shopping ████░░░░░░ 2.0
                            Søvn     ██████░░░░ 3.5

Afhængighed: ████████░░ 4.3 (Moderat-Høj)

→ Primær regulering via mad og skærm
→ Moderat afhængighedsgrad
```

### Etiske overvejelser

1. **Anonymitet**: Data om forbrug er særligt følsomt
2. **Ingen illegale stoffer**: Vi spørger ikke om hash, kokain etc.
3. **Ingen diagnose**: Vi siger ikke "du er alkoholiker"
4. **Fokus på funktion**: Vi måler reguleringsmønster, ikke misbrug
5. **Normalisering**: Alle bruger noget til at regulere - det er graden der tæller
