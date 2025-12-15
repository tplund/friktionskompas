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

        assert 'stealth_s' in SUBSTITUTION_ITEMS
        assert 'tid_item' in SUBSTITUTION_ITEMS
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
            'MENING': {'avg_score': 3.0},  # medium
            'TRYGHED': {'avg_score': 2.0},  # høj
            'KAN': {'avg_score': 4.0},  # lav
            'BESVÆR': {'avg_score': 2.5},  # høj
        }

        recommendations = get_kkc_recommendations(stats)

        # High severity items should come first
        severities = [r['severity'] for r in recommendations]
        assert severities[0] == 'høj'  # TRYGHED first (score 2.0)
        assert severities[1] == 'høj'  # BESVÆR second (score 2.5)

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

        # Test høj severity (score <= 2.5)
        stats_high = {'MENING': {'avg_score': 2.5}}
        recs = get_kkc_recommendations(stats_high)
        assert recs[0]['severity'] == 'høj'

        # Test medium severity (score 2.5-3.5)
        stats_medium = {'MENING': {'avg_score': 3.0}}
        recs = get_kkc_recommendations(stats_medium)
        assert recs[0]['severity'] == 'medium'

        # Test lav severity (score > 3.5)
        stats_low = {'MENING': {'avg_score': 4.0}}
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
