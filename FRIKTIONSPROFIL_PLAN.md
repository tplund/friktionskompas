# Implementeringsplan: Friktionsprofil-modul

## Overblik

Friktionsprofilen er et individuelt målingsværktøj der supplerer det eksisterende Friktionskompasset (gruppemåling). Hvor Friktionskompasset måler "hvordan oplever teamet friktion?", måler Friktionsprofilen "hvordan bevæger pres sig gennem dig?" - individuel reguleringsarkitektur.

### Use cases
- **MUS-samtaler**: Leder og medarbejder ser begges profiler
- **Konfliktløsning**: Sammenlign 2 personers profiler
- **Individuel coaching**: Dybere indsigt end gruppemåling
- **Onboarding**: Forstå nye medarbejderes friktionsmønstre

---

## Arkitektur

### Datamodel

Friktionsprofilen måler 4 felter × 4 lag = 16 datapunkter per person:

```
            TRYGHED   MENING    KAN      BESVÆR
Kognition   [score]   [score]   [score]  [score]
Indre       [score]   [score]   [score]  [score]
Emotion     [score]   [score]   [score]  [score]
Biologi     [score]   [score]   [score]  [score]
```

Hvert felt har 4 spørgsmål - et per lag (Biologi, Emotion, Indre, Kognition).

### Nye database-tabeller

```sql
-- Friktionsprofil spørgsmål
CREATE TABLE profil_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field TEXT NOT NULL,           -- TRYGHED, MENING, KAN, BESVÆR
    layer TEXT NOT NULL,           -- BIOLOGI, EMOTION, INDRE, KOGNITION
    text_da TEXT NOT NULL,
    reverse_scored INTEGER DEFAULT 0,
    sequence INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Friktionsprofil sessioner (en måling = en session)
CREATE TABLE profil_sessions (
    id TEXT PRIMARY KEY,
    person_name TEXT,              -- Valgfrit navn
    person_email TEXT,             -- Til at sende rapport
    context TEXT,                  -- 'mus', 'konflikt', 'coaching', 'general'

    -- Valgfri kobling til organisation
    unit_id TEXT,                  -- FK til organizational_units
    campaign_id TEXT,              -- Hvis del af en kampagne

    -- Metadata
    is_complete INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (unit_id) REFERENCES organizational_units(id)
);

-- Friktionsprofil svar
CREATE TABLE profil_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES profil_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES profil_questions(id)
);

-- Indexes
CREATE INDEX idx_profil_responses_session ON profil_responses(session_id);
CREATE INDEX idx_profil_sessions_unit ON profil_sessions(unit_id);
```

### Sammenligningstabel (til MUS/konflikt)

```sql
-- Profil-sammenligning (2 personer)
CREATE TABLE profil_comparisons (
    id TEXT PRIMARY KEY,
    session_id_1 TEXT NOT NULL,    -- Person 1
    session_id_2 TEXT NOT NULL,    -- Person 2
    context TEXT,                  -- 'mus', 'konflikt'
    notes TEXT,                    -- Facilitators noter
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id_1) REFERENCES profil_sessions(id),
    FOREIGN KEY (session_id_2) REFERENCES profil_sessions(id)
);
```

---

## Spørgsmål (16 stk)

Fra prototype-dokumentet - 4 spørgsmål per felt:

### TRYGHED

| Lag | Spørgsmål |
|-----|-----------|
| Biologi | Jeg reagerer hurtigt fysisk, når noget virker uforudsigeligt |
| Emotion | Jeg opfanger små signaler eller stemninger meget tydeligt |
| Indre | Jeg bliver urolig, hvis min oplevelse af virkeligheden bliver udfordret |
| Kognition | Jeg falder til ro, når jeg forstår, hvad der foregår |

### MENING

| Lag | Spørgsmål |
|-----|-----------|
| Biologi | Når noget ikke giver mening, føles det fysisk forkert |
| Emotion | Jeg mærker stærkt, hvad der er vigtigt for mig |
| Indre | Jeg får hurtigt retning, når jeg tænker over noget |
| Kognition | Jeg kan holde meget pres ud, hvis meningen er klar |

### KAN

