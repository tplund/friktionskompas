"""
Tests for Par-måling (Pair Assessment) functionality.

Tests cover:
- Creating pair sessions
- Joining pair sessions with codes
- Status updates
- Comparison generation
- Database schema verification (required columns)
"""
import pytest
from db_profil import (
    init_profil_tables,
    create_pair_session,
    get_pair_session,
    get_pair_session_by_code,
    get_pair_session_by_profil_session,
    join_pair_session,
    update_pair_status,
    save_responses,
    complete_session,
    get_questions_by_field
)
from analysis_profil import compare_profiles, calculate_perception_gaps
from db import get_db


class TestDatabaseSchema:
    """
    Tests for required database columns.

    These tests ensure that database migrations have been run correctly.
    If these fail, the app will crash at runtime when users try to use features.

    IMPORTANT: These tests catch issues where:
    - Migrations haven't been run on production
    - ALTER TABLE statements failed silently
    - Test database schema differs from production
    """

    def test_profil_responses_has_response_type_column(self):
        """
        Verify profil_responses has response_type column.

        This column is required for the perception gap feature where users
        can save both their own answer and their prediction of partner's answer.

        Added in: Perception gap feature (2025-12)
        """
        with get_db() as conn:
            columns = [col[1] for col in conn.execute("PRAGMA table_info(profil_responses)").fetchall()]
            assert 'response_type' in columns, (
                "profil_responses missing 'response_type' column. "
                "Run migration: curl https://friktionskompasset.dk/admin/run-profil-migration -H 'X-Admin-API-Key: ...'"
            )

    def test_pair_sessions_has_pair_mode_column(self):
        """
        Verify pair_sessions has pair_mode column.

        This column is required for version selection (basis/standard/udvidet)
        in pair assessments.

        Added in: Version selection feature (2025-12)
        """
        with get_db() as conn:
            columns = [col[1] for col in conn.execute("PRAGMA table_info(pair_sessions)").fetchall()]
            assert 'pair_mode' in columns, (
                "pair_sessions missing 'pair_mode' column. "
                "Run migration: curl https://friktionskompasset.dk/admin/run-profil-migration -H 'X-Admin-API-Key: ...'"
            )


class TestPairSessionDatabase:
    """Tests for pair session database operations"""

    def test_create_pair_session(self):
        """Test creating a new pair session"""
        result = create_pair_session('TestUser', 'test@example.com')

        assert 'pair_id' in result
        assert 'pair_code' in result
        assert 'session_id' in result
        assert result['pair_id'].startswith('pair-')
        assert len(result['pair_code']) == 6
        assert result['session_id'].startswith('profil-')

    def test_create_pair_session_with_mode(self):
        """Test creating pair session with different modes"""
        # Default mode is 'standard'
        result1 = create_pair_session('TestUser1', 'test1@example.com')
        pair1 = get_pair_session(result1['pair_id'])
        assert pair1['pair_mode'] == 'standard'

        # Basis mode
        result2 = create_pair_session('TestUser2', 'test2@example.com', pair_mode='basis')
        pair2 = get_pair_session(result2['pair_id'])
        assert pair2['pair_mode'] == 'basis'

        # Standard mode explicit
        result3 = create_pair_session('TestUser3', 'test3@example.com', pair_mode='standard')
        pair3 = get_pair_session(result3['pair_id'])
        assert pair3['pair_mode'] == 'standard'

    def test_pair_code_format(self):
        """Test that pair codes are 6 uppercase alphanumeric chars without confusable chars"""
        result = create_pair_session('TestUser', 'test@example.com')
        code = result['pair_code']

        assert len(code) == 6
        assert code.isupper() or code.isdigit() or all(c.isupper() or c.isdigit() for c in code)
        # Should not contain confusable characters
        for char in '0O1IL':
            assert char not in code

    def test_get_pair_session(self):
        """Test retrieving a pair session by ID"""
        result = create_pair_session('TestUser', 'test@example.com')
        pair = get_pair_session(result['pair_id'])

        assert pair is not None
        assert pair['id'] == result['pair_id']
        assert pair['pair_code'] == result['pair_code']
        assert pair['person_a_name'] == 'TestUser'
        assert pair['person_a_email'] == 'test@example.com'
        assert pair['status'] == 'waiting'

    def test_get_pair_session_by_code(self):
        """Test retrieving a pair session by code"""
        result = create_pair_session('TestUser', 'test@example.com')
        pair = get_pair_session_by_code(result['pair_code'])

        assert pair is not None
        assert pair['id'] == result['pair_id']

    def test_get_pair_session_by_profil_session(self):
        """Test finding pair session by profil session ID"""
        result = create_pair_session('TestUser', 'test@example.com')
        pair = get_pair_session_by_profil_session(result['session_id'])

        assert pair is not None
        assert pair['id'] == result['pair_id']

    def test_join_pair_session(self):
        """Test joining an existing pair session"""
        # Create pair session
        create_result = create_pair_session('PersonA', 'a@example.com')

        # Join pair session
        join_result = join_pair_session(
            create_result['pair_code'],
            'PersonB',
            'b@example.com'
        )

        assert join_result is not None
        assert join_result['pair_id'] == create_result['pair_id']
        assert 'session_id' in join_result
        assert join_result['session_id'] != create_result['session_id']

        # Verify pair session updated
        pair = get_pair_session(create_result['pair_id'])
        assert pair['person_b_name'] == 'PersonB'
        assert pair['person_b_email'] == 'b@example.com'
        assert pair['person_b_session_id'] == join_result['session_id']

    def test_join_invalid_code(self):
        """Test joining with invalid code returns None"""
        result = join_pair_session('INVALID', 'PersonB', 'b@example.com')
        assert result is None

    def test_join_already_used_code(self):
        """Test joining a pair that already has a partner returns None"""
        # Create and join
        create_result = create_pair_session('PersonA', 'a@example.com')
        join_pair_session(create_result['pair_code'], 'PersonB', 'b@example.com')

        # Try to join again
        result = join_pair_session(create_result['pair_code'], 'PersonC', 'c@example.com')
        assert result is None


