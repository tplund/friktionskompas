"""
Tests for Par-måling (Pair Assessment) functionality.

Tests cover:
- Creating pair sessions
- Joining pair sessions with codes
- Status updates
- Comparison generation
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
from analysis_profil import compare_profiles


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
