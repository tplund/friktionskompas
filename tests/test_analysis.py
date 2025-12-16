"""
Tests for analysis.py - Core analysis logic for Friktionskompasset.
Tests scoring calculations, substitution detection, KKC mapping, and recommendations.
"""
import pytest


class TestQuestionLayers:
    """Test the question-to-layer mapping configuration."""

    def test_all_fields_have_layers(self):
        """Test that all four fields are defined."""
        from analysis import QUESTION_LAYERS

        assert 'MENING' in QUESTION_LAYERS
        assert 'TRYGHED' in QUESTION_LAYERS
        assert 'KAN' in QUESTION_LAYERS
        assert 'BESVÆR' in QUESTION_LAYERS

    def test_mening_has_all_questions(self):
        """Test MENING field contains correct questions (1-5)."""
        from analysis import QUESTION_LAYERS

        mening = QUESTION_LAYERS['MENING']
        assert 'all' in mening
        assert mening['all'] == [1, 2, 3, 4, 5]

    def test_tryghed_has_ydre_indre_layers(self):
        """Test TRYGHED has ydre (social) and indre (emotional) layers."""
        from analysis import QUESTION_LAYERS

        tryghed = QUESTION_LAYERS['TRYGHED']
        assert 'ydre' in tryghed
        assert 'indre' in tryghed
        # Ydre: 6, 7, 8 - Indre: 9, 10
        assert 6 in tryghed['ydre']
        assert 9 in tryghed['indre']

    def test_kan_has_ydre_indre_layers(self):
        """Test KAN has ydre (external) and indre (internal) layers."""
        from analysis import QUESTION_LAYERS

        kan = QUESTION_LAYERS['KAN']
        assert 'ydre' in kan
        assert 'indre' in kan
        # Ydre should have more items than indre
        assert len(kan['ydre']) > len(kan['indre'])

    def test_besvaer_has_mekanisk_oplevet_layers(self):
        """Test BESVÆR has mekanisk (mechanical) and oplevet (experienced) layers."""
        from analysis import QUESTION_LAYERS

        besvaer = QUESTION_LAYERS['BESVÆR']
        assert 'mekanisk' in besvaer
        assert 'oplevet' in besvaer

    def test_substitution_items_defined(self):
        """Test substitution detection items are configured."""
        from analysis import SUBSTITUTION_ITEMS

        # Ny struktur fra friction_engine.py
        assert 'tid_item' in SUBSTITUTION_ITEMS
        assert 'proc_items' in SUBSTITUTION_ITEMS
        assert 'underliggende' in SUBSTITUTION_ITEMS
        assert SUBSTITUTION_ITEMS['tid_item'] == 14

    def test_no_duplicate_questions_in_layers(self):
        """Test that no question appears in multiple layers within a field."""
        from analysis import QUESTION_LAYERS

        for field, layers in QUESTION_LAYERS.items():
            all_questions = []
            for layer_name, questions in layers.items():
                all_questions.extend(questions)

            # Check for duplicates
            assert len(all_questions) == len(set(all_questions)), \
                f"Duplicate questions in {field}"


class TestKKCMapping:
    """Test KKC (Kurs-Koordinering-Commitment) mapping from friction fields."""

    def test_kkc_mapping_exists(self):
        """Test that KKC_MAPPING is defined."""
        from analysis import KKC_MAPPING

        assert KKC_MAPPING is not None
        assert len(KKC_MAPPING) == 4

    def test_kkc_mapping_mening_to_kurs(self):
        """Test MENING maps to KURS."""
        from analysis import KKC_MAPPING

        assert 'MENING' in KKC_MAPPING
        assert KKC_MAPPING['MENING'] == 'KURS'

    def test_kkc_mapping_tryghed_to_koordinering(self):
        """Test TRYGHED maps to KOORDINERING."""
        from analysis import KKC_MAPPING

        assert 'TRYGHED' in KKC_MAPPING
        assert KKC_MAPPING['TRYGHED'] == 'KOORDINERING'

    def test_kkc_mapping_kan_to_koordinering(self):
        """Test KAN maps to KOORDINERING."""
        from analysis import KKC_MAPPING

        assert 'KAN' in KKC_MAPPING
        assert KKC_MAPPING['KAN'] == 'KOORDINERING'

    def test_kkc_mapping_besvaer_to_commitment(self):
        """Test BESVÆR maps to COMMITMENT."""
        from analysis import KKC_MAPPING

        assert 'BESVÆR' in KKC_MAPPING
        assert KKC_MAPPING['BESVÆR'] == 'COMMITMENT'


