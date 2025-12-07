"""
Routes for Friktionsprofil - Screening and Deep Measurement
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db_friktionsprofil import (
    init_friktionsprofil_tables,
    get_screening_questions, create_screening_session,
    save_screening_responses, get_screening_session,
    get_deep_questions, create_deep_session,
    save_deep_responses, get_deep_session
)

# Initialize tables on import
init_friktionsprofil_tables()

# Create Blueprint
friktionsprofil = Blueprint('friktionsprofil', __name__, url_prefix='/friktionsprofil')


# ========================================
# INDEX / MENU
# ========================================

@friktionsprofil.route('/')
def index():
    """Landing page for Friktionsprofil"""
    return render_template('friktionsprofil/index.html')


# ========================================
# SCREENING ROUTES
# ========================================

@friktionsprofil.route('/screening')
def screening():
    """Screening start page"""
    return render_template('friktionsprofil/screening.html', session_id=None)


@friktionsprofil.route('/screening/start', methods=['POST'])
def start_screening():
    """Create screening session and show survey"""
    person_name = request.form.get('person_name')
    person_email = request.form.get('person_email')

    session_id = create_screening_session(
        person_name=person_name,
        person_email=person_email
    )

    questions = get_screening_questions()

    return render_template('friktionsprofil/screening.html',
                          session_id=session_id,
                          questions=questions)


@friktionsprofil.route('/screening/<session_id>/submit', methods=['POST'])
def submit_screening(session_id):
    """Save screening responses and show result"""
    # Collect responses
    responses = {}
    for key, value in request.form.items():
        if key.startswith('S'):
            responses[key] = int(value)

    # Save and calculate scores
    save_screening_responses(session_id, responses)

    return redirect(url_for('friktionsprofil.screening_result', session_id=session_id))


@friktionsprofil.route('/screening/<session_id>/result')
def screening_result(session_id):
    """Show screening result"""
    session_data = get_screening_session(session_id)
    if not session_data:
        flash('Session ikke fundet', 'error')
        return redirect(url_for('friktionsprofil.screening'))

    return render_template('friktionsprofil/screening_result.html', session=session_data)


# ========================================
# DEEP MEASUREMENT ROUTES
# ========================================

SECTION_ORDER = ['A', 'B', 'C', 'D', 'E', 'F']


@friktionsprofil.route('/dyb')
def deep_start():
    """Deep measurement start page"""
    return render_template('friktionsprofil/deep_survey.html', session_id=None)


@friktionsprofil.route('/dyb/start', methods=['POST'])
def start_deep():
    """Create deep session and show first section"""
    person_name = request.form.get('person_name')
    person_email = request.form.get('person_email')

    session_id = create_deep_session(
        person_name=person_name,
        person_email=person_email
    )

    # Initialize session storage for responses
    session[f'deep_{session_id}'] = {}

    return redirect(url_for('friktionsprofil.deep_section', session_id=session_id, section='A'))


@friktionsprofil.route('/dyb/<session_id>/section/<section>')
def deep_section(session_id, section):
    """Show specific section of deep measurement"""
    if section not in SECTION_ORDER:
        return redirect(url_for('friktionsprofil.deep_section', session_id=session_id, section='A'))

    questions = get_deep_questions(section)

    # Get saved responses from session
    saved_responses = session.get(f'deep_{session_id}', {})

    # Calculate prev/next sections
    idx = SECTION_ORDER.index(section)
    prev_section = SECTION_ORDER[idx - 1] if idx > 0 else None

    return render_template('friktionsprofil/deep_survey.html',
                          session_id=session_id,
                          current_section=section,
                          questions=questions,
                          saved_responses=saved_responses,
                          prev_section=prev_section)


@friktionsprofil.route('/dyb/<session_id>/submit', methods=['POST'])
def submit_deep(session_id):
    """Save section responses and move to next section or finish"""
    current_section = request.form.get('current_section', 'A')

    # Get current saved responses
    saved_key = f'deep_{session_id}'
    if saved_key not in session:
        session[saved_key] = {}

    # Save new responses
    for key, value in request.form.items():
        if key.startswith(('A', 'B', 'C', 'D', 'E', 'F')) and len(key) <= 3:
            session[saved_key][key] = int(value)

    # Force session save
    session.modified = True

    # Find next section
    idx = SECTION_ORDER.index(current_section)

    if idx < len(SECTION_ORDER) - 1:
        # Go to next section
        next_section = SECTION_ORDER[idx + 1]
        return redirect(url_for('friktionsprofil.deep_section',
                               session_id=session_id, section=next_section))
    else:
        # All sections done - save to database
        all_responses = session.get(saved_key, {})
        save_deep_responses(session_id, all_responses)

        # Clear session storage
        session.pop(saved_key, None)

        return redirect(url_for('friktionsprofil.deep_result', session_id=session_id))


@friktionsprofil.route('/dyb/<session_id>/result')
def deep_result(session_id):
    """Show deep measurement result"""
    session_data = get_deep_session(session_id)
    if not session_data:
        flash('Session ikke fundet', 'error')
        return redirect(url_for('friktionsprofil.deep_start'))

    return render_template('friktionsprofil/deep_result.html', session=session_data)
