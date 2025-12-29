"""
Analyse-funktioner for Friktionsprofil
Beregner farvegrid, båndbredde, manifestationslag og fortolkninger
"""
from typing import Dict, List, Optional, Tuple
from db_profil import get_response_matrix, get_session, get_responses_by_type, get_pair_session

# Konstanter
FIELDS = ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']
LAYERS = ['BIOLOGI', 'EMOTION', 'INDRE', 'KOGNITION']

# Farve-mapping (fra prototype-dokument)
COLOR_THRESHOLDS = {
    'green': (1.0, 2.2),   # Robust / lav presfølsomhed
    'yellow': (2.3, 3.7),  # Sensitiv / svingende
    'orange': (3.8, 5.0),  # Lav tærskel / sårbart
}

# Danske labels
FIELD_LABELS = {
    'TRYGHED': 'Tryghed',
    'MENING': 'Mening',
    'KAN': 'Kan',
    'BESVÆR': 'Besvær'
}

LAYER_LABELS = {
    'BIOLOGI': 'Biologi',
    'EMOTION': 'Emotion',
    'INDRE': 'Indre',
    'KOGNITION': 'Kognition'
}

COLOR_LABELS = {
    'green': 'Robust',
    'yellow': 'Sensitiv',
    'orange': 'Sårbar'
}


def score_to_color(score: float) -> str:
    """Konverter score til farve"""
    if score <= 2.2:
        return 'green'
    elif score <= 3.7:
        return 'yellow'
    else:
        return 'orange'


def get_color_matrix(session_id: str) -> Dict[str, Dict[str, str]]:
    """
    Hent farvegrid for en session
    Returnerer: {felt: {lag: farve}}
    """
    score_matrix = get_response_matrix(session_id)

    color_matrix = {}
    for field in FIELDS:
        color_matrix[field] = {}
        for layer in LAYERS:
            score = score_matrix.get(field, {}).get(layer)
            if score is not None:
                color_matrix[field][layer] = score_to_color(score)
            else:
                color_matrix[field][layer] = 'unknown'

    return color_matrix


def analyze_column(field: str, layer_scores: Dict[str, float]) -> Dict:
    """
    Analyser en enkelt friktionssøjle (et felt på tværs af lag)
    """
    colors = {layer: score_to_color(score) for layer, score in layer_scores.items()}

    # Find manifestationslag (første orange nedefra)
    manifestation = None
    for layer in LAYERS:  # BIOLOGI -> EMOTION -> INDRE -> KOGNITION
        if colors.get(layer) == 'orange':
            manifestation = layer
            break

    # Beregn gennemsnitsscore for feltet
    scores = list(layer_scores.values())
    avg_score = sum(scores) / len(scores) if scores else 0

    # Beregn båndbredde (kogn - bio)
    bio_score = layer_scores.get('BIOLOGI', 3)
    kogn_score = layer_scores.get('KOGNITION', 3)
    bandwidth = kogn_score - bio_score  # Negativ = pres sidder i kroppen

    return {
        'field': field,
        'scores': layer_scores,
        'colors': colors,
        'manifestation_layer': manifestation,
        'avg_score': round(avg_score, 2),
        'bandwidth': round(bandwidth, 2),
        'overall_color': score_to_color(avg_score)
    }


def get_full_analysis(session_id: str) -> Dict:
    """
    Fuld analyse af en friktionsprofil
    """
    session = get_session(session_id)
    if not session:
        return None

    score_matrix = get_response_matrix(session_id)

    # Analyser hver søjle
    columns = {}
    for field in FIELDS:
        layer_scores = score_matrix.get(field, {})
        columns[field] = analyze_column(field, layer_scores)

    # Samlet profil-analyse
    all_scores = []
    for field_data in columns.values():
        all_scores.extend(field_data['scores'].values())

    total_avg = sum(all_scores) / len(all_scores) if all_scores else 0

    # Find dominerende manifestationslag
    manifestations = [c['manifestation_layer'] for c in columns.values() if c['manifestation_layer']]
    dominant_manifestation = max(set(manifestations), key=manifestations.count) if manifestations else None

    # Beregn samlet båndbredde
    bandwidths = [c['bandwidth'] for c in columns.values()]
    avg_bandwidth = sum(bandwidths) / len(bandwidths) if bandwidths else 0

    return {
        'session': session,
        'score_matrix': score_matrix,
        'color_matrix': get_color_matrix(session_id),
        'columns': columns,
        'summary': {
            'total_avg_score': round(total_avg, 2),
            'overall_color': score_to_color(total_avg),
            'dominant_manifestation': dominant_manifestation,
            'avg_bandwidth': round(avg_bandwidth, 2),
            'bandwidth_interpretation': interpret_bandwidth(avg_bandwidth)
        },
        'interpretations': generate_interpretations(columns)
    }


