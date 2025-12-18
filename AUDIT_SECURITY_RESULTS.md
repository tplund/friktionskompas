# SIKKERHEDSAUDIT - Friktionskompasset

**Dato:** 2025-12-18
**Auditor:** Claude Code (go-live audit)
**Status:** DELVIST FIXET

---

## AUDIT SCOPE

### Hvad blev tjekket:
1. Debug/test endpoints der skal fjernes
2. SQL injection vulnerabilities
3. Multi-tenant isolation (customer_id filter)
4. OAuth state parameter validation
5. Session management og timeout
6. Hardcoded secrets
7. CSRF protection
8. Rate limiting
9. Offentlige API endpoints og deres auth

---

## FIXES IMPLEMENTERET

### 1. Debug/Test Endpoints Fjernet/Beskyttet

| Endpoint | Handling | Lokation |
|----------|----------|----------|
| `/api/debug-analyser/<unit_id>` | FJERNET | admin_app.py:2360 |
| `/test/assessment/<assessment_id>/detailed` | FJERNET | admin_app.py:3765 |
| `/profil/generate-test-data` | BESKYTTET med @admin_required | admin_app.py:4036 |
| `/api/clear-cache/<secret>` | FJERNET | admin_app.py:4977 |
| `/api/vary-testdata/<secret_key>` | FJERNET | admin_app.py:5142 |
| `/api/fix-testdata-trends/<secret_key>` | FJERNET | admin_app.py:5147 |
| `/api/list-assessments/<secret_key>` | FJERNET | admin_app.py:5151 |

### 2. Hardcoded Secret Key Fixet

**Fil:** `profil_app.py:22-27`

Før:
```python
app.secret_key = 'friktionsprofil-secret-key-change-in-production'
```

Efter:
```python
app.secret_key = os.environ.get('SECRET_KEY') or secrets_module.token_hex(32)
```

### 3. SQL Injection Fixet

**Backup Restore (`admin_app.py:5378-5384`):**
- Tilføjet validering af kolonne-navne fra JSON backup
- Kun navne der matcher `^[a-zA-Z_][a-zA-Z0-9_]*$` accepteres
- Rækker med ugyldige kolonner springes over

**MCP Server (`mcp_server.py:237-240`):**
- Tilføjet validering af tabelnavn i `table_schema` query
- Returnerer fejl for ugyldige tabelnavne

---

## IKKE FIXET - KRÆVER YDERLIGERE ARBEJDE

### 1. CSRF Protection (ANBEFALES FØR GO-LIVE)

**Status:** Ikke implementeret
**Risiko:** MEDIUM-HØJ

**Hvad skal gøres:**
1. Tilføj `Flask-WTF` til requirements.txt
2. Initialiser CSRFProtect i admin_app.py
3. Tilføj CSRF tokens til alle forms i templates
4. Evt. tilføj CSRF exemption for API endpoints med API key

```bash
# Tilføj til requirements.txt
Flask-WTF>=1.2.0
```

```python
# I admin_app.py
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)
```

### 2. Rate Limiting (ANBEFALES FØR GO-LIVE)

**Status:** Ikke implementeret
**Risiko:** MEDIUM

**Hvad skal gøres:**
1. Tilføj `Flask-Limiter` til requirements.txt
2. Konfigurer rate limits på auth endpoints

```bash
# Tilføj til requirements.txt
Flask-Limiter>=3.5.0
```

```python
# I admin_app.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")  # Max 5 login forsøg per minut
def login():
    ...
```

**Endpoints der skal beskyttes:**
- `/login` - 5/min
- `/register` - 3/min
- `/forgot-password` - 3/min
- `/login/email` - 5/min
- `/resend-code` - 2/min

---

## OK FUND (Ingen action påkrævet)

### Multi-tenant Isolation
- `get_customer_filter()` bruges konsekvent på alle data-access endpoints
- Customer isolation er implementeret korrekt

### OAuth State Validation
- Authlib håndterer state parameter automatisk
- OAuth flow er sikker

### Session Management
- `PERMANENT_SESSION_LIFETIME = 8 timer` - Acceptabelt for intern app
- `SESSION_REFRESH_EACH_REQUEST = True` - Timeout refreshes ved aktivitet

### API Endpoints Auth
- `/api/admin/status` - Beskyttet med `@api_or_admin_required`
- `/api/admin/clear-cache` - Beskyttet med `@api_or_admin_required`

### Offentlige Endpoints (By Design)
Disse endpoints er offentlige og det er OK:
- `/profil/*` - B2C profil (session-baseret sikkerhed)
- `/profil/api/questions` - Stateless spørgsmål API
- `/profil/api/calculate` - Stateless beregning (gemmer intet)
- `/s/<token>` - Survey (token er secret)

---

## AUDIT METODE

### Søgninger udført:
```bash
# Debug endpoints
grep -n "/api/(fix-testdata|list-assessments|vary-testdata|clear-cache|debug|test)" *.py

# Hardcoded secrets
grep -n "secret_key|frik2025" *.py

# SQL injection (f-strings i execute)
grep -n "execute\([^)]*f['\"]" *.py

# CSRF
grep -n "CSRFProtect|flask_wtf" *.py

# Rate limiting
grep -n "rate_limit|RateLimiter|limiter" *.py

# Auth decorators
grep -n "@login_required|@admin_required" admin_app.py
```

### Filer gennemgået:
- `admin_app.py` (7500+ linjer)
- `profil_app.py`
- `survey_app.py`
- `mcp_server.py`
- `db_multitenant.py`
- `db_hierarchical.py`
- `update_admin_password.py`

---

## OPSUMMERING

| Kategori | Status |
|----------|--------|
| Debug endpoints | FIXET |
| Hardcoded secrets | FIXET |
| SQL injection | FIXET |
| CSRF protection | IKKE FIXET (kræver Flask-WTF) |
| Rate limiting | IKKE FIXET (kræver Flask-Limiter) |
| Multi-tenant isolation | OK |
| OAuth | OK |
| Session management | OK |

### Anbefalinger før go-live:

1. **KRITISK:** Implementer CSRF protection (Flask-WTF)
2. **VIGTIGT:** Implementer rate limiting på auth endpoints (Flask-Limiter)
3. **NICE-TO-HAVE:** Fjern `update_admin_password.py` fra repo

### Test efter fixes:

```bash
# Kør tests for at sikre fixes ikke bryder noget
python -m pytest tests/ -v --tb=short

# Verificer fjernede endpoints returnerer 404
curl https://friktionskompasset.dk/api/debug-analyser/test
curl https://friktionskompasset.dk/test/assessment/test/detailed
curl https://friktionskompasset.dk/api/clear-cache/frik2025cache
```

---

## ÆNDRINGSLOG

| Dato | Handling |
|------|----------|
| 2025-12-18 | Initial audit gennemført |
| 2025-12-18 | Debug endpoints fjernet |
| 2025-12-18 | Hardcoded secret key fixet i profil_app.py |
| 2025-12-18 | SQL injection i backup restore fixet |
| 2025-12-18 | SQL injection i MCP server fixet |
