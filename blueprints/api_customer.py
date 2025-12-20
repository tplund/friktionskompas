"""
Customer API v1 blueprint - REST API for Enterprise customers.

Routes:
- GET  /api/v1/assessments - List assessments
- POST /api/v1/assessments - Create assessment
- GET  /api/v1/assessments/<id> - Get assessment details
- GET  /api/v1/assessments/<id>/results - Get assessment results
- GET  /api/v1/units - List organizational units
- GET  /api/v1/export - Bulk data export
"""

import secrets
import hashlib
import uuid
import csv
import io
from datetime import datetime
from flask import Blueprint, jsonify, request, g, Response

from auth_helpers import customer_api_required, customer_api_write_required
from db_hierarchical import get_db, get_unit_stats, get_assessment_overview
from friction_engine import score_to_percent, get_severity

api_customer_bp = Blueprint('api_customer', __name__, url_prefix='/api/v1')


@api_customer_bp.route('/assessments', methods=['GET'])
@customer_api_required
def api_v1_list_assessments():
    """
    List assessments for customer.

    Query params:
        - status: Filter by status (sent, completed, scheduled)
        - limit: Max results (default 50, max 100)
        - offset: Pagination offset

    Returns:
        {"data": [...], "meta": {"limit": 50, "offset": 0, "total": 123}}
    """
    customer_id = g.api_customer_id

    status_filter = request.args.get('status')
    try:
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return jsonify({'error': 'Invalid limit or offset', 'code': 'VALIDATION_ERROR'}), 400

    with get_db() as conn:
        status_clause = ""
        params = [customer_id]
        if status_filter:
            status_clause = "AND a.status = ?"
            params.append(status_filter)

        total = conn.execute(f"""
            SELECT COUNT(*) as cnt FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE ou.customer_id = ? {status_clause}
        """, params).fetchone()['cnt']

        assessments = conn.execute(f"""
            SELECT a.id, a.name, a.period, a.status, a.assessment_type_id,
                   a.created_at, a.sent_at, a.scheduled_at,
                   ou.id as unit_id, ou.name as unit_name, ou.full_path,
                   a.include_leader_assessment,
                   COUNT(DISTINCT t.token) as tokens_sent,
                   COUNT(DISTINCT CASE WHEN t.is_used = 1 THEN t.token END) as tokens_used
            FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            LEFT JOIN tokens t ON t.assessment_id = a.id
            WHERE ou.customer_id = ? {status_clause}
            GROUP BY a.id
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        data = []
        for a in assessments:
            data.append({
                'id': a['id'],
                'name': a['name'],
                'period': a['period'],
                'status': a['status'],
                'type': a['assessment_type_id'],
                'unit': {
                    'id': a['unit_id'],
                    'name': a['unit_name'],
                    'path': a['full_path']
                },
                'tokens_sent': a['tokens_sent'],
                'tokens_used': a['tokens_used'],
                'response_rate': round(a['tokens_used'] / a['tokens_sent'] * 100, 1) if a['tokens_sent'] > 0 else 0,
                'include_leader': bool(a['include_leader_assessment']),
                'created_at': a['created_at'],
                'sent_at': a['sent_at'],
                'scheduled_at': a['scheduled_at']
            })

    return jsonify({
        'data': data,
        'meta': {'limit': limit, 'offset': offset, 'total': total}
    })


@api_customer_bp.route('/assessments/<assessment_id>', methods=['GET'])
@customer_api_required
def api_v1_get_assessment(assessment_id):
    """Get single assessment details."""
    customer_id = g.api_customer_id

    with get_db() as conn:
        assessment = conn.execute("""
            SELECT a.*, ou.name as unit_name, ou.full_path, ou.customer_id
            FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE a.id = ? AND ou.customer_id = ?
        """, (assessment_id, customer_id)).fetchone()

        if not assessment:
            return jsonify({'error': 'Assessment not found', 'code': 'NOT_FOUND'}), 404

        token_stats = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as used
            FROM tokens WHERE assessment_id = ?
        """, (assessment_id,)).fetchone()

        response_count = conn.execute("""
            SELECT COUNT(DISTINCT id) as cnt FROM responses WHERE assessment_id = ?
        """, (assessment_id,)).fetchone()['cnt']

    return jsonify({
        'data': {
            'id': assessment['id'],
            'name': assessment['name'],
            'period': assessment['period'],
            'status': assessment['status'],
            'type': assessment['assessment_type_id'],
            'unit': {
                'id': assessment['target_unit_id'],
                'name': assessment['unit_name'],
                'path': assessment['full_path']
            },
            'settings': {
                'min_responses': assessment['min_responses'],
                'mode': assessment['mode'],
                'include_leader_assessment': bool(assessment['include_leader_assessment']),
                'include_leader_self': bool(assessment['include_leader_self'])
            },
            'tokens': {
                'sent': token_stats['total'] or 0,
                'used': token_stats['used'] or 0
            },
            'response_count': response_count,
            'created_at': assessment['created_at'],
            'sent_at': assessment['sent_at'],
            'scheduled_at': assessment['scheduled_at']
        }
    })


