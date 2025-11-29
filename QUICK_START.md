# Friktionskompasset - Quick Start Guide

## 1. Installer Dependencies

Først skal du sikre at alle Python packages er installeret:

```bash
pip install -r requirements.txt
```

Hvis du får fejl, prøv:
```bash
pip install Flask==3.0.0 Jinja2==3.1.4 python-dotenv==1.0.1
```

---

## 2. Start Appen

Kør admin interfacet (hovedappen):

```bash
python admin_app.py
```

Appen starter på: **http://localhost:5001**

---

## 3. Log Ind

**Default admin credentials:**
- **Username:** `admin`
- **Password:** `admin123`

⚠️ **VIGTIGT:** Skift passwordet i produktion!

---

## 4. Kom I Gang

### 4.1 Upload Organisationer (CSV)

1. Klik på **"Bulk Upload"** i menuen
2. Download CSV-skabelon eller test CSV
3. Upload din CSV fil
4. Organisationer oprettes automatisk i hierarkisk struktur

**CSV Format:**
```csv
FirstName;Lastname;Email;phone;Organisation
Mette;Hansen;mette@test.dk;+4512345001;Odder Kommune//Ældrepleje//Hjemmeplejen Nord
```

### 4.2 Opret Kampagne (Gammel Måde - Uden Nye Features)

1. Naviger til en organisation
2. Klik "Ny Kampagne"
3. Udfyld navn, periode
4. Kampagnen sendes automatisk

### 4.3 Opret Kampagne MED LEDER-PERSPEKTIV (NYE FEATURES!)

**Fra Python konsol eller script:**

```python
from db_hierarchical import create_campaign_with_modes, generate_tokens_with_respondent_types

# Opret anonymous campaign med leder-perspektiv
campaign_id = create_campaign_with_modes(
    target_unit_id="unit-xxx",  # Fra databasen
    name="Q1 2025 - Hjemmeplejen",
    period="2025 Q1",
    mode='anonymous',
    include_leader_assessment=True,  # Leder vurderer teamet
    include_leader_self=True,        # Leder svarer om sig selv
    min_responses=5
)

# Generer tokens
tokens = generate_tokens_with_respondent_types(campaign_id)
print(tokens)
```

**Output:**
```python
{
    'unit-abc': {
        'employee': ['token1', 'token2', ...],  # 5 medarbejder-tokens
        'leader_assess': ['token-L1'],          # 1 leder-vurderings-token
        'leader_self': ['token-L2']             # 1 leder-selv-token
    }
}
```

### 4.4 Test Spørgeskema

**For medarbejder:**
- Gå til: `http://localhost:5001/?token=<employee_token>`
- Besvar spørgsmål om egne friktioner

**For leder (team-vurdering):**
- Gå til: `http://localhost:5001/?token=<leader_assess_token>`
- Besvar: "Hvad tror du dine medarbejdere oplever?"

**For leder (egne friktioner):**
- Gå til: `http://localhost:5001/?token=<leader_self_token>`
- Besvar om egne friktioner som leder

---

## 5. Se Resultater

1. Naviger til kampagnen i admin interfacet
2. Se aggregerede scores per friktions-felt
3. Se response rate

**Med nye features (kommer i Fase 2):**
- Misalignment dashboard (sammenlign medarbejder vs. leder)
- KKC-scores (Direction-Alignment-Commitment)
- Substitutions-detektering

---

## 6. Multi-Tenant Features

### Opret Kunde (kun admin)

1. Log ind som admin
2. Gå til "Customers"
3. Opret ny kunde
4. Opret manager-bruger for kunden

### Log ind som Manager

Managers kan kun se data for deres egen kunde.

---

## 7. Database Inspektion

### Se database indhold:

```bash
sqlite3 friktionskompas_v3.db
```

**Nyttige queries:**
```sql
-- Se alle campaigns
SELECT * FROM campaigns;

-- Se tokens med respondent types
SELECT campaign_id, unit_id, respondent_type, COUNT(*)
FROM tokens
GROUP BY campaign_id, unit_id, respondent_type;

-- Se respondent types
SELECT * FROM respondent_types;

-- Se campaign modes
SELECT * FROM campaign_modes;

-- Se KKC mapping
SELECT * FROM kcc_mapping;
```