def interpret_bandwidth(bandwidth: float) -> str:
    """Fortolk båndbredde-score"""
    if bandwidth >= 1.0:
        return "Høj båndbredde - pres kan løftes op i kognition"
    elif bandwidth >= -0.5:
        return "Moderat båndbredde - svingende evne til at løfte pres"
    else:
        return "Lav båndbredde - pres sætter sig ofte i de dybe lag"


def generate_interpretations(columns: Dict) -> Dict[str, str]:
    """
    Generer tekstuelle fortolkninger for hver søjle
    """
    interpretations = {}

    for field, data in columns.items():
        colors = data['colors']
        manifestation = data['manifestation_layer']
        bandwidth = data['bandwidth']

        parts = []

        # Analysér mønster
        orange_count = sum(1 for c in colors.values() if c == 'orange')
        green_count = sum(1 for c in colors.values() if c == 'green')

        if orange_count >= 3:
            parts.append(f"{FIELD_LABELS[field]}-friktion er høj i hele søjlen")
        elif orange_count == 0 and green_count >= 3:
            parts.append(f"{FIELD_LABELS[field]}-søjlen er robust")
        else:
            # Beskriv hvor friktionen sidder
            orange_layers = [l for l, c in colors.items() if c == 'orange']
            if orange_layers:
                layer_names = [LAYER_LABELS[l] for l in orange_layers]
                parts.append(f"{FIELD_LABELS[field]}-friktion manifesterer i {', '.join(layer_names)}")

        # Manifestationslag
        if manifestation:
            parts.append(f"Pres stopper typisk i {LAYER_LABELS[manifestation]}-laget")

        # Båndbredde
        if bandwidth < -1:
            parts.append("Lav båndbredde mellem krop og kognition")
        elif bandwidth > 1:
            parts.append("God båndbredde - kan regulere via forståelse")

        interpretations[field] = ". ".join(parts) if parts else "Balanceret profil"

    return interpretations


def compare_profiles(session_id_1: str, session_id_2: str) -> Dict:
    """
    Sammenlign to profiler og identificer forskelle
    """
    analysis_1 = get_full_analysis(session_id_1)
    analysis_2 = get_full_analysis(session_id_2)

    if not analysis_1 or not analysis_2:
        return None

    differences = {}

    for field in FIELDS:
        field_diff = {
            'layers': {},
            'significant_gaps': []
        }

        for layer in LAYERS:
            score_1 = analysis_1['score_matrix'].get(field, {}).get(layer, 0)
            score_2 = analysis_2['score_matrix'].get(field, {}).get(layer, 0)
            diff = score_2 - score_1

            color_1 = analysis_1['color_matrix'].get(field, {}).get(layer, 'unknown')
            color_2 = analysis_2['color_matrix'].get(field, {}).get(layer, 'unknown')

            field_diff['layers'][layer] = {
                'score_1': score_1,
                'score_2': score_2,
                'difference': round(diff, 2),
                'color_1': color_1,
                'color_2': color_2,
                'color_changed': color_1 != color_2
            }

            # Markér signifikante forskelle
            if abs(diff) >= 1.5:
                direction = "højere" if diff > 0 else "lavere"
                field_diff['significant_gaps'].append(
                    f"{LAYER_LABELS[layer]}: Person 2 er {abs(diff):.1f} point {direction}"
                )

        differences[field] = field_diff

    # Generer sammenlignings-indsigter
    insights = generate_comparison_insights(analysis_1, analysis_2, differences)

    return {
        'profile_1': analysis_1,
        'profile_2': analysis_2,
        'differences': differences,
        'insights': insights
    }


