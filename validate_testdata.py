"""
Validerer testdata for Friktionskompasset.

Tjekker:
1. Fuldstaendighed - alle noedvendige data er til stede
2. Realisme - scores er i gyldigt interval, fordelinger er realistiske
3. Referentiel integritet - alle foreign keys er gyldige
4. Kunde-specifikke assertions (Esbjerg kanonisk, Herning demo)

Brug: python validate_testdata.py
"""

import sqlite3
import os
from collections import defaultdict

# Database path
DB_PATH = os.environ.get('DATABASE_PATH', '/var/data/friktionskompas_v3.db')
if not os.path.exists(DB_PATH):
    DB_PATH = 'friktionskompas_v3.db'

# Test kunde IDs
HERNING_ID = 'cust-0nlG8ldxSYU'
ESBJERG_ID = 'cust-SHKIi10cOe8'

# Gyldige vaerdier
VALID_RESPONDENT_TYPES = {'employee', 'leader_assess', 'leader_self'}
# Note: BESVAER er dansk for "difficulty" - database har dansk med ae/oe
VALID_FIELDS = {'MENING', 'TRYGHED', 'KAN', 'BESVÆR'}


class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []

    def add_error(self, msg):
        self.errors.append(f"[X] ERROR: {msg}")

    def add_warning(self, msg):
        self.warnings.append(f"[!] WARNING: {msg}")

    def add_info(self, msg):
        self.info.append(f"[i] {msg}")

    def is_valid(self):
        return len(self.errors) == 0

    def print_summary(self):
        print("\n" + "=" * 60)
        print("VALIDERINGS-RESULTAT")
        print("=" * 60)

        if self.info:
            for msg in self.info:
                print(msg)

        if self.warnings:
            print("\n--- ADVARSLER ---")
            for msg in self.warnings:
                print(msg)

        if self.errors:
            print("\n--- FEJL ---")
            for msg in self.errors:
                print(msg)

        print("\n" + "-" * 60)
        if self.is_valid():
            print("[OK] VALIDERING BESTAAET")
        else:
            print(f"[FAIL] VALIDERING FEJLET ({len(self.errors)} fejl)")
        print("-" * 60)


def validate_referential_integrity(conn, result):
    """Tjek at alle foreign keys er gyldige"""
    print("\n1. REFERENTIEL INTEGRITET")
    print("-" * 40)

    # Responses -> Assessments
    orphan_responses = conn.execute("""
        SELECT COUNT(*) FROM responses r
        LEFT JOIN assessments a ON r.assessment_id = a.id
        WHERE a.id IS NULL
    """).fetchone()[0]

    if orphan_responses > 0:
        result.add_error(f"{orphan_responses} responses refererer til ikke-eksisterende assessments")
    else:
        print(f"  [OK] Alle responses har gyldig assessment_id")

    # Responses -> Questions
    orphan_questions = conn.execute("""
        SELECT COUNT(*) FROM responses r
        LEFT JOIN questions q ON r.question_id = q.id
        WHERE q.id IS NULL
    """).fetchone()[0]

    if orphan_questions > 0:
        result.add_error(f"{orphan_questions} responses refererer til ikke-eksisterende spoergsmaal")
    else:
        print(f"  [OK] Alle responses har gyldig question_id")

    # Assessments -> Units
    orphan_assessments = conn.execute("""
        SELECT COUNT(*) FROM assessments a
        LEFT JOIN organizational_units ou ON a.target_unit_id = ou.id
        WHERE ou.id IS NULL
    """).fetchone()[0]

    if orphan_assessments > 0:
        result.add_error(f"{orphan_assessments} assessments refererer til ikke-eksisterende units")
    else:
        print(f"  [OK] Alle assessments har gyldig target_unit_id")

    # Units -> Customers
    orphan_units = conn.execute("""
        SELECT COUNT(*) FROM organizational_units ou
        LEFT JOIN customers c ON ou.customer_id = c.id
        WHERE c.id IS NULL
    """).fetchone()[0]

    if orphan_units > 0:
        result.add_error(f"{orphan_units} units refererer til ikke-eksisterende customers")
    else:
        print(f"  [OK] Alle units har gyldig customer_id")