@api_customer_bp.route('/assessments/<assessment_id>/results', methods=['GET'])
@customer_api_required
def api_v1_get_assessment_results(assessment_id):
    """Get assessment results with friction scores."""
    customer_id = g.api_customer_id
    include_units = request.args.get('include_units', 'false').lower() == 'true'

    with get_db() as conn:
        assessment = conn.execute("""
            SELECT a.*, ou.name as unit_name, ou.full_path, ou.customer_id
            FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE a.id = ? AND ou.customer_id = ?
        """, (assessment_id, customer_id)).fetchone()

        if not assessment:
            return jsonify({'error': 'Assessment not found', 'code': 'NOT_FOUND'}), 404

        stats = get_unit_stats(assessment['target_unit_id'], assessment_id, include_children=True)

        scores = {}
        response_count = 0
        for field in ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']:
            field_data = next((s for s in stats if s['field'] == field), None)
            if field_data:
                score = field_data['avg_score']
                severity = get_severity(score)
                scores[field] = {
                    'score': round(score, 2) if score else None,
                    'percent': score_to_percent(score) if score else None,
                    'severity': severity.name if score else None,
                    'response_count': field_data['response_count']
                }
                response_count = max(response_count, field_data['response_count'])
            else:
                scores[field] = {'score': None, 'percent': None, 'severity': None, 'response_count': 0}

        result = {
            'assessment': {
                'id': assessment['id'],
                'name': assessment['name'],
                'period': assessment['period'],
                'unit_name': assessment['unit_name']
            },
            'scores': scores,
            'response_count': response_count
        }

        if include_units:
            unit_overview = get_assessment_overview(assessment_id)
            result['unit_breakdown'] = [
                {
                    'id': u['id'],
                    'name': u['name'],
                    'path': u['full_path'],
                    'tokens_sent': u['tokens_sent'],
                    'tokens_used': u['tokens_used'],
                    'besvær_score': round(u['besvær_score'], 2) if u['besvær_score'] else None
                }
                for u in unit_overview
            ]

    return jsonify({'data': result})