---

## 8. Generer Testdata

**Fra admin interface:**
1. Log ind som admin
2. Klik "Generate Test Data" knap
3. Der genereres:
   - 2 organisationer (Odder Kommune + TechCorp)
   - ~30 medarbejdere
   - 4 kampagner med svar

**Eller kør:**
```bash
python demo_data_hierarchical.py
```

---

## 9. Troubleshooting

### Appen starter ikke

**Fejl:** `ModuleNotFoundError: No module named 'flask'`
- **Løsning:** `pip install -r requirements.txt`

**Fejl:** `Address already in use: 5001`
- **Løsning:** Skift port i `admin_app.py` eller stop anden proces på port 5001

### Database fejl

**Fejl:** `no such table: respondent_types`
- **Løsning:** Kør migration: `python run_migration.py`

**Fejl:** `no such column: mode`
- **Løsning:** Kør migration igen

### Login virker ikke

**Default credentials:**
- Username: `admin`
- Password: `admin123`

Hvis det ikke virker:
```python
# Reset admin password
from db_multitenant import get_db, hash_password

with get_db() as conn:
    new_hash = hash_password("admin123")
    conn.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (new_hash,))
    print("Password reset!")
```

---

## 10. Stop Appen

- Tryk **Ctrl+C** i terminalen hvor appen kører

---

## 11. Næste Skridt Efter Quick Start

1. **Upload rigtige data** via CSV
2. **Opret kampagne** med nye features (leder-perspektiv)
3. **Test flow** med forskellige respondent types
4. **Se misalignment** (kommer i Fase 2)
5. **Eksporter resultater**

---

## Appendix: Kode-eksempler

### Komplet Eksempel: Opret Organisation + Kampagne

```python
from db_hierarchical import (
    create_unit_from_path,
    create_campaign_with_modes,
    generate_tokens_with_respondent_types
)

# 1. Opret organisation
unit_id = create_unit_from_path(
    path="Min Kommune//IT Afdeling//Team Alpha",
    leader_name="Jane Doe",
    leader_email="jane@kommune.dk",
    employee_count=8
)

# 2. Opret anonymous campaign med leder-perspektiv
campaign_id = create_campaign_with_modes(
    target_unit_id=unit_id,
    name="Q1 2025 Friktion",
    period="2025 Q1",
    mode='anonymous',
    include_leader_assessment=True,
    include_leader_self=True,
    min_responses=5
)

# 3. Generer tokens
tokens = generate_tokens_with_respondent_types(campaign_id)

# 4. Print tokens til distribution
for unit_id, token_dict in tokens.items():
    print(f"\nUnit: {unit_id}")

    print("\nMedarbejder-tokens (send til teamet):")
    for token in token_dict['employee']:
        print(f"  http://localhost:5001/?token={token}")

    print("\nLeder-token (vurder teamet):")
    print(f"  http://localhost:5001/?token={token_dict['leader_assess'][0]}")

    print("\nLeder-token (egne friktioner):")
    print(f"  http://localhost:5001/?token={token_dict['leader_self'][0]}")
```

### Identified Campaign Eksempel

```python
# Opret identified campaign (navngivne respondenter)
campaign_id = create_campaign_with_modes(
    target_unit_id=unit_id,
    name="MUS 2025 - Team Alpha",
    period="2025",
    mode='identified',  # Ikke anonym!
    include_leader_assessment=False,
    include_leader_self=False,
    min_responses=1
)

# Generer tokens med navne
respondent_names = {
    unit_id: [
        'Alice Johnson',
        'Bob Smith',
        'Carol Williams'
    ]
}

tokens = generate_tokens_with_respondent_types(campaign_id, respondent_names)

# Print personlige links
for token, name in tokens[unit_id]['employee']:
    print(f"{name}: http://localhost:5001/?token={token}")
```

---

**Lavet:** 2025-11-14
**Version:** 1.0 (Fase 1 completed)