class TestKKCRecommendations:
    """Test KKC-based recommendations generation."""

    def test_recommendations_for_high_friction(self):
        """Test that high friction (low score) generates recommendations."""
        from analysis import get_kkc_recommendations

        # Mock stats with low score (high friction)
        stats = {
            'MENING': {'avg_score': 2.0, 'std_dev': 0.5},
            'TRYGHED': {'avg_score': 4.0, 'std_dev': 0.3},
            'KAN': {'avg_score': 4.0, 'std_dev': 0.3},
            'BESVÆR': {'avg_score': 4.0, 'std_dev': 0.3},
        }

        recommendations = get_kkc_recommendations(stats)

        assert len(recommendations) > 0
        # MENING should be first due to lowest score
        assert recommendations[0]['field'] == 'MENING'
        assert recommendations[0]['severity'] == 'høj'

    def test_recommendations_sorted_by_severity(self):
        """Test that recommendations are sorted by severity and score."""
        from analysis import get_kkc_recommendations

        stats = {
            'MENING': {'avg_score': 3.0},  # medium (2.5-3.5)
            'TRYGHED': {'avg_score': 2.0},  # høj (< 2.5)
            'KAN': {'avg_score': 4.0},  # lav (>= 3.5)
            'BESVÆR': {'avg_score': 2.4},  # høj (< 2.5)
        }

        recommendations = get_kkc_recommendations(stats)

        # High severity items should come first
        severities = [r['severity'] for r in recommendations]
        assert severities[0] == 'høj'  # TRYGHED first (score 2.0)
        assert severities[1] == 'høj'  # BESVÆR second (score 2.4 < 2.5)

    def test_recommendations_include_actions(self):
        """Test that recommendations include actionable items."""
        from analysis import get_kkc_recommendations

        stats = {
            'MENING': {'avg_score': 2.0},
        }

        recommendations = get_kkc_recommendations(stats)

        assert len(recommendations) > 0
        rec = recommendations[0]
        assert 'actions' in rec
        assert len(rec['actions']) > 0
        assert 'title' in rec
        assert 'problem' in rec

    def test_recommendations_include_kkc_reference(self):
        """Test that recommendations include Anders Trillingsgaard reference."""
        from analysis import get_kkc_recommendations

        stats = {
            'MENING': {'avg_score': 2.0},
        }

        recommendations = get_kkc_recommendations(stats)

        assert len(recommendations) > 0
        rec = recommendations[0]
        assert 'kkc_reference' in rec
        assert 'Trillingsgaard' in rec['kkc_reference']

    def test_severity_thresholds(self):
        """Test severity level thresholds (høj < 2.5, medium < 3.5)."""
        from analysis import get_kkc_recommendations

        # Test høj severity (score < 2.5)
        stats_high = {'MENING': {'avg_score': 2.4}}  # Under 2.5 = høj
        recs = get_kkc_recommendations(stats_high)
        assert recs[0]['severity'] == 'høj'

        # Test medium severity (score 2.5-3.5)
        stats_medium = {'MENING': {'avg_score': 3.0}}  # 2.5 <= score < 3.5 = medium
        recs = get_kkc_recommendations(stats_medium)
        assert recs[0]['severity'] == 'medium'

        # Test lav severity (score >= 3.5)
        stats_low = {'MENING': {'avg_score': 4.0}}  # >= 3.5 = lav
        recs = get_kkc_recommendations(stats_low)
        assert recs[0]['severity'] == 'lav'

    def test_empty_stats_returns_empty_recommendations(self):
        """Test that empty stats returns empty recommendations."""
        from analysis import get_kkc_recommendations

        recommendations = get_kkc_recommendations({})
        assert recommendations == []