@api_customer_bp.route('/units', methods=['GET'])
@customer_api_required
def api_v1_list_units():
    """Get organizational structure for customer."""
    customer_id = g.api_customer_id
    flat_mode = request.args.get('flat', 'false').lower() == 'true'
    parent_id = request.args.get('parent_id')

    with get_db() as conn:
        where_clause = "ou.customer_id = ?"
        params = [customer_id]

        if parent_id:
            where_clause += " AND ou.parent_id = ?"
            params.append(parent_id)

        units = conn.execute(f"""
            SELECT ou.id, ou.name, ou.full_path, ou.level, ou.parent_id,
                   ou.leader_name, ou.leader_email, ou.employee_count,
                   ou.sick_leave_percent, ou.created_at,
                   (SELECT COUNT(*) FROM organizational_units sub WHERE sub.parent_id = ou.id) as child_count
            FROM organizational_units ou
            WHERE {where_clause}
            ORDER BY ou.full_path
        """, params).fetchall()

        data = []
        for u in units:
            data.append({
                'id': u['id'],
                'name': u['name'],
                'path': u['full_path'],
                'level': u['level'],
                'parent_id': u['parent_id'],
                'leader': {
                    'name': u['leader_name'],
                    'email': u['leader_email']
                } if u['leader_name'] else None,
                'employee_count': u['employee_count'],
                'sick_leave_percent': u['sick_leave_percent'],
                'child_count': u['child_count'],
                'created_at': u['created_at']
            })

        if not flat_mode and not parent_id:
            units_by_id = {u['id']: u for u in data}
            roots = []
            for u in data:
                u['children'] = []
            for u in data:
                if u['parent_id'] and u['parent_id'] in units_by_id:
                    units_by_id[u['parent_id']]['children'].append(u)
                else:
                    roots.append(u)
            data = roots

    return jsonify({
        'data': data,
        'meta': {
            'total': len(units) if flat_mode else len(data),
            'mode': 'flat' if flat_mode else 'hierarchical'
        }
    })


@api_customer_bp.route('/assessments', methods=['POST'])
@customer_api_required
@customer_api_write_required
def api_v1_create_assessment():
    """Create a new assessment."""
    customer_id = g.api_customer_id
    data = request.get_json()

    if not data:
        return jsonify({'error': 'JSON body required', 'code': 'VALIDATION_ERROR'}), 400

    required = ['name', 'period', 'target_unit_id']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({
            'error': f'Missing required fields: {", ".join(missing)}',
            'code': 'VALIDATION_ERROR'
        }), 400

    with get_db() as conn:
        unit = conn.execute("""
            SELECT id, name FROM organizational_units
            WHERE id = ? AND customer_id = ?
        """, (data['target_unit_id'], customer_id)).fetchone()

        if not unit:
            return jsonify({
                'error': 'Target unit not found or not accessible',
                'code': 'NOT_FOUND'
            }), 404

        assessment_id = f"assess-{secrets.token_urlsafe(8)}"

        conn.execute("""
            INSERT INTO assessments (id, name, period, target_unit_id, assessment_type_id,
                                    include_leader_assessment, min_responses, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')
        """, (
            assessment_id,
            data['name'],
            data['period'],
            data['target_unit_id'],
            data.get('type', 'gruppe_friktion'),
            1 if data.get('include_leader_assessment') else 0,
            data.get('min_responses', 5)
        ))

    return jsonify({
        'data': {
            'id': assessment_id,
            'name': data['name'],
            'period': data['period'],
            'target_unit_id': data['target_unit_id'],
            'status': 'draft'
        },
        'message': 'Assessment created successfully'
    }), 201


