"""
Analyse-funktioner for Friktionskompasset
Håndterer lagdeling (ydre/indre) og avancerede analyser

BEMÆRK: Beregningslogik er nu centraliseret i friction_engine.py
Denne fil wrapper database-operationer og bruger friction_engine funktioner.
"""
from typing import Dict, List, Optional
from db_hierarchical import get_db
from cache import cached

# Import fra central beregningsmotor
from friction_engine import (
    # Konstanter
    FRICTION_FIELDS, QUESTION_LAYERS, THRESHOLDS, SUBSTITUTION_ITEMS,
    # Enums og dataklasser
    Severity, SpreadLevel, FieldScore, GapAnalysis, SubstitutionResult, Warning,
    # Core funktioner
    score_to_percent, percent_to_score, adjust_score,
    get_severity, get_percent_class, get_spread_level,
    calculate_std_dev, calculate_field_scores,
    calculate_gap, check_leader_blocked, analyze_gaps,
    calculate_substitution_for_respondent, calculate_substitution,
    get_warnings, get_start_here_recommendation as engine_get_start_here,
    get_profile_type, to_percent, get_color_class
)


@cached(ttl=300, prefix="stats")
def get_unit_stats_with_layers(
    unit_id: str,
    assessment_id: str,
    respondent_type: str = 'employee',
    include_children: bool = True
) -> Dict:
    """
    Hent statistik med lagdeling (cached i 5 minutter)

    Returns:
        {
            'MENING': {
                'avg_score': 3.2,
                'response_count': 45,
                'std_dev': 1.2,  # Standardafvigelse
                'spread': 'høj',  # 'lav', 'medium', 'høj'
                'all': {spørgsmål}
            },
            'TRYGHED': {
                'avg_score': 2.8,  # Samlet
                'response_count': 45,
                'std_dev': 0.8,
                'spread': 'medium',
                'ydre': {'avg_score': 3.1, 'response_count': 30},
                'indre': {'avg_score': 2.4, 'response_count': 15}
            },
            ...
        }
    """
    with get_db() as conn:
        # Build subtree query
        if include_children:
            subtree_cte = """
                WITH RECURSIVE subtree AS (
                    SELECT id FROM organizational_units WHERE id = ?
                    UNION ALL
                    SELECT ou.id FROM organizational_units ou
                    JOIN subtree st ON ou.parent_id = st.id
                )
            """
            unit_filter = "r.unit_id IN (SELECT id FROM subtree)"
            params = [unit_id, assessment_id, respondent_type]
        else:
            subtree_cte = ""
            unit_filter = "r.unit_id = ?"
            params = [unit_id, assessment_id, respondent_type]

        # Query for aggregated question stats
        query = f"""
            {subtree_cte}
            SELECT
                q.id as question_id,
                q.field,
                q.sequence,
                AVG(CASE
                    WHEN q.reverse_scored = 1 THEN 6 - r.score
                    ELSE r.score
                END) as avg_score,
                COUNT(r.id) as response_count
            FROM questions q
            LEFT JOIN responses r ON q.id = r.question_id
                AND {unit_filter}
                AND r.assessment_id = ?
                AND r.respondent_type = ?
            WHERE q.is_default = 1
            GROUP BY q.id, q.field, q.sequence
            ORDER BY q.sequence
        """

        rows = conn.execute(query, params).fetchall()

        # Query for individual responses (for std dev calculation per field)
        individual_query = f"""
            {subtree_cte}
            SELECT
                q.field,
                CASE
                    WHEN q.reverse_scored = 1 THEN 6 - r.score
                    ELSE r.score
                END as score
            FROM questions q
            JOIN responses r ON q.id = r.question_id
                AND {unit_filter}
                AND r.assessment_id = ?
                AND r.respondent_type = ?
            WHERE q.is_default = 1
        """

        individual_rows = conn.execute(individual_query, params).fetchall()

        # Calculate std dev per field using friction_engine
        field_scores_raw = {}
        for row in individual_rows:
            field = row['field']
            if field not in field_scores_raw:
                field_scores_raw[field] = []
            field_scores_raw[field].append(row['score'])

        field_std_devs = {}
        for field, scores in field_scores_raw.items():
            field_std_devs[field] = calculate_std_dev(scores)

        # Organize by field and layer
        results = {}

        for field, layers in QUESTION_LAYERS.items():
            field_data = {
                'avg_score': 0,
                'response_count': 0
            }

            all_scores = []
            all_counts = []

            for layer_name, question_ids in layers.items():
                layer_rows = [r for r in rows if r['sequence'] in question_ids]

                if layer_rows:
                    layer_scores = [r['avg_score'] for r in layer_rows if r['avg_score'] is not None]
                    layer_count = sum(r['response_count'] for r in layer_rows)

                    if layer_scores:
                        layer_avg = sum(layer_scores) / len(layer_scores)
                        field_data[layer_name] = {
                            'avg_score': round(layer_avg, 1),
                            'response_count': layer_count,
                            'question_count': len(layer_rows)
                        }

                        all_scores.extend(layer_scores)
                        all_counts.append(layer_count)

            # Calculate overall field score
            if all_scores:
                field_data['avg_score'] = round(sum(all_scores) / len(all_scores), 1)
                field_data['response_count'] = sum(all_counts)

            # Add standard deviation and spread classification using friction_engine
            std_dev = field_std_devs.get(field, 0)
            field_data['std_dev'] = round(std_dev, 2)

            # Classify spread using friction_engine
            spread_level = get_spread_level(std_dev)
            field_data['spread'] = spread_level.value  # 'lav', 'medium', eller 'høj'

            results[field] = field_data

        return results


