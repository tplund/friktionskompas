"""
Spørgeskema-app for Friktionskompasset
Respondenter udfylder via token-link
"""
from flask import Flask, render_template, request, redirect, url_for, flash
import os
import secrets
from db_hierarchical import (
    validate_and_use_token, save_response, get_questions, get_db
)

app = Flask(__name__)

# Sikker secret key fra miljøvariabel (fallback til autogeneret i development)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)


@app.route('/preview')
def preview():
    """Preview mode - kræver ikke token"""
    respondent_type = request.args.get('type', 'employee')

    # Hent spørgsmål
    questions = get_questions()

    # Instruktioner baseret på respondent type
    instructions = {
        'employee': {
            'title': 'Medarbejder-spørgeskema',
            'instruction': 'Svar ud fra din egen oplevelse af arbejdet',
            'description': 'Besvar spørgsmålene ærligt baseret på hvordan DU oplever din arbejdssituation.'
        },
        'leader_assess': {
            'title': 'Leder: Vurdering af teamet',
            'instruction': 'Svar IKKE om dig selv, men om hvad du tror dine medarbejdere oplever',
            'description': 'Forestil dig gennemsnitsmedarbejderen i dit team. Hvad ville de svare på disse spørgsmål?'
        },
        'leader_self': {
            'title': 'Leder: Egne friktioner',
            'instruction': 'Svar om dine EGNE friktioner som leder',
            'description': 'Har DU de værktøjer, den tryghed og mening du skal bruge for at lede godt?'
        }
    }

    instr = instructions.get(respondent_type, instructions['employee'])

    return render_template('survey.html',
        token='preview',
        questions=questions,
        respondent_type=respondent_type,
        respondent_name='Preview',
        title=instr['title'],
        instruction=instr['instruction'],
        description=instr['description'],
        is_preview=True
    )


@app.route('/')
def index():
    """Landing page - kræver token"""
    token = request.args.get('token')

    if not token:
        return render_template('survey_error.html',
            error="Ingen token angivet. Du skal have et link fra din organisation.")

    # Valider token
    token_data = validate_and_use_token(token)

    if not token_data:
        return render_template('survey_error.html',
            error="Ugyldig eller allerede brugt token.")

    # Hent spørgsmål
    questions = get_questions()

    # Hent respondent type og navn
    with get_db() as conn:
        token_info = conn.execute("""
            SELECT respondent_type, respondent_name, campaign_id, unit_id
            FROM tokens
            WHERE token = ?
        """, (token,)).fetchone()

    respondent_type = token_info['respondent_type']
    respondent_name = token_info['respondent_name']

    # Instruktioner baseret på respondent type
    instructions = {
        'employee': {
            'title': 'Medarbejder-spørgeskema',
            'instruction': 'Svar ud fra din egen oplevelse af arbejdet',
            'description': 'Besvar spørgsmålene ærligt baseret på hvordan DU oplever din arbejdssituation.'
        },
        'leader_assess': {
            'title': 'Leder: Vurdering af teamet',
            'instruction': 'Svar IKKE om dig selv, men om hvad du tror dine medarbejdere oplever',
            'description': 'Forestil dig gennemsnitsmedarbejderen i dit team. Hvad ville de svare på disse spørgsmål?'
        },
        'leader_self': {
            'title': 'Leder: Egne friktioner',
            'instruction': 'Svar om dine EGNE friktioner som leder',
            'description': 'Har DU de værktøjer, den tryghed og mening du skal bruge for at lede godt?'
        }
    }

    instr = instructions.get(respondent_type, instructions['employee'])

    return render_template('survey.html',
        token=token,
        questions=questions,
        respondent_type=respondent_type,
        respondent_name=respondent_name,
        title=instr['title'],
        instruction=instr['instruction'],
        description=instr['description'],
        is_preview=False
    )


@app.route('/submit', methods=['POST'])
def submit():
    """Gem svar"""
    token = request.form.get('token')

    if not token:
        flash('Ingen token angivet', 'error')
        return redirect(url_for('index'))

    # Hent token info
    with get_db() as conn:
        token_info = conn.execute("""
            SELECT campaign_id, unit_id, respondent_type, respondent_name, is_used
            FROM tokens
            WHERE token = ?
        """, (token,)).fetchone()

        if not token_info:
            flash('Ugyldig token', 'error')
            return redirect(url_for('index'))

        if token_info['is_used']:
            flash('Token allerede brugt', 'error')
            return redirect(url_for('index'))

    campaign_id = token_info['campaign_id']
    unit_id = token_info['unit_id']
    respondent_type = token_info['respondent_type']
    respondent_name = token_info['respondent_name']

    # Hent fritekst-svar
    free_text_situation = request.form.get('free_text_situation', '').strip()
    free_text_general = request.form.get('free_text_general', '').strip()

    # Kombiner fritekst
    combined_comment = ""
    if free_text_situation:
        combined_comment += f"SITUATION: {free_text_situation}"
    if free_text_general:
        if combined_comment:
            combined_comment += "\n\n"
        combined_comment += f"GENERELT: {free_text_general}"

    # Gem alle svar
    questions = get_questions()
    saved_count = 0

    for question in questions:
        q_id = question['id']
        score = request.form.get(f'q_{q_id}')

        if score:
            score = int(score)

            # Gem svar med respondent_type, navn og fritekst (kun på første svar)
            with get_db() as conn:
                # Tilføj fritekst til første response
                comment = combined_comment if saved_count == 0 and combined_comment else None

                conn.execute("""
                    INSERT INTO responses
                    (campaign_id, unit_id, question_id, score, respondent_type, respondent_name, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (campaign_id, unit_id, q_id, score, respondent_type, respondent_name, comment))

            saved_count += 1

    # Marker token som brugt
    with get_db() as conn:
        conn.execute("""
            UPDATE tokens
            SET is_used = 1, used_at = CURRENT_TIMESTAMP
            WHERE token = ?
        """, (token,))

    return render_template('survey_thanks.html',
        saved_count=saved_count,
        respondent_type=respondent_type
    )


if __name__ == '__main__':
    app.run(debug=True, port=5002)
