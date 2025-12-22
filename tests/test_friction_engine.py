"""
Tests for friction_engine.py - Central beregningsmotor
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from friction_engine import (
    score_to_percent, percent_to_score, adjust_score,
    get_severity, get_percent_class, get_spread_level,
    calculate_std_dev, calculate_field_scores,
    calculate_gap, check_leader_blocked, analyze_gaps,
    calculate_substitution_for_respondent, calculate_substitution,
    get_warnings, get_start_here_recommendation, get_profile_type,
    Severity, SpreadLevel, FieldScore, GapAnalysis, SubstitutionResult,
    THRESHOLDS, FRICTION_FIELDS
)


class TestScoreConversion:
    """Test score <-> percent konvertering (7-point skala)"""

    def test_score_to_percent_basic(self):
        """Test basisk konvertering (1-7 skala)"""
        assert score_to_percent(7) == 100.0
        assert abs(score_to_percent(1) - 14.3) < 0.1  # 1/7 * 100
        assert score_to_percent(3.5) == 50.0
        assert abs(score_to_percent(4.9) - 70.0) < 0.1

    def test_score_to_percent_edge_cases(self):
        """Test edge cases"""
        assert score_to_percent(0) == 0.0
        assert score_to_percent(None) == 0.0

    def test_percent_to_score(self):
        """Test omvendt konvertering (7-point skala)"""
        assert percent_to_score(100) == 7.0
        assert percent_to_score(50) == 3.5
        assert abs(percent_to_score(70) - 4.9) < 0.1

    def test_roundtrip(self):
        """Test at konvertering er konsistent"""
        for score in [1, 2, 3, 4, 5, 6, 7]:
            pct = score_to_percent(score)
            back = percent_to_score(pct)
            assert abs(back - score) < 0.01


class TestAdjustScore:
    """Test reverse scoring (7-point skala: 8 - score)"""

    def test_normal_score(self):
        """Ikke-reverse scores forbliver uændrede"""
        assert adjust_score(7, reverse_scored=False) == 7
        assert adjust_score(1, reverse_scored=False) == 1
        assert adjust_score(4, reverse_scored=False) == 4

    def test_reverse_score(self):
        """Reverse scores inverteres korrekt (8 - score)"""
        assert adjust_score(7, reverse_scored=True) == 1  # 8-7=1
        assert adjust_score(1, reverse_scored=True) == 7  # 8-1=7
        assert adjust_score(4, reverse_scored=True) == 4  # 8-4=4 (midtpunkt)
        assert adjust_score(6, reverse_scored=True) == 2  # 8-6=2
        assert adjust_score(2, reverse_scored=True) == 6  # 8-2=6


class TestSeverity:
    """Test severity klassificering (7-point skala)"""

    def test_severity_high(self):
        """Scores under 3.5 = høj severity (~50%)"""
        assert get_severity(3.4) == Severity.HIGH
        assert get_severity(1.0) == Severity.HIGH
        assert get_severity(2.5) == Severity.HIGH

    def test_severity_medium(self):
        """Scores 3.5-4.9 = medium severity (50-70%)"""
        assert get_severity(3.5) == Severity.MEDIUM
        assert get_severity(4.0) == Severity.MEDIUM
        assert get_severity(4.8) == Severity.MEDIUM

    def test_severity_low(self):
        """Scores >= 4.9 = lav severity (>=70%)"""
        assert get_severity(4.9) == Severity.LOW
        assert get_severity(5.5) == Severity.LOW
        assert get_severity(7.0) == Severity.LOW


class TestPercentClass:
    """Test CSS-klasse baseret på procent"""

    def test_score_high(self):
        """>= 70% = grøn"""
        assert get_percent_class(70) == 'score-high'
        assert get_percent_class(85) == 'score-high'
        assert get_percent_class(100) == 'score-high'

    def test_score_medium(self):
        """50-70% = gul"""
        assert get_percent_class(50) == 'score-medium'
        assert get_percent_class(60) == 'score-medium'
        assert get_percent_class(69) == 'score-medium'

    def test_score_low(self):
        """< 50% = rød"""
        assert get_percent_class(49) == 'score-low'
        assert get_percent_class(30) == 'score-low'
        assert get_percent_class(0) == 'score-low'


class TestSpreadLevel:
    """Test spredningsklassificering (7-point skala)"""

    def test_spread_low(self):
        """Std dev < 0.7 = lav"""
        assert get_spread_level(0.3) == SpreadLevel.LOW
        assert get_spread_level(0.69) == SpreadLevel.LOW

    def test_spread_medium(self):
        """Std dev 0.7-1.4 = medium"""
        assert get_spread_level(0.7) == SpreadLevel.MEDIUM
        assert get_spread_level(1.0) == SpreadLevel.MEDIUM
        assert get_spread_level(1.39) == SpreadLevel.MEDIUM

    def test_spread_high(self):
        """Std dev >= 1.4 = høj"""
        assert get_spread_level(1.4) == SpreadLevel.HIGH
        assert get_spread_level(2.0) == SpreadLevel.HIGH


class TestStdDev:
    """Test standardafvigelsesberegning"""

    def test_std_dev_identical(self):
        """Identiske scores = 0 std dev"""
        assert calculate_std_dev([3, 3, 3, 3]) == 0.0

    def test_std_dev_varied(self):
        """Varierede scores"""
        result = calculate_std_dev([1, 2, 3, 4, 5])
        assert result > 1.0  # Bør være ca. 1.41

    def test_std_dev_single(self):
        """Én score = 0"""
        assert calculate_std_dev([3]) == 0.0

    def test_std_dev_empty(self):
        """Tom liste = 0"""
        assert calculate_std_dev([]) == 0.0


class TestCalculateFieldScores:
    """Test field score beregning"""

    def test_basic_field_scores(self):
        """Test basisk beregning"""
        responses = [
            {'sequence': 1, 'score': 4, 'reverse_scored': False},
            {'sequence': 2, 'score': 4, 'reverse_scored': False},
            {'sequence': 3, 'score': 4, 'reverse_scored': False},
            {'sequence': 4, 'score': 4, 'reverse_scored': False},
            {'sequence': 5, 'score': 4, 'reverse_scored': False},
        ]
        result = calculate_field_scores(responses)

        assert 'MENING' in result
        assert result['MENING'].avg_score == 4.0
        assert result['MENING'].response_count == 5

    def test_reverse_scoring_in_fields(self):
        """Test at reverse scoring anvendes korrekt (8 - score på 7-point)"""
        responses = [
            {'sequence': 1, 'score': 7, 'reverse_scored': True},  # Bliver 8-7=1
            {'sequence': 2, 'score': 7, 'reverse_scored': True},  # Bliver 8-7=1
        ]
        result = calculate_field_scores(responses)

        # Med reverse scoring bør gennemsnittet være 1.0 (8-7=1)
        assert result['MENING'].avg_score == 1.0

    def test_empty_responses(self):
        """Test med tom liste"""
        result = calculate_field_scores([])

        for field in FRICTION_FIELDS:
            assert result[field].avg_score == 0
            assert result[field].response_count == 0


class TestGapAnalysis:
    """Test gap-analyse mellem respondenttyper (7-point skala)"""

    def test_calculate_gap_significant(self):
        """Test signifikant gap (> 1.4)"""
        gap, severity, misaligned = calculate_gap(2.5, 4.5)

        assert gap == 2.0
        assert severity == 'kritisk'
        assert misaligned is True

    def test_calculate_gap_moderate(self):
        """Test moderat gap (0.84-1.4)"""
        gap, severity, misaligned = calculate_gap(4.0, 5.0)

        assert gap == 1.0
        assert severity == 'moderat'
        assert misaligned is True

    def test_calculate_gap_ok(self):
        """Test acceptabelt gap (< 0.84)"""
        gap, severity, misaligned = calculate_gap(5.0, 5.5)

        assert gap == 0.5
        assert severity is None
        assert misaligned is False

    def test_leader_blocked(self):
        """Test leder blokeret logik (threshold 4.9)"""
        # Begge under 4.9 = blokeret
        assert check_leader_blocked(4.0, 4.0) is True
        assert check_leader_blocked(3.5, 4.8) is True

        # Én over 4.9 = ikke blokeret
        assert check_leader_blocked(4.0, 4.9) is False
        assert check_leader_blocked(4.9, 4.0) is False

        # Begge over 4.9 = ikke blokeret
        assert check_leader_blocked(5.5, 5.5) is False


class TestSubstitution:
    """Test substitutionsanalyse (Kahneman) - 7-point skala"""

    def test_substitution_flagged(self):
        """Test at substitution flagges korrekt"""
        # Respondent med høj tid_bias og høj underliggende
        scores = {
            14: 1,   # Har IKKE tid nok -> TID_MANGEL = 8-1 = 7
            19: 6,   # Lav mekanisk friktion
            20: 6,   # Lav mekanisk friktion
            21: 6,   # Lav mekanisk friktion
            22: 6,   # Lav mekanisk friktion
            5: 6,    # Høj tilfredshed
            10: 6,   # Høj tilfredshed
            17: 6,   # Høj tilfredshed
            18: 6,   # Høj tilfredshed
        }
        result = calculate_substitution_for_respondent(scores)

        # TID_MANGEL = 8-1 = 7
        # PROC = (6 + (8-6) + (8-6) + (8-6)) / 4 = (6+2+2+2)/4 = 3.0
        # TID_BIAS = 7 - 3.0 = 4.0 >= 0.84 ✓
        # UNDERLIGGENDE = max(6,6,6,6) = 6 >= 4.9 ✓
        assert result['flagged'] is True
        assert result['tid_bias'] >= 0.84

    def test_substitution_not_flagged(self):
        """Test at normal respondent ikke flagges"""
        # Respondent med lav tid_bias
        scores = {
            14: 6,   # Har tid nok -> TID_MANGEL = 8-6 = 2
            19: 2,   # Høj mekanisk friktion
            20: 2,   # Høj mekanisk friktion
            21: 2,   # Høj mekanisk friktion
            22: 2,   # Høj mekanisk friktion
            5: 2,    # Lav tilfredshed
            10: 2,
            17: 2,
            18: 2,
        }
        result = calculate_substitution_for_respondent(scores)

        # Burde ikke flagges pga lav underliggende
        assert result['flagged'] is False


class TestWarnings:
    """Test warning-generering (7-point skala)"""

    def test_high_friction_warning(self):
        """Test at høj friktion genererer warning"""
        field_scores = {
            'MENING': FieldScore(
                field='MENING',
                avg_score=2.5,  # Kritisk lav (under 3.5)
                response_count=10,
                std_dev=0.7,
                spread=SpreadLevel.MEDIUM
            )
        }
        warnings = get_warnings(field_scores)

        assert len(warnings) >= 1
        assert any(w.type == 'high_friction' for w in warnings)

    def test_gap_warning(self):
        """Test at gap genererer warning"""
        field_scores = {'MENING': FieldScore('MENING', 4.0, 10, 0.7, SpreadLevel.LOW)}
        gap_analysis = {
            'MENING': GapAnalysis(
                field='MENING',
                employee_score=3.0,
                leader_assess_score=5.5,
                leader_self_score=5.5,
                gap=2.5,
                gap_severity='kritisk',
                has_misalignment=True,
                leader_blocked=False
            )
        }
        warnings = get_warnings(field_scores, gap_analysis)

        assert any(w.type == 'gap' for w in warnings)


class TestStartHereRecommendation:
    """Test KKC 'Start Her' anbefaling (7-point skala)"""

    def test_start_with_tryghed(self):
        """TRYGHED prioriteres først (ny rækkefølge: TRYGHED, MENING, KAN, BESVÆR)"""
        scores = {
            'MENING': FieldScore('MENING', 3.0, 10, 0.7, SpreadLevel.LOW),
            'TRYGHED': FieldScore('TRYGHED', 3.0, 10, 0.7, SpreadLevel.LOW),
            'KAN': FieldScore('KAN', 3.0, 10, 0.7, SpreadLevel.LOW),
            'BESVÆR': FieldScore('BESVÆR', 3.0, 10, 0.7, SpreadLevel.LOW),
        }
        assert get_start_here_recommendation(scores) == 'TRYGHED'

    def test_start_with_mening_if_tryghed_ok(self):
        """MENING prioriteres når TRYGHED er OK"""
        scores = {
            'MENING': FieldScore('MENING', 3.0, 10, 0.7, SpreadLevel.LOW),
            'TRYGHED': FieldScore('TRYGHED', 5.5, 10, 0.7, SpreadLevel.LOW),
            'KAN': FieldScore('KAN', 3.0, 10, 0.7, SpreadLevel.LOW),
            'BESVÆR': FieldScore('BESVÆR', 3.0, 10, 0.7, SpreadLevel.LOW),
        }
        assert get_start_here_recommendation(scores) == 'MENING'

    def test_no_recommendation_if_all_ok(self):
        """Ingen anbefaling hvis alt er OK (>= 4.9)"""
        scores = {
            'MENING': FieldScore('MENING', 5.5, 10, 0.7, SpreadLevel.LOW),
            'TRYGHED': FieldScore('TRYGHED', 5.5, 10, 0.7, SpreadLevel.LOW),
            'KAN': FieldScore('KAN', 5.5, 10, 0.7, SpreadLevel.LOW),
            'BESVÆR': FieldScore('BESVÆR', 5.5, 10, 0.7, SpreadLevel.LOW),
        }
        assert get_start_here_recommendation(scores) is None


class TestProfileType:
    """Test profiltype-bestemmelse (7-point skala)"""

    def test_retningsloest_team(self):
        """Kritisk lav MENING (< 3.5) = retningsløst"""
        scores = {
            'MENING': FieldScore('MENING', 3.0, 10, 0.7, SpreadLevel.LOW),
            'TRYGHED': FieldScore('TRYGHED', 5.5, 10, 0.7, SpreadLevel.LOW),
            'KAN': FieldScore('KAN', 5.5, 10, 0.7, SpreadLevel.LOW),
            'BESVÆR': FieldScore('BESVÆR', 5.5, 10, 0.7, SpreadLevel.LOW),
        }
        assert get_profile_type(scores) == 'retningsløst_team'

    def test_hoejtydende_team(self):
        """Alle scores >= 5.6 = højtydende (80% på 7-point)"""
        scores = {
            'MENING': FieldScore('MENING', 6.0, 10, 0.5, SpreadLevel.LOW),
            'TRYGHED': FieldScore('TRYGHED', 5.8, 10, 0.5, SpreadLevel.LOW),
            'KAN': FieldScore('KAN', 5.6, 10, 0.5, SpreadLevel.LOW),
            'BESVÆR': FieldScore('BESVÆR', 5.9, 10, 0.5, SpreadLevel.LOW),
        }
        assert get_profile_type(scores) == 'højtydende_team'


class TestThresholds:
    """Test at grænseværdier er korrekte (7-point skala)"""

    def test_threshold_values(self):
        """Verificer grænseværdier for 7-point skala"""
        assert THRESHOLDS['percent_green'] == 70
        assert THRESHOLDS['percent_yellow'] == 50
        assert THRESHOLDS['severity_high'] == 3.5    # 50% på 7-point
        assert THRESHOLDS['severity_medium'] == 4.9  # 70% på 7-point
        assert THRESHOLDS['gap_significant'] == 1.4  # 20% på 7-point
        assert THRESHOLDS['gap_moderate'] == 0.84    # 12% på 7-point
        assert THRESHOLDS['tid_bias'] == 0.84        # 12% på 7-point
        assert THRESHOLDS['underliggende'] == 4.9    # 70% på 7-point
