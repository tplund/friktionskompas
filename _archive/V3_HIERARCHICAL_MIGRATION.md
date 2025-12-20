# Friktionskompas V3 - Hierarkisk Struktur

## Hvad er nyt?

### ✅ Før (v2): Flat struktur
```
Organization
  ├── Department 1
  ├── Department 2
  └── Department 3
```

### 🎯 Nu (v3): Hierarkisk træstruktur
```
Organization
  ├── Afdeling A
  │   ├── Team 1
  │   └── Team 2
  └── Afdeling B
      ├── Team 3
      └── Team 4
```

## Nøgleændringer

### 1. **Én tabel for alt: `organizational_units`**
Alle enheder (virksomheder, afdelinger, teams) er nu "units" i ét træ:

```sql
organizational_units:
  - id (unique)
  - parent_id (NULL = top level)
  - name 
  - full_path (cached: "TechCorp//IT//Development")
  - level (0, 1, 2...)
  - leader_name, leader_email
  - employee_count, sick_leave_percent
```

### 2. **CSV Import med `//` separator**

Du kan nu importere hierarkier direkte i CSV:

```csv
Organisation,Leder,Email,Medarbejdere,Sygefravær
TechCorp//IT Afdeling//Development,Anders Hansen,anders@techcorp.dk,15,3.2
TechCorp//IT Afdeling//Support,Mette Nielsen,mette@techcorp.dk,8,5.1
TechCorp//HR & Admin//Rekruttering,Jesper Berg,jesper@techcorp.dk,4,2.1
```

Systemet opretter automatisk manglende parent units!

### 3. **Kampagner på hvilket som helst niveau**

En kampagne kan sendes til **en hvilken som helst unit**, og rammer automatisk alle leaf-units under den:

```python
# Send kampagne til hele TechCorp
campaign = create_campaign(target_unit_id="techcorp-root", ...)

# Send kampagne kun til IT Afdeling (rammer Development + Support)
campaign = create_campaign(target_unit_id="techcorp-it", ...)

# Send kampagne kun til ét specifikt team
campaign = create_campaign(target_unit_id="techcorp-it-dev", ...)
```

### 4. **Smart aggregering**

Data kan aggregeres op gennem træet:

```python
# Stats kun for Development team
stats = get_unit_stats(unit_id="dev-team", campaign_id="...", include_children=False)

# Stats for hele IT (Development + Support)
stats = get_unit_stats(unit_id="it-dept", campaign_id="...", include_children=True)

# Stats for hele TechCorp
stats = get_unit_stats(unit_id="techcorp-root", campaign_id="...", include_children=True)
```

## Nøglefunktioner

### Opret units fra path
```python
from db_hierarchical import create_unit_from_path

# Opretter automatisk alle nødvendige parent units
unit_id = create_unit_from_path(
    path="TechCorp//IT Afdeling//Development",
    leader_name="Anders Hansen",
    leader_email="anders@techcorp.dk",
    employee_count=15,
    sick_leave_percent=3.2
)
```

### Find children
```python
from db_hierarchical import get_unit_children

# Direkte children
children = get_unit_children(unit_id="it-dept", recursive=False)

# Hele subtræet
all_descendants = get_unit_children(unit_id="it-dept", recursive=True)
```

### Find leaf units
```python
from db_hierarchical import get_leaf_units

# Alle leaf units i hele databasen
all_leaves = get_leaf_units()

# Leaf units under specifik parent
it_leaves = get_leaf_units(parent_unit_id="it-dept")
```

### Breadcrumbs
```python
from db_hierarchical import get_unit_path

# Få hele stien fra root til unit
path = get_unit_path(unit_id="dev-team")
# Returns: [{"name": "TechCorp", ...}, {"name": "IT", ...}, {"name": "Development", ...}]
```

## Database ændringer

### Udgået
- ❌ `organizations` table
- ❌ `departments` table  
- ❌ `campaign_departments` join table

### Nyt
- ✅ `organizational_units` (erstatter organizations + departments)
- ✅ `campaigns.target_unit_id` (erstatter mange-til-mange relation)
- ✅ `tokens.unit_id` (erstatter department_id)
- ✅ `responses.unit_id` (erstatter department_id)

## Migration

Hvis du har eksisterende data i v2, skal du migrere:

1. **Backup din database**
2. **Kør migration script** (TODO: laves hvis nødvendigt)
3. Eller start fresh med `demo_data_hierarchical.py`

## Demo Data

Kør demo setup:

```bash
python demo_data_hierarchical.py
```

Dette opretter:
- **TechCorp** (7 leaf units, 62 medarbejdere)
  - IT Afdeling (Development, Support)
  - HR & Admin (Rekruttering, Løn & Personale)
  - Sales & Marketing (Salg Nord, Salg Syd, Marketing)

- **ServiceGruppen** (6 leaf units, 65 medarbejdere)
  - Kundeservice (Team A, Team B)
  - Back Office (Administration, Økonomi)
  - Drift (Daghold, Aftenhold)

Plus 2 kampagner med realistiske svar!

## Næste skridt

Nu skal admin UI'et opdateres til at håndtere hierarkisk visning og navigation. Det er perfekt til **Claude Code**! 🚀
