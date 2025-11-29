# Friktionskompasset - Implementeringsplan for nye funktioner

## Dato: 2025-11-14

---

## 1. OVERSIGT OVER NYE FUNKTIONER

### 1.1 Leder-perspektiv: Måling af misalignment
**Formål:** Måle både medarbejdernes oplevede friktioner OG lederens vurdering af teamets friktioner PLUS lederens egne friktioner.

**Værdi:**
- Afsløre misalignment mellem lederens mentale model og teamets virkelighed
- Identificere om lederen selv er bremset af systemet (mangler handlerum)
- Vise præcist hvor kommunikationen knækker

**Tre datalag:**
1. Medarbejdernes oplevede friktioner (som nu)
2. Lederens vurdering: "Hvad tror du medarbejderne oplever?"
3. Lederens egne friktioner

### 1.2 KKC-integration: Kobling til Direction-Alignment-Commitment
**Formål:** Mappe friktioner til Anders Trillingsgaards KKC-model som kommunerne allerede bruger.

**Mapping:**
- **Kurs (Direction)** ↔ Meningsfriktion
- **Koordinering (Alignment)** ↔ Tryghed + Kan-friktion
- **Commitment** ↔ Besværsfriktion

**Værdi:**
- Viser HVORFOR de har D-A-C problemer, ikke bare AT de har dem
- Troværdighed gennem integration med eksisterende værktøjer
- Afsløre substitutioner (folk rapporterer forkert friktion)

### 1.3 To produkter: Anonym vs. Ikke-anonym måling
**Formål:** Tilbyde både systemindsigt (anonym) og individuel udvikling (åben).

**Produkt A: Team-måling (anonym)**
- Systemindsigt og strukturelle problemer
- Misalignment mellem leder og team
- Benchmark på tværs af afdelinger
- Minimum 5 svar for at vise resultater

**Produkt B: Individuel måling (åben/valgfri)**
- MUS (medarbejderudviklingssamtaler)
- 1:1 mellem leder og medarbejder
- Onboarding af nye medarbejdere
- Hver person får eget "friktionskort"

**Sikkerhed i ikke-anonym version:**
- Må KUN bruges til udvikling, aldrig vurdering
- Hver person ejer sin egen data
- Kan trækkes tilbage når som helst
- Kræver træning af lederen

---

## 2. NUVÆRENDE ARKITEKTUR

### 2.1 Database struktur
**Tabeller:**
- `organizational_units` - Hierarkisk træstruktur
- `campaigns` - Kampagner rettet mod units
- `tokens` - Tokens per leaf unit
- `questions` - Spørgsmål (4 felter: MENING, TRYGHED, MULIGHED, BESVÆR)
- `responses` - Svar (campaign_id, unit_id, question_id, score 1-5)
- `contacts` - Email/telefon kontakter
- `customers` - Multi-tenant kunder
- `users` - Brugere (admin/manager)

### 2.2 Nuværende friktions-felter
1. **MENING** - Er arbejdet meningsfuldt?
2. **TRYGHED** - Tør folk sige fra?
3. **MULIGHED** (KAN) - Har folk værktøjer og viden?
4. **BESVÆR** - Er systemerne besværlige?

### 2.3 Respondent-flow
1. Medarbejder får token via email/SMS
2. Udfylder spørgeskema anonymt
3. Svar gemmes med (campaign_id, unit_id, question_id, score)
4. Aggregering på unit-niveau (gennemsnit per felt)

---

## 3. TEKNISK IMPLEMENTERING

## 3.1 DATABASE ÆNDRINGER

### 3.1.1 Ny tabel: `respondent_types`
```sql
CREATE TABLE respondent_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,  -- 'employee', 'leader_assess', 'leader_self'
    name_da TEXT NOT NULL,
    description_da TEXT
);

-- Default data
INSERT INTO respondent_types (code, name_da, description_da) VALUES
('employee', 'Medarbejder', 'Medarbejdersvar om egne friktioner'),
('leader_assess', 'Leder (teamvurdering)', 'Lederens vurdering af hvad teamet oplever'),
('leader_self', 'Leder (egne friktioner)', 'Lederens egne friktioner');
```

### 3.1.2 Ny tabel: `campaign_modes`
```sql
CREATE TABLE campaign_modes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,  -- 'anonymous', 'identified'
    name_da TEXT NOT NULL,
    description_da TEXT
);

INSERT INTO campaign_modes (code, name_da, description_da) VALUES
('anonymous', 'Anonym', 'Team-måling med minimum 5 svar'),
('identified', 'Identificeret', 'Individuel måling til udvikling');
```

### 3.1.3 Udvid `campaigns` tabel
```sql
ALTER TABLE campaigns ADD COLUMN mode TEXT DEFAULT 'anonymous'
    CHECK(mode IN ('anonymous', 'identified'));
ALTER TABLE campaigns ADD COLUMN include_leader_assessment INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN include_leader_self INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN min_responses INTEGER DEFAULT 5;
```