def validate_score_ranges(conn, result):
    """Tjek at alle scores er i gyldigt interval (1-7)"""
    print("\n2. SCORE INTERVALLER")
    print("-" * 40)

    invalid_scores = conn.execute("""
        SELECT COUNT(*), MIN(score), MAX(score)
        FROM responses
        WHERE score < 1 OR score > 7
    """).fetchone()

    if invalid_scores[0] > 0:
        result.add_error(f"{invalid_scores[0]} responses har ugyldig score (min={invalid_scores[1]}, max={invalid_scores[2]})")
    else:
        # Vis score-fordeling
        stats = conn.execute("""
            SELECT MIN(score), MAX(score), AVG(score), COUNT(*)
            FROM responses
        """).fetchone()
        print(f"  [OK] Alle scores i interval 1-7")
        print(f"    Min: {stats[0]}, Max: {stats[1]}, Gns: {stats[2]:.2f}, Total: {stats[3]}")


def validate_respondent_types(conn, result):
    """Tjek at alle respondent_type vaerdier er gyldige"""
    print("\n3. RESPONDENT TYPES")
    print("-" * 40)

    types = conn.execute("""
        SELECT respondent_type, COUNT(*) as cnt
        FROM responses
        GROUP BY respondent_type
    """).fetchall()

    print("  Fordeling:")
    for t, cnt in types:
        valid = "[OK]" if t in VALID_RESPONDENT_TYPES else "[X]"
        print(f"    {valid} {t}: {cnt:,}")
        if t not in VALID_RESPONDENT_TYPES:
            result.add_error(f"Ugyldig respondent_type: '{t}' ({cnt} responses)")


def validate_question_fields(conn, result):
    """Tjek at alle spoergsmaal har gyldigt field"""
    print("\n4. SPOERGSMAALS-FELTER")
    print("-" * 40)

    fields = conn.execute("""
        SELECT field, COUNT(*) as cnt
        FROM questions
        WHERE is_default = 1
        GROUP BY field
    """).fetchall()

    print("  Aktive spoergsmaal per felt:")
    for f, cnt in fields:
        valid = "[OK]" if f in VALID_FIELDS else "[?]"
        print(f"    {valid} {f}: {cnt}")
        if f and f not in VALID_FIELDS:
            result.add_warning(f"Uventet felt: '{f}'")


def validate_assessment_completeness(conn, result):
    """Tjek at B2B assessments har alle respondent-typer"""
    print("\n5. ASSESSMENT FULDSTAENDIGHED")
    print("-" * 40)

    # Find B2B assessments (dem med include_leader_assessment=1)
    assessments = conn.execute("""
        SELECT a.id, a.name, ou.name as unit_name
        FROM assessments a
        JOIN organizational_units ou ON a.target_unit_id = ou.id
        WHERE a.include_leader_assessment = 1
    """).fetchall()

    missing_types = []
    for a_id, a_name, unit_name in assessments:
        # Tjek respondent types for denne assessment
        types = conn.execute("""
            SELECT DISTINCT respondent_type
            FROM responses
            WHERE assessment_id = ?
        """, [a_id]).fetchall()
        types_set = {t[0] for t in types}

        # B2B skal have alle tre typer
        expected = {'employee', 'leader_assess', 'leader_self'}
        missing = expected - types_set

        if missing:
            missing_types.append((a_name, missing))

    if missing_types:
        print(f"  [!] {len(missing_types)} B2B assessments mangler respondent-typer:")
        for name, missing in missing_types[:5]:  # Vis max 5
            result.add_warning(f"{name}: mangler {missing}")
    else:
        print(f"  [OK] Alle {len(assessments)} B2B assessments har alle respondent-typer")


def validate_herning_data(conn, result):
    """Specifik validering af Herning demo-data"""
    print("\n6. HERNING KOMMUNE (Demo)")
    print("-" * 40)

    # Antal enheder
    units = conn.execute("""
        SELECT COUNT(*) FROM organizational_units
        WHERE customer_id = ?
    """, [HERNING_ID]).fetchone()[0]

    # Antal assessments
    assessments = conn.execute("""
        SELECT COUNT(*) FROM assessments a
        JOIN organizational_units ou ON a.target_unit_id = ou.id
        WHERE ou.customer_id = ?
    """, [HERNING_ID]).fetchone()[0]

    # Antal responses
    responses = conn.execute("""
        SELECT COUNT(*) FROM responses r
        JOIN assessments a ON r.assessment_id = a.id
        JOIN organizational_units ou ON a.target_unit_id = ou.id
        WHERE ou.customer_id = ?
    """, [HERNING_ID]).fetchone()[0]

    print(f"  Units: {units}")
    print(f"  Assessments: {assessments}")
    print(f"  Responses: {responses:,}")

    if units < 5:
        result.add_warning(f"Herning har kun {units} units (forventet mindst 5)")
    if assessments < 10:
        result.add_warning(f"Herning har kun {assessments} assessments (forventet mindst 10)")

    # Tjek trend-data (Q1-Q4)
    trend_units = conn.execute("""
        SELECT ou.name, COUNT(DISTINCT a.period) as periods
        FROM assessments a
        JOIN organizational_units ou ON a.target_unit_id = ou.id
        WHERE ou.customer_id = ?
        AND a.period LIKE 'Q% 2025'
        GROUP BY ou.name
        HAVING periods >= 4
    """, [HERNING_ID]).fetchall()

    if trend_units:
        print(f"  Trend-data (4 kvartaler): {len(trend_units)} units")
        for name, periods in trend_units[:3]:
            print(f"    - {name}: {periods} perioder")
    else:
        result.add_warning("Ingen units har komplet trend-data (4 kvartaler)")


