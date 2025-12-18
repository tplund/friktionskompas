"""
Esbjerg Kommune - Kanonisk Testdata Verifikation

Disse tests verificerer at Esbjerg-data er korrekt og stabil.
Hvis en test fejler, er der enten:
1. En bug i koden der håndterer data forkert
2. Nogen har ændret Esbjerg-data (IKKE tilladt uden godkendelse!)

Se ESBJERG_TESTDATA.md for dokumentation af testdata-design.
"""

import pytest
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / 'friktionskompas_v3.db'
ESBJERG_CUSTOMER_ID = 'cust-SHKIi10cOe8'


@pytest.fixture
def db():
    """Database connection fixture"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    yield conn
    conn.close()


class TestEsbjergStructure:
    """Tests for Esbjerg organizational structure"""

    def test_esbjerg_customer_exists(self, db):
        """Esbjerg Kommune skal eksistere som kunde"""
        result = db.execute(
            "SELECT name FROM customers WHERE id = ?",
            [ESBJERG_CUSTOMER_ID]
        ).fetchone()
        assert result is not None, "Esbjerg Kommune kunde mangler!"
        assert result['name'] == 'Esbjerg Kommune'

    def test_esbjerg_has_correct_unit_count(self, db):
        """Esbjerg skal have præcis 13 enheder"""
        result = db.execute(
            "SELECT COUNT(*) as count FROM organizational_units WHERE customer_id = ?",
            [ESBJERG_CUSTOMER_ID]
        ).fetchone()
        assert result['count'] == 13, f"Forventede 13 enheder, fik {result['count']}"

    def test_esbjerg_has_duplicate_name_with_herning(self, db):
        """Både Esbjerg og Herning skal have 'Social- og Sundhedsforvaltningen'"""
        result = db.execute("""
            SELECT COUNT(DISTINCT customer_id) as count
            FROM organizational_units
            WHERE name = 'Social- og Sundhedsforvaltningen'
        """).fetchone()
        assert result['count'] >= 2, \
            "Der skal være mindst 2 kunder med 'Social- og Sundhedsforvaltningen'"

    def test_handicap_area_has_no_data(self, db):
        """Handicapområdet skal eksistere men have ingen målinger"""
        result = db.execute("""
            SELECT ou.id, COUNT(a.id) as assessment_count
            FROM organizational_units ou
            LEFT JOIN assessments a ON a.target_unit_id = ou.id
            WHERE ou.customer_id = ? AND ou.name = 'Handicapområdet'
            GROUP BY ou.id
        """, [ESBJERG_CUSTOMER_ID]).fetchone()
        assert result is not None, "Handicapområdet enhed mangler!"
        assert result['assessment_count'] == 0, \
            "Handicapområdet skal være tom (ingen målinger)"


class TestEsbjergScores:
    """Tests for Esbjerg score profiles"""

    def _get_unit_scores(self, db, unit_name):
        """Helper: Get average employee scores for a unit"""
        return db.execute("""
            SELECT
                AVG(CASE WHEN q.field = 'TRYGHED' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as tryghed,
                AVG(CASE WHEN q.field = 'MENING' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as mening,
                AVG(CASE WHEN q.field = 'KAN' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as kan,
                AVG(CASE WHEN q.field = 'BESVÆR' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as besvaer
            FROM organizational_units ou
            JOIN assessments a ON a.target_unit_id = ou.id
            JOIN responses r ON r.assessment_id = a.id
            JOIN questions q ON r.question_id = q.id
            WHERE ou.customer_id = ? AND ou.name = ? AND r.respondent_type = 'employee'
        """, [ESBJERG_CUSTOMER_ID, unit_name]).fetchone()

    def test_birkebo_has_average_scores(self, db):
        """Birkebo skal have gennemsnitlige scores omkring 3.5"""
        scores = self._get_unit_scores(db, 'Birkebo')
        assert scores is not None, "Birkebo data mangler!"

        for field in ['tryghed', 'mening', 'kan', 'besvaer']:
            score = scores[field]
            assert 3.0 <= score <= 4.0, \
                f"Birkebo {field} skal være 3.0-4.0, fik {score:.2f}"

    def test_skovbrynet_has_high_scores(self, db):
        """Skovbrynet skal have høje scores (over 4.0)"""
        scores = self._get_unit_scores(db, 'Skovbrynet')
        assert scores is not None, "Skovbrynet data mangler!"

        for field in ['tryghed', 'mening', 'kan', 'besvaer']:
            score = scores[field]
            assert score >= 4.0, \
                f"Skovbrynet {field} skal være >= 4.0, fik {score:.2f}"

    def test_solhjem_has_crisis_scores(self, db):
        """Solhjem skal have lave scores (under 2.5)"""
        scores = self._get_unit_scores(db, 'Solhjem')
        assert scores is not None, "Solhjem data mangler!"

        for field in ['tryghed', 'mening', 'kan', 'besvaer']:
            score = scores[field]
            assert score <= 2.5, \
                f"Solhjem {field} skal være <= 2.5, fik {score:.2f}"

    def test_strandparken_has_leader_gap(self, db):
        """Strandparken skal have stort gap mellem medarbejder og leder (> 1.5)"""
        result = db.execute("""
            SELECT
                AVG(CASE WHEN r.respondent_type = 'employee' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_avg,
                AVG(CASE WHEN r.respondent_type = 'leader_assess' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as leader_avg
            FROM organizational_units ou
            JOIN assessments a ON a.target_unit_id = ou.id
            JOIN responses r ON r.assessment_id = a.id
            JOIN questions q ON r.question_id = q.id
            WHERE ou.customer_id = ? AND ou.name = 'Strandparken'
        """, [ESBJERG_CUSTOMER_ID]).fetchone()

        assert result['employee_avg'] is not None, "Strandparken employee data mangler!"
        assert result['leader_avg'] is not None, "Strandparken leader data mangler!"

        gap = abs(result['leader_avg'] - result['employee_avg'])
        assert gap >= 1.5, \
            f"Strandparken gap skal være >= 1.5, fik {gap:.2f}"


class TestEsbjergB2C:
    """Tests for Esbjerg B2C assessments"""

    def test_individuel_profil_has_one_respondent(self, db):
        """Individuel Profil Test skal have præcis 1 respondent"""
        result = db.execute("""
            SELECT COUNT(DISTINCT r.respondent_name) as respondent_count
            FROM organizational_units ou
            JOIN assessments a ON a.target_unit_id = ou.id
            JOIN responses r ON r.assessment_id = a.id
            WHERE ou.customer_id = ? AND ou.name = 'Individuel Profil Test'
        """, [ESBJERG_CUSTOMER_ID]).fetchone()

        assert result['respondent_count'] == 1, \
            f"Individuel Profil Test skal have 1 respondent, fik {result['respondent_count']}"

    def test_minimal_data_has_uniform_scores(self, db):
        """Minimal Data Test skal have identiske scores (ingen variation)"""
        result = db.execute("""
            SELECT
                MIN(r.score) as min_score,
                MAX(r.score) as max_score
            FROM organizational_units ou
            JOIN assessments a ON a.target_unit_id = ou.id
            JOIN responses r ON r.assessment_id = a.id
            WHERE ou.customer_id = ? AND ou.name = 'Minimal Data Test'
        """, [ESBJERG_CUSTOMER_ID]).fetchone()

        assert result['min_score'] == result['max_score'] == 3.0, \
            f"Minimal Data Test skal have alle scores = 3.0, fik min={result['min_score']}, max={result['max_score']}"


class TestEsbjergSubstitution:
    """Tests for Kahneman substitution pattern"""

    def test_substitution_pattern_exists(self, db):
        """Substitution Test skal have lav MENING og BESVÆR, høj TRYGHED og KAN"""
        result = db.execute("""
            SELECT
                AVG(CASE WHEN q.field = 'TRYGHED' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as tryghed,
                AVG(CASE WHEN q.field = 'MENING' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as mening,
                AVG(CASE WHEN q.field = 'KAN' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as kan,
                AVG(CASE WHEN q.field = 'BESVÆR' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as besvaer
            FROM organizational_units ou
            JOIN assessments a ON a.target_unit_id = ou.id
            JOIN responses r ON r.assessment_id = a.id
            JOIN questions q ON r.question_id = q.id
            WHERE ou.customer_id = ? AND ou.name = 'Substitution Test'
        """, [ESBJERG_CUSTOMER_ID]).fetchone()

        # TRYGHED og KAN skal være høje (> 3.5)
        assert result['tryghed'] >= 3.5, \
            f"Substitution TRYGHED skal være >= 3.5, fik {result['tryghed']:.2f}"
        assert result['kan'] >= 3.5, \
            f"Substitution KAN skal være >= 3.5, fik {result['kan']:.2f}"

        # MENING og BESVÆR skal være lave (< 2.5)
        assert result['mening'] <= 2.5, \
            f"Substitution MENING skal være <= 2.5, fik {result['mening']:.2f}"
        assert result['besvaer'] <= 2.5, \
            f"Substitution BESVÆR skal være <= 2.5, fik {result['besvaer']:.2f}"


class TestEsbjergDataIntegrity:
    """Tests for data integrity"""

    def test_all_assessments_have_responses(self, db):
        """Alle Esbjerg assessments (undtagen tomme enheder) skal have svar"""
        result = db.execute("""
            SELECT a.name, COUNT(r.id) as response_count
            FROM assessments a
            LEFT JOIN responses r ON r.assessment_id = a.id
            WHERE a.target_unit_id IN (
                SELECT id FROM organizational_units WHERE customer_id = ?
            )
            GROUP BY a.id
            HAVING response_count = 0
        """, [ESBJERG_CUSTOMER_ID]).fetchall()

        assert len(result) == 0, \
            f"Følgende assessments har ingen svar: {[r['name'] for r in result]}"

    def test_response_scores_are_valid(self, db):
        """Alle scores skal være mellem 1 og 5"""
        result = db.execute("""
            SELECT COUNT(*) as invalid_count
            FROM responses r
            JOIN assessments a ON r.assessment_id = a.id
            WHERE a.target_unit_id IN (
                SELECT id FROM organizational_units WHERE customer_id = ?
            )
            AND (r.score < 1 OR r.score > 5)
        """, [ESBJERG_CUSTOMER_ID]).fetchone()

        assert result['invalid_count'] == 0, \
            f"Fandt {result['invalid_count']} svar med ugyldig score (ikke 1-5)"