### 3.1.4 Udvid `tokens` tabel
```sql
ALTER TABLE tokens ADD COLUMN respondent_type TEXT DEFAULT 'employee'
    CHECK(respondent_type IN ('employee', 'leader_assess', 'leader_self'));
ALTER TABLE tokens ADD COLUMN respondent_name TEXT;  -- Kun for identified mode
```

### 3.1.5 Udvid `responses` tabel
```sql
ALTER TABLE responses ADD COLUMN respondent_type TEXT DEFAULT 'employee'
    CHECK(respondent_type IN ('employee', 'leader_assess', 'leader_self'));
ALTER TABLE responses ADD COLUMN respondent_name TEXT;  -- Kun for identified mode
```

### 3.1.6 Ny tabel: `kcc_mapping` (KKC-integration)
```sql
CREATE TABLE kcc_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kcc_dimension TEXT NOT NULL,  -- 'Direction', 'Alignment', 'Commitment'
    friction_field TEXT NOT NULL,  -- 'MENING', 'TRYGHED', 'MULIGHED', 'BESVÆR'
    weight REAL DEFAULT 1.0,
    description_da TEXT
);

-- Default mappings
INSERT INTO kcc_mapping (kcc_dimension, friction_field, weight, description_da) VALUES
('Direction', 'MENING', 1.0, 'Kurs måles primært gennem meningsfriktion'),
('Alignment', 'TRYGHED', 0.6, 'Koordinering kræver tryghed'),
('Alignment', 'MULIGHED', 0.4, 'Koordinering kræver klarhed om hvem der kan hvad'),
('Commitment', 'BESVÆR', 1.0, 'Engagement bremses af besværsfriktioner');
```

### 3.1.7 Ny tabel: `substitution_patterns` (til detektering af substitutioner)
```sql
CREATE TABLE substitution_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    respondent_type TEXT NOT NULL,
    reported_field TEXT NOT NULL,  -- Hvad de siger problemet er
    likely_actual_field TEXT NOT NULL,  -- Hvad det sandsynligvis er
    confidence REAL,  -- 0-1
    reasoning TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
);
```

---

## 3.2 BACKEND FUNKTIONER

### 3.2.1 Nye funktioner i `db_hierarchical.py`

```python
def create_campaign_with_modes(
    target_unit_id: str,
    name: str,
    period: str,
    mode: str = 'anonymous',  # 'anonymous' eller 'identified'
    include_leader_assessment: bool = False,
    include_leader_self: bool = False,
    min_responses: int = 5,
    sent_from: str = 'admin'
) -> str:
    """
    Opret kampagne med valgfri mode og leder-perspektiver
    """
    # Implementation...

def generate_tokens_with_respondent_types(
    campaign_id: str,
    respondent_names: Dict[str, List[str]] = None  # {unit_id: [navne]} for identified mode
) -> Dict[str, Dict[str, List[str]]]:
    """
    Generer tokens med respondent_type

    Returns:
        {
            unit_id: {
                'employee': [tokens],
                'leader_assess': [tokens],  # hvis enabled
                'leader_self': [tokens]     # hvis enabled
            }
        }
    """
    # Implementation...

def get_misalignment_analysis(
    campaign_id: str,
    unit_id: str,
    field: str = None  # Specifik felt eller None for alle
) -> Dict:
    """
    Analysér misalignment mellem medarbejdere og leders vurdering

    Returns:
        {
            'MENING': {
                'employee_avg': 2.3,
                'leader_assess_avg': 3.8,
                'gap': 1.5,
                'interpretation': 'Lederen overvurderer teamets oplevelse af mening'
            },
            ...
        }
    """
    # Implementation...

def get_leader_friction_blockers(campaign_id: str, unit_id: str) -> Dict:
    """
    Analysér lederens egne friktioner der begrænser handlerum

    Returns:
        {
            'has_blockers': True,
            'blocked_fields': ['MENING', 'TRYGHED'],
            'leader_frictions': {
                'MENING': 2.1,
                'TRYGHED': 1.9,
                ...
            },
            'recommendations': [...]
        }
    """
    # Implementation...

def calculate_kcc_scores(campaign_id: str, unit_id: str,
                        respondent_type: str = 'employee') -> Dict:
    """
    Beregn KKC-scores baseret på friktioner

    Returns:
        {
            'Direction': 3.2,  # Fra MENING
            'Alignment': 2.8,  # Fra TRYGHED (60%) + MULIGHED (40%)
            'Commitment': 2.5  # Fra BESVÆR
        }
    """
    # Implementation...

def detect_substitution_patterns(campaign_id: str, unit_id: str) -> List[Dict]:
    """
    Detektér mulige substitutions-mønstre

    Eksempel:
    - Høj BESVÆR + lav TRYGHED → Siger "systemet er besværligt" men mener "jeg tør ikke"
    - Høj KAN-friktion + leder vurderer KAN højt → Misalignment om kompetencer

    Returns:
        [
            {
                'reported_field': 'BESVÆR',
                'likely_actual_field': 'TRYGHED',
                'confidence': 0.7,
                'reasoning': 'Høj besværsfriktion (4.2) med lav trygheds-score (1.8) ...'
            }
        ]
    """
    # Implementation...

def get_individual_friction_card(
    campaign_id: str,
    unit_id: str,
    respondent_name: str
) -> Dict:
    """
    Hent individuel friktionskort (kun for identified campaigns)

    Returns:
        {
            'name': 'Mette Hansen',
            'unit': 'Hjemmeplejen Nord',
            'frictions': {
                'MENING': 4.3,
                'TRYGHED': 4.1,
                'MULIGHED': 3.8,
                'BESVÆR': 1.5  # Ekstrem besværsfriktion!
            },
            'primary_blocker': 'BESVÆR',
            'recommendations': [
                'Fjern systembesvær specifikt for denne medarbejder',
                'Undersøg hvilke procedurer der bremser'
            ]
        }
    """
    # Implementation...

def check_anonymity_threshold(campaign_id: str, unit_id: str) -> Dict:
    """
    Check om anonymitetstærskel er nået

    Returns:
        {
            'can_show_results': True/False,
            'response_count': 7,
            'min_required': 5,
            'missing': 0
        }
    """
    # Implementation...
```