| Lag | Spørgsmål |
|-----|-----------|
| Biologi | Jeg mærker energifald hurtigt i kroppen |
| Emotion | Jeg bliver let overvældet, hvis der er mange ting på én gang |
| Indre | Jeg regulerer mig selv bedst ved at forstå, hvad jeg skal |
| Kognition | Jeg kan tænke klart, selv når jeg er presset *(omvendt score)* |

### BESVÆR

| Lag | Spørgsmål |
|-----|-----------|
| Biologi | Små ting kan føles tunge, når jeg er træt |
| Emotion | Jeg undgår ting, der føles som bøvl eller kompleksitet |
| Indre | Jeg gør ting lettere ved at forstå processen |
| Kognition | Jeg mister overblik i opgaver med mange små elementer |

---

## Analyse-logik

### Trin 1: Score-beregning
- Hver celle i 4×4 matrix = direkte score (1-5)
- Omvendt score for markerede spørgsmål: `6 - score`

### Trin 2: Farve-mapping

| Score-interval | Farve | Betydning |
|----------------|-------|-----------|
| 1.0 – 2.2 | 🟩 Grøn | Robust / lav presfølsomhed |
| 2.3 – 3.7 | 🟨 Gul | Sensitiv / svingende |
| 3.8 – 5.0 | 🟧 Orange | Lav tærskel / sårbart |

### Trin 3: Søjle-analyse (per felt)
```python
def analyze_column(field_scores):
    """Analyser en enkelt friktionssøjle"""
    return {
        'scores': field_scores,  # Dict med lag -> score
        'colors': {lag: map_color(score) for lag, score in field_scores.items()},
        'manifestation_layer': find_first_orange(field_scores),
        'avg_score': sum(field_scores.values()) / len(field_scores)
    }
```

### Trin 4: Båndbredde-beregning
```python
def calculate_bandwidth(field_scores):
    """
    Høj båndbredde = pres kan rejse højt opad
    Lav båndbredde = søjlen 'knækker' i midten
    """
    kogn = field_scores['KOGNITION']
    bio = field_scores['BIOLOGI']

    # Simpel version: forskel mellem top og bund
    bandwidth = kogn - bio

    # Positiv = god båndbredde (kan løfte pres op)
    # Negativ = lav båndbredde (pres sidder fast i kroppen)
    return bandwidth
```

### Trin 5: Manifestationslag
```python
def find_manifestation_layer(field_scores):
    """Find det første lag med orange (høj friktion)"""
    layer_order = ['BIOLOGI', 'EMOTION', 'INDRE', 'KOGNITION']

    for layer in layer_order:
        if field_scores[layer] >= 3.8:  # Orange tærskel
            return layer

    return None  # Ingen orange = robust søjle
```

---

## Fil-struktur

```
friktionsprofil/
├── db_profil.py              # Database-funktioner
├── analysis_profil.py        # Analyse-logik
├── profil_app.py             # Flask routes (eller tilføj til admin_app.py)
└── templates/
    └── profil/
        ├── survey.html       # Spørgeskema (16 spørgsmål)
        ├── report.html       # Individuel rapport med farvegrid
        ├── compare.html      # Sammenligning af 2 profiler
        └── admin.html        # Admin-oversigt over profiler
```

**Alternativ**: Integrér direkte i eksisterende filer med prefix `profil_*`

---

## Routes

### Survey-flow

```python
# Start ny profil-session
GET /profil/start
    → Vis formular: navn, email, context
    → Opret session, redirect til spørgsmål

# Udfyld spørgeskema
GET /profil/<session_id>
    → Vis 16 spørgsmål grupperet efter felt
    → Submit gemmer alle svar

POST /profil/<session_id>/submit
    → Gem svar i profil_responses
    → Marker session som complete
    → Redirect til rapport

# Se rapport
GET /profil/<session_id>/report
    → Beregn farvegrid
    → Vis rapport med fortolkning
```

### Admin-routes

```python
# Liste alle profiler (filtreret på customer)
GET /admin/profiler
    → Oversigt med søgning/filtrering

# Se enkelt profil
GET /admin/profil/<session_id>
    → Fuld rapport + metadata

# Sammenlign 2 profiler
GET /admin/profil/compare/<session1>/<session2>
    → Side-by-side farvegrid
    → Highlight forskelle
    → Forslag til samtale-punkter

# Opret profil-invitation (send link)
POST /admin/profil/invite
    → Opret session med email
    → Send invitation via Mailjet
```