def get_comparison_by_respondent_type(
    unit_id: str,
    assessment_id: str,
    include_children: bool = True
) -> Dict:
    """
    Sammenlign scores på tværs af respondent types

    Returns:
        {
            'MENING': {
                'employee': 2.3,
                'leader_assess': 3.8,
                'leader_self': 3.0,
                'gap': 1.5,  # employee vs leader_assess
                'gap_severity': 'kritisk',  # 'moderat' eller 'kritisk'
                'has_misalignment': True
            },
            ...
        }
    """
    results = {}

    # Hent for hver respondent type
    employee_stats = get_unit_stats_with_layers(unit_id, assessment_id, 'employee', include_children)
    leader_assess_stats = get_unit_stats_with_layers(unit_id, assessment_id, 'leader_assess', include_children)
    leader_self_stats = get_unit_stats_with_layers(unit_id, assessment_id, 'leader_self', include_children)

    for field in FRICTION_FIELDS:
        employee_score = employee_stats.get(field, {}).get('avg_score', 0)
        leader_assess_score = leader_assess_stats.get(field, {}).get('avg_score', 0)
        leader_self_score = leader_self_stats.get(field, {}).get('avg_score', 0)

        # Brug friction_engine til gap-beregning
        gap, gap_severity, has_misalignment = calculate_gap(
            employee_score, leader_assess_score, leader_self_score
        )

        results[field] = {
            'employee': employee_score,
            'leader_assess': leader_assess_score,
            'leader_self': leader_self_score,
            'gap': gap,
            'gap_severity': gap_severity,
            'has_misalignment': has_misalignment
        }

    return results


def get_detailed_breakdown(
    unit_id: str,
    assessment_id: str,
    include_children: bool = True
) -> Dict:
    """
    Komplet breakdown med alle lag og respondent types

    Returns struktureret data klar til dashboard
    """
    return {
        'employee': get_unit_stats_with_layers(unit_id, assessment_id, 'employee', include_children),
        'leader_assess': get_unit_stats_with_layers(unit_id, assessment_id, 'leader_assess', include_children),
        'leader_self': get_unit_stats_with_layers(unit_id, assessment_id, 'leader_self', include_children),
        'comparison': get_comparison_by_respondent_type(unit_id, assessment_id, include_children)
    }


def check_anonymity_threshold(assessment_id: str, unit_id: str) -> Dict:
    """
    Check om anonymitetstærskel er nået

    Returns:
        {
            'can_show_results': True/False,
            'response_count': 7,
            'min_required': 5,
            'missing': 0
        }
    """
    with get_db() as conn:
        # Hent assessment - brug default værdier hvis kolonner mangler
        try:
            assessment = conn.execute("""
                SELECT min_responses, mode
                FROM assessments
                WHERE id = ?
            """, (assessment_id,)).fetchone()
            min_required = assessment['min_responses'] if assessment else 5
            mode = assessment['mode'] if assessment else 'anonymous'
        except Exception:
            # Kolonner findes ikke - brug defaults
            min_required = 5
            mode = 'anonymous'

        # For identified mode, always show
        if mode == 'identified':
            return {'can_show_results': True, 'mode': 'identified'}

        # Count employee responses
        response_count = conn.execute("""
            SELECT COUNT(DISTINCT id) as cnt
            FROM responses
            WHERE assessment_id = ? AND unit_id = ? AND respondent_type = 'employee'
        """, (assessment_id, unit_id)).fetchone()['cnt']

        can_show = response_count >= min_required
        missing = max(0, min_required - response_count)

        return {
            'can_show_results': can_show,
            'response_count': response_count,
            'min_required': min_required,
            'missing': missing,
            'mode': 'anonymous'
        }


@cached(ttl=300, prefix="substitution")
def calculate_substitution_db(unit_id: str, assessment_id: str, respondent_type: str = 'employee') -> Dict:
    """
    Beregn substitution (tid) fra database - wrapper til friction_engine (cached i 5 minutter)

    Returns:
        Dict med response_count, flagged_count, flagged_pct, avg_tid_bias, flagged
    """
    with get_db() as conn:
        # Hent alle responses for denne unit/assessment/type
        responses = conn.execute("""
            SELECT
                r.respondent_name,
                q.sequence,
                q.reverse_scored,
                r.score
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            WHERE r.unit_id = ?
              AND r.assessment_id = ?
              AND r.respondent_type = ?
              AND q.sequence IN (5, 10, 14, 17, 18, 19, 20, 21, 22, 23)
            ORDER BY r.respondent_name, q.sequence
        """, (unit_id, assessment_id, respondent_type)).fetchall()

        if not responses:
            return {
                'tid_mangel': 0,
                'proc': 0,
                'underliggende': 0,
                'kalender_gap': 0,
                'tid_bias': 0,
                'flagged': False,
                'response_count': 0,
                'flagged_count': 0,
                'flagged_pct': 0
            }

        # Grupper per respondent
        respondent_scores = {}
        for row in responses:
            name = row['respondent_name']
            if name not in respondent_scores:
                respondent_scores[name] = {}
            respondent_scores[name][row['sequence']] = row['score']

        # Brug friction_engine til beregning
        result = calculate_substitution(respondent_scores)

        return {
            'response_count': result.response_count,
            'flagged_count': result.flagged_count,
            'flagged_pct': result.flagged_pct,
            'avg_tid_bias': result.avg_tid_bias,
            'flagged': result.flagged
        }


