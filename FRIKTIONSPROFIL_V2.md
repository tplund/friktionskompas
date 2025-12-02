# Friktionsprofil V2 - Udvidet med Kapacitet og Båndbredde

## Overblik

Friktionsprofilen måler individuel reguleringsarkitektur på to dimensioner:

1. **Sensitivitet** (de oprindelige 16 spørgsmål): "Hvor meget friktion oplever du?"
2. **Kapacitet** (8 nye spørgsmål): "Hvor meget kan du bære/gøre trods friktion?"

### To typer målinger

| Type | Instruktion | Tidsramme | Use case |
|------|-------------|-----------|----------|
| **Profil-version** | "Sådan er jeg typisk" | Sidste 6 måneder | Baseline, MUS, onboarding |
| **Situations-version** | "Lige nu, i denne situation" | Aktuelt | Konflikt, pres, projektvurdering |

---

## Spørgsmålsstruktur

### Basis: 16 Sensitivitets-spørgsmål (eksisterende)

Måler homeostatisk pres og følsomhed i 4 felter × 4 lag.

| Felt | Biologi | Emotion | Indre | Kognition |
|------|---------|---------|-------|-----------|
| TRYGHED | Reagerer fysisk på uforudsigelighed | Opfanger signaler tydeligt | Urolig hvis virkelighed udfordres | Falder til ro via forståelse* |
| MENING | Føles fysisk forkert uden mening | Mærker stærkt hvad der er vigtigt | Får hurtigt retning* | Kan holde pres ud med mening* |
| KAN | Mærker energifald hurtigt | Let overvældet | Regulerer via forståelse* | Kan tænke klart under pres* |
| BESVÆR | Små ting føles tunge | Undgår bøvl/kompleksitet | Gør ting lettere via proces* | Mister overblik |

*Omvendt scoret

---

### Udvidelse: 8 Kapacitets-spørgsmål (NYE)

Måler "tage sig sammen"-mekanikken og båndbredde.

#### KAN - Kapacitet

| Lag | Spørgsmål | State-version |
|-----|-----------|---------------|
| INDRE | Jeg kan godt gennemføre noget, selvom jeg ikke har lyst | I denne situation kan jeg godt gøre det her, selvom jeg egentlig ikke har lyst |
| KOGNITION | Når jeg har besluttet mig for noget, får jeg det normalt gjort – også selvom det er kedeligt | Når jeg har besluttet mig for det her, kan jeg godt holde fast, også selvom det er kedeligt |

#### BESVÆR - Kapacitet

| Lag | Spørgsmål | State-version |
|-----|-----------|---------------|
| KOGNITION | Jeg laver ofte ting færdige, selvom de føles besværlige eller meningsløse | Jeg kan godt færdiggøre det her, selvom det føles bøvlet |
| INDRE | Jeg kan bære meget bøvl, hvis det er det, der skal til, for at tingene fungerer | Jeg kan godt bære det besvær, der følger med den her situation |

#### TRYGHED - Kapacitet (sårbarhed for udfordring)

| Lag | Spørgsmål | State-version |
|-----|-----------|---------------|
| INDRE | Jeg bliver meget ramt, hvis nogen stiller spørgsmålstegn ved mine intentioner | I denne situation bliver jeg ramt, hvis nogen udfordrer mine intentioner |

#### MENING - Kapacitet (sårbarhed for meningsudfordring)

| Lag | Spørgsmål | State-version |
|-----|-----------|---------------|
| INDRE | Jeg bliver stærkt påvirket, når nogen udfordrer min forståelse af, hvad der er rigtigt/vigtigt | I denne situation bliver jeg påvirket, hvis min forståelse af hvad der er rigtigt udfordres |

#### Båndbredde-spørgsmål

| Lag | Spørgsmål | Hvad måles |
|-----|-----------|------------|
| EMOTION→INDRE | Når jeg bliver følelsesmæssigt presset, kan jeg normalt godt holde ud, indtil jeg har talt med nogen eller tænkt det igennem | Emotionel udholdenhed |
| INDRE→KOGNITION | Når noget rammer mig hårdt, kan jeg efter noget tid tænke klart over det | Kapacitet til at løfte pres opad |

---

## Kort Screening (5-6 spørgsmål)

Til hurtig vurdering (intro, kursus, første samtale):

| Nr | Felt | Spørgsmål | Hvad måles |
|----|------|-----------|------------|
| 1 | TRYGHED | Jeg føler mig ofte urolig eller på vagt i hverdagen | Baseline tryghed |
| 2 | MENING | Det er tydeligt for mig, hvad der er vigtigt i mit liv* | Meningsklarhed |
| 3 | KAN | Jeg har generelt nemt ved at få gjort det, jeg skal* | Handlekapacitet |
| 4 | BESVÆR | Hverdagen føles ofte bøvlet og tung | Oplevet besvær |
| 5 | LAG | Når jeg bliver presset, mærker jeg det mest i kroppen | Manifestation: biologi |
| 6 | LAG | Når jeg bliver presset, føler jeg mest, at jeg er forkert | Manifestation: indre |

*Omvendt scoret

### Screening-resultat

Giver:
- Felt med højest friktion (TRYGHED/MENING/KAN/BESVÆR)
- Primært manifestationslag (Biologi vs Indre)
- Anbefaling om fuld profil hvis >2 høje scores

---

## Analyse-udvidelse

### Dobbelt farvekodning