### 3.2.2 Nye funktioner i `analysis.py` (ny fil)

```python
def generate_comparison_report(
    campaign_id: str,
    unit_id: str
) -> Dict:
    """
    Generer fuld sammenligningsrapport mellem medarbejdere og leder

    Inkluderer:
    - Misalignment analyse
    - Lederens egne blockers
    - KKC-scores for begge perspektiver
    - Substitutions-detektering
    - Handlingsanbefalinger
    """
    # Implementation...

def calculate_action_priorities(
    campaign_id: str,
    unit_id: str
) -> List[Dict]:
    """
    Prioritér handlinger baseret på:
    - Størst friktion
    - Størst misalignment
    - Lederens egne blockers
    - Substitutions-mønstre

    Returns sorted list af handlingspunkter
    """
    # Implementation...
```

---

## 3.3 FRONTEND ÆNDRINGER

### 3.3.1 Ny kampagne-oprettelsesflow

**Template:** `templates/admin/new_campaign.html`

Tilføj valgmuligheder:
```html
<!-- Mode valg -->
<div class="form-group">
    <label>Kampagne type</label>
    <select name="mode">
        <option value="anonymous">Anonym team-måling (minimum 5 svar)</option>
        <option value="identified">Identificeret individuel måling</option>
    </select>
</div>

<!-- Leder-perspektiv -->
<div class="form-group">
    <label>
        <input type="checkbox" name="include_leader_assessment">
        Inkludér lederens vurdering af teamet
    </label>
</div>

<div class="form-group">
    <label>
        <input type="checkbox" name="include_leader_self">
        Inkludér lederens egne friktioner
    </label>
</div>

<!-- Kun for identified mode -->
<div id="identified-options" style="display: none;">
    <div class="form-group">
        <label>Upload CSV med medarbejdernavne</label>
        <input type="file" name="employee_names">
    </div>
</div>
```

### 3.3.2 Nyt dashboard: Misalignment view

**Template:** `templates/admin/misalignment_dashboard.html`

Viser:
- Side-by-side visning af medarbejder vs. leder-vurdering
- Gap-indikatorer (visuelt med farver)
- Lederens egne friktioner
- Anbefalinger

```html
<h2>Misalignment Analyse</h2>

<div class="comparison-grid">
    <!-- For hver friktions-felt -->
    <div class="field-comparison">
        <h3>MENING</h3>

        <div class="scores">
            <div class="employee-score">
                <label>Medarbejdere oplever</label>
                <span class="score">2.3</span>
            </div>

            <div class="gap-indicator {{ 'high' if gap > 1.0 }}">
                <span class="gap-value">▲ 1.5</span>
                <p>Lederen overvurderer teamets oplevelse</p>
            </div>

            <div class="leader-score">
                <label>Leder tror teamet oplever</label>
                <span class="score">3.8</span>
            </div>
        </div>
    </div>
</div>

<div class="leader-blockers">
    <h3>Lederens egne friktioner</h3>
    <!-- Vis hvor lederen selv er bremset -->
</div>
```

### 3.3.3 KKC Integration dashboard

**Template:** `templates/admin/kcc_dashboard.html`

```html
<h2>KKC-analyse (Direction-Alignment-Commitment)</h2>

<div class="kcc-scores">
    <div class="kcc-dimension">
        <h3>Direction (Kurs)</h3>
        <div class="mapping-info">← MENING friktion</div>
        <div class="score-comparison">
            <span>Medarbejdere: 2.3</span>
            <span>Leder tror: 3.8</span>
        </div>
        <p class="interpretation">
            Lav Direction pga. meningsfriktion.
            Lederen undervurderer problemet.
        </p>
    </div>

    <!-- Alignment, Commitment... -->
</div>
```