class TestPairSessionStatus:
    """Tests for pair session status updates"""

    def test_status_waiting_initial(self):
        """Test initial status is 'waiting'"""
        result = create_pair_session('TestUser', 'test@example.com')
        status = update_pair_status(result['pair_id'])
        assert status == 'waiting'

    def test_status_partial_after_join(self):
        """Test status is 'partial' after partner joins"""
        result = create_pair_session('PersonA', 'a@example.com')
        join_pair_session(result['pair_code'], 'PersonB', 'b@example.com')

        status = update_pair_status(result['pair_id'])
        assert status == 'partial'

    def test_status_complete_after_both_finish(self):
        """Test status is 'complete' when both surveys are done"""
        # Create pair
        result = create_pair_session('PersonA', 'a@example.com')
        session_a = result['session_id']

        # Join
        join_result = join_pair_session(result['pair_code'], 'PersonB', 'b@example.com')
        session_b = join_result['session_id']

        # Complete both surveys
        questions = get_questions_by_field()
        all_questions = []
        for field, qs in questions.items():
            all_questions.extend(qs)

        responses = {q['id']: 4 for q in all_questions}

        save_responses(session_a, responses)
        complete_session(session_a)
        save_responses(session_b, responses)
        complete_session(session_b)

        # Check status
        status = update_pair_status(result['pair_id'])
        assert status == 'complete'


class TestPairComparison:
    """Tests for pair comparison generation"""

    def test_compare_completed_pair(self):
        """Test generating comparison for completed pair"""
        # Create and complete pair
        result = create_pair_session('PersonA', 'a@example.com')
        join_result = join_pair_session(result['pair_code'], 'PersonB', 'b@example.com')

        # Get questions and create different response patterns
        questions = get_questions_by_field()
        all_questions = []
        for field, qs in questions.items():
            all_questions.extend(qs)

        # Person A: high scores
        responses_a = {q['id']: 5 for q in all_questions}
        save_responses(result['session_id'], responses_a)
        complete_session(result['session_id'])

        # Person B: low scores
        responses_b = {q['id']: 2 for q in all_questions}
        save_responses(join_result['session_id'], responses_b)
        complete_session(join_result['session_id'])

        # Generate comparison
        comparison = compare_profiles(result['session_id'], join_result['session_id'])

        assert comparison is not None
        assert 'profile_1' in comparison
        assert 'profile_2' in comparison
        assert 'differences' in comparison
        assert 'insights' in comparison
        assert len(comparison['insights']) > 0


