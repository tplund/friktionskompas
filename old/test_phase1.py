"""
Test script for Fase 1: Database og grundlæggende backend
Tester assessment modes og respondent types funktionalitet
"""
from db_hierarchical import (
    create_unit, create_assessment_with_modes, generate_tokens_with_respondent_types,
    get_assessment_info, get_respondent_types, get_assessment_modes,
    get_all_leaf_units_under, get_db
)


def print_section(title):
    """Print section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def test_respondent_types_and_modes():
    """Test at respondent types og assessment modes er oprettet korrekt"""
    print_section("TEST 1: Respondent Types og Assessment Modes")

    # Test respondent types
    types = get_respondent_types()
    print(f"\n[INFO] Respondent Types ({len(types)}):")
    for t in types:
        print(f"  - {t['code']}: {t['name_da']}")

    assert len(types) == 3, "Skal være 3 respondent types"
    codes = [t['code'] for t in types]
    assert 'employee' in codes, "Mangler 'employee' type"
    assert 'leader_assess' in codes, "Mangler 'leader_assess' type"
    assert 'leader_self' in codes, "Mangler 'leader_self' type"

    # Test assessment modes
    modes = get_assessment_modes()
    print(f"\n[INFO] Assessment Modes ({len(modes)}):")
    for m in modes:
        print(f"  - {m['code']}: {m['name_da']}")

    assert len(modes) == 2, "Skal være 2 assessment modes"
    mode_codes = [m['code'] for m in modes]
    assert 'anonymous' in mode_codes, "Mangler 'anonymous' mode"
    assert 'identified' in mode_codes, "Mangler 'identified' mode"

    print("\n[OK] Respondent types og assessment modes oprettet korrekt!")


def test_anonymous_assessment_with_leader_perspective():
    """Test anonymous assessment med leder-perspektiv"""
    print_section("TEST 2: Anonymous Assessment med Leder-perspektiv")

    # Opret test organization
    print("\n[INFO] Opretter test organisation...")
    unit_id = create_unit(
        name="Test Afdeling",
        parent_id=None,
        leader_name="Test Leder",
        leader_email="leder@test.dk",
        employee_count=5,
        customer_id=None
    )
    print(f"  Unit ID: {unit_id}")

    # Opret anonymous assessment med leder-perspektiv
    print("\n[INFO] Opretter anonymous assessment med leder-perspektiv...")
    assessment_id = create_assessment_with_modes(
        target_unit_id=unit_id,
        name="Test Assessment - Anonymous",
        period="2025 Q1",
        mode='anonymous',
        include_leader_assessment=True,
        include_leader_self=True,
        min_responses=5
    )
    print(f"  Assessment ID: {assessment_id}")

    # Verificer assessment info
    assessment = get_assessment_info(assessment_id)
    print(f"\n[INFO] Assessment info:")
    print(f"  Mode: {assessment['mode']}")
    print(f"  Leader Assessment: {assessment['include_leader_assessment']}")
    print(f"  Leader Self: {assessment['include_leader_self']}")
    print(f"  Min Responses: {assessment['min_responses']}")

    assert assessment['mode'] == 'anonymous', "Mode skal være 'anonymous'"
    assert assessment['include_leader_assessment'] == 1, "Leader assessment skal være enabled"
    assert assessment['include_leader_self'] == 1, "Leader self skal være enabled"
    assert assessment['min_responses'] == 5, "Min responses skal være 5"

    # Generer tokens
    print("\n[INFO] Genererer tokens...")
    tokens = generate_tokens_with_respondent_types(assessment_id)

    print(f"\n[INFO] Tokens genereret for {len(tokens)} unit(s):")
    for uid, token_dict in tokens.items():
        print(f"\n  Unit: {uid}")
        for resp_type, token_list in token_dict.items():
            print(f"    {resp_type}: {len(token_list)} tokens")

    # Verificer at vi har de rigtige respondent types
    assert unit_id in tokens, f"Unit {unit_id} skal have tokens"
    unit_tokens = tokens[unit_id]

    assert 'employee' in unit_tokens, "Skal have employee tokens"
    assert len(unit_tokens['employee']) == 5, "Skal have 5 employee tokens"

    assert 'leader_assess' in unit_tokens, "Skal have leader_assess token"
    assert len(unit_tokens['leader_assess']) == 1, "Skal have 1 leader_assess token"

    assert 'leader_self' in unit_tokens, "Skal have leader_self token"
    assert len(unit_tokens['leader_self']) == 1, "Skal have 1 leader_self token"

    # Verificer i database
    with get_db() as conn:
        # Count tokens per respondent_type
        token_counts = conn.execute("""
            SELECT respondent_type, COUNT(*) as cnt
            FROM tokens
            WHERE assessment_id = ?
            GROUP BY respondent_type
        """, (assessment_id,)).fetchall()

        print(f"\n[INFO] Token counts i database:")
        for row in token_counts:
            print(f"  {row['respondent_type']}: {row['cnt']}")

    print("\n[OK] Anonymous assessment med leder-perspektiv testet succesfuldt!")


def test_identified_assessment():
    """Test identified assessment"""
    print_section("TEST 3: Identified Assessment")

    # Opret test organization
    print("\n[INFO] Opretter test organisation...")
    unit_id = create_unit(
        name="Test Team Identified",
        parent_id=None,
        leader_name="Team Leder",
        leader_email="teamleder@test.dk",
        employee_count=3,  # Ikke brugt i identified mode
        customer_id=None
    )
    print(f"  Unit ID: {unit_id}")

    # Opret identified assessment (UDEN leder-perspektiv)
    print("\n[INFO] Opretter identified assessment...")
    assessment_id = create_assessment_with_modes(
        target_unit_id=unit_id,
        name="Test Assessment - Identified",
        period="2025 Q1",
        mode='identified',
        include_leader_assessment=False,
        include_leader_self=False,
        min_responses=1  # Ikke relevant for identified
    )
    print(f"  Assessment ID: {assessment_id}")

    # Generer tokens med navne
    print("\n[INFO] Genererer tokens med navne...")
    respondent_names = {
        unit_id: ['Mette Hansen', 'Jens Nielsen', 'Anne Larsen']
    }

    tokens = generate_tokens_with_respondent_types(assessment_id, respondent_names)

    print(f"\n[INFO] Tokens genereret:")
    for uid, token_dict in tokens.items():
        print(f"\n  Unit: {uid}")
        for resp_type, token_list in token_dict.items():
            print(f"    {resp_type}:")
            for token, name in token_list:
                print(f"      - {name}: {token[:8]}...")

    # Verificer at navne er gemt i database
    with get_db() as conn:
        token_info = conn.execute("""
            SELECT token, respondent_type, respondent_name
            FROM tokens
            WHERE assessment_id = ?
            ORDER BY respondent_name
        """, (assessment_id,)).fetchall()

        print(f"\n[INFO] Tokens i database:")
        for row in token_info:
            print(f"  {row['respondent_type']}: {row['respondent_name']} ({row['token'][:8]}...)")

        # Verificer at alle navne er gemt
        names = [row['respondent_name'] for row in token_info]
        assert 'Mette Hansen' in names, "Mangler Mette Hansen"
        assert 'Jens Nielsen' in names, "Mangler Jens Nielsen"
        assert 'Anne Larsen' in names, "Mangler Anne Larsen"

    print("\n[OK] Identified assessment testet succesfuldt!")


def test_hybrid_assessment():
    """Test identified assessment MED leder-perspektiv (hybrid)"""
    print_section("TEST 4: Hybrid Assessment (Identified + Leader Perspective)")

    # Opret test organization
    print("\n[INFO] Opretter test organisation...")
    unit_id = create_unit(
        name="Test Team Hybrid",
        parent_id=None,
        leader_name="Hybrid Leder",
        leader_email="hybrid@test.dk",
        employee_count=0,
        customer_id=None
    )
    print(f"  Unit ID: {unit_id}")

    # Opret identified assessment MED leder-perspektiv
    print("\n[INFO] Opretter hybrid assessment...")
    assessment_id = create_assessment_with_modes(
        target_unit_id=unit_id,
        name="Test Assessment - Hybrid",
        period="2025 Q1",
        mode='identified',
        include_leader_assessment=True,  # Leder skal vurdere teamet
        include_leader_self=True,       # Leder skal svare om sig selv
        min_responses=1
    )
    print(f"  Assessment ID: {assessment_id}")

    # Generer tokens
    print("\n[INFO] Genererer tokens...")
    respondent_names = {
        unit_id: ['Person A', 'Person B']
    }

    tokens = generate_tokens_with_respondent_types(assessment_id, respondent_names)

    print(f"\n[INFO] Tokens genereret:")
    for uid, token_dict in tokens.items():
        print(f"\n  Unit: {uid}")
        for resp_type, token_list in token_dict.items():
            if resp_type == 'employee':
                print(f"    {resp_type}:")
                for token, name in token_list:
                    print(f"      - {name}: {token[:8]}...")
            else:
                print(f"    {resp_type}: {len(token_list)} tokens")

    # Verificer at vi har både employee (identified) og leader tokens
    unit_tokens = tokens[unit_id]
    assert 'employee' in unit_tokens, "Skal have employee tokens"
    assert 'leader_assess' in unit_tokens, "Skal have leader_assess token"
    assert 'leader_self' in unit_tokens, "Skal have leader_self token"

    # Verificer i database
    with get_db() as conn:
        token_info = conn.execute("""
            SELECT respondent_type, COUNT(*) as cnt
            FROM tokens
            WHERE assessment_id = ?
            GROUP BY respondent_type
        """, (assessment_id,)).fetchall()

        print(f"\n[INFO] Token distribution:")
        for row in token_info:
            print(f"  {row['respondent_type']}: {row['cnt']}")

    print("\n[OK] Hybrid assessment testet succesfuldt!")


def cleanup_test_data():
    """Slet testdata"""
    print_section("CLEANUP: Sletter testdata")

    with get_db() as conn:
        # Slet alle test assessments
        deleted_assessments = conn.execute("""
            DELETE FROM assessments WHERE name LIKE 'Test Assessment%'
        """)

        # Slet alle test units (cascade vil slette tokens, responses etc.)
        deleted_units = conn.execute("""
            DELETE FROM organizational_units WHERE name LIKE 'Test%'
        """)

        print(f"[INFO] Slettet test assessments og units")

    print("[OK] Cleanup færdig!")


def run_all_tests():
    """Kør alle tests"""
    print("\n" + "="*60)
    print("  FASE 1 TESTS - CAMPAIGN MODES OG RESPONDENT TYPES")
    print("="*60)

    try:
        test_respondent_types_and_modes()
        test_anonymous_assessment_with_leader_perspective()
        test_identified_assessment()
        test_hybrid_assessment()

        print("\n" + "="*60)
        print("  ALLE TESTS BESTÅET!")
        print("="*60)

        # Cleanup
        cleanup = input("\nVil du slette testdata? (y/n): ")
        if cleanup.lower() == 'y':
            cleanup_test_data()

    except AssertionError as e:
        print(f"\n[ERROR] Test fejlede: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[ERROR] Uventet fejl: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