### 3.3.4 Individuelt friktionskort

**Template:** `templates/admin/individual_friction_card.html`

Kun for identified campaigns:
```html
<h2>Friktionskort: {{ respondent_name }}</h2>

<div class="individual-profile">
    <div class="friction-radar">
        <!-- Radar chart af 4 friktioner -->
    </div>

    <div class="primary-blocker">
        <h3>Primær barriere: BESVÆR</h3>
        <p>Score: 1.5 (meget lav - høj friktion)</p>
    </div>

    <div class="recommendations">
        <h3>Anbefalinger til udvikling</h3>
        <ul>
            <li>Fjern systembesvær specifikt for denne person</li>
            <li>Identificer hvilke procedurer der bremser</li>
        </ul>
    </div>
</div>
```

---

## 3.4 SPØRGESKEMA ÆNDRINGER

### 3.4.1 Tre forskellige instruktioner baseret på respondent_type

**For `employee` (som nu):**
> "Svar ud fra din egen oplevelse af arbejdet"

**For `leader_assess`:**
> "Svar IKKE om dig selv, men om hvad du tror dine medarbejdere oplever.
> Forestil dig gennemsnitsmedarbejderen i dit team.
> Hvad ville de svare på disse spørgsmål?"

**For `leader_self`:**
> "Svar om dine EGNE friktioner som leder.
> Har DU de værktøjer, den tryghed og mening du skal bruge for at lede godt?"

### 3.4.2 Template opdatering

**Template:** `templates/index.html` eller `templates/survey_preview.html`

```python
# I view funktion
respondent_type = token_data.get('respondent_type', 'employee')

instructions = {
    'employee': "Svar ud fra din egen oplevelse af arbejdet",
    'leader_assess': "Svar om hvad du tror dine medarbejdere oplever (IKKE dig selv)",
    'leader_self': "Svar om dine EGNE friktioner som leder"
}

return render_template('survey.html',
    questions=questions,
    instruction=instructions[respondent_type],
    respondent_type=respondent_type
)
```

---

## 4. IMPLEMENTERINGSFASER

### FASE 1: Database og grundlæggende backend (Uge 1-2)
**Opgaver:**
1. ✅ Opret nye tabeller (respondent_types, campaign_modes, kcc_mapping, substitution_patterns)
2. ✅ Udvid eksisterende tabeller (campaigns, tokens, responses)
3. ✅ Skriv migrations-script
4. ✅ Implementer `create_campaign_with_modes()`
5. ✅ Implementer `generate_tokens_with_respondent_types()`
6. ✅ Test token-generering med forskellige modes

**Succeskriterier:**
- Kan oprette campaign med mode='anonymous' eller 'identified'
- Kan generere tokens for employee, leader_assess, leader_self
- Database constraints fungerer korrekt

---

### FASE 2: Leder-perspektiv funktionalitet (Uge 2-3)
**Opgaver:**
1. ✅ Implementer `get_misalignment_analysis()`
2. ✅ Implementer `get_leader_friction_blockers()`
3. ✅ Opdater spørgeskema-view med tre instruktioner
4. ✅ Test full flow: Opret campaign → generer tokens → udfyld som employee OG leader
5. ✅ Verificer at respondent_type gemmes korrekt

**Succeskriterier:**
- Kan se forskel mellem employee og leader_assess svar
- Misalignment gap beregnes korrekt
- Lederens egne friktioner vises separat

---

### FASE 3: KKC-integration (Uge 3-4)
**Opgaver:**
1. ✅ Implementer `calculate_kcc_scores()`
2. ✅ Opret KKC dashboard template
3. ✅ Implementer `detect_substitution_patterns()`
4. ✅ Test mapping mellem friktioner og KKC-dimensioner
5. ✅ Valider at vægtningen giver mening

**Succeskriterier:**
- KKC-scores beregnes korrekt fra friktioner
- Substitutions-detektering finder mønstre
- Dashboard viser KKC i sammenhæng med friktioner

---

### FASE 4: Anonym vs. Identificeret mode (Uge 4-5)
**Opgaver:**
1. ✅ Implementer `check_anonymity_threshold()`
2. ✅ Opdater dashboard til at skjule data hvis < 5 svar (anonymous mode)
3. ✅ Implementer `get_individual_friction_card()`
4. ✅ Opret individual friction card template
5. ✅ Test privacy: Verificer at navne kun vises i identified mode

**Succeskriterier:**
- Anonymous campaigns viser kun data ved ≥5 svar
- Identified campaigns viser individuelle kort
- Privacy constraints overholdes

---

### FASE 5: Rapportering og visualisering (Uge 5-6)
**Opgaver:**
1. ✅ Opret misalignment dashboard template
2. ✅ Implementer `generate_comparison_report()`
3. ✅ Implementer `calculate_action_priorities()`
4. ✅ Tilføj visualiseringer (gap indicators, radar charts)
5. ✅ PDF export af rapporter