def generate_comparison_insights(analysis_1: Dict, analysis_2: Dict, differences: Dict) -> List[str]:
    """
    Generer indsigter baseret på sammenligning
    """
    insights = []

    name_1 = analysis_1['session'].get('person_name', 'Person 1')
    name_2 = analysis_2['session'].get('person_name', 'Person 2')

    # Sammenlign manifestationslag
    manifest_1 = analysis_1['summary']['dominant_manifestation']
    manifest_2 = analysis_2['summary']['dominant_manifestation']

    if manifest_1 and manifest_2 and manifest_1 != manifest_2:
        insights.append(
            f"{name_1} manifesterer typisk i {LAYER_LABELS.get(manifest_1, manifest_1)}, "
            f"mens {name_2} manifesterer i {LAYER_LABELS.get(manifest_2, manifest_2)}. "
            f"Dette kan give friktion i kommunikation."
        )

    # Sammenlign båndbredde
    bw_1 = analysis_1['summary']['avg_bandwidth']
    bw_2 = analysis_2['summary']['avg_bandwidth']
    bw_diff = abs(bw_1 - bw_2)

    if bw_diff >= 1.5:
        higher = name_1 if bw_1 > bw_2 else name_2
        lower = name_2 if bw_1 > bw_2 else name_1
        insights.append(
            f"{higher} har markant højere båndbredde end {lower}. "
            f"{higher} kan lettere løfte pres til kognition, mens {lower} "
            f"oftere regulerer fra de dybere lag."
        )

    # Find felter med størst forskel
    for field, diff_data in differences.items():
        if diff_data['significant_gaps']:
            insights.append(
                f"I {FIELD_LABELS[field]}-feltet: " + "; ".join(diff_data['significant_gaps'])
            )

    # Potentielle konfliktpunkter
    for field in FIELDS:
        col_1 = analysis_1['columns'][field]
        col_2 = analysis_2['columns'][field]

        # Hvis den ene er robust og den anden sårbar i samme felt
        if col_1['overall_color'] == 'green' and col_2['overall_color'] == 'orange':
            insights.append(
                f"I {FIELD_LABELS[field]} er {name_1} robust mens {name_2} er sårbar. "
                f"{name_1} kan have svært ved at forstå {name_2}s reaktioner på dette felt."
            )
        elif col_2['overall_color'] == 'green' and col_1['overall_color'] == 'orange':
            insights.append(
                f"I {FIELD_LABELS[field]} er {name_2} robust mens {name_1} er sårbar. "
                f"{name_2} kan have svært ved at forstå {name_1}s reaktioner på dette felt."
            )

    return insights


