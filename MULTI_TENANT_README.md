# Multi-Tenant Implementation - Friktionskompasset

## Oversigt

Systemet understøtter nu multi-tenant funktionalitet med customer isolation og bruger-baseret adgangskontrol.

## Funktioner

### 1. **Customer Isolation**
- Hver organisation tilhører en kunde (customer)
- Data er isoleret mellem kunder
- Admin kan se alle data
- Manager kan kun se data for deres egen kunde

### 2. **Roller**

#### Admin
- Kan se alle kunder og organisationer
- Kan oprette kunder og brugere
- Har fuld adgang til systemet
- Ingen customer_id (kan se alt)

#### Manager
- Kan kun se og redigere data for deres egen kunde
- Kan oprette organisationer for deres kunde
- Kan sende kampagner til deres kunde's organisationer
- Har en customer_id

### 3. **Login System**
- Alle routes kræver login (@login_required)
- Customer management kræver admin rolle (@admin_required)
- Session-baseret autentificering
- Password hashing med SHA256

### 4. **Default Admin User**
```
Brugernavn: admin
Password: admin123
Rolle: Admin
```

**VIGTIGT: Skift password i produktion!**

## Database Ændringer

### Nye Tabeller

#### customers
```sql
- id (PRIMARY KEY)
- name
- contact_email
- is_active
- created_at
```

#### users
```sql
- id (PRIMARY KEY)
- username (UNIQUE)
- password_hash
- name
- email
- role (admin/manager)
- customer_id (FOREIGN KEY -> customers)
- is_active
- created_at
- last_login
```

### Opdaterede Tabeller

#### organizational_units
- Tilføjet kolonne: `customer_id` (FOREIGN KEY -> customers)

## Navigation

### For Admin
- 📊 Hjem - Organisationsoversigt
- ➕ Ny Organisation - Opret organisation
- 📤 Bulk Upload - CSV import
- 📨 Ny Kampagne - Send kampagne
- 👥 Kunder & Brugere - Customer management (kun admin)

### For Manager
Samme som admin, men uden "Kunder & Brugere" menupunkt.

## Customer Management (Kun Admin)

### Opret Kunde
1. Gå til "Kunder & Brugere"
2. Klik på "Opret ny kunde"
3. Indtast kunde navn og kontakt email
4. Klik "Opret kunde"

### Opret Manager Bruger
1. Gå til "Kunder & Brugere"
2. Klik på "Opret ny bruger"
3. Udfyld formularen:
   - Brugernavn (skal være unikt)
   - Password
   - Navn
   - Email (valgfrit)
   - Rolle: Vælg "Manager"
   - Kunde: Vælg den relevante kunde
4. Klik "Opret bruger"

## Data Isolation

### Hvordan det virker

**Admin:**
- Queries bruger `WHERE 1=1` (ingen filtering)
- Kan se og redigere alle organisationer
- Kan se alle kampagner

**Manager:**
- Queries bruger `WHERE customer_id = ?`
- Kan kun se organisationer for deres kunde
- Kan kun se kampagner for deres kunde's organisationer

### Implementering

Alle queries bruger `get_customer_filter()` helper funktionen:

```python
user = get_current_user()
where_clause, params = get_customer_filter(user['role'], user['customer_id'])

sql = f"SELECT * FROM organizational_units WHERE {where_clause}"
conn.execute(sql, params)
```

## CSV Upload

Når en bruger uploader CSV, får de oprettede organisationer automatisk brugerens customer_id:

```python
stats = bulk_upload_from_csv(content, customer_id=user['customer_id'])
```

Dette sikrer at:
- Admin kan uploade organisationer uden customer (customer_id = None)
- Manager kan kun uploade for deres egen kunde

## Sikkerhed

### Adgangskontrol
- Alle admin routes kræver login
- Customer management kræver admin rolle
- Data queries filtreres automatisk baseret på brugerens rolle
- Managers kan ikke se andre kunders data

### Password Sikkerhed
- Passwords hashes med SHA256
- Aldrig gemt i plain text
- Default admin password bør ændres med det samme i produktion

### Session Management
- Flask session-baseret
- Secret key skal ændres i produktion (admin_app.py:29)

## Filer

### Nye Filer
- `db_multitenant.py` - Multi-tenant database funktioner
- `templates/login.html` - Login side
- `templates/admin/customers.html` - Customer management
- `MULTI_TENANT_README.md` - Denne fil

### Opdaterede Filer
- `admin_app.py` - Login system og customer filtering
- `db_hierarchical.py` - Support for customer_id i create_unit
- `csv_upload_hierarchical.py` - Support for customer_id i CSV upload
- `templates/admin/layout.html` - Navigation med bruger info

## Kom I Gang

### 1. Initialiser Database
Database initialiseres automatisk når admin_app.py startes første gang.

### 2. Log Ind
1. Gå til http://localhost:5001/login
2. Brug admin/admin123
3. SKIFT PASSWORD

### 3. Opret Første Kunde
1. Gå til "Kunder & Brugere"
2. Opret en kunde (fx "Acme Corp")

### 4. Opret Manager Bruger
1. Opret en manager bruger for kunden
2. Log ud som admin
3. Log ind som manager for at teste isolation

### 5. Upload Data
Som manager:
1. Upload CSV data
2. Data får automatisk kundens customer_id
3. Log ind som admin for at verificere at du kan se begge kunders data

## Fremtidige Forbedringer

- [ ] Password reset funktionalitet
- [ ] Bruger deaktivering (is_active flag)
- [ ] Audit log (hvem har gjort hvad)
- [ ] Email verification
- [ ] Two-factor authentication
- [ ] Customer deaktivering
- [ ] Bruger profil side med password change
- [ ] Bedre password hashing (bcrypt i stedet for SHA256)

## Support

Ved problemer, tjek:
1. Er du logget ind?
2. Har du de rigtige rettigheder (admin/manager)?
3. Tilhører organisationen din kunde?

## Teknisk Stack

- **Backend:** Flask (Python)
- **Database:** SQLite
- **Auth:** Session-baseret med decorators
- **Templates:** Jinja2
- **Styling:** Inline CSS (embedded i templates)
