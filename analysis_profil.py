"""
Analyse-funktioner for Friktionsprofil
Beregner farvegrid, båndbredde, manifestationslag og fortolkninger
"""
from typing import Dict, List, Optional, Tuple
from db_profil import get_response_matrix, get_session

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