def get_layer_interpretation(field: str, layer: str, score: float) -> str:
    """
    Få fortolkning af en layer-score

    Args:
        field: MENING, TRYGHED, MULIGHED, BESVÆR
        layer: ydre, indre, proces, lethed, all
        score: 1-5

    Returns:
        Menneskevenlig fortolkning
    """
    if score >= 4.0:
        level = "høj"
        implication = "god"
    elif score >= 3.0:
        level = "middel"
        implication = "ok"
    elif score >= 2.0:
        level = "lav"
        implication = "problematisk"
    else:
        level = "meget lav"
        implication = "kritisk"

    interpretations = {
        ('TRYGHED', 'ydre'): f"Psykologisk tryghed er {level} - {implication} social sikkerhed",
        ('TRYGHED', 'indre'): f"Emotionel robusthed er {level} - {implication} håndtering af uvished",
        ('KAN', 'ydre'): f"Ydre kan (rammer) er {level} - {implication} ressourcer og systemer",
        ('KAN', 'indre'): f"Indre kan (evne) er {level} - {implication} viden og kompetencer",
        ('BESVÆR', 'proces'): f"Procesfriktion er {level} - {'lidt bøvl' if level == 'høj' else 'meget bøvl' if level == 'lav' else 'moderat bøvl'}",
        ('BESVÆR', 'lethed'): f"Oplevet lethed er {level} - {'flyder godt' if level == 'høj' else 'opleves tungt' if level == 'lav' else 'ok flow'}",
    }

    key = (field, layer)
    return interpretations.get(key, f"{field} {layer} er {level}")


def get_free_text_comments(unit_id: str, assessment_id: str, include_children: bool = True) -> List[Dict]:
    """
    Hent alle fritekst-kommentarer for en unit/assessment

    Returns:
        [
            {
                'respondent_type': 'employee',
                'respondent_name': 'Respondent #1',
                'comment': 'SITUATION: ...\n\nGENERELT: ...',
                'situation': '...',
                'general': '...'
            },
            ...
        ]
    """
    with get_db() as conn:
        # Build subtree query
        if include_children:
            subtree_cte = """
                WITH RECURSIVE subtree AS (
                    SELECT id FROM organizational_units WHERE id = ?
                    UNION ALL
                    SELECT ou.id FROM organizational_units ou
                    JOIN subtree st ON ou.parent_id = st.id
                )
            """
            unit_filter = "r.unit_id IN (SELECT id FROM subtree)"
            params = [unit_id, assessment_id]
        else:
            subtree_cte = ""
            unit_filter = "r.unit_id = ?"
            params = [unit_id, assessment_id]

        query = f"""
            {subtree_cte}
            SELECT DISTINCT
                r.respondent_type,
                r.respondent_name,
                r.comment
            FROM responses r
            WHERE {unit_filter}
              AND r.assessment_id = ?
              AND r.comment IS NOT NULL
              AND r.comment != ''
            ORDER BY r.respondent_type, r.respondent_name
        """

        rows = conn.execute(query, params).fetchall()

        # Parse SITUATION/GENERELT fra combined comment
        comments = []
        for row in rows:
            comment_text = row['comment']

            # Split SITUATION og GENERELT
            situation = ""
            general = ""

            if "SITUATION:" in comment_text and "GENERELT:" in comment_text:
                parts = comment_text.split("GENERELT:")
                situation = parts[0].replace("SITUATION:", "").strip()
                general = parts[1].strip()
            elif "SITUATION:" in comment_text:
                situation = comment_text.replace("SITUATION:", "").strip()
            elif "GENERELT:" in comment_text:
                general = comment_text.replace("GENERELT:", "").strip()
            else:
                general = comment_text

            comments.append({
                'respondent_type': row['respondent_type'],
                'respondent_name': row['respondent_name'],
                'comment': comment_text,
                'situation': situation,
                'general': general
            })

        return comments


# ============================================
# KKC-INTEGRATION (Anders Trillingsgaard)
# ============================================

# Mapping fra friktionsfelter til KKC-elementer
KKC_MAPPING = {
    'MENING': 'KURS',
    'TRYGHED': 'KOORDINERING',
    'KAN': 'KOORDINERING',
    'BESVÆR': 'COMMITMENT'
}