| Dimension | Score 1.0-2.2 | Score 2.3-3.7 | Score 3.8-5.0 |
|-----------|---------------|---------------|---------------|
| Sensitivitet | 🟢 Robust | 🟡 Sensitiv | 🟠 Sårbar |
| Kapacitet | 🟢 Høj kapacitet | 🟡 Moderat | 🟠 Lav kapacitet |

### Profil-typer (eksempler)

| Type | Sensitivitet | Kapacitet | Beskrivelse |
|------|--------------|-----------|-------------|
| "Robust performer" | Lav | Høj | Tåler meget, handler uanset |
| "Sensitiv performer" | Høj | Høj | Mærker meget, men kan handle |
| "Meningsstyret" | Høj | Lav i KAN/BESVÆR uden mening | Kan kun handle når det giver mening |
| "Pligtopfylder" | Lav | Høj | Gør ting uanset lyst/mening |
| "Presset" | Høj | Lav | Mærker meget, kan ikke handle |

---

## Database-udvidelse

### Ny tabel: profil_question_versions

```sql
CREATE TABLE profil_question_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_name TEXT NOT NULL,         -- 'v1', 'v2', 'screening'
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Udvidelse af profil_questions

```sql
ALTER TABLE profil_questions ADD COLUMN version_id INTEGER REFERENCES profil_question_versions(id);
ALTER TABLE profil_questions ADD COLUMN question_type TEXT DEFAULT 'sensitivity'; -- 'sensitivity', 'capacity', 'bandwidth', 'screening'
ALTER TABLE profil_questions ADD COLUMN state_text_da TEXT; -- Situations-version af spørgsmålet
```

### Udvidelse af profil_sessions

```sql
ALTER TABLE profil_sessions ADD COLUMN measurement_type TEXT DEFAULT 'profile'; -- 'profile', 'situation', 'screening'
ALTER TABLE profil_sessions ADD COLUMN situation_context TEXT; -- Hvis situation: hvad handler det om
```

---

## Instruktions-tekster

### Profil-version (default)
> Svar på spørgsmålene ud fra, hvordan det **typisk** er for dig i hverdagen.
> Tænk på det sidste halve år som helhed – ikke kun i dag eller denne uge.

### Situations-version
> Svar på spørgsmålene ud fra, hvordan du oplever det **lige nu** i forhold til [kontekst].
> Tænk på den konkrete situation eller opgave, du har i tankerne.

### Screening
> Svar hurtigt og intuitivt – der er ingen rigtige eller forkerte svar.
> Dette er en kort screening for at finde ud af, om en fuld friktionsprofil vil være nyttig.

---

## Roadmap

### Fase 1: Dokumentation (nu)
- [x] Opdateret FRIKTIONSPROFIL_V2.md

### Fase 2: Database-udvidelse
- [ ] Tilføj nye kolonner til profil_questions
- [ ] Tilføj nye kolonner til profil_sessions
- [ ] Indsæt de 8 nye kapacitets-spørgsmål
- [ ] Indsæt de 6 screening-spørgsmål

### Fase 3: Survey-flow
- [ ] Vælg målingstype ved start (profil/situation/screening)
- [ ] Vis relevante spørgsmål baseret på type
- [ ] Situations-kontekst felt

### Fase 4: Analyse-udvidelse
- [ ] Beregn både sensitivitet og kapacitet
- [ ] Dobbelt farvekodning i rapport
- [ ] Profil-type identifikation

### Fase 5: Admin-interface
- [ ] Spørgsmålseditor (tekst, felt, lag, scoring)
- [ ] Versionering af spørgsmålssæt
- [ ] Introduktions- og afslutningstekster per version

---

## TODO: Admin Spørgsmålseditor

Nyt menupunkt under Indstillinger:

### Funktioner
1. **Liste alle spørgsmål** - med felt, lag, type, version
2. **Rediger spørgsmål** - tekst (profil + situation), scoring, sequence
3. **Tilføj/fjern spørgsmål** - med validering af felt/lag kombination
4. **Versionering** - opret ny version, kopier eksisterende, aktiver/deaktiver
5. **Intro/outro tekster** - per version og målingstype

### UI-skitse

```
┌─────────────────────────────────────────────────────────────────┐
│ Friktionsprofil Spørgsmål                                       │
├─────────────────────────────────────────────────────────────────┤
│ Version: [v2 - Med kapacitet ▼]  Type: [Alle ▼]                │
├─────────────────────────────────────────────────────────────────┤
│ # │ Felt    │ Lag      │ Type       │ Tekst (profil)           │
│───┼─────────┼──────────┼────────────┼──────────────────────────│
│ 1 │ TRYGHED │ BIOLOGI  │ Sensitivit │ Jeg reagerer hurtigt...  │
│ 2 │ TRYGHED │ EMOTION  │ Sensitivit │ Jeg opfanger små...      │
│ 3 │ TRYGHED │ INDRE    │ Sensitivit │ Jeg bliver urolig...     │
│...│         │          │            │                          │
│17 │ KAN     │ INDRE    │ Kapacitet  │ Jeg kan godt gennemf...  │
│18 │ KAN     │ KOGNITION│ Kapacitet  │ Når jeg har besluttet... │
└─────────────────────────────────────────────────────────────────┘
│ [+ Tilføj spørgsmål]  [Eksporter]  [Ny version]                │
└─────────────────────────────────────────────────────────────────┘
```
