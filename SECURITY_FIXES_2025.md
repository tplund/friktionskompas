# API Security Fixes - December 2025

## Summary

Critical security fixes implemented for Friktionskompasset production deployment.

## Changes Implemented

### 1. Security Headers Middleware (`admin_app.py`)

Added `@app.after_request` handler to inject security headers on all responses:

- **Content-Security-Policy**: Restricts resource loading to trusted sources
- **X-Frame-Options**: Prevents clickjacking (SAMEORIGIN)
- **X-Content-Type-Options**: Prevents MIME-type sniffing
- **X-XSS-Protection**: Browser XSS filter enabled
- **Referrer-Policy**: Controls referrer information leakage
- **Permissions-Policy**: Restricts browser features (geolocation, camera, etc.)
- **Strict-Transport-Security**: HSTS enabled in production only

**Location**: Lines 125-147 in `admin_app.py`

### 2. Debug Mode Security

#### admin_app.py
- Debug mode now controlled by `FLASK_DEBUG` environment variable
- Defaults to `false` (production-safe)
- Set `FLASK_DEBUG=true` for local development only

**Locations**:
- Line 108: `app.debug` configuration
- Lines 2474-2476: `if __name__` block updated

#### profil_app.py
- Same debug mode controls applied
- Consistent security configuration

**Locations**:
- Line 34: `app.debug` configuration
- Lines 253-255: `if __name__` block updated

### 3. CORS Configuration (`admin_app.py`)

Added Flask-CORS for API endpoints:

```python
CORS(app, resources={
    r"/api/*": {
        "origins": env.CORS_ORIGINS,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-API-Key", "X-Admin-API-Key"]
    }
})
```

**Environment Variable**:
- `CORS_ORIGINS`: Comma-separated list of allowed origins
- Default: `https://friktionskompasset.dk,https://frictioncompass.com`

**Location**: Lines 123-131 in `admin_app.py`

### 4. Upload Size Limit

Added 16MB max upload limit:

```python
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
```

**Locations**:
- Line 115 in `admin_app.py`
- Line 37 in `profil_app.py`

### 5. Secure Session Cookies

Enhanced cookie security:

```python
app.config['SESSION_COOKIE_SECURE'] = not app.debug  # HTTPS only in prod
app.config['SESSION_COOKIE_HTTPONLY'] = True         # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'        # CSRF protection
```

**Locations**:
- Lines 116-118 in `admin_app.py`
- Lines 38-40 in `profil_app.py`

### 6. SECRET_KEY Validation

Production SECRET_KEY now required:

```python
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY and not os.environ.get('FLASK_DEBUG'):
    raise RuntimeError('SECRET_KEY must be set in production')
```

**Impact**: Application will not start in production without SECRET_KEY environment variable.

**Locations**:
- Lines 102-105 in `admin_app.py`
- Lines 28-31 in `profil_app.py`

### 7. Error Handler (500)

Production error handler hides tracebacks:

```python
@app.errorhandler(500)
def handle_500(e):
    if app.debug:
        raise e
    return render_template('errors/500.html'), 500
```

**Template Created**: `templates/errors/500.html`

**Location**: Lines 2474-2480 in `admin_app.py`

### 8. Dev Tools Protection (`blueprints/dev_tools.py`)

Added environment check for sensitive endpoints:

```python
def dev_tools_enabled():
    return (os.environ.get('ENABLE_DEV_TOOLS', 'false').lower() == 'true' or
            current_app.debug)
```

Protected endpoints:
- `/admin/vary-testdata`
- `/admin/fix-missing-leader-data`
- `/admin/rename-assessments`
- `/admin/generate-test-data`

**Environment Variable**: `ENABLE_DEV_TOOLS=true` to enable in production (not recommended)

**Location**: Lines 46-50 in `blueprints/dev_tools.py`

### 9. Per-Customer API Rate Limiting

Implemented customer-specific rate limiting:

#### extensions.py
```python
def get_api_key_or_ip():
    if hasattr(g, 'api_customer_id') and g.api_customer_id:
        return f"api_customer:{g.api_customer_id}"
    return get_remote_address()
```

**Location**: Lines 17-24 in `extensions.py`

#### API Endpoint Limits (`blueprints/api_customer.py`)

- **GET requests**: 100/minute per customer
  - `/api/v1/assessments`
  - `/api/v1/assessments/<id>`
  - `/api/v1/assessments/<id>/results`
  - `/api/v1/units`

- **POST requests**: 20/minute per customer
  - `/api/v1/assessments` (create)

- **Export endpoint**: 10/hour per customer
  - `/api/v1/export`

**Locations**: Throughout `blueprints/api_customer.py`

### 10. Dependencies

Added to `requirements.txt`:

```
Flask-CORS==4.0.0
```

## Environment Variables

### Production Required

```bash
SECRET_KEY=<secure-random-key>
```

### Production Optional

```bash
FLASK_DEBUG=false                    # Default: false
CORS_ORIGINS=https://example.com     # Default: friktionskompasset.dk,frictioncompass.com
ENABLE_DEV_TOOLS=false               # Default: false
RATELIMIT_ENABLED=true               # Default: true
```

## Testing

### Verify Security Headers

```bash
curl -I https://friktionskompasset.dk/
```

Check for:
- Content-Security-Policy
- X-Frame-Options
- X-Content-Type-Options
- Strict-Transport-Security (in production)

### Verify Rate Limiting

```bash
# Test API rate limit
for i in {1..101}; do
  curl -H "X-API-Key: YOUR_KEY" https://friktionskompasset.dk/api/v1/assessments
done
```

Expected: 429 Too Many Requests after 100 requests

### Verify Dev Tools Protection

```bash
# Without ENABLE_DEV_TOOLS set
curl -X POST https://friktionskompasset.dk/admin/vary-testdata
```

Expected: Redirect with error message (when not in debug mode)

## Migration Notes

### Pre-Deployment

1. **Set SECRET_KEY** on Render:
   ```bash
   # Via Render API or Dashboard
   SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_hex(32))">
   ```

2. **Install new dependency**:
   ```bash
   pip install Flask-CORS==4.0.0
   ```
   (Render will do this automatically from requirements.txt)

### Post-Deployment Verification

1. Check security headers with `curl -I`
2. Verify API rate limiting works
3. Confirm dev tools are disabled
4. Test error handling (500 page doesn't show tracebacks)

## Rollback Plan

If issues occur:

1. Revert to previous commit
2. Or set environment variable:
   ```bash
   FLASK_DEBUG=true  # Temporarily for debugging
   ```

## Files Modified

1. `admin_app.py` - Main app security config
2. `profil_app.py` - Profil app security config
3. `blueprints/dev_tools.py` - Dev tools protection
4. `blueprints/api_customer.py` - API rate limiting
5. `extensions.py` - Rate limiter key function
6. `requirements.txt` - Added Flask-CORS
7. `templates/errors/500.html` - Error page (new file)

## Security Checklist

- [x] Security headers on all responses
- [x] Debug mode disabled by default
- [x] CORS configured for API only
- [x] Upload size limits enforced
- [x] Session cookies secured (HTTPS, HttpOnly, SameSite)
- [x] SECRET_KEY required in production
- [x] Error tracebacks hidden in production
- [x] Dev tools protected by environment variable
- [x] Per-customer API rate limiting
- [x] HSTS enabled in production

## References

- OWASP Security Headers: https://owasp.org/www-project-secure-headers/
- Flask Security Best Practices: https://flask.palletsprojects.com/en/3.0.x/security/
- Flask-Limiter Documentation: https://flask-limiter.readthedocs.io/