def validate_esbjerg_data(conn, result):
    """Specifik validering af Esbjerg kanonisk testdata"""
    print("\n7. ESBJERG KOMMUNE (Kanonisk)")
    print("-" * 40)

    # Tjek at Esbjerg eksisterer
    customer = conn.execute("""
        SELECT name FROM customers WHERE id = ?
    """, [ESBJERG_ID]).fetchone()

    if not customer:
        result.add_error(f"Esbjerg Kommune ikke fundet (ID: {ESBJERG_ID})")
        return

    # Antal enheder
    units = conn.execute("""
        SELECT name FROM organizational_units
        WHERE customer_id = ?
        ORDER BY name
    """, [ESBJERG_ID]).fetchall()

    print(f"  Units: {len(units)}")
    for u in units[:8]:
        print(f"    - {u[0]}")

    # Kanoniske test-units der SKAL eksistere
    required_units = ['Birkebo', 'Skovbrynet', 'Solhjem', 'Strandparken']
    unit_names = {u[0] for u in units}

    for req in required_units:
        if req not in unit_names:
            result.add_error(f"Kanonisk test-unit '{req}' mangler i Esbjerg")
        else:
            print(f"  [OK] {req} findes")


def validate_score_distributions(conn, result):
    """Tjek at score-fordelinger er realistiske (ikke alle samme vaerdi)"""
    print("\n8. SCORE FORDELINGER")
    print("-" * 40)

    # Find assessments hvor alle scores er identiske
    suspicious = conn.execute("""
        SELECT a.id, a.name, MIN(r.score) as min_s, MAX(r.score) as max_s
        FROM assessments a
        JOIN responses r ON a.id = r.assessment_id
        GROUP BY a.id
        HAVING min_s = max_s
    """).fetchall()

    if suspicious:
        for a_id, name, min_s, max_s in suspicious:
            result.add_warning(f"Assessment '{name}' har identiske scores (alle = {min_s})")
    else:
        print(f"  [OK] Ingen assessments med identiske scores")

    # Tjek score-variance per assessment
    low_variance = conn.execute("""
        SELECT a.id, a.name,
               AVG(r.score) as avg_s,
               (SUM((r.score - sub.avg_score) * (r.score - sub.avg_score)) / COUNT(*)) as variance
        FROM assessments a
        JOIN responses r ON a.id = r.assessment_id
        JOIN (
            SELECT assessment_id, AVG(score) as avg_score
            FROM responses
            GROUP BY assessment_id
        ) sub ON sub.assessment_id = a.id
        GROUP BY a.id
        HAVING variance < 0.5
    """).fetchall()

    if low_variance:
        print(f"  [!] {len(low_variance)} assessments har meget lav score-variance")
        for a_id, name, avg, var in low_variance[:3]:
            result.add_info(f"{name}: gns={avg:.2f}, varians={var:.3f}")
    else:
        print(f"  [OK] Alle assessments har realistisk score-variance")


def main():
    print("=" * 60)
    print("TESTDATA VALIDERING - FRIKTIONSKOMPASSET")
    print("=" * 60)
    print(f"Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[X] Database ikke fundet: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    result = ValidationResult()

    try:
        # Koer alle valideringer
        validate_referential_integrity(conn, result)
        validate_score_ranges(conn, result)
        validate_respondent_types(conn, result)
        validate_question_fields(conn, result)
        validate_assessment_completeness(conn, result)
        validate_herning_data(conn, result)
        validate_esbjerg_data(conn, result)
        validate_score_distributions(conn, result)

        # Vis resultat
        result.print_summary()

    finally:
        conn.close()

    return result.is_valid()


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