class TestPairRoutes:
    """Tests for pair HTTP routes"""

    def test_pair_start_page_loads(self, client):
        """Test GET /profil/pair/start returns 200"""
        response = client.get('/profil/pair/start')
        assert response.status_code == 200
        assert 'Par-måling' in response.get_data(as_text=True)

    def test_pair_join_page_loads(self, client):
        """Test GET /profil/pair/join returns 200"""
        response = client.get('/profil/pair/join')
        assert response.status_code == 200
        assert '6-tegns kode' in response.get_data(as_text=True)

    def test_pair_join_with_prefilled_code(self, client):
        """Test GET /profil/pair/join?code=ABC123 prefills the code"""
        response = client.get('/profil/pair/join?code=ABC123')
        assert response.status_code == 200
        assert 'ABC123' in response.get_data(as_text=True)

    def test_pair_start_creates_session(self, client):
        """Test POST /profil/pair/start creates a pair session"""
        response = client.post('/profil/pair/start', data={
            'name': 'TestUser',
            'email': 'test@example.com'
        }, follow_redirects=False)

        # Should redirect to survey
        assert response.status_code == 302
        assert '/profil/' in response.location

    def test_pair_join_with_valid_code(self, client):
        """Test POST /profil/pair/join with valid code"""
        # First create a pair session
        result = create_pair_session('PersonA', 'a@example.com')

        # Then join it
        response = client.post('/profil/pair/join', data={
            'code': result['pair_code'],
            'name': 'PersonB',
            'email': 'b@example.com'
        }, follow_redirects=False)

        # Should redirect to survey
        assert response.status_code == 302
        assert '/profil/' in response.location

    def test_pair_join_with_invalid_code(self, client):
        """Test POST /profil/pair/join with invalid code shows error"""
        response = client.post('/profil/pair/join', data={
            'code': 'BADCOD',
            'name': 'PersonB',
            'email': 'b@example.com'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert 'Ugyldig kode' in response.get_data(as_text=True)

    def test_pair_status_check_api(self, client):
        """Test GET /profil/pair/<id>/status/check returns JSON"""
        result = create_pair_session('PersonA', 'a@example.com')

        response = client.get(f'/profil/pair/{result["pair_id"]}/status/check')

        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data
        assert data['status'] == 'waiting'


class TestPerceptionGaps:
    """Tests for perception gap / partner prediction functionality"""

    def test_save_responses_with_type(self):
        """Test saving responses with response_type parameter"""
        result = create_pair_session('PersonA', 'a@example.com')
        session_id = result['session_id']

        questions = get_questions_by_field()
        all_questions = []
        for field, qs in questions.items():
            all_questions.extend(qs)

        # Save own responses
        own_responses = {q['id']: 4 for q in all_questions}
        save_responses(session_id, own_responses, response_type='own')

        # Save predictions
        pred_responses = {q['id']: 6 for q in all_questions}
        save_responses(session_id, pred_responses, response_type='prediction')

        # Verify both types were saved
        from db_profil import get_responses_by_type
        own = get_responses_by_type(session_id, 'own')
        pred = get_responses_by_type(session_id, 'prediction')

        assert len(own) == len(all_questions)
        assert len(pred) == len(all_questions)
        assert all(v == 4 for v in own.values())
        assert all(v == 6 for v in pred.values())

    def test_calculate_perception_gaps_no_predictions(self):
        """Test perception gaps returns empty when no predictions exist"""
        # Create pair with only 'own' responses
        result = create_pair_session('PersonA', 'a@example.com')
        join_result = join_pair_session(result['pair_code'], 'PersonB', 'b@example.com')

        questions = get_questions_by_field()
        all_questions = []
        for field, qs in questions.items():
            all_questions.extend(qs)

        responses = {q['id']: 4 for q in all_questions}
        save_responses(result['session_id'], responses, response_type='own')
        complete_session(result['session_id'])
        save_responses(join_result['session_id'], responses, response_type='own')
        complete_session(join_result['session_id'])

        # Calculate gaps
        gaps = calculate_perception_gaps(result['session_id'], join_result['session_id'])

        assert gaps is not None
        assert gaps['has_predictions'] == False
        assert len(gaps['biggest_surprises']) == 0

    def test_calculate_perception_gaps_with_predictions(self):
        """Test perception gaps calculation with predictions"""
        # Create pair
        result = create_pair_session('Anna', 'anna@example.com')
        join_result = join_pair_session(result['pair_code'], 'Bo', 'bo@example.com')

        questions = get_questions_by_field()
        all_questions = []
        for field, qs in questions.items():
            all_questions.extend(qs)

        # Anna's own scores and predictions
        anna_own = {q['id']: 3 for q in all_questions}
        anna_pred = {q['id']: 3 for q in all_questions}  # Tror Bo svarer 3
        save_responses(result['session_id'], anna_own, response_type='own')
        save_responses(result['session_id'], anna_pred, response_type='prediction')
        complete_session(result['session_id'])

        # Bo's own scores (different from Anna's prediction) and predictions
        bo_own = {q['id']: 6 for q in all_questions}  # Bo svarer faktisk 6 (gap = 3!)
        bo_pred = {q['id']: 3 for q in all_questions}  # Tror Anna svarer 3 (korrekt)
        save_responses(join_result['session_id'], bo_own, response_type='own')
        save_responses(join_result['session_id'], bo_pred, response_type='prediction')
        complete_session(join_result['session_id'])

        # Calculate gaps
        gaps = calculate_perception_gaps(result['session_id'], join_result['session_id'])

        assert gaps is not None
        assert gaps['has_predictions'] == True
        assert gaps['name_a'] == 'Anna'
        assert gaps['name_b'] == 'Bo'

        # Anna guessed wrong about Bo (predicted 3, actual 6)
        assert len(gaps['a_gaps']) > 0
        for qid, gap_data in gaps['a_gaps'].items():
            assert gap_data['predicted'] == 3
            assert gap_data['actual'] == 6
            assert gap_data['gap'] == 3  # Bo scored higher
            assert gap_data['abs_gap'] == 3

        # Bo guessed correctly about Anna (predicted 3, actual 3)
        for qid, gap_data in gaps['b_gaps'].items():
            assert gap_data['gap'] == 0  # Correct guess

        # Should have surprises from Anna's wrong guesses
        assert len(gaps['biggest_surprises']) > 0
        for surprise in gaps['biggest_surprises']:
            assert surprise['person_guessing'] == 'Anna'
            assert surprise['person_surprising'] == 'Bo'
            assert surprise['abs_gap'] >= 2

    def test_perception_gaps_biggest_surprises_sorted(self):
        """Test that biggest surprises are sorted by gap size"""
        result = create_pair_session('PersonA', 'a@example.com')
        join_result = join_pair_session(result['pair_code'], 'PersonB', 'b@example.com')

        questions = get_questions_by_field()
        all_questions = []
        for field, qs in questions.items():
            all_questions.extend(qs)

        # Create varying gaps
        a_own = {}
        a_pred = {}
        b_own = {}
        b_pred = {}

        for i, q in enumerate(all_questions):
            a_own[q['id']] = 4
            b_pred[q['id']] = 4  # B guesses correctly

            # A's predictions vary: some wrong, some right
            if i < 3:
                a_pred[q['id']] = 1  # Big gap (5)
                b_own[q['id']] = 6
            elif i < 6:
                a_pred[q['id']] = 3  # Medium gap (2)
                b_own[q['id']] = 5
            else:
                a_pred[q['id']] = 4  # No gap
                b_own[q['id']] = 4

        save_responses(result['session_id'], a_own, response_type='own')
        save_responses(result['session_id'], a_pred, response_type='prediction')
        complete_session(result['session_id'])

        save_responses(join_result['session_id'], b_own, response_type='own')
        save_responses(join_result['session_id'], b_pred, response_type='prediction')
        complete_session(join_result['session_id'])

        gaps = calculate_perception_gaps(result['session_id'], join_result['session_id'])

        # Biggest surprises should be sorted descending by abs_gap
        surprises = gaps['biggest_surprises']
        assert len(surprises) == 3  # Max 3 surprises
        assert surprises[0]['abs_gap'] >= surprises[1]['abs_gap']
        if len(surprises) > 2:
            assert surprises[1]['abs_gap'] >= surprises[2]['abs_gap']