**Succeskriterier:**
- Misalignment vises intuitivt visuelt
- Handlingsanbefalinger prioriteres automatisk
- Kan eksportere fuld rapport

---

### FASE 6: Testing og validering (Uge 6-7)
**Opgaver:**
1. ✅ End-to-end test af anonymous campaign
2. ✅ End-to-end test af identified campaign
3. ✅ Test med rigtige data (testorganisation)
4. ✅ Valider at misalignment-beregninger er korrekte
5. ✅ Sikkerhedstest: Verificer at privacy overholdes
6. ✅ Performance test med mange respondenter

**Succeskriterier:**
- Ingen bugs i happy path
- Privacy garanteret
- Performance acceptabel (< 2s response time)

---

### FASE 7: Dokumentation og træning (Uge 7-8)
**Opgaver:**
1. ✅ Skriv brugerdokumentation
2. ✅ Lav vejledning til ledere om brug af identified mode
3. ✅ Etiske retningslinjer for brug af navngivne data
4. ✅ Video tutorials
5. ✅ Træn pilot-kunder

**Succeskriterier:**
- Ledere forstår forskellen mellem anonymous og identified
- Etiske retningslinjer er klare
- Pilot-kunder kan selv oprette campaigns

---

## 5. DATAMODEL EKSEMPLER

### 5.1 Anonymous campaign med leder-perspektiv

**Kampagne:**
```python
{
    'id': 'camp-xyz',
    'name': 'Odder Kommune Q1 2025',
    'mode': 'anonymous',
    'include_leader_assessment': True,
    'include_leader_self': True,
    'min_responses': 5
}
```

**Tokens genereret:**
```python
{
    'unit-abc': {
        'employee': ['token1', 'token2', 'token3', ...],  # 10 tokens
        'leader_assess': ['token-L1'],  # 1 token til leder
        'leader_self': ['token-L2']     # 1 token til leder (egne friktioner)
    }
}
```

**Responses:**
```python
# Medarbejder 1
{'campaign_id': 'camp-xyz', 'unit_id': 'unit-abc', 'question_id': 1,
 'score': 2, 'respondent_type': 'employee', 'respondent_name': None}

# Leder vurderer teamet
{'campaign_id': 'camp-xyz', 'unit_id': 'unit-abc', 'question_id': 1,
 'score': 4, 'respondent_type': 'leader_assess', 'respondent_name': None}

# Leder om sig selv
{'campaign_id': 'camp-xyz', 'unit_id': 'unit-abc', 'question_id': 1,
 'score': 3, 'respondent_type': 'leader_self', 'respondent_name': None}
```

**Aggregering:**
```python
# MENING felt
{
    'employee_avg': 2.3,      # Gennemsnit af employee responses
    'leader_assess_avg': 3.8, # Lederens vurdering
    'leader_self_avg': 3.0,   # Lederens egen friktion
    'gap': 1.5,               # Misalignment!
    'interpretation': 'Lederen overvurderer teamets oplevelse af mening'
}
```

---

### 5.2 Identified campaign (individuel udvikling)

**Kampagne:**
```python
{
    'id': 'camp-abc',
    'name': 'Team Nord - Personlig udvikling',
    'mode': 'identified',
    'include_leader_assessment': False,
    'include_leader_self': False,
    'min_responses': 1  # Ikke relevant for identified
}
```

**Tokens:**
```python
{
    'unit-abc': {
        'employee': [
            {'token': 'token1', 'name': 'Mette Hansen'},
            {'token': 'token2', 'name': 'Jens Nielsen'},
            {'token': 'token3', 'name': 'Anne Larsen'}
        ]
    }
}
```

**Responses:**
```python
{'campaign_id': 'camp-abc', 'unit_id': 'unit-abc', 'question_id': 1,
 'score': 4, 'respondent_type': 'employee', 'respondent_name': 'Mette Hansen'}
```

**Individuel friktionskort:**
```python
{
    'name': 'Mette Hansen',
    'frictions': {
        'MENING': 4.3,   # Høj - godt!
        'TRYGHED': 4.1,  # Høj - godt!
        'MULIGHED': 3.8, # Middel
        'BESVÆR': 1.5    # Lav - PROBLEM!
    },
    'primary_blocker': 'BESVÆR',
    'recommendations': [
        'Fjern systembesvær',
        'Identificér unødige procedurer'
    ]
}
```

---

## 6. SIKKERHED OG ETIK

### 6.1 Privacy regler for identified mode

**MUST:**
1. Kun til udvikling, ALDRIG vurdering/performance review
2. Medarbejder skal give eksplicit samtykke
3. Data kan trækkes tilbage når som helst
4. Kun medarbejder og deres leder kan se individuelle data
5. Ingen eksport til tredjeparter uden samtykke

