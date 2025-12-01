#!/usr/bin/env python3
"""
Automatisk systemtest for Friktionskompasset
Kører alle kritiske tests og rapporterer status
"""
import sys
import os

# Tilføj projekt-root til path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)

def print_result(name, success, details=""):
    status = "[PASS]" if success else "[FAIL]"
    print(f"  {status}  {name}")
    if details:
        print(f"           {details}")

def test_database_connection():
    """Test database forbindelse"""
    try:
        from db_hierarchical import get_db, init_db
        init_db()
        with get_db() as conn:
            result = conn.execute("SELECT COUNT(*) FROM questions").fetchone()
            count = result[0]
        return True, f"{count} spørgsmål i databasen"
    except Exception as e:
        return False, str(e)

def test_profil_database():
    """Test profil database"""
    try:
        from db_profil import get_db, init_profil_tables
        init_profil_tables()
        with get_db() as conn:
            result = conn.execute("SELECT COUNT(*) FROM profil_questions").fetchone()
            count = result[0]
        return True, f"{count} profil-spørgsmål"
    except Exception as e:
        return False, str(e)

def test_multitenant():
    """Test multi-tenant database"""
    try:
        from db_multitenant import init_multitenant_db, get_db
        init_multitenant_db()
        with get_db() as conn:
            result = conn.execute("SELECT COUNT(*) FROM users").fetchone()
            count = result[0]
        return True, f"{count} brugere"
    except Exception as e:
        return False, str(e)

def test_flask_app():
    """Test at Flask app kan importeres"""
    try:
        from admin_app import app
        return True, f"App loaded: {app.name}"
    except Exception as e:
        return False, str(e)

def test_mailjet_config():
    """Test Mailjet konfiguration"""
    try:
        from mailjet_integration import MAILJET_API_KEY, MAILJET_API_SECRET, FROM_EMAIL
        has_key = bool(MAILJET_API_KEY and len(MAILJET_API_KEY) > 5)
        has_secret = bool(MAILJET_API_SECRET and len(MAILJET_API_SECRET) > 5)
        if has_key and has_secret:
            return True, f"FROM_EMAIL: {FROM_EMAIL}"
        elif has_key:
            return False, "API Secret mangler"
        else:
            return False, "API Key mangler"
    except Exception as e:
        return False, str(e)

def test_mailjet_connection():
    """Test Mailjet API forbindelse"""
    try:
        from mailjet_integration import test_mailjet_connection
        success = test_mailjet_connection()
        return success, "API forbindelse OK" if success else "Kunne ikke forbinde"
    except Exception as e:
        return False, str(e)

def test_email_logging():
    """Test email logging tabel"""
    try:
        from mailjet_integration import ensure_email_logs_table, get_email_stats
        ensure_email_logs_table()
        stats = get_email_stats()
        total = stats.get('total', 0)
        return True, f"{total} emails logget"
    except Exception as e:
        return False, str(e)

def test_screening():
    """Test screening modul"""
    try:
        from screening_profil import SCREENINGS
        return True, f"{len(SCREENINGS)} screenings defineret"
    except Exception as e:
        return False, str(e)

def test_analysis():
    """Test analyse modul"""
    try:
        from analysis import get_detailed_breakdown, check_anonymity_threshold
        # Test at funktioner kan importeres
        return True, "Analyse funktioner OK"
    except Exception as e:
        return False, str(e)

def test_templates():
    """Test at templates findes"""
    template_dirs = [
        'templates/admin',
        'templates/profil',
    ]
    missing = []
    for d in template_dirs:
        if not os.path.exists(d):
            missing.append(d)

    if missing:
        return False, f"Mangler: {', '.join(missing)}"

    # Tæl templates
    count = 0
    for d in template_dirs:
        count += len([f for f in os.listdir(d) if f.endswith('.html')])
    return True, f"{count} templates fundet"