def calculate_perception_gaps(session_id_a: str, session_id_b: str) -> Optional[Dict]:
    """
    Beregner perception gaps mellem to par-profiler.

    For hver person: sammenlign hvad partneren gættede (prediction)
    med hvad personen faktisk svarede (own).

    Returns:
        {
            'a_gaps': {question_id: {predicted, actual, gap, question_text}},
            'b_gaps': {question_id: {predicted, actual, gap, question_text}},
            'biggest_surprises': [
                {
                    'surprised_person': 'A'/'B',
                    'surprised_name': str,
                    'guesser_name': str,
                    'question_text': str,
                    'field': str,
                    'predicted': int,
                    'actual': int,
                    'gap': int,
                    'insight': str
                }
            ]
        }
    """
    # Hent sessions
    session_a = get_session(session_id_a)
    session_b = get_session(session_id_b)
    if not session_a or not session_b:
        return None

    name_a = session_a.get('person_name') or 'Person A'
    name_b = session_b.get('person_name') or 'Person B'

    # Hent svar
    # A's egne svar og B's gæt på A
    a_own = {r['question_id']: r for r in get_responses_by_type(session_id_a, 'own')}
    b_predictions_for_a = {r['question_id']: r for r in get_responses_by_type(session_id_b, 'prediction')}

    # B's egne svar og A's gæt på B
    b_own = {r['question_id']: r for r in get_responses_by_type(session_id_b, 'own')}
    a_predictions_for_b = {r['question_id']: r for r in get_responses_by_type(session_id_a, 'prediction')}

    # Beregn gaps for A (B gættede på A)
    a_gaps = {}
    for q_id, own_resp in a_own.items():
        pred_resp = b_predictions_for_a.get(q_id)
        if pred_resp:
            gap = own_resp['score'] - pred_resp['score']
            a_gaps[q_id] = {
                'predicted': pred_resp['score'],
                'actual': own_resp['score'],
                'gap': gap,
                'abs_gap': abs(gap),
                'question_text': own_resp.get('text_da', ''),
                'field': own_resp.get('field', ''),
                'layer': own_resp.get('layer', ''),
                'guesser': name_b,
                'owner': name_a
            }

    # Beregn gaps for B (A gættede på B)
    b_gaps = {}
    for q_id, own_resp in b_own.items():
        pred_resp = a_predictions_for_b.get(q_id)
        if pred_resp:
            gap = own_resp['score'] - pred_resp['score']
            b_gaps[q_id] = {
                'predicted': pred_resp['score'],
                'actual': own_resp['score'],
                'gap': gap,
                'abs_gap': abs(gap),
                'question_text': own_resp.get('text_da', ''),
                'field': own_resp.get('field', ''),
                'layer': own_resp.get('layer', ''),
                'guesser': name_a,
                'owner': name_b
            }

    # Find de største overraskelser (|gap| >= 2)
    all_gaps = []

    for q_id, gap_data in a_gaps.items():
        if gap_data['abs_gap'] >= 2:
            all_gaps.append({
                'surprised_person': 'A',
                'surprised_name': name_a,
                'guesser_name': name_b,
                'question_id': q_id,
                'question_text': gap_data['question_text'],
                'field': gap_data['field'],
                'layer': gap_data['layer'],
                'predicted': gap_data['predicted'],
                'actual': gap_data['actual'],
                'gap': gap_data['gap'],
                'abs_gap': gap_data['abs_gap'],
                'insight': generate_gap_insight(
                    name_a, name_b, gap_data['gap'],
                    gap_data['question_text'], gap_data['field']
                )
            })

    for q_id, gap_data in b_gaps.items():
        if gap_data['abs_gap'] >= 2:
            all_gaps.append({
                'surprised_person': 'B',
                'surprised_name': name_b,
                'guesser_name': name_a,
                'question_id': q_id,
                'question_text': gap_data['question_text'],
                'field': gap_data['field'],
                'layer': gap_data['layer'],
                'predicted': gap_data['predicted'],
                'actual': gap_data['actual'],
                'gap': gap_data['gap'],
                'abs_gap': gap_data['abs_gap'],
                'insight': generate_gap_insight(
                    name_b, name_a, gap_data['gap'],
                    gap_data['question_text'], gap_data['field']
                )
            })

    # Sorter efter absolut gap og tag top 3
    all_gaps.sort(key=lambda x: x['abs_gap'], reverse=True)
    biggest_surprises = all_gaps[:3]

    return {
        'a_gaps': a_gaps,
        'b_gaps': b_gaps,
        'biggest_surprises': biggest_surprises,
        'total_gap_count': len([g for g in all_gaps if g['abs_gap'] >= 2]),
        'name_a': name_a,
        'name_b': name_b
    }


def generate_gap_insight(surprised_name: str, guesser_name: str,
                         gap: int, question_text: str, field: str) -> str:
    """
    Genererer indsigtstekst for en perception gap
    """
    field_label = FIELD_LABELS.get(field, field)

    if gap > 0:
        # Surprised person scorede højere end gættet (mere friktion)
        if gap >= 3:
            return f"{surprised_name} oplever betydeligt mere {field_label.lower()}-friktion end {guesser_name} troede."
        else:
            return f"{surprised_name} oplever mere {field_label.lower()}-friktion end {guesser_name} forventede."
    else:
        # Surprised person scorede lavere end gættet (mindre friktion)
        if gap <= -3:
            return f"{surprised_name} oplever betydeligt mindre {field_label.lower()}-friktion end {guesser_name} troede."
        else:
            return f"{surprised_name} er mere robust på dette punkt end {guesser_name} forventede."