**Implementation:**
```python
def get_individual_friction_card(campaign_id, unit_id, respondent_name,
                                requesting_user):
    # Check access rights
    if requesting_user['role'] != 'admin':
        # Verificer at user er leder for denne unit
        # ELLER at user er medarbejderen selv
        if not (is_leader_of_unit(requesting_user, unit_id) or
                requesting_user['name'] == respondent_name):
            raise PermissionError("Ingen adgang til individuelle data")

    # Check consent
    consent = get_consent_record(campaign_id, respondent_name)
    if not consent or consent['withdrawn']:
        raise PermissionError("Samtykke trukket tilbage")

    # Return data...
```

### 6.2 Anonymitetstærskel enforcement

```python
def get_unit_stats(unit_id, campaign_id, include_children=True):
    # Check campaign mode
    campaign = get_campaign(campaign_id)

    if campaign['mode'] == 'anonymous':
        # Count responses
        response_count = count_responses(campaign_id, unit_id, include_children)

        if response_count < campaign['min_responses']:
            return {
                'can_show': False,
                'message': f'Minimum {campaign["min_responses"]} svar krævet. '
                          f'Kun {response_count} modtaget.',
                'response_count': response_count
            }

    # Vis data...
```

---

## 7. TESTSCENARIER

### 7.1 Scenario 1: Misalignment detektering

**Setup:**
- Organisation: Odder Kommune // Ældrepleje // Hjemmeplejen Nord
- 8 medarbejdere + 1 leder
- Anonymous campaign med leder-perspektiv

**Test:**
1. Generer tokens (8 employee + 1 leader_assess + 1 leader_self)
2. Medarbejdere svarer:
   - MENING: [2, 2, 3, 2, 1, 2, 3, 2] → avg 2.1
   - TRYGHED: [2, 1, 2, 1, 2, 2, 1, 2] → avg 1.6
3. Leder vurderer teamet (leader_assess):
   - MENING: 4 (tror det går fint)
   - TRYGHED: 3 (tror folk tør sige fra)
4. Leder om sig selv (leader_self):
   - MENING: 2 (forstår ikke selv hvorfor opgaven betyder noget)
   - TRYGHED: 2 (tør ikke selv udfordre opad)

**Forventet output:**
```python
{
    'misalignment': {
        'MENING': {
            'gap': 1.9,  # Stor!
            'interpretation': 'Kritisk misalignment - lederen er ude af sync'
        },
        'TRYGHED': {
            'gap': 1.4,
            'interpretation': 'Lederen undervurderer trygheds-problemet'
        }
    },
    'leader_blockers': {
        'has_blockers': True,
        'blocked_fields': ['MENING', 'TRYGHED'],
        'interpretation': 'Lederen er selv bremset - mangler mening og tryghed'
    },
    'root_cause': 'Lederen kan ikke skabe det de selv mangler',
    'recommendations': [
        '1. Start med lederens EGNE friktioner (de er selv bremset)',
        '2. Lederen skal have klarhed om mening før de kan formidle det',
        '3. Byg trygheds-kultur oppefra (lederen tør ikke selv, så teamet tør heller ikke)'
    ]
}
```

---

### 7.2 Scenario 2: Substitution detektering

**Setup:**
- Team rapporterer høj BESVÆR (4.2)
- Men samtidig lav TRYGHED (1.8)
- Leder vurderer BESVÆR lavt (2.0) og TRYGHED middel (3.0)

**Test:**
Run `detect_substitution_patterns(campaign_id, unit_id)`

**Forventet output:**
```python
[{
    'reported_field': 'BESVÆR',
    'likely_actual_field': 'TRYGHED',
    'confidence': 0.72,
    'reasoning': 'Teamet siger "systemet er besværligt" (4.2) men har samtidig '
                 'meget lav tryghed (1.8). Misalignment med leder (som tror BESVÆR er 2.0) '
                 'indikerer at folk bruger system-klager som proxy for at undgå at sige '
                 '"jeg tør ikke rejse kritik".',
    'recommended_action': 'Start med at bygge psykologisk tryghed, ikke med at '
                         'optimere systemer. Det reelle problem er social risiko.'
}]
```

---

### 7.3 Scenario 3: KKC mapping

**Setup:**
- Friktioner: MENING=2.1, TRYGHED=1.9, MULIGHED=3.2, BESVÆR=4.1

**Test:**
Run `calculate_kcc_scores(campaign_id, unit_id, 'employee')`

**Forventet output:**
```python
{
    'Direction': 2.1,  # = MENING (1:1 mapping)
    'Alignment': 2.4,  # = TRYGHED*0.6 + MULIGHED*0.4 = 1.9*0.6 + 3.2*0.4
    'Commitment': 4.1, # = BESVÆR (1:1 mapping)

    'interpretation': {
        'Direction': 'Lav - folk forstår ikke hvorfor arbejdet betyder noget',
        'Alignment': 'Lav - primært pga. tryghed (folk tør ikke koordinere)',
        'Commitment': 'Kritisk lav - ekstreme system-besværligheder bremser handling'
    },

    'comparison_to_kcc_survey': {
        'Direction': {
            'kcc_reported': 3.5,  # Hvis de har lavet D-A-C måling
            'friction_calculated': 2.1,
            'discrepancy': 1.4,
            'note': 'Folk over-rapporterer Direction i surveys (socialt ønskeligt), '
                   'men friktionsmåling afslører lavere faktisk oplevelse'
        }
    }
}
```