def get_kkc_recommendations(stats: Dict, comparison: Dict = None) -> List[Dict]:
    """
    Generer KKC-baserede anbefalinger baseret på friktions-scores

    Args:
        stats: Friktions-scores fra get_unit_stats_with_layers()
        comparison: Optional sammenligning mellem respondent types

    Returns:
        Liste af anbefalinger sorteret efter prioritet (højeste friktion først)
        [
            {
                'field': 'MENING',
                'kkc_element': 'KURS',
                'score': 2.1,
                'severity': 'høj',
                'title': 'Start med KURS',
                'problem': '...',
                'actions': ['...', '...', '...'],
                'follow_up': '...',
                'kkc_reference': '...'
            },
            ...
        ]
    """
    recommendations = []

    # Definer anbefalinger for hver friktionstype
    kkc_actions = {
        'MENING': {
            'title': 'Start med KURS',
            'problem': 'Teamet mangler en klar retning - de ved ikke hvorfor opgaverne giver værdi eller hvordan de bidrager til helheden.',
            'actions': [
                '🛑 STOP-øvelse (10 min): "Hvilken opgave giver MINDST mening for dig? Hvad tror du formålet er?"',
                '🎯 Formuler kursen sammen: "Hvordan hjælper dette teams arbejde borgeren/kunden konkret?" Skriv det i ÉN sætning. Hæng den op.',
                '🔗 Kobl opgaver til kursen: For hver tilbagevendende opgave - "Hvordan understøtter dette vores kurs?" Hvis ikke → drop eller redesign.'
            ],
            'follow_up': 'Gentag måling om 6-8 uger. Er Mening-scoren steget? Kan alle svare på "Hvorfor gør vi det her?"',
            'kkc_reference': 'Anders Trillingsgaard: Kurs handler om retning og mening - "Hvorfor gør vi det?"'
        },
        'TRYGHED': {
            'title': 'Styrk KOORDINERING gennem psykologisk tryghed',
            'problem': 'Folk holder ting for sig selv eller er bange for at dele usikkerhed. Dårligt samarbejde og manglende åbenhed.',
            'actions': [
                '👥 "Hvem-kan-hvad"-tavle: Synliggør hvem der ved hvad. Gør det trygt at spørge.',
                '🔄 Ugentlig check-in: 15 min - "Hvad er du i tvivl om?" Normaliser at det er OK ikke at vide.',
                '🎓 Fejl-deling: Én gang om måneden - "Hvad lærte vi af en fejl?" Normaliser at alle laver fejl.'
            ],
            'follow_up': 'Observér: Begynder folk at spørge højt i stedet for at gætte? Deles fejl åbent?',
            'kkc_reference': 'Anders Trillingsgaard: Koordinering handler om samarbejde og klarhed - "Hvem gør hvad?"'
        },
        'KAN': {
            'title': 'Styrk KOORDINERING gennem bedre evne og rammer',
            'problem': 'Folk kan ikke gøre deres arbejde ordentligt - de mangler enten evner (indre kan) eller værktøjer og rammer (ydre kan).',
            'actions': [
                '🗺️ Kortlæg mangler: Lav en liste - "Hvad mangler I for at KUNNE gøre jeres arbejde?" Opdel i: hvad kan I ikke? vs. hvad har I ikke?',
                '📚 "Kan-kort": Hvem kan hvad? Hvor er viden og værktøjer? Gør det synligt.',
                '🔧 Fikse én ting ad gangen: Vælg ÉN manglende evne eller ressource. Træn eller skaff den inden næste måned.'
            ],
            'follow_up': 'Kan folk bedre gøre deres arbejde? Er både evner (indre) og rammer (ydre) på plads?',
            'kkc_reference': 'Anders Trillingsgaard: Koordinering handler om at kunne levere - både evne og ressourcer skal være til stede.'
        },
        'BESVÆR': {
            'title': 'Styrk COMMITMENT gennem systemforenkling',
            'problem': 'Systemet passer ikke til virkeligheden - folk omgår regler, laver dobbeltarbejde eller bruger workarounds.',
            'actions': [
                '🔍 Identificér workarounds: "Hvilke regler/procedurer følger I IKKE? Hvorfor?"',
                '✂️ Forenkl én procedure ad gangen: Vælg den mest irriterende. Fjern unødige trin.',
                '🤝 Skab commitment: "Kan vi alle blive enige om at gøre det på denne måde?" Hvis ikke - hvorfor?'
            ],
            'follow_up': 'Stopper folk med at omgå reglerne? Er procedurerne enklere? Føles systemet mere realistisk?',
            'kkc_reference': 'Anders Trillingsgaard: Commitment handler om at systemet matcher virkeligheden - "Kan vi levere det vi siger ja til?"'
        }
    }

    # Beregn prioritet for hver friktion
    for field in ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']:
        score = stats.get(field, {}).get('avg_score', 0)

        if score == 0:
            continue

        # Bestem severity baseret på THRESHOLDS fra friction_engine
        severity_enum = get_severity(score)
        if severity_enum == Severity.HIGH:
            severity = 'høj'
            severity_emoji = '🔴'
        elif severity_enum == Severity.MEDIUM:
            severity = 'medium'
            severity_emoji = '🟡'
        else:
            severity = 'lav'
            severity_emoji = '🟢'

        actions = kkc_actions.get(field, {})

        recommendation = {
            'field': field,
            'kkc_element': KKC_MAPPING[field],
            'score': score,
            'severity': severity,
            'severity_emoji': severity_emoji,
            'title': actions.get('title', ''),
            'problem': actions.get('problem', ''),
            'actions': actions.get('actions', []),
            'follow_up': actions.get('follow_up', ''),
            'kkc_reference': actions.get('kkc_reference', '')
        }

        # Tilføj layer-info hvis relevant
        field_data = stats.get(field, {})
        if 'ydre' in field_data:
            recommendation['ydre_score'] = field_data['ydre']['avg_score']
        if 'indre' in field_data:
            recommendation['indre_score'] = field_data['indre']['avg_score']

        # Tilføj spredning
        recommendation['std_dev'] = field_data.get('std_dev', 0)
        recommendation['spread'] = field_data.get('spread', 'lav')

        # Tilføj gap hvis comparison findes
        if comparison and field in comparison:
            recommendation['gap'] = comparison[field].get('gap', 0)
            recommendation['has_misalignment'] = comparison[field].get('has_misalignment', False)

        recommendations.append(recommendation)

    # Sortér efter severity (høj først) og derefter score (lavest først)
    severity_order = {'høj': 0, 'medium': 1, 'lav': 2}
    recommendations.sort(key=lambda x: (severity_order[x['severity']], x['score']))

    return recommendations