@api_customer_bp.route('/export', methods=['GET'])
@customer_api_required
def api_v1_export():
    """
    API endpoint for bulk data export.

    Query params:
        - format: json (default) or csv
        - anonymization: none, pseudonymized (default), or full
        - assessment_id: Optional filter to specific assessment
        - include_responses: true/false (default true)
        - include_scores: true/false (default true)
        - include_questions: true/false (default true)
        - include_units: true/false (default false)
    """
    customer_id = g.api_customer_id
    export_format = request.args.get('format', 'json')
    anonymization = request.args.get('anonymization', 'pseudonymized')
    assessment_id = request.args.get('assessment_id')

    include_responses = request.args.get('include_responses', 'true').lower() == 'true'
    include_scores = request.args.get('include_scores', 'true').lower() == 'true'
    include_questions = request.args.get('include_questions', 'true').lower() == 'true'
    include_units = request.args.get('include_units', 'false').lower() == 'true'

    if anonymization not in ['none', 'pseudonymized', 'full']:
        return jsonify({'error': 'Invalid anonymization level', 'code': 'INVALID_PARAM'}), 400

    def anonymize_email(email, level):
        if level == 'none':
            return email
        elif level == 'pseudonymized':
            hash_bytes = hashlib.sha256(email.encode()).digest()[:16]
            return str(uuid.UUID(bytes=hash_bytes))
        else:
            return None

    def anonymize_unit_name(name, unit_id, level):
        if level == 'full':
            return f"unit_{unit_id}"
        return name

    with get_db() as conn:
        export_data = {
            'export_date': datetime.now().isoformat(),
            'export_version': '1.0',
            'anonymization_level': anonymization
        }

        where_conditions = ["ou.customer_id = ?"]
        params = [customer_id]

        if assessment_id:
            where_conditions.append("a.id = ?")
            params.append(assessment_id)

        where_clause = " AND ".join(where_conditions)

        if include_responses:
            responses = conn.execute(f"""
                SELECT r.id as response_id, r.question_id, r.score,
                       r.created_at as response_date, r.respondent_name, r.respondent_type,
                       a.id as assessment_id, a.name as assessment_name, a.period,
                       ou.id as unit_id, ou.name as unit_name
                FROM responses r
                JOIN assessments a ON r.assessment_id = a.id
                JOIN organizational_units ou ON r.unit_id = ou.id
                WHERE {where_clause}
                ORDER BY r.created_at
            """, params).fetchall()

            export_data['responses'] = [
                {
                    'response_id': r['response_id'],
                    'question_id': r['question_id'],
                    'score': r['score'],
                    'response_date': r['response_date'],
                    'respondent_id': anonymize_email(r['respondent_name'] or '', anonymization) if r['respondent_name'] else None,
                    'is_leader': r['respondent_type'] == 'leader',
                    'assessment_id': r['assessment_id'],
                    'unit_id': r['unit_id'],
                    'unit_name': anonymize_unit_name(r['unit_name'], r['unit_id'], anonymization),
                }
                for r in responses
            ]

        if include_scores:
            scores = conn.execute(f"""
                SELECT a.id as assessment_id, ou.id as unit_id, ou.name as unit_name, q.field,
                       AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                       COUNT(DISTINCT r.respondent_name) as response_count
                FROM responses r
                JOIN assessments a ON r.assessment_id = a.id
                JOIN organizational_units ou ON r.unit_id = ou.id
                JOIN questions q ON r.question_id = q.id
                WHERE {where_clause}
                GROUP BY a.id, ou.id, q.field
            """, params).fetchall()

            export_data['aggregated_scores'] = [
                {
                    'assessment_id': s['assessment_id'],
                    'unit_id': s['unit_id'],
                    'unit_name': anonymize_unit_name(s['unit_name'], s['unit_id'], anonymization),
                    'field': s['field'],
                    'score': round(s['avg_score'], 2) if s['avg_score'] else None,
                    'percent': round(score_to_percent(s['avg_score']), 1) if s['avg_score'] else None,
                    'response_count': s['response_count']
                }
                for s in scores
            ]

        if include_questions:
            questions = conn.execute("""
                SELECT id, sequence, field, text_da, text_en, reverse_scored
                FROM questions WHERE is_default = 1 ORDER BY sequence
            """).fetchall()

            export_data['questions'] = [dict(q) for q in questions]

        if include_units:
            units = conn.execute("""
                SELECT id, name, full_path, parent_id, level
                FROM organizational_units WHERE customer_id = ?
            """, (customer_id,)).fetchall()

            export_data['units'] = [
                {
                    'id': u['id'],
                    'name': anonymize_unit_name(u['name'], u['id'], anonymization),
                    'path': u['full_path'] if anonymization != 'full' else None,
                    'parent_id': u['parent_id'],
                    'level': u['level']
                }
                for u in units
            ]

    if export_format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')

        if include_responses and 'responses' in export_data:
            writer.writerow(['response_id', 'question_id', 'score', 'response_date',
                           'respondent_id', 'is_leader', 'assessment_id', 'unit_id', 'unit_name'])
            for r in export_data['responses']:
                writer.writerow([r['response_id'], r['question_id'], r['score'], r['response_date'],
                               r['respondent_id'], r['is_leader'], r['assessment_id'], r['unit_id'], r['unit_name']])

        return Response(
            '\ufeff' + output.getvalue(),
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': 'attachment; filename=export.csv'}
        )

    return jsonify({'data': export_data})
