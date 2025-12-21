# Deployment Checklist - Security Fixes

## Pre-Deployment

### 1. Generate SECRET_KEY (if not already set)

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and save it securely.

### 2. Set Environment Variables on Render

Via Render Dashboard or API:

```bash
# Required
SECRET_KEY=<paste-generated-key-here>

# Optional (defaults shown)
FLASK_DEBUG=false
CORS_ORIGINS=https://friktionskompasset.dk,https://frictioncompass.com
ENABLE_DEV_TOOLS=false
RATELIMIT_ENABLED=true
```

### 3. Verify Dependencies

Check that `requirements.txt` includes:

```
Flask-CORS==4.0.0
```

## Deployment

### Push to GitHub

```bash
git add .
git commit -m "Security fixes: headers, CORS, rate limiting, error handling"
git push origin main
```

Render will automatically detect the push and deploy.

### Monitor Deployment

1. Go to: https://dashboard.render.com
2. Watch the deployment logs
3. Wait for "Deploy live" status

## Post-Deployment Verification

### 1. Quick Smoke Test

```bash
# Should return 200 OK
curl -I https://friktionskompasset.dk/

# Check for security headers in output
```

Expected headers:
- Content-Security-Policy
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- Strict-Transport-Security (HTTPS only)

### 2. Run Verification Script

```bash
python verify_security.py https://friktionskompasset.dk
```

Optional with API key test:
```bash
python verify_security.py https://friktionskompasset.dk --api-key YOUR_API_KEY
```

### 3. Manual Tests

#### Test 1: Security Headers
```bash
curl -I https://friktionskompasset.dk/ | grep -E "(CSP|X-Frame|X-Content|HSTS)"
```

#### Test 2: Dev Tools Protected
```bash
# Should redirect or return 403 (not execute)
curl -X POST https://friktionskompasset.dk/admin/vary-testdata
```

#### Test 3: Error Handling
Trigger a 500 error and verify:
- No Python traceback visible
- Generic error page shown instead

#### Test 4: CORS
```bash
curl -X OPTIONS https://friktionskompasset.dk/api/v1/assessments \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: GET" \
  -i
```

Look for `Access-Control-Allow-Origin` header.

#### Test 5: Rate Limiting
```bash
# Make 101 requests quickly
for i in {1..101}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "X-API-Key: YOUR_KEY" \
    https://friktionskompasset.dk/api/v1/assessments
done | tail -5
```

Last few should show `429` (Too Many Requests).

## Rollback Plan

If critical issues occur:

### Option 1: Revert Deployment
```bash
git revert HEAD
git push origin main
```

### Option 2: Emergency Debug Mode
```bash
# On Render, set temporarily
FLASK_DEBUG=true
```

**WARNING**: Only use debug mode for troubleshooting, revert immediately after.

## Common Issues

### Issue: App won't start - "SECRET_KEY must be set"
**Solution**: Set `SECRET_KEY` environment variable on Render

### Issue: CORS errors in browser console
**Solution**: Add allowed origin to `CORS_ORIGINS` environment variable

### Issue: Rate limiting too aggressive
**Solution**: Adjust limits in `blueprints/api_customer.py` or disable with `RATELIMIT_ENABLED=false`

### Issue: Dev tools needed in production
**Solution**: Temporarily set `ENABLE_DEV_TOOLS=true` (remember to disable after use)

## Monitoring

### Check Logs

```bash
# Via Render dashboard
# Or via API
curl -H "Authorization: Bearer YOUR_RENDER_TOKEN" \
  https://api.render.com/v1/services/srv-d4q8t8k9c44c73b8ut60/logs
```

### Watch for:
- 429 responses (rate limiting working)
- 500 errors (investigate if frequent)
- Security header presence in responses

## Success Criteria

- [ ] App starts successfully
- [ ] Security headers present on all responses
- [ ] CORS working for API endpoints
- [ ] Rate limiting functioning (429 after threshold)
- [ ] Dev tools protected (redirect/error when accessed)
- [ ] 500 errors don't show tracebacks
- [ ] Session cookies have Secure, HttpOnly, SameSite flags
- [ ] No console errors on frontend

## Files Changed

- `admin_app.py` - Security config, headers, error handling
- `profil_app.py` - Security config
- `blueprints/dev_tools.py` - Environment protection
- `blueprints/api_customer.py` - Rate limiting
- `extensions.py` - Rate limit key function
- `requirements.txt` - Flask-CORS added
- `templates/errors/500.html` - Generic error page

## Documentation

- `SECURITY_FIXES_2025.md` - Detailed documentation of all changes
- `verify_security.py` - Automated verification script
- This checklist

## Support

If issues persist:
1. Check Render logs
2. Review `SECURITY_FIXES_2025.md` for configuration details
3. Test locally with `FLASK_DEBUG=true`
4. Verify all environment variables are set correctly