---

## UI-design

### Farvegrid (rapport)

```
┌─────────────────────────────────────────────────────────┐
│                  DIN FRIKTIONSPROFIL                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│            TRYGHED    MENING     KAN      BESVÆR        │
│                                                          │
│  Kognition   🟩        🟨        🟩        🟨           │
│                                                          │
│  Indre       🟨        🟩        🟨        🟧           │
│                                                          │
│  Emotion     🟧        🟨        🟧        🟨           │
│                                                          │
│  Biologi     🟧        🟩        🟨        🟩           │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  🟩 Robust    🟨 Sensitiv    🟧 Sårbar                  │
└─────────────────────────────────────────────────────────┘
```

### Sammenligning (2 profiler)

```
┌──────────────────────────────────────────────────────────────────┐
│                    PROFIL-SAMMENLIGNING                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  TRYGHED           Person A          Person B         Forskel    │
│  ─────────────────────────────────────────────────────────────   │
│  Kognition            🟩                🟨              ↓         │
│  Indre                🟨                🟧              ↓↓        │
│  Emotion              🟧                🟨              ↑         │
│  Biologi              🟧                🟩              ↑↑        │
│                                                                   │
│  → Person A: Pres sætter sig i kroppen, svært at løfte op        │
│  → Person B: Regulerer bedre biologisk, men indre lag er sårbart │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Implementation - Faser

### Fase 1: Database og grundstruktur
- [ ] Opret `db_profil.py` med tabeller og CRUD-funktioner
- [ ] Tilføj de 16 spørgsmål som default data
- [ ] Kør migration på eksisterende database

### Fase 2: Survey-flow
- [ ] Opret `profil/survey.html` template
- [ ] Implementer routes: start, udfyld, submit
- [ ] Test fuld flow fra start til rapport

### Fase 3: Analyse og rapport
- [ ] Implementer `analysis_profil.py` med score/farve-beregning
- [ ] Opret `profil/report.html` med farvegrid
- [ ] Tilføj søjle-fortolkning og båndbredde

### Fase 4: Admin-integration
- [ ] Tilføj "Friktionsprofiler" til admin-menu
- [ ] Liste-view med filtrering
- [ ] Integration med eksisterende bruger/customer-system

### Fase 5: Sammenligning
- [ ] Implementer compare-logik
- [ ] Opret `profil/compare.html` template
- [ ] Tilføj automatiske observations-punkter

### Fase 6: Invitation/distribution
- [ ] Email-invitation via Mailjet
- [ ] Token-baseret adgang (som eksisterende survey)
- [ ] Kobling til MUS/kampagne hvis ønsket

---

## Genbrug fra eksisterende kode

| Komponent | Genbruges fra | Tilpasning |
|-----------|---------------|------------|
| Database context manager | `db_hierarchical.py` | Ingen |
| Token-generering | `db_hierarchical.py` | Ny tabel |
| Email-udsendelse | `mailjet_integration.py` | Ny template |
| Login/auth | `db_multitenant.py` | Ingen |
| Customer-filter | `admin_app.py` | Tilføj til profil-queries |
| Base templates | `templates/admin/layout.html` | Extend |
| Farve-styling | `survey.html` | Tilpas til grid |

---

## Estimat

| Fase | Kompleksitet |
|------|--------------|
| Fase 1: Database | Lav |
| Fase 2: Survey-flow | Medium |
| Fase 3: Analyse/rapport | Medium |
| Fase 4: Admin | Lav |
| Fase 5: Sammenligning | Medium |
| Fase 6: Distribution | Lav |

---

## Beslutningspunkter

Før implementation, afklar:

1. **Standalone vs integreret survey-app?**
   - Anbefaling: Tilføj routes til eksisterende `survey_app.py` med `/profil/` prefix

2. **Kobling til organisationsstruktur?**
   - Anbefaling: Valgfri - profiler kan stå alene eller kobles til unit

3. **Anonym vs identificeret?**
   - Anbefaling: Altid identificeret (navnet er centralt for MUS/konflikt)

4. **Udvidet spørgsmålssæt (båndbredde-spørgsmål)?**
   - Anbefaling: Start med de 16 basis, tilføj senere

5. **AI-genereret fortolkning?**
   - Anbefaling: Start med regelbaseret, overvej AI senere