def test_static_files():
    """Test at static filer findes"""
    if not os.path.exists('static'):
        return False, "static/ mappe mangler"

    files = os.listdir('static')
    return True, f"{len(files)} static filer"

def test_render_config():
    """Test Render konfiguration"""
    issues = []

    if not os.path.exists('render.yaml'):
        issues.append("render.yaml mangler")

    if not os.path.exists('requirements.txt'):
        issues.append("requirements.txt mangler")

    if not os.path.exists('Procfile'):
        issues.append("Procfile mangler")

    if issues:
        return False, ", ".join(issues)

    # Tjek requirements
    with open('requirements.txt') as f:
        reqs = f.read()

    required = ['Flask', 'gunicorn', 'bcrypt', 'mailjet']
    missing = [r for r in required if r.lower() not in reqs.lower()]

    if missing:
        return False, f"Mangler i requirements: {', '.join(missing)}"

    return True, "Alle deploy filer OK"

def test_persistent_disk_config():
    """Test at koden understøtter persistent disk"""
    try:
        from db_hierarchical import DB_PATH, RENDER_DISK_PATH
        return True, f"Disk path: {RENDER_DISK_PATH}, DB: {DB_PATH}"
    except ImportError:
        return False, "RENDER_DISK_PATH ikke defineret"
    except Exception as e:
        return False, str(e)

def run_all_tests():
    """Kør alle tests"""
    print_header("FRIKTIONSKOMPASSET - SYSTEMTEST")
    print(f"  Kører fra: {os.getcwd()}")

    tests = [
        ("Database forbindelse", test_database_connection),
        ("Profil database", test_profil_database),
        ("Multi-tenant", test_multitenant),
        ("Flask app", test_flask_app),
        ("Templates", test_templates),
        ("Static filer", test_static_files),
        ("Render config", test_render_config),
        ("Persistent disk config", test_persistent_disk_config),
        ("Mailjet config", test_mailjet_config),
        ("Email logging", test_email_logging),
        ("Screening modul", test_screening),
        ("Analyse modul", test_analysis),
    ]

    results = []

    print_header("KØRER TESTS")

    for name, test_func in tests:
        try:
            success, details = test_func()
        except Exception as e:
            success, details = False, f"Exception: {e}"

        results.append((name, success, details))
        print_result(name, success, details)

    # Opsummering
    passed = sum(1 for _, s, _ in results if s)
    failed = sum(1 for _, s, _ in results if not s)

    print_header("OPSUMMERING")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total:  {len(results)}")

    if failed == 0:
        print("\n  ALLE TESTS BESTAAET!")
    else:
        print("\n  NOGLE TESTS FEJLEDE")
        print("\n  Fejlede tests:")
        for name, success, details in results:
            if not success:
                print(f"    - {name}: {details}")

    print()
    return failed == 0

def run_live_test(base_url="https://friktionskompas.onrender.com"):
    """Test live deployment"""
    import urllib.request
    import urllib.error

    print_header(f"LIVE TEST: {base_url}")

    endpoints = [
        ("/", "Forside redirect"),
        ("/login", "Login side"),
        ("/webhook/mailjet", "Webhook (405 expected)"),
        ("/881785f5a46238616dba5c7ba38aa2c6.txt", "Mailjet verification"),
    ]

    for path, name in endpoints:
        url = base_url + path
        try:
            req = urllib.request.Request(url, method='GET')
            response = urllib.request.urlopen(req, timeout=10)
            code = response.getcode()
            print_result(name, True, f"HTTP {code}")
        except urllib.error.HTTPError as e:
            # 405 er forventet for webhook, 302 for redirect
            if e.code in [302, 405]:
                print_result(name, True, f"HTTP {e.code} (expected)")
            else:
                print_result(name, False, f"HTTP {e.code}")
        except Exception as e:
            print_result(name, False, str(e))

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Kør lokale tests
    all_passed = run_all_tests()

    # Kør live tests hvis --live flag
    if "--live" in sys.argv:
        run_live_test()

    sys.exit(0 if all_passed else 1)