---

## 8. MIGRATIONSSCRIPT

### 8.1 SQL migration fil: `migrations/001_add_respondent_modes.sql`

```sql
-- ================================
-- MIGRATION: Tilføj respondent modes og KKC
-- Dato: 2025-11-14
-- ================================

BEGIN TRANSACTION;

-- 1. Respondent types
CREATE TABLE respondent_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name_da TEXT NOT NULL,
    description_da TEXT
);

INSERT INTO respondent_types (code, name_da, description_da) VALUES
('employee', 'Medarbejder', 'Medarbejdersvar om egne friktioner'),
('leader_assess', 'Leder (teamvurdering)', 'Lederens vurdering af hvad teamet oplever'),
('leader_self', 'Leder (egne friktioner)', 'Lederens egne friktioner');

-- 2. Campaign modes
CREATE TABLE campaign_modes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name_da TEXT NOT NULL,
    description_da TEXT
);

INSERT INTO campaign_modes (code, name_da, description_da) VALUES
('anonymous', 'Anonym', 'Team-måling med minimum 5 svar'),
('identified', 'Identificeret', 'Individuel måling til udvikling');

-- 3. Extend campaigns
ALTER TABLE campaigns ADD COLUMN mode TEXT DEFAULT 'anonymous'
    CHECK(mode IN ('anonymous', 'identified'));
ALTER TABLE campaigns ADD COLUMN include_leader_assessment INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN include_leader_self INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN min_responses INTEGER DEFAULT 5;

-- 4. Extend tokens
ALTER TABLE tokens ADD COLUMN respondent_type TEXT DEFAULT 'employee'
    CHECK(respondent_type IN ('employee', 'leader_assess', 'leader_self'));
ALTER TABLE tokens ADD COLUMN respondent_name TEXT;

-- 5. Extend responses
ALTER TABLE responses ADD COLUMN respondent_type TEXT DEFAULT 'employee'
    CHECK(respondent_type IN ('employee', 'leader_assess', 'leader_self'));
ALTER TABLE responses ADD COLUMN respondent_name TEXT;

-- 6. KKC mapping
CREATE TABLE kcc_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kcc_dimension TEXT NOT NULL,
    friction_field TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    description_da TEXT
);

INSERT INTO kcc_mapping (kcc_dimension, friction_field, weight, description_da) VALUES
('Direction', 'MENING', 1.0, 'Kurs måles primært gennem meningsfriktion'),
('Alignment', 'TRYGHED', 0.6, 'Koordinering kræver tryghed'),
('Alignment', 'MULIGHED', 0.4, 'Koordinering kræver klarhed om hvem der kan hvad'),
('Commitment', 'BESVÆR', 1.0, 'Engagement bremses af besværsfriktioner');

-- 7. Substitution patterns
CREATE TABLE substitution_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    respondent_type TEXT NOT NULL,
    reported_field TEXT NOT NULL,
    likely_actual_field TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
);

CREATE INDEX idx_substitution_patterns_campaign
    ON substitution_patterns(campaign_id, unit_id);

-- 8. Consent tracking (for identified campaigns)
CREATE TABLE data_consent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    respondent_name TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    consent_given INTEGER DEFAULT 1,
    consent_given_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    withdrawn INTEGER DEFAULT 0,
    withdrawn_at TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
    UNIQUE(campaign_id, respondent_name)
);

COMMIT;
```

---

## 9. API ENDPOINTS (nye eller ændrede)

### 9.1 Campaign creation

**Endpoint:** `POST /admin/campaign/new`

**Request:**
```json
{
    "target_unit_id": "unit-abc",
    "name": "Q1 2025 Måling",
    "period": "2025 Q1",
    "mode": "anonymous",
    "include_leader_assessment": true,
    "include_leader_self": true,
    "min_responses": 5
}
```

**Response:**
```json
{
    "campaign_id": "camp-xyz",
    "tokens_generated": {
        "unit-abc": {
            "employee": 10,
            "leader_assess": 1,
            "leader_self": 1
        }
    },
    "total_tokens": 12
}
```

---

### 9.2 Misalignment analysis

**Endpoint:** `GET /admin/campaign/{campaign_id}/unit/{unit_id}/misalignment`

