# Plan: Målingstype-konfiguration per Kunde/Domæne

## Oversigt

System hvor superadmin kan konfigurere hvilke målingstyper (tests) der er tilgængelige for forskellige kunder og domæner.

## Målingstyper (Assessment Types)

| Type | Beskrivelse | Spørgsmål | Målgruppe |
|------|-------------|-----------|-----------|
| `screening` | Hurtig screening | 6 spørgsmål | Alle - hurtigt overblik |
| `profil_fuld` | Fuld friktionsprofil | 30+ spørgsmål | Individuel - grundig analyse |
| `profil_situation` | Situations-profil | 30+ spørgsmål | Individuel - i specifik situation |
| `gruppe_friktion` | Gruppe-friktionsanalyse | 24 spørgsmål | Teams - organisatorisk måling |
| `gruppe_leder` | Leder-specifik måling | 24 spørgsmål + leder-spørgsmål | Teams med lederfokus |
| `kapacitet` | Kapacitetsmåling | 8 spørgsmål | "Tage sig sammen"-mekanik |
| `baandbredde` | Båndbredde-måling | 2 spørgsmål | Løfte pres opad |

## Database Ændringer

### Ny tabel: `assessment_types`
```sql
CREATE TABLE assessment_types (
    id TEXT PRIMARY KEY,           -- fx 'screening', 'profil_fuld'
    name_da TEXT NOT NULL,
    name_en TEXT NOT NULL,
    description_da TEXT,
    description_en TEXT,
    question_count INTEGER,        -- Antal spørgsmål
    duration_minutes INTEGER,      -- Estimeret tid
    is_individual BOOLEAN,         -- true = individuel, false = gruppe
    is_active BOOLEAN DEFAULT 1,   -- Kan deaktiveres globalt
    sequence INTEGER DEFAULT 0,    -- Sortering
    icon TEXT,                     -- Emoji/ikon
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Ny tabel: `customer_assessment_types`
```sql
CREATE TABLE customer_assessment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    assessment_type_id TEXT REFERENCES assessment_types(id) ON DELETE CASCADE,
    is_enabled BOOLEAN DEFAULT 1,
    custom_name_da TEXT,           -- Override af navn (valgfrit)
    custom_name_en TEXT,
    UNIQUE(customer_id, assessment_type_id)
);
```

### Ny tabel: `domain_assessment_types`
```sql
CREATE TABLE domain_assessment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER REFERENCES domains(id) ON DELETE CASCADE,
    assessment_type_id TEXT REFERENCES assessment_types(id) ON DELETE CASCADE,
    is_enabled BOOLEAN DEFAULT 1,
    UNIQUE(domain_id, assessment_type_id)
);
```

### Presets tabel
```sql
CREATE TABLE assessment_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,            -- fx "B2C Standard", "Enterprise Full"
    description TEXT,
    is_default BOOLEAN DEFAULT 0,  -- Standard preset for nye kunder
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE preset_assessment_types (
    preset_id INTEGER REFERENCES assessment_presets(id) ON DELETE CASCADE,
    assessment_type_id TEXT REFERENCES assessment_types(id) ON DELETE CASCADE,
    PRIMARY KEY(preset_id, assessment_type_id)
);
```

## Prioritet (fallback-logik)

1. **Domain config** - Hvis domæne har eksplicit konfiguration, brug den
2. **Customer config** - Ellers brug kundens konfiguration
3. **Preset default** - Ellers brug standard-preset
4. **Alle aktive typer** - Fallback: vis alle aktive assessment_types

## Admin UI

### Superadmin: Målingstyper
`/admin/assessment-types` - CRUD for assessment_types

### Superadmin: Presets
`/admin/assessment-presets` - Administrer presets
- Opret/rediger presets
- Vælg hvilke typer der er i hvert preset
- Marker én som default

### Admin: Kunde-konfiguration
`/admin/customers/<id>/assessments` - Konfigurer per kunde
- Dropdown: Vælg preset ELLER
- Checkboxes: Manuel valg af typer
- Override navne (valgfrit)

### Superadmin: Domæne-konfiguration
`/admin/domains/<id>/assessments` - Override per domæne
- Inherit from customer (default)
- Custom selection

## Forslag til Standard Presets

### "B2C Individuel"
- screening ✓
- profil_fuld ✓
- profil_situation ✗
- gruppe_* ✗

### "B2B Standard"
- screening ✓
- profil_fuld ✓
- gruppe_friktion ✓
- gruppe_leder ✗

### "Enterprise Full"
- Alle typer aktiveret

## Implementation Steps

1. [ ] Database migrering (create tables)
2. [ ] Seed assessment_types med de 7 typer
3. [ ] Seed presets (3 standard presets)
4. [ ] Helper funktion: `get_available_assessments(customer_id, domain_id)`
5. [ ] Admin UI: `/admin/assessment-types`
6. [ ] Admin UI: `/admin/assessment-presets`
7. [ ] Integration i "Ny måling" flow
8. [ ] Integration i friktionsprofil-landing

## API Helper

```python
def get_available_assessments(customer_id=None, domain_id=None):
    """
    Hent tilgængelige målingstyper for en given kunde/domæne.

    Prioritet:
    1. Domain-specific config
    2. Customer config
    3. Default preset
    4. All active types
    """
    with get_db() as conn:
        # Check domain first
        if domain_id:
            domain_types = conn.execute('''
                SELECT at.* FROM assessment_types at
                JOIN domain_assessment_types dat ON at.id = dat.assessment_type_id
                WHERE dat.domain_id = ? AND dat.is_enabled = 1 AND at.is_active = 1
                ORDER BY at.sequence
            ''', (domain_id,)).fetchall()
            if domain_types:
                return domain_types

        # Check customer
        if customer_id:
            customer_types = conn.execute('''
                SELECT at.* FROM assessment_types at
                JOIN customer_assessment_types cat ON at.id = cat.assessment_type_id
                WHERE cat.customer_id = ? AND cat.is_enabled = 1 AND at.is_active = 1
                ORDER BY at.sequence
            ''', (customer_id,)).fetchall()
            if customer_types:
                return customer_types

        # Default preset
        default_types = conn.execute('''
            SELECT at.* FROM assessment_types at
            JOIN preset_assessment_types pat ON at.id = pat.assessment_type_id
            JOIN assessment_presets ap ON pat.preset_id = ap.id
            WHERE ap.is_default = 1 AND at.is_active = 1
            ORDER BY at.sequence
        ''').fetchall()
        if default_types:
            return default_types

        # Fallback: all active types
        return conn.execute('''
            SELECT * FROM assessment_types WHERE is_active = 1 ORDER BY sequence
        ''').fetchall()
```

## Næste Skridt

Vil du have mig til at implementere dette? Jeg foreslår vi starter med:
1. Database-skemaet
2. Seed data
3. Admin UI for assessment types