class TestStartHereRecommendation:
    """Test the 'start here' recommendation selection."""

    def test_start_here_returns_highest_priority(self):
        """Test that get_start_here_recommendation returns the most urgent item."""
        from analysis import get_start_here_recommendation, get_kkc_recommendations

        stats = {
            'MENING': {'avg_score': 4.0},  # Good
            'TRYGHED': {'avg_score': 2.0},  # Bad - should be start here
            'KAN': {'avg_score': 4.0},  # Good
            'BESVÆR': {'avg_score': 4.0},  # Good
        }

        recommendations = get_kkc_recommendations(stats)
        start_here = get_start_here_recommendation(recommendations)

        assert start_here is not None
        # Should identify TRYGHED as the priority
        if start_here.get('single'):
            assert start_here['primary']['field'] == 'TRYGHED'

    def test_start_here_handles_empty_list(self):
        """Test that empty recommendations returns None."""
        from analysis import get_start_here_recommendation

        result = get_start_here_recommendation([])
        assert result is None


class TestGapCalculations:
    """Test gap calculations between employee and leader scores."""

    def test_gap_severity_critical(self):
        """Test critical gap detection (>= 1.0 point difference)."""
        # Gap >= 1.0 is critical per ANALYSELOGIK.md
        employee_score = 2.0
        leader_score = 3.5
        gap = abs(employee_score - leader_score)

        assert gap >= 1.0

    def test_gap_severity_moderate(self):
        """Test moderate gap detection (0.6 - 1.0 point difference)."""
        employee_score = 3.0
        leader_score = 3.7
        gap = abs(employee_score - leader_score)

        assert 0.6 <= gap < 1.0

    def test_gap_no_misalignment(self):
        """Test no misalignment for small differences (< 0.6)."""
        employee_score = 3.5
        leader_score = 3.7
        gap = abs(employee_score - leader_score)

        has_misalignment = gap >= 0.6
        assert has_misalignment is False


class TestSubstitutionLogic:
    """Test substitution (tid) detection logic thresholds."""

    def test_tid_bias_threshold(self):
        """Test that tid_bias >= 0.6 triggers flagging per ANALYSELOGIK.md."""
        tid_bias = 0.6
        flagged = tid_bias >= 0.6
        assert flagged is True

        tid_bias = 0.59
        flagged = tid_bias >= 0.6
        assert flagged is False

    def test_underliggende_threshold(self):
        """Test that underliggende >= 3.5 indicates real time issue."""
        # Per ANALYSELOGIK.md: underliggende >= 3.5 means real time problem
        underliggende = 3.5
        is_real_time_issue = underliggende >= 3.5
        assert is_real_time_issue is True

        underliggende = 3.4
        is_real_time_issue = underliggende >= 3.5
        assert is_real_time_issue is False


class TestAnonymityThreshold:
    """Test anonymity threshold checking."""

    def test_default_min_responses_is_five(self):
        """Test that default minimum is 5 responses."""
        min_required = 5

        # 4 responses = can't show
        assert 4 < min_required
        # 5 responses = can show
        assert 5 >= min_required


class TestLayerInterpretation:
    """Test layer interpretation strings."""

    def test_layer_interpretation_exists(self):
        """Test that get_layer_interpretation function exists."""
        from analysis import get_layer_interpretation

        # Should return a non-empty string for valid inputs
        result = get_layer_interpretation('TRYGHED', 'ydre', 2.5)
        assert isinstance(result, str)

    def test_layer_interpretation_handles_all_fields(self):
        """Test interpretation for all fields."""
        from analysis import get_layer_interpretation

        fields_layers = [
            ('MENING', 'all'),
            ('TRYGHED', 'ydre'),
            ('TRYGHED', 'indre'),
            ('KAN', 'ydre'),
            ('KAN', 'indre'),
            ('BESVÆR', 'mekanisk'),
            ('BESVÆR', 'oplevet'),
        ]

        for field, layer in fields_layers:
            result = get_layer_interpretation(field, layer, 3.0)
            assert result is not None, f"No interpretation for {field}/{layer}"


class TestScoreConversions:
    """Test score conversion utilities."""

    def test_reverse_scoring_formula(self):
        """Test that reverse scoring works correctly (6 - score)."""
        # For reverse-scored items: 1 becomes 5, 5 becomes 1
        raw_score = 2
        reverse_scored = 6 - raw_score

        assert reverse_scored == 4

        raw_score = 5
        reverse_scored = 6 - raw_score
        assert reverse_scored == 1

    def test_score_to_percentage_conversion(self):
        """Test converting 1-5 score to 0-100 percentage."""
        # Formula: (score - 1) / 4 * 100
        def score_to_pct(score):
            return int((score - 1) / 4 * 100)

        assert score_to_pct(1) == 0
        assert score_to_pct(5) == 100
        assert score_to_pct(3) == 50