**Response:**
```json
{
    "unit": {
        "id": "unit-abc",
        "name": "Hjemmeplejen Nord",
        "full_path": "Odder Kommune//Ældrepleje//Hjemmeplejen Nord"
    },
    "response_counts": {
        "employee": 8,
        "leader_assess": 1,
        "leader_self": 1
    },
    "misalignment": {
        "MENING": {
            "employee_avg": 2.1,
            "leader_assess_avg": 4.0,
            "gap": 1.9,
            "severity": "critical",
            "interpretation": "Lederen er kritisk ude af sync med teamets virkelighed"
        },
        "TRYGHED": {...},
        "MULIGHED": {...},
        "BESVÆR": {...}
    },
    "leader_self_frictions": {
        "MENING": 2.0,
        "TRYGHED": 2.2,
        "MULIGHED": 3.1,
        "BESVÆR": 2.8
    },
    "blockers": {
        "has_blockers": true,
        "blocked_fields": ["MENING", "TRYGHED"],
        "impact": "Lederen kan ikke give det de selv mangler"
    },
    "recommendations": [
        "Start med lederens egne friktioner",
        "Byg trygheds-kultur oppefra",
        ...
    ]
}
```

---

### 9.3 KKC scores

**Endpoint:** `GET /admin/campaign/{campaign_id}/unit/{unit_id}/kcc`

**Response:**
```json
{
    "employee_perspective": {
        "Direction": 2.1,
        "Alignment": 2.4,
        "Commitment": 4.1
    },
    "leader_assessment": {
        "Direction": 4.0,
        "Alignment": 3.2,
        "Commitment": 3.5
    },
    "mapping_details": {
        "Direction": {
            "sources": [{"field": "MENING", "weight": 1.0, "score": 2.1}],
            "calculation": "MENING * 1.0 = 2.1"
        },
        "Alignment": {
            "sources": [
                {"field": "TRYGHED", "weight": 0.6, "score": 1.9},
                {"field": "MULIGHED", "weight": 0.4, "score": 3.2}
            ],
            "calculation": "TRYGHED*0.6 + MULIGHED*0.4 = 2.4"
        },
        "Commitment": {
            "sources": [{"field": "BESVÆR", "weight": 1.0, "score": 4.1}],
            "calculation": "BESVÆR * 1.0 = 4.1"
        }
    }
}
```

---

### 9.4 Individual friction card

**Endpoint:** `GET /admin/campaign/{campaign_id}/individual/{respondent_name}`

**Authorization:** Kun leder for unit eller medarbejderen selv

**Response:**
```json
{
    "respondent_name": "Mette Hansen",
    "unit": "Hjemmeplejen Nord",
    "campaign": "Q1 2025",
    "frictions": {
        "MENING": 4.3,
        "TRYGHED": 4.1,
        "MULIGHED": 3.8,
        "BESVÆR": 1.5
    },
    "primary_blocker": "BESVÆR",
    "profile_type": "High-performer blocked by systems",
    "recommendations": [
        "Fjern systembesvær - denne person har høj mening/tryghed/kompetence",
        "Identificér specifikke procedurer der bremser",
        "Giv mere autonomi til at omgå unødvendige processer"
    ],
    "comparison_to_team": {
        "MENING": {"self": 4.3, "team_avg": 2.1, "delta": +2.2},
        "TRYGHED": {"self": 4.1, "team_avg": 1.9, "delta": +2.2},
        "MULIGHED": {"self": 3.8, "team_avg": 3.0, "delta": +0.8},
        "BESVÆR": {"self": 1.5, "team_avg": 4.1, "delta": -2.6}
    }
}
```

---

## 10. NÆSTE SKRIDT

### Umiddelbare handlinger:
1. **Review denne plan** - Er der noget vi har overset?
2. **Prioritér faser** - Skal vi ændre rækkefølgen?
3. **Ressource-allokering** - Hvor meget tid har vi per uge?
4. **Pilot-kunde** - Hvem skal vi teste med?

### Beslutninger der skal træffes:
1. **KKC-vægtning** - Er 60/40 for Alignment korrekt, eller skal det justeres?
2. **Anonymitetstærskel** - Skal det være 5, eller skal det være konfigurerbart?
3. **Substitutions-detektering** - Hvilke mønstre skal vi starte med?
4. **Individuel data retention** - Hvor længe gemmes identified campaign data?

### Risici:
1. **Privacy** - Sikre at identified mode ikke misbruges
2. **Kompleksitet** - Er det for meget for brugere at forstå?
3. **Fortolkning** - Risiko for over-fortolkning af misalignment
4. **Performance** - Mange beregninger kan blive langsomme

---

## KONKLUSION

Dette er en ambitiøs men gennemtænkt plan der transformerer Friktionskompasset fra et måleværktøj til et diagnostisk system der:

1. **Afslører misalignment** mellem lederens mentale model og virkeligheden
2. **Identificerer root causes** (lederens egne blockers)
3. **Integrerer med eksisterende værktøjer** (KKC)
4. **Tilbyder både system-indsigt og individuel udvikling**

Kernen forbliver den samme: Måle friktioner ærligt uden at fortolke for meget. Men nu med lag der viser HVOR problemet opstår (i teamet, hos lederen, eller i misforståelsen imellem).

---

**Lavet af:** Claude Code
**Dato:** 2025-11-14
**Version:** 1.0