def get_start_here_recommendation(recommendations: List[Dict]) -> Optional[Dict]:
    """
    Find den vigtigste anbefaling at starte med baseret på friktionshierarki.

    RETURNERER DICT MED:
    - single: True/False - om der er én klar prioritet eller flere ligeværdige
    - primary: Dict med hovedanbefaling (hvis single=True)
    - recommendations: List af ligeværdige anbefalinger (hvis single=False)
    - reason: Forklaring på prioriteringen

    FRIKTIONSHIERARKI (vigtighed):
    1. TRYGHED - Vigtigst! Uden tryghed hjælper intet andet
    2. MENING - Næstvigtigst. Giver retning og motivation
    3. KAN - Kompetencer og ressourcer
    4. BESVÆR - Processer og systemer (ofte nemmest at fikse)

    LOGIK:
    - Hvis Tryghed eller Mening er lav → Start der (uanset andre scores)
    - Hvis Tryghed/Mening er OK → Kan og Besvær kan tackles, Besvær er ofte nemmest
    - Hvis alle scores er tætte (< 0.4 spænd) → Anbefal at starte med Besvær (nemmest)

    Returns:
        Dict med prioriteringsinfo, eller None hvis ingen problemer
    """
    # Hierarki: Tryghed → Mening → Kan → Besvær
    PRIORITY_ORDER = {'TRYGHED': 1, 'MENING': 2, 'KAN': 3, 'BESVÆR': 4}

    if not recommendations:
        return None

    # Filtrer til kun høj og medium severity (under 70%)
    problems = [rec for rec in recommendations if rec['severity'] in ['høj', 'medium']]

    if not problems:
        return None

    # Hvis kun én, returner den
    if len(problems) == 1:
        return {
            'single': True,
            'primary': problems[0],
            'reason': 'Kun ét friktionsområde under 70%'
        }

    # Check om ALLE problemer har meget tætte scores (< 0.4 range)
    all_scores = [r['score'] for r in problems]
    total_range = max(all_scores) - min(all_scores)

    # Hjælpefunktion til at finde felt-prioritet
    def get_priority(field):
        return PRIORITY_ORDER.get(field, 99)

    if total_range < 0.4:
        # Alle scores er tætte - brug hierarkiet til at prioritere
        # Check om Tryghed eller Mening er blandt problemerne
        tryghed_problem = next((p for p in problems if p['field'] == 'TRYGHED'), None)
        mening_problem = next((p for p in problems if p['field'] == 'MENING'), None)

        if tryghed_problem:
            # Tryghed er lav - start der
            return {
                'single': True,
                'primary': tryghed_problem,
                'reason': f'Scores er tætte (spænd: {total_range:.1f}), men TRYGHED er fundamentet – start der.'
            }
        elif mening_problem:
            # Mening er lav - start der
            return {
                'single': True,
                'primary': mening_problem,
                'reason': f'Scores er tætte (spænd: {total_range:.1f}), men MENING giver retning – start der.'
            }
        else:
            # Kun Kan/Besvær er problemer - Besvær er ofte nemmest at fikse
            besvaer_problem = next((p for p in problems if p['field'] == 'BESVÆR'), None)
            if besvaer_problem:
                return {
                    'single': True,
                    'primary': besvaer_problem,
                    'reason': f'Scores er tætte (spænd: {total_range:.1f}). BESVÆR er ofte nemmest at fikse – start der for hurtige gevinster.'
                }
            else:
                # Kun Kan tilbage
                return {
                    'single': True,
                    'primary': problems[0],
                    'reason': f'Scores er tætte (spænd: {total_range:.1f}). Start med KAN for at styrke kompetencer.'
                }

    # Gruppér efter severity
    high = [r for r in problems if r['severity'] == 'høj']
    medium = [r for r in problems if r['severity'] == 'medium']

    # Start med højeste severity gruppe
    top_group = high if high else medium

    if len(top_group) == 1:
        return {
            'single': True,
            'primary': top_group[0],
            'reason': f'Eneste {top_group[0]["severity"]} friktion (under {"50%" if top_group[0]["severity"] == "høj" else "70%"})'
        }

    # Flere i samme gruppe - brug hierarkiet til at prioritere
    # Tryghed → Mening → Kan → Besvær
    tryghed = next((p for p in top_group if p['field'] == 'TRYGHED'), None)
    mening = next((p for p in top_group if p['field'] == 'MENING'), None)

    if tryghed:
        return {
            'single': True,
            'primary': tryghed,
            'reason': f'TRYGHED er fundamentet – uden tryghed hjælper de andre tiltag ikke.'
        }
    elif mening:
        return {
            'single': True,
            'primary': mening,
            'reason': f'MENING giver retning og motivation – vigtigere end processuelle forbedringer.'
        }
    else:
        # Kun Kan/Besvær - Besvær er ofte nemmest, men hvis Kan er markant værre, tag den
        kan = next((p for p in top_group if p['field'] == 'KAN'), None)
        besvaer = next((p for p in top_group if p['field'] == 'BESVÆR'), None)

        if kan and besvaer:
            # Hvis Kan er markant værre (> 0.3 forskel), prioriter den
            if besvaer['score'] - kan['score'] > 0.3:
                return {
                    'single': True,
                    'primary': kan,
                    'reason': f'KAN er markant lavere end BESVÆR – kompetencer først.'
                }
            else:
                return {
                    'single': True,
                    'primary': besvaer,
                    'reason': f'BESVÆR er ofte nemmest at fikse – start der for hurtige gevinster.'
                }
        elif kan:
            return {
                'single': True,
                'primary': kan,
                'reason': f'Start med KAN for at styrke kompetencer og ressourcer.'
            }
        else:
            return {
                'single': True,
                'primary': besvaer,
                'reason': f'BESVÆR handler om processer og systemer – ofte nemmest at fikse.'
            }