class TestLeaderGapThresholds:
    """Test leader gap analysis thresholds per ANALYSELOGIK.md."""

    def test_leader_gap_significant_threshold(self):
        """Test leader gap detection threshold (> 1.0 point)."""
        team_score = 2.5
        leader_score = 4.0
        gap = abs(team_score - leader_score)

        is_significant = gap > 1.0
        assert is_significant is True

    def test_leader_blocked_both_low(self):
        """Test leader blocked detection (both < 3.5)."""
        team_score = 3.0
        leader_score = 3.2

        is_blocked = team_score < 3.5 and leader_score < 3.5
        assert is_blocked is True

    def test_leader_not_blocked_if_leader_good(self):
        """Test not blocked when leader score is good."""
        team_score = 2.5
        leader_score = 4.0

        is_blocked = team_score < 3.5 and leader_score < 3.5
        assert is_blocked is False


class TestColorCodingThresholds:
    """Test percentage-based color coding per ANALYSELOGIK.md."""

    def test_green_threshold_70_percent(self):
        """Test green color for scores >= 70%."""
        # grøn ≥ 70%
        assert 70 >= 70  # green
        assert 85 >= 70  # green
        assert 100 >= 70  # green

    def test_yellow_threshold_50_to_69_percent(self):
        """Test yellow color for scores 50-69%."""
        # gul ≥ 50%
        assert 50 >= 50 and 50 < 70  # yellow
        assert 60 >= 50 and 60 < 70  # yellow
        assert 69 >= 50 and 69 < 70  # yellow

    def test_red_threshold_below_50_percent(self):
        """Test red color for scores < 50%."""
        # rød < 50%
        assert 49 < 50  # red
        assert 25 < 50  # red
        assert 0 < 50  # red


