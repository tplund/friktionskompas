# Friktionskompasset v3

**Multi-tenant friktionsanalyse-platform** med hierarkisk organisationsstruktur og avanceret analyse baseret på KKC-framework.

Et handlingsorienteret ledelsesværktøj der måler friktioner for adfærd på fire felter:
- **MENING** - Oplevelse af meningsløshed → **KURS**
- **TRYGHED** - Det usagte → **KOORDINERING**
- **KAN** - Manglende evne eller ressourcer → **KOORDINERING**
- **BESVÆR** - Workarounds og regelomgåelse → **COMMITMENT**

Anbefalingerne følger **Anders Trillingsgaards KKC-model** (Kurs, Koordinering, Commitment).

---

## 📖 VIGTIGT: Læs Dette Først

**For udviklere/Claude sessions:**
- **`SYSTEM_DESIGN.md`** - Alle analyse-kriterier, design decisions, og system dokumentation
- **`.clinerules`** - Auto-loaded ved Claude Code sessions

Disse filer sikrer konsistente kriterier på tværs af sessions og ændringer.

---

## 🚀 Quick Start

### Setup
```bash
# Install dependencies
pip install flask bcrypt

# Initialize database
python db_hierarchical.py
python db_multitenant.py

# Start servers
python app.py           # Port 5002 - Survey interface
python admin_app.py     # Port 5001 - Admin dashboard
```

### Default Login
- **URL:** http://localhost:5001
- **Username:** admin
- **Password:** admin123
- ⚠️ **SKIFT PASSWORD I PRODUKTION!**

---

## ✨ Features v3

✅ **Multi-tenant** - Flere kunder i samme installation med fuld isolation
✅ **Hierarkisk organisation** - Ubegrænset dybde: Virksomhed → Afdeling → Team
✅ **24 spørgsmål** - Opdelt i 4 felter med lagdeling (ydre/indre)
✅ **3 respondent types** - employee, leader_assess, leader_self
✅ **Gap-analyse** - Sammenlign leder og medarbejder opfattelse
✅ **Sprednings-analyse** - Detekter uensartet oplevelse i team
✅ **Blocked leader** - Flag når leder selv har friktioner
✅ **Substitution detection** - Kahneman bias (tid vs. utilfredshed)
✅ **KKC anbefalinger** - Konkrete handlinger baseret på friktioner
✅ **Bulk upload** - CSV import af hierarkisk struktur
✅ **Email/SMS sending** - Mailjet integration
✅ **Anonymitet** - Konfigurerbar threshold (default: 5 svar)

---

## 🏗️ Arkitektur

### Multi-tenant
- Kunder isoleret via `customer_id`
- Users: `admin` (ser alt) eller `manager` (ser kun egen kunde)
- Customer filter på alle queries

### Hierarkisk Organisation
```
Virksomhed (root)
├── Afdeling A (branch)
│   ├── Team 1 (leaf)
│   └── Team 2 (leaf)
└── Afdeling B (branch)
    └── Team 3 (leaf)
```

- Campaigns targets en unit → rammer alle leaf units under den
- Tokens genereres per leaf unit
- Responses gemmes på leaf unit level

### Respondent Types
1. **employee** - Medarbejderes oplevelse (hoveddata)
2. **leader_assess** - Lederens vurdering af teamet
3. **leader_self** - Lederens egne friktioner

---

## 📊 Analyse Kriterier

Se **`SYSTEM_DESIGN.md`** for alle detaljer, men kort:

- **Severity:** ≤50% = høj, ≤70% = medium, >70% = lav
- **Gap:** >20% forskel = signifikant
- **Spredning:** σ ≥1.0 = høj (uensartet oplevelse)
- **Blocked leader:** Team OG leder < 70%
- **Substitution:** tid_bias ≥0.6 OG underliggende ≥3.5

---

## 🗂️ Projekt Struktur

```
├── app.py                      # Survey app (port 5002)
├── admin_app.py                # Admin dashboard (port 5001)
├── db_hierarchical.py          # Database setup & core functions
├── db_multitenant.py           # Multi-tenant & authentication
├── analysis.py                 # Analyse-funktioner & KKC
├── csv_upload_hierarchical.py # Bulk upload
├── mailjet_integration.py      # Email/SMS sending
├── templates/
│   ├── survey/                # Survey UI
│   └── admin/                 # Admin dashboard
├── SYSTEM_DESIGN.md           # 📖 VIGTIG: Læs dette først!
├── .clinerules                # Claude Code auto-load rules
└── README.md                  # This file
```

---

## 🎯 KKC Framework

Integration med Anders Trillingsgaard's framework:

- **MENING** → KURS (retning og formål)
- **TRYGHED** → KOORDINERING (samarbejde)
- **KAN** → KOORDINERING (evner + ressourcer)
- **BESVÆR** → COMMITMENT (system matcher virkelighed)

---

## 🔄 Workflows

### 1. Opret Organisation
```
Admin → Bulk Upload → Upload CSV med hierarki
Format: "Virksomhed//Afdeling//Team"
```

### 2. Send Måling
```
Admin → Ny Måling → Vælg target unit → Generer tokens → Send
```

### 3. Analyser Resultater
```
Admin → Målinger → Detailed Analysis
- Gap-analyse (leder vs. medarbejder)
- Blocked leader check
- Sprednings-analyse
- KKC anbefalinger
```

---

## 🛠️ Udvikling

### Før du laver ændringer:
1. Læs `SYSTEM_DESIGN.md`
2. Forstå kriterierne (gap, severity, etc.)
3. Test med eksisterende data

### Hvis du ændrer kriterier:
1. Opdater koden
2. **Opdater `SYSTEM_DESIGN.md`**
3. Dokumenter hvorfor
4. Test impact på eksisterende campaigns

---

## 🔐 Sikkerhed

- ✅ Bcrypt password hashing
- ✅ Customer isolation via WHERE clauses
- ✅ Anonymitet threshold (min 5 responses)
- ⚠️ Skift default admin password i produktion!
- ⚠️ Sæt SECRET_KEY miljøvariabel i produktion

---

## 📝 License

[Indsæt licens her]

---

**Vigtig:** Ved start af nye Claude sessions læses `SYSTEM_DESIGN.md` automatisk via `.clinerules`