def get_alerts_and_findings(breakdown: Dict, comparison: Dict, substitution: Dict = None) -> List[Dict]:
    """
    Saml alle vigtige advarsler og fund fra analysen

    Returns:
        Liste af alerts sorteret efter alvorlighed
        [
            {
                'severity': 'kritisk' | 'moderat' | 'info',
                'type': 'kritisk_lav_score' | 'gap' | 'spread' | 'blocked' | 'substitution' | 'paradoks',
                'field': 'MENING' | 'TRYGHED' | ...,
                'icon': '🔴',
                'title': 'Kritisk lav score - MENING',
                'description': 'Medarbejdere scorer kun 38% ...',
                'recommendation': 'Start her - dette er det mest akutte problemområde'
            },
            ...
        ]
    """
    alerts = []

    # 1. KRITISK LAV SCORE (< 40% / 2.0)
    for field in FRICTION_FIELDS:
        emp_score = breakdown['employee'].get(field, {}).get('avg_score', 0)
        if emp_score > 0 and emp_score < 2.0:
            alerts.append({
                'severity': 'kritisk',
                'type': 'kritisk_lav_score',
                'field': field,
                'icon': '🔴',
                'title': f'Kritisk lav score - {field}',
                'description': f'Medarbejdere scorer kun {int(emp_score/5*100)}% ({emp_score:.1f}/5). Dette er under kritisk tærskel (40%).',
                'recommendation': 'Dette er et akut problemområde der kræver øjeblikkelig handling.'
            })

    # 2. GAP - LEDER/MEDARBEJDER UENIGHED
    for field in FRICTION_FIELDS:
        comp = comparison.get(field, {})
        gap_severity = comp.get('gap_severity')
        gap = comp.get('gap', 0)
        emp = comp.get('employee', 0)
        leader = comp.get('leader_assess', 0)

        if gap_severity:
            direction = "undervurderer" if emp < leader else "overvurderer"
            severity_map = {'kritisk': 'kritisk', 'moderat': 'moderat'}

            alerts.append({
                'severity': severity_map.get(gap_severity, 'moderat'),
                'type': 'gap',
                'field': field,
                'icon': '⚠️',
                'title': f'{gap_severity.title()} forskel - {field}',
                'description': f'Medarbejdere: {int(emp/5*100)}% | Leder vurderer: {int(leader/5*100)}% (forskel: {int(gap*20)}%).',
                'recommendation': f'Lederen {direction} teamets {field.lower()}-friktioner. Dialog nødvendig.'
            })

    # 3. HØJ SPREDNING
    for field in FRICTION_FIELDS:
        field_data = breakdown['employee'].get(field, {})
        spread = field_data.get('spread')
        std_dev = field_data.get('std_dev', 0)

        if spread == 'høj':
            alerts.append({
                'severity': 'moderat',
                'type': 'spread',
                'field': field,
                'icon': '📊',
                'title': f'Høj spredning - {field}',
                'description': f'Standardafvigelse: {std_dev:.2f}. Meget uensartet oplevelse i teamet.',
                'recommendation': 'Nogle har det godt, andre dårligt. Undersøg forskelle mellem medarbejdere - potentiel konflikt eller ulige arbejdsvilkår.'
            })

    # 4. BLOCKED LEADER
    for field in FRICTION_FIELDS:
        emp = breakdown['employee'].get(field, {}).get('avg_score', 0)
        leader_self = breakdown['leader_self'].get(field, {}).get('avg_score', 0)

        # Brug friction_engine til blocked check
        if check_leader_blocked(emp, leader_self):
            alerts.append({
                'severity': 'moderat',
                'type': 'blocked',
                'field': field,
                'icon': '🚧',
                'title': f'Leder blokeret - {field}',
                'description': f'Team: {int(emp/5*100)}% | Leder selv: {int(leader_self/5*100)}%. Begge under 70%.',
                'recommendation': 'Lederen har samme friktioner som teamet og kan ikke effektivt hjælpe. Leder bør først adressere egne friktioner.'
            })

    # 5. LEDER PARADOKS (leder selv meget forskellig fra vurdering af team)
    for field in FRICTION_FIELDS:
        leader_assess = breakdown['leader_assess'].get(field, {}).get('avg_score', 0)
        leader_self = breakdown['leader_self'].get(field, {}).get('avg_score', 0)
        paradox_gap = abs(leader_self - leader_assess)

        if paradox_gap >= THRESHOLDS['gap_significant']:  # 20% forskel
            direction = "højere" if leader_self > leader_assess else "lavere"
            alerts.append({
                'severity': 'info',
                'type': 'paradoks',
                'field': field,
                'icon': '🤔',
                'title': f'Leder paradoks - {field}',
                'description': f'Leder vurderer team: {int(leader_assess/5*100)}% | Leder selv: {int(leader_self/5*100)}% (forskel: {int(paradox_gap*20)}%).',
                'recommendation': f'Lederen oplever {direction} {field.lower()}-friktion end teamet. Dette kan påvirke lederens forståelse af teamets situation.'
            })

    # 6. SUBSTITUTION
    if substitution and substitution.get('flagged'):
        count = substitution.get('flagged_count', 0)
        total = substitution.get('response_count', 0)
        pct = substitution.get('flagged_pct', 0)

        alerts.append({
            'severity': 'moderat',
            'type': 'substitution',
            'field': None,
            'icon': '💡',
            'title': 'Substitution detekteret',
            'description': f'{count} af {total} medarbejdere ({pct:.0f}%) substituerer - siger "jeg mangler tid" men mener "jeg er utilfreds".',
            'recommendation': 'Adresser MENING/TRYGHED/KAN - IKKE proces-optimering. Effektivisering vil ikke hjælpe.'
        })

    # Sortér: kritisk > moderat > info
    severity_order = {'kritisk': 0, 'moderat': 1, 'info': 2}
    alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))

    return alerts