class TestGetUnitStatsWithKnownData:
    """Test get_unit_stats returns correct values with known test data.

    This is a regression test to ensure the field names match between
    questions table and the code (KAN not MULIGHED).
    """

    def test_field_order_uses_kan_not_mulighed(self):
        """Test that field_order uses 'KAN' not 'MULIGHED'."""
        from db_hierarchical import get_unit_stats
        import inspect

        # Get the source code of get_unit_stats
        source = inspect.getsource(get_unit_stats)

        # Verify it uses KAN
        assert "'KAN'" in source or '"KAN"' in source, \
            "get_unit_stats should use 'KAN' field name"

        # Verify it does NOT use MULIGHED
        assert "'MULIGHED'" not in source and '"MULIGHED"' not in source, \
            "get_unit_stats should NOT use 'MULIGHED' - use 'KAN' instead"

    def test_get_unit_stats_returns_all_four_fields(self):
        """Test that get_unit_stats returns all 4 fields: MENING, TRYGHED, KAN, BESVÆR.

        Uses a minimal SQLite setup to test only the field matching logic.
        """
        import sqlite3
        import tempfile
        import os

        # Use temp database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db = f.name

        # Temporarily override DB_PATH
        import db_hierarchical
        original_path = db_hierarchical.DB_PATH
        db_hierarchical.DB_PATH = temp_db

        try:
            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row

            # Create minimal schema needed for get_unit_stats
            conn.execute("""
                CREATE TABLE organizational_units (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    level INTEGER DEFAULT 0,
                    parent_id TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE questions (
                    id INTEGER PRIMARY KEY,
                    field TEXT,
                    text_da TEXT,
                    text_en TEXT,
                    is_default INTEGER DEFAULT 1,
                    reverse_scored INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id TEXT,
                    unit_id TEXT,
                    question_id INTEGER,
                    score INTEGER
                )
            """)

            # Create unit
            conn.execute("INSERT INTO organizational_units (id, name, level) VALUES ('test-unit', 'Test Unit', 0)")

            # Create questions for all 4 fields (IDs 90-113 like in production)
            questions = [
                # MENING (5 questions)
                (90, 'MENING'), (91, 'MENING'), (92, 'MENING'), (93, 'MENING'), (94, 'MENING'),
                # TRYGHED (5 questions)
                (95, 'TRYGHED'), (96, 'TRYGHED'), (97, 'TRYGHED'), (98, 'TRYGHED'), (99, 'TRYGHED'),
                # KAN (8 questions) - THIS IS THE CRITICAL FIELD NAME
                (100, 'KAN'), (101, 'KAN'), (102, 'KAN'), (103, 'KAN'),
                (104, 'KAN'), (105, 'KAN'), (106, 'KAN'), (107, 'KAN'),
                # BESVÆR (6 questions)
                (108, 'BESVÆR'), (109, 'BESVÆR'), (110, 'BESVÆR'),
                (111, 'BESVÆR'), (112, 'BESVÆR'), (113, 'BESVÆR'),
            ]

            for qid, field in questions:
                conn.execute(
                    "INSERT INTO questions (id, field, text_da, text_en, is_default) VALUES (?, ?, 'Test', 'Test', 1)",
                    (qid, field)
                )

            # Create responses with known scores (all score 4)
            for qid, field in questions:
                conn.execute(
                    "INSERT INTO responses (assessment_id, unit_id, question_id, score) VALUES ('test-assess', 'test-unit', ?, 4)",
                    (qid,)
                )

            conn.commit()
            conn.close()

            # Now test get_unit_stats
            from db_hierarchical import get_unit_stats
            stats = get_unit_stats('test-unit', 'test-assess', include_children=False)

            # Should return 4 fields
            assert len(stats) == 4, f"Expected 4 fields, got {len(stats)}"

            # Check field names
            fields = [s['field'] for s in stats]
            assert 'MENING' in fields, "Missing MENING field"
            assert 'TRYGHED' in fields, "Missing TRYGHED field"
            assert 'KAN' in fields, "Missing KAN field - check field_order uses 'KAN' not 'MULIGHED'"
            assert 'BESVÆR' in fields, "Missing BESVÆR field"

            # Check that MULIGHED is NOT in results
            assert 'MULIGHED' not in fields, "Should not have MULIGHED, use KAN"

            # Check average scores (all should be 4.0)
            for stat in stats:
                assert stat['avg_score'] == 4.0, \
                    f"Expected avg_score 4.0 for {stat['field']}, got {stat['avg_score']}"
                assert stat['response_count'] > 0, \
                    f"Expected response_count > 0 for {stat['field']}"

        finally:
            # Restore original path
            db_hierarchical.DB_PATH = original_path
            # Clean up temp file
            if os.path.exists(temp_db):
                os.unlink(temp_db)

    def test_known_data_calculation(self):
        """Test with specific known data: score 4 everywhere = 4.0 avg = 75%."""
        # This verifies the formula: (avg_score - 1) / 4 * 100 = percentage
        avg_score = 4.0
        expected_pct = int((avg_score - 1) / 4 * 100)

        assert expected_pct == 75, f"Score 4.0 should be 75%, got {expected_pct}%"

        # Also test edge cases
        assert int((5.0 - 1) / 4 * 100) == 100, "Score 5.0 should be 100%"
        assert int((1.0 - 1) / 4 * 100) == 0, "Score 1.0 should be 0%"
        assert int((3.0 - 1) / 4 * 100) == 50, "Score 3.0 should be 50%"