def calculate_meta_gaps(session_id_a: str, session_id_b: str) -> Optional[Dict]:
    """
    Beregner meta-perception gaps (udvidet mode).

    For hver person: sammenlign hvad de tror partneren tror om dem (meta)
    med hvad partneren faktisk gættede (prediction).

    Dette afslører "blinde pletter" - hvor er der forskel mellem
    hvad personen tror andre ser, og hvad andre faktisk ser?

    Returns:
        {
            'a_blind_spots': [...],  # Hvor A misforstår hvad B tror
            'b_blind_spots': [...],  # Hvor B misforstår hvad A tror
            'biggest_blind_spots': Top 3 med indsigtstekster
        }
    """
    # Hent sessions
    session_a = get_session(session_id_a)
    session_b = get_session(session_id_b)
    if not session_a or not session_b:
        return None

    name_a = session_a.get('person_name') or 'Person A'
    name_b = session_b.get('person_name') or 'Person B'

    # A's meta (hvad A tror B gætter om A) vs B's prediction (hvad B faktisk gætter om A)
    a_meta = {r['question_id']: r for r in get_responses_by_type(session_id_a, 'meta_prediction')}
    b_predictions_for_a = {r['question_id']: r for r in get_responses_by_type(session_id_b, 'prediction')}

    # B's meta vs A's prediction
    b_meta = {r['question_id']: r for r in get_responses_by_type(session_id_b, 'meta_prediction')}
    a_predictions_for_b = {r['question_id']: r for r in get_responses_by_type(session_id_a, 'prediction')}

    # Beregn A's blinde pletter
    a_blind_spots = []
    for q_id, meta_resp in a_meta.items():
        actual_pred = b_predictions_for_a.get(q_id)
        if actual_pred:
            gap = actual_pred['score'] - meta_resp['score']
            if abs(gap) >= 2:
                a_blind_spots.append({
                    'question_id': q_id,
                    'question_text': meta_resp.get('text_da', ''),
                    'field': meta_resp.get('field', ''),
                    'meta_score': meta_resp['score'],
                    'actual_prediction': actual_pred['score'],
                    'gap': gap,
                    'abs_gap': abs(gap),
                    'insight': generate_blind_spot_insight(name_a, name_b, gap, meta_resp.get('field', ''))
                })

    # Beregn B's blinde pletter
    b_blind_spots = []
    for q_id, meta_resp in b_meta.items():
        actual_pred = a_predictions_for_b.get(q_id)
        if actual_pred:
            gap = actual_pred['score'] - meta_resp['score']
            if abs(gap) >= 2:
                b_blind_spots.append({
                    'question_id': q_id,
                    'question_text': meta_resp.get('text_da', ''),
                    'field': meta_resp.get('field', ''),
                    'meta_score': meta_resp['score'],
                    'actual_prediction': actual_pred['score'],
                    'gap': gap,
                    'abs_gap': abs(gap),
                    'insight': generate_blind_spot_insight(name_b, name_a, gap, meta_resp.get('field', ''))
                })

    # Kombiner og sorter
    all_blind_spots = (
        [{'person': 'A', 'name': name_a, **bs} for bs in a_blind_spots] +
        [{'person': 'B', 'name': name_b, **bs} for bs in b_blind_spots]
    )
    all_blind_spots.sort(key=lambda x: x['abs_gap'], reverse=True)

    return {
        'a_blind_spots': a_blind_spots,
        'b_blind_spots': b_blind_spots,
        'biggest_blind_spots': all_blind_spots[:3],
        'name_a': name_a,
        'name_b': name_b
    }


def generate_blind_spot_insight(person_name: str, partner_name: str,
                                gap: int, field: str) -> str:
    """
    Genererer indsigtstekst for en blind plet
    """
    field_label = FIELD_LABELS.get(field, field)

    if gap > 0:
        # Partner gætter højere end person troede
        return f"{person_name} undervurderer hvor meget {partner_name} ser {field_label.lower()}-friktion."
    else:
        # Partner gætter lavere end person troede
        return f"{person_name} overvurderer hvor sårbar {partner_name} opfatter dem som på {field_label.lower()}."


def get_profile_summary_text(session_id: str) -> str:
    """
    Generer samlet tekstbeskrivelse af profilen
    """
    analysis = get_full_analysis(session_id)
    if not analysis:
        return "Profil ikke fundet"

    session = analysis['session']
    name = session.get('person_name', 'Personen')
    summary = analysis['summary']

    parts = [f"## Friktionsprofil for {name}\n"]

    # Overordnet
    overall = COLOR_LABELS[summary['overall_color']]
    parts.append(f"**Overordnet**: {overall} profil (gns. score: {summary['total_avg_score']})")

    # Båndbredde
    parts.append(f"\n**Båndbredde**: {summary['bandwidth_interpretation']}")

    # Manifestation
    if summary['dominant_manifestation']:
        manifest = LAYER_LABELS[summary['dominant_manifestation']]
        parts.append(f"\n**Typisk manifestationslag**: {manifest}")

    # Søjle-fortolkninger
    parts.append("\n### Søjle-analyse")
    for field, interpretation in analysis['interpretations'].items():
        parts.append(f"- **{FIELD_LABELS[field]}**: {interpretation}")

    return "\n".join(parts)


if __name__ == "__main__":
    # Test med en profil
    from db_profil import list_sessions

    sessions = list_sessions()
    if sessions:
        session = sessions[0]
        print(f"\nAnalyserer: {session['person_name']}")
        print("=" * 50)
        print(get_profile_summary_text(session['id']))
