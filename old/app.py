"""
Friktionskompas - Flask App
"""
from flask import Flask, render_template, request, redirect, url_for, flash
from db import init_db, get_questions, save_response, get_response_count, get_field_stats, clear_all_responses, get_db
from demo_data import generate_demo_responses
from analysis import get_recommendation, get_color_class, format_field_name

app = Flask(__name__)
app.secret_key = 'friktionskompas-demo-secret-key-2025'

# Initialize database on first run
with app.app_context():
    init_db()


@app.route('/')
def index():
    """Medarbejder-interface: Besvar spørgsmål"""
    questions = get_questions()
    
    # Gruppér spørgsmål efter felt
    by_field = {}
    for q in questions:
        field = q['field']
        if field not in by_field:
            by_field[field] = []
        by_field[field].append(q)
    
    return render_template('index.html', 
                         questions=questions,
                         by_field=by_field,
                         format_field_name=format_field_name)


@app.route('/submit', methods=['POST'])
def submit():
    """Gem svar"""
    team_id = request.form.get('team_id', 'team-a').strip()
    period = request.form.get('period', '2025Q4').strip()
    
    questions = get_questions()
    
    # Gem hvert svar
    for q in questions:
        q_id = q['id']
        score = int(request.form.get(f'score_{q_id}', '3'))
        comment = request.form.get(f'comment_{q_id}', '').strip()
        
        save_response(team_id, period, q_id, score, comment if comment else None)
    
    flash('Tak for dine svar! De er gemt anonymt.', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    """Leder-dashboard: RÅ DATA - bare spørgsmål og svar"""
    team_id = request.args.get('team_id', 'team-demo')
    period = request.args.get('period', '2025Q4')
    
    # Tæl antal svar
    count = get_response_count(team_id, period)
    
    # Hent statistik (kun hvis >= 5 svar)
    stats = []
    question_results = []
    
    if count >= 5:
        stats = get_field_stats(team_id, period)
        
        # Hent ALLE spørgsmål med deres svar-fordeling
        questions = get_questions()
        
        with get_db() as conn:
            for q in questions:
                # Hent svar-fordeling for dette spørgsmål
                rows = conn.execute("""
                    SELECT 
                        r.score,
                        COUNT(*) as count,
                        GROUP_CONCAT(r.comment, '|||') as comments
                    FROM responses r
                    WHERE r.team_id = ? AND r.period = ? AND r.question_id = ?
                    GROUP BY r.score
                    ORDER BY r.score
                """, (team_id, period, q['id'])).fetchall()
                
                # Beregn hvor mange svarede i hver kategori
                total = sum(row['count'] for row in rows)
                agree_count = sum(row['count'] for row in rows if row['score'] <= 2)  # 1-2 = enig
                disagree_count = sum(row['count'] for row in rows if row['score'] >= 4)  # 4-5 = uenig
                
                # Justér for reverse-scored spørgsmål
                if q['reverse_scored']:
                    agree_count, disagree_count = disagree_count, agree_count
                
                # Hent alle kommentarer
                all_comments = []
                for row in rows:
                    if row['comments']:
                        all_comments.extend([c.strip() for c in row['comments'].split('|||') if c.strip()])
                
                question_results.append({
                    'field': q['field'],
                    'text': q['text_da'],
                    'reverse_scored': q['reverse_scored'],
                    'total': total,
                    'agree_count': agree_count,
                    'disagree_count': disagree_count,
                    'comments': all_comments[:3],  # Max 3 kommentarer
                    'avg_score': sum(row['score'] * row['count'] for row in rows) / total if total > 0 else 0
                })
        
        # Gruppér spørgsmål efter felt
        by_field = {}
        for qr in question_results:
            field = qr['field']
            if field not in by_field:
                by_field[field] = []
            by_field[field].append(qr)
    
    return render_template('dashboard_raw.html',
                         team_id=team_id,
                         period=period,
                         count=count,
                         stats=stats,
                         by_field=by_field,
                         get_color_class=get_color_class,
                         format_field_name=format_field_name)


@app.route('/demo/quick', methods=['POST'])
def demo_quick():
    """Hurtig demo: Ryd data + generer 10 svar + gå til dashboard"""
    team_id = 'team-demo'
    period = '2025Q4'
    sector = request.form.get('sector', 'generic')
    
    # Ryd eksisterende
    clear_all_responses()
    
    # Generer 10 nye med sektor-specifikke kommentarer
    generate_demo_responses(team_id, period, 10, sector)
    
    sector_names = {
        'generic': 'generiske',
        'ældrepleje': 'ældrepleje',
        'skole': 'skole'
    }
    sector_name = sector_names.get(sector, sector)
    
    flash(f'✅ Genereret 10 demo-svar med {sector_name} kommentarer!', 'success')
    return redirect(url_for('dashboard', team_id=team_id, period=period))


@app.route('/demo/clear', methods=['POST'])
def demo_clear():
    """Ryd alle data"""
    clear_all_responses()
    flash('🗑️ Alle data slettet', 'info')
    return redirect(url_for('index'))


@app.route('/debug')
def debug():
    """Debug-side: Se alle individuelle svar (kun til testfasen)"""
    team_id = request.args.get('team_id', 'team-demo')
    period = request.args.get('period', '2025Q4')
    
    # Hent alle svar med spørgsmålstekst
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                r.id,
                r.created_at,
                q.field,
                q.text_da,
                q.reverse_scored,
                r.score,
                CASE 
                    WHEN q.reverse_scored = 1 THEN 6 - r.score 
                    ELSE r.score 
                END as adjusted_score,
                r.comment
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            WHERE r.team_id = ? AND r.period = ?
            ORDER BY r.created_at DESC, q.sequence
        """, (team_id, period)).fetchall()
    
    # Gruppér efter tidspunkt (approx respondent)
    from collections import defaultdict
    by_time = defaultdict(list)
    for row in rows:
        # Gruppér efter minut (approx samme person)
        time_key = row['created_at'][:16] if row['created_at'] else 'unknown'
        by_time[time_key].append(dict(row))
    
    respondents = list(by_time.values())
    
    return render_template('debug.html',
                         team_id=team_id,
                         period=period,
                         respondents=respondents,
                         format_field_name=format_field_name)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