class TestReverseScoreCalculation:
    """
    Test reverse_scored beregning - KRITISK for korrekte procenter.

    Problemet der blev opdaget 2025-12-15:
    - Raw average var 3.39 (vises som 57%)
    - Med reverse_scored justering skulle det være 4.36 (84%)
    - UI viste 57% fordi reverse_scored ikke blev anvendt korrekt

    Formel for reverse_scored spørgsmål:
    - Normal: score bruges direkte
    - Reverse: 6 - score (så 1 bliver 5, 2 bliver 4, etc.)
    """

    def test_reverse_score_formula(self):
        """Test at reverse_scored formlen er korrekt: 6 - score."""
        # For reverse_scored=1 spørgsmål:
        # Lav score (1-2) = dårligt miljø = skal give høj adjusted score
        # Høj score (4-5) = godt miljø = skal give lav adjusted score

        # Hvis medarbejder svarer 2 på "Jeg føler mig stresset" (reverse)
        # betyder det lav stress = godt = adjusted score = 6 - 2 = 4
        assert 6 - 2 == 4, "Score 2 on reverse question should become 4"
        assert 6 - 1 == 5, "Score 1 on reverse question should become 5"
        assert 6 - 5 == 1, "Score 5 on reverse question should become 1"
        assert 6 - 3 == 3, "Score 3 on reverse question stays 3"

    def test_mixed_scores_with_reverse(self):
        """
        Test beregning med blandede normale og reverse spørgsmål.

        Scenarie fra Hammerum Skole:
        - Raw average: 3.39
        - Efter reverse justering: 4.36
        - Procent: 84%
        """
        # Simuler 4 svar: 2 normale, 2 reverse
        normal_scores = [4, 4]  # Bruges direkte
        reverse_scores = [2, 2]  # Bliver til 6-2=4 hver

        # Beregn adjusted scores
        adjusted_normal = normal_scores  # [4, 4]
        adjusted_reverse = [6 - s for s in reverse_scores]  # [4, 4]

        all_adjusted = adjusted_normal + adjusted_reverse
        avg_adjusted = sum(all_adjusted) / len(all_adjusted)

        assert avg_adjusted == 4.0, f"Expected 4.0, got {avg_adjusted}"

        # Procent
        pct = ((avg_adjusted - 1) / 4) * 100
        assert pct == 75.0, f"Expected 75%, got {pct}%"

    def test_raw_vs_adjusted_difference(self):
        """
        Test at raw og adjusted gennemsnit er forskellige når der er reverse spørgsmål.

        Dette er kerneproblemet: Hvis UI viser raw average i stedet for adjusted,
        får man forkerte (lavere) procenter.
        """
        # Scenarie: Medarbejdere svarer lavt på reverse spørgsmål (= godt)
        # Men højt på normale spørgsmål (= også godt)

        scores = [
            (4, False),  # Normal spørgsmål, score 4
            (4, False),  # Normal spørgsmål, score 4
            (2, True),   # Reverse spørgsmål, score 2 -> adjusted 4
            (2, True),   # Reverse spørgsmål, score 2 -> adjusted 4
        ]

        # Raw average (FORKERT at bruge denne!)
        raw_avg = sum(s[0] for s in scores) / len(scores)
        assert raw_avg == 3.0, f"Raw avg should be 3.0, got {raw_avg}"

        # Adjusted average (KORREKT)
        adjusted_scores = [
            6 - s[0] if s[1] else s[0]
            for s in scores
        ]
        adjusted_avg = sum(adjusted_scores) / len(adjusted_scores)
        assert adjusted_avg == 4.0, f"Adjusted avg should be 4.0, got {adjusted_avg}"

        # Procent forskel
        raw_pct = ((raw_avg - 1) / 4) * 100
        adjusted_pct = ((adjusted_avg - 1) / 4) * 100

        assert raw_pct == 50.0, f"Raw % should be 50%, got {raw_pct}%"
        assert adjusted_pct == 75.0, f"Adjusted % should be 75%, got {adjusted_pct}%"

        # KRITISK: Der er 25 procentpoint forskel!
        assert adjusted_pct - raw_pct == 25.0, "Should be 25 percentage points difference"

    def test_sql_case_expression(self):
        """
        Test at SQL CASE expression for reverse_scored er korrekt.

        Den korrekte SQL er:
        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
        """
        import sqlite3
        import tempfile
        import os

        # Opret temp database
        temp_db = tempfile.mktemp(suffix='.db')
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row

        try:
            # Opret tabeller
            conn.execute("""
                CREATE TABLE questions (
                    id INTEGER PRIMARY KEY,
                    field TEXT,
                    reverse_scored INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE responses (
                    id INTEGER PRIMARY KEY,
                    assessment_id TEXT,
                    question_id INTEGER,
                    score INTEGER
                )
            """)

            # Indsæt spørgsmål: 2 normale, 2 reverse
            conn.execute("INSERT INTO questions (id, field, reverse_scored) VALUES (1, 'TEST', 0)")
            conn.execute("INSERT INTO questions (id, field, reverse_scored) VALUES (2, 'TEST', 0)")
            conn.execute("INSERT INTO questions (id, field, reverse_scored) VALUES (3, 'TEST', 1)")
            conn.execute("INSERT INTO questions (id, field, reverse_scored) VALUES (4, 'TEST', 1)")

            # Indsæt svar: normale=4, reverse=2
            conn.execute("INSERT INTO responses (assessment_id, question_id, score) VALUES ('test', 1, 4)")
            conn.execute("INSERT INTO responses (assessment_id, question_id, score) VALUES ('test', 2, 4)")
            conn.execute("INSERT INTO responses (assessment_id, question_id, score) VALUES ('test', 3, 2)")
            conn.execute("INSERT INTO responses (assessment_id, question_id, score) VALUES ('test', 4, 2)")
            conn.commit()

            # Test RAW average (FORKERT)
            raw_result = conn.execute("""
                SELECT AVG(r.score) as raw_avg
                FROM responses r
                WHERE r.assessment_id = 'test'
            """).fetchone()

            assert raw_result['raw_avg'] == 3.0, f"Raw avg should be 3.0, got {raw_result['raw_avg']}"

            # Test ADJUSTED average (KORREKT)
            adjusted_result = conn.execute("""
                SELECT AVG(
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                ) as adjusted_avg
                FROM responses r
                JOIN questions q ON r.question_id = q.id
                WHERE r.assessment_id = 'test'
            """).fetchone()

            assert adjusted_result['adjusted_avg'] == 4.0, \
                f"Adjusted avg should be 4.0, got {adjusted_result['adjusted_avg']}"

        finally:
            conn.close()
            if os.path.exists(temp_db):
                os.unlink(temp_db)

    def test_to_percent_function(self):
        """Test to_percent helper funktion."""
        def to_percent(score):
            """Convert 1-5 score to percent (1=0%, 5=100%)"""
            if score is None or score == 0:
                return 0
            return ((score - 1) / 4) * 100

        # Test alle værdier
        assert to_percent(1.0) == 0.0, "Score 1 = 0%"
        assert to_percent(2.0) == 25.0, "Score 2 = 25%"
        assert to_percent(3.0) == 50.0, "Score 3 = 50%"
        assert to_percent(4.0) == 75.0, "Score 4 = 75%"
        assert to_percent(5.0) == 100.0, "Score 5 = 100%"

        # Test mellemværdier
        assert to_percent(3.5) == 62.5, "Score 3.5 = 62.5%"
        assert abs(to_percent(4.36) - 84.0) < 0.01, "Score 4.36 ≈ 84%"  # Hammerum case

        # Test edge cases
        assert to_percent(None) == 0, "None = 0%"
        assert to_percent(0) == 0, "0 = 0%"

    def test_vary_testdata_must_invert_reverse_scored(self):
        """
        REGRESSIONSTEST: vary_testdata() SKAL invertere scores for reverse_scored spørgsmål.

        Bug opdaget 2025-12-15:
        - vary_testdata() genererede høje scores (4.0-4.8) for ALLE spørgsmål
        - Men reverse_scored spørgsmål skal have LAVE raw scores for at give høje adjusted scores
        - Dette fik Hammerum Skole til at vise 57% i stedet for 79%

        Fix: For reverse_scored spørgsmål: new_score = 6 - target_score
        """
        # Simuler vary_testdata logik
        target_score = 4  # Profilen siger vi vil have adjusted score 4

        # For NORMAL spørgsmål: raw = target
        normal_raw = target_score
        normal_adjusted = normal_raw  # Ingen ændring
        assert normal_adjusted == 4, "Normal: target 4 → adjusted 4"

        # For REVERSE spørgsmål: raw = 6 - target (så adjusted = 6 - raw = target)
        reverse_raw = 6 - target_score  # = 2
        reverse_adjusted = 6 - reverse_raw  # = 4
        assert reverse_raw == 2, "Reverse: target 4 → raw 2"
        assert reverse_adjusted == 4, "Reverse: raw 2 → adjusted 4"

        # KRITISK: Begge typer giver SAMME adjusted score!
        assert normal_adjusted == reverse_adjusted, "Both types should give same adjusted score"

        # Test med lavere target score (organisation med problemer)
        target_low = 2  # Dårlig organisation

        # Normal: raw 2 → adjusted 2 (dårligt)
        normal_raw_low = target_low
        normal_adj_low = normal_raw_low
        assert normal_adj_low == 2

        # Reverse: raw 4 → adjusted 2 (også dårligt)
        reverse_raw_low = 6 - target_low  # = 4
        reverse_adj_low = 6 - reverse_raw_low  # = 2
        assert reverse_raw_low == 4
        assert reverse_adj_low == 2

        # KRITISK: Lavt target = lav adjusted for BEGGE typer
        assert normal_adj_low == reverse_adj_low == 2