# ============================================
# TEST FUNKTIONER
# ============================================

if __name__ == "__main__":
    # Test med en assessment
    test_assessment_id = "assess-kOh-b8KuRRM"
    test_unit_id = "unit-jDE1s_J-Ot8"

    print("="*60)
    print("TEST: LAGDELT ANALYSE")
    print("="*60)

    breakdown = get_detailed_breakdown(test_unit_id, test_assessment_id)

    print("\n[EMPLOYEE PERSPECTIVE]")
    for field, data in breakdown['employee'].items():
        print(f"\n{field}:")
        print(f"  Overall: {data['avg_score']}")
        for layer, layer_data in data.items():
            if layer not in ['avg_score', 'response_count'] and isinstance(layer_data, dict):
                print(f"    {layer}: {layer_data['avg_score']} ({layer_data['response_count']} svar)")

    print("\n[COMPARISON]")
    for field, comp in breakdown['comparison'].items():
        print(f"\n{field}:")
        print(f"  Employee: {comp['employee']}")
        print(f"  Leader assess: {comp['leader_assess']}")
        print(f"  Gap: {comp['gap']} {'⚠️ MISALIGNMENT' if comp['has_misalignment'] else '✓'}")


# ============================================
# TREND ANALYSE
# ============================================

def get_trend_data(unit_id: str = None, customer_id: str = None) -> Dict:
    """
    Hent trend-data: friktionsscores over tid for sammenligning.

    Args:
        unit_id: Specifik unit at analysere (valgfri)
        customer_id: Filtrer på kunde (valgfri)

    Returns:
        {
            'assessments': [
                {
                    'id': 'assess-xxx',
                    'name': 'Måling Q1',
                    'period': 'Q1 2025',
                    'date': '2025-01-15',
                    'unit_name': 'Herning Kommune',
                    'response_count': 45,
                    'scores': {
                        'MENING': 3.2,
                        'TRYGHED': 2.8,
                        'KAN': 3.5,
                        'BESVÆR': 2.1
                    }
                },
                ...
            ],
            'fields': ['TRYGHED', 'MENING', 'KAN', 'BESVÆR'],
            'summary': {
                'total_assessments': 5,
                'date_range': '2024-06 til 2025-03'
            }
        }
    """
    with get_db() as conn:
        # Build filter
        filters = []
        params = []

        if unit_id:
            # Include unit and all children
            filters.append("""
                c.target_unit_id IN (
                    WITH RECURSIVE subtree AS (
                        SELECT id FROM organizational_units WHERE id = ?
                        UNION ALL
                        SELECT ou.id FROM organizational_units ou
                        JOIN subtree st ON ou.parent_id = st.id
                    )
                    SELECT id FROM subtree
                )
            """)
            params.append(unit_id)

        if customer_id:
            filters.append("ou.customer_id = ?")
            params.append(customer_id)

        # Only include group measurements (gruppe_friktion) in trend
        filters.append("c.assessment_type_id = 'gruppe_friktion'")

        where_clause = " AND ".join(filters) if filters else "1=1"

        # Get assessments with response counts
        assessments_query = f"""
            SELECT
                c.id,
                c.name,
                c.period,
                DATE(c.created_at) as date,
                c.target_unit_id,
                ou.name as unit_name,
                ou.full_path,
                COUNT(DISTINCT r.id) as response_count
            FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            LEFT JOIN responses r ON r.assessment_id = c.id
            WHERE {where_clause}
            GROUP BY c.id
            HAVING response_count > 0
            ORDER BY c.created_at ASC
        """

        assessments_raw = conn.execute(assessments_query, params).fetchall()

        if not assessments_raw:
            return {
                'assessments': [],
                'fields': ['TRYGHED', 'MENING', 'KAN', 'BESVÆR'],
                'summary': {'total_assessments': 0, 'date_range': '-'}
            }

        assessments = []
        for camp in assessments_raw:
            # Get field averages for this assessment
            scores_query = """
                SELECT
                    q.field,
                    AVG(CASE
                        WHEN q.reverse_scored = 1 THEN 6 - r.score
                        ELSE r.score
                    END) as avg_score
                FROM responses r
                JOIN questions q ON r.question_id = q.id
                WHERE r.assessment_id = ?
                GROUP BY q.field
            """
            score_rows = conn.execute(scores_query, (camp['id'],)).fetchall()

            scores = {}
            for row in score_rows:
                scores[row['field']] = round(row['avg_score'], 2)

            assessments.append({
                'id': camp['id'],
                'name': camp['name'],
                'period': camp['period'],
                'date': camp['date'],
                'unit_id': camp['target_unit_id'],
                'unit_name': camp['unit_name'],
                'full_path': camp['full_path'],
                'response_count': camp['response_count'],
                'scores': scores
            })

        # Aggregate by period for cleaner trend visualization
        period_data = {}
        for a in assessments:
            period = a['period'] or a['date']
            if period not in period_data:
                period_data[period] = {
                    'period': period,
                    'date': a['date'],
                    'scores': {f: [] for f in ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']},
                    'unit_count': 0,
                    'units': []
                }
            period_data[period]['unit_count'] += 1
            period_data[period]['units'].append(a['unit_name'])
            for field, score in a.get('scores', {}).items():
                if score is not None:
                    period_data[period]['scores'][field].append(score)

        # Calculate averages per period
        aggregated = []
        for period, data in sorted(period_data.items(), key=lambda x: x[1]['date'] or ''):
            avg_scores = {}
            for field, scores in data['scores'].items():
                if scores:
                    avg_scores[field] = round(sum(scores) / len(scores), 2)
            aggregated.append({
                'period': data['period'],
                'date': data['date'],
                'scores': avg_scores,
                'unit_count': data['unit_count'],
                'units': data['units']
            })

        # Calculate summary
        dates = [c['date'] for c in assessments if c['date']]
        date_range = f"{min(dates)} til {max(dates)}" if dates else "-"

        return {
            'assessments': aggregated,  # Now aggregated by period
            'raw_assessments': assessments,  # Keep raw data if needed
            'fields': ['TRYGHED', 'MENING', 'KAN', 'BESVÆR'],
            'summary': {
                'total_assessments': len(assessments),
                'total_periods': len(aggregated),
                'date_range': date_range
            }
        }


def get_unit_trend(unit_id: str) -> Dict:
    """
    Hent trend for specifik unit (og children) over alle kampagner.

    Returns:
        {
            'unit_name': 'Herning Kommune',
            'assessments': [...],  # Sorteret efter dato
            'trend': {
                'MENING': {'first': 3.0, 'last': 3.5, 'change': +0.5, 'direction': 'up'},
                ...
            }
        }
    """
    data = get_trend_data(unit_id=unit_id)

    if not data['assessments']:
        return {
            'unit_name': 'Ukendt',
            'assessments': [],
            'trend': {}
        }

    unit_name = data['assessments'][0]['unit_name'] if data['assessments'] else 'Ukendt'

    # Calculate trend for each field
    trend = {}
    for field in data['fields']:
        scores = [c['scores'].get(field) for c in data['assessments'] if c['scores'].get(field)]
        if len(scores) >= 2:
            first = scores[0]
            last = scores[-1]
            change = round(last - first, 2)
            direction = 'up' if change > 0.1 else ('down' if change < -0.1 else 'stable')
            trend[field] = {
                'first': first,
                'last': last,
                'change': change,
                'direction': direction
            }
        elif len(scores) == 1:
            trend[field] = {
                'first': scores[0],
                'last': scores[0],
                'change': 0,
                'direction': 'stable'
            }

    return {
        'unit_name': unit_name,
        'assessments': data['assessments'],
        'trend': trend
    }
