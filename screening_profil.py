"""
Screening-modul for Friktionsprofil
Sammenligner en persons profil med teoretiske diagnose-signaturer

VIGTIGT: Dette er et eksperimentelt screeningsværktøj, IKKE en diagnose.
Skal valideres klinisk for brug i praksis.
"""
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from analysis_profil import get_full_analysis, FIELDS, LAYERS

# ========================================
# SCREENING KRITERIER
# ========================================

@dataclass
class ScreeningKriterie:
    """Et specifikt kriterie der kan checkes"""
    navn: str
    beskrivelse: str
    check: Callable[[Dict, Dict], bool]  # (score_matrix, summary) -> bool
    vaegt: float = 1.0  # Hvor vigtig er dette kriterie


@dataclass
class DiagnoseScreening:
    """Definition af en diagnose-screening"""
    navn: str
    kort_navn: str
    beskrivelse: str
    kriterier: List[ScreeningKriterie]
    min_match_for_visning: float = 0.4  # Minimum match for at vise (40%)


# ========================================
# HELPER FUNKTIONER
# ========================================

def get_score(matrix: Dict, felt: str, lag: str) -> float:
    """Hent score fra matrix med default 3.0"""
    return matrix.get(felt, {}).get(lag, 3.0)

def avg_felt(matrix: Dict, felt: str) -> float:
    """Gennemsnitlig score for et felt"""
    scores = [matrix.get(felt, {}).get(lag, 3.0) for lag in LAYERS]
    return sum(scores) / len(scores)

def avg_lag(matrix: Dict, lag: str) -> float:
    """Gennemsnitlig score for et lag påtværs af felter"""
    scores = [matrix.get(felt, {}).get(lag, 3.0) for felt in FIELDS]
    return sum(scores) / len(scores)

def baandbredde(matrix: Dict, felt: str) -> float:
    """Baandbredde for et felt (kognition - biologi)"""
    bio = get_score(matrix, felt, 'BIOLOGI')
    kog = get_score(matrix, felt, 'KOGNITION')
    return kog - bio

def total_friktion(matrix: Dict) -> float:
    """Total friktion (gennemsnit af alle scores)"""
    all_scores = []
    for felt in FIELDS:
        for lag in LAYERS:
            all_scores.append(get_score(matrix, felt, lag))
    return sum(all_scores) / len(all_scores)


# ========================================
# DIAGNOSE DEFINITIONER
# ========================================

SCREENINGS = {
    'robust': DiagnoseScreening(
        navn="Robust / Ingen indikation",
        kort_navn="Robust",
        beskrivelse="En balanceret profil med generelt lave friktionsniveauer.",
        min_match_for_visning=0.5,
        kriterier=[
            ScreeningKriterie(
                navn="Lav total friktion",
                beskrivelse="Gennemsnitlig score under 2.5",
                check=lambda m, s: total_friktion(m) < 2.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Ingen høje felter",
                beskrivelse="Ingen felter med gennemsnit over 3.5",
                check=lambda m, s: all(avg_felt(m, f) < 3.5 for f in FIELDS),
                vaegt=1.5
            ),
            ScreeningKriterie(
                navn="God baandbredde",
                beskrivelse="Positiv baandbredde i mindst 3 felter",
                check=lambda m, s: sum(1 for f in FIELDS if baandbredde(m, f) > 0) >= 3,
                vaegt=1.0
            ),
            ScreeningKriterie(
                navn="Lav BESVAER",
                beskrivelse="BESVAER-gennemsnit under 2.5",
                check=lambda m, s: avg_felt(m, 'BESVÆR') < 2.5,
                vaegt=1.0
            ),
        ]
    ),

    'adhd': DiagnoseScreening(
        navn="ADHD-lignende mønster",
        kort_navn="ADHD",
        beskrivelse="Moenster med høj biologisk reaktivitet i KAN og BESVAER, lav baandbredde, og hurtig overbelastning.",
        min_match_for_visning=0.5,
        kriterier=[
            ScreeningKriterie(
                navn="Høj KAN-biologi",
                beskrivelse="KAN i biologi-laget over 3.5 (mærker energifald tydeligt)",
                check=lambda m, s: get_score(m, 'KAN', 'BIOLOGI') >= 3.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Høj BESVAER-biologi",
                beskrivelse="BESVAER i biologi-laget over 3.5 (alt føles tungt)",
                check=lambda m, s: get_score(m, 'BESVÆR', 'BIOLOGI') >= 3.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Lav baandbredde i KAN",
                beskrivelse="Negativ eller lav baandbredde i KAN (under 0)",
                check=lambda m, s: baandbredde(m, 'KAN') < 0,
                vaegt=1.5
            ),
            ScreeningKriterie(
                navn="Høj emotion i KAN/BESVAER",
                beskrivelse="Emotion høj i både KAN og BESVAER",
                check=lambda m, s: get_score(m, 'KAN', 'EMOTION') >= 3.5 and get_score(m, 'BESVÆR', 'EMOTION') >= 3.5,
                vaegt=1.0
            ),
            ScreeningKriterie(
                navn="Variabel MENING",
                beskrivelse="MENING-emotion høj (mærker hvad der er vigtigt) men MENING-indre lav (får ikke retning)",
                check=lambda m, s: get_score(m, 'MENING', 'EMOTION') >= 3.5 and get_score(m, 'MENING', 'INDRE') <= 2.5,
                vaegt=1.0
            ),
        ]
    ),

    'autisme': DiagnoseScreening(
        navn="Autisme-lignende mønster",
        kort_navn="Autisme",
        beskrivelse="Moenster med høj sensorisk følsomhed, stærk kognitiv regulering, og følsomhed ved udfordret virkelighed.",
        min_match_for_visning=0.5,
        kriterier=[
            ScreeningKriterie(
                navn="Høj sensorisk reaktivitet",
                beskrivelse="TRYGHED i biologi-laget over 3.5",
                check=lambda m, s: get_score(m, 'TRYGHED', 'BIOLOGI') >= 3.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Staerk kognitiv regulering",
                beskrivelse="TRYGHED/MENING i kognition-laget under 2.5 (kan bruge forstaelse til at falde til ro)",
                check=lambda m, s: get_score(m, 'TRYGHED', 'KOGNITION') <= 2.5 or get_score(m, 'MENING', 'KOGNITION') <= 2.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Høj indre-følsomhed",
                beskrivelse="TRYGHED i indre-laget over 3.5 (urolig ved udfordret virkelighed)",
                check=lambda m, s: get_score(m, 'TRYGHED', 'INDRE') >= 3.5,
                vaegt=1.5
            ),
            ScreeningKriterie(
                navn="Overvaeldes af mange ting",
                beskrivelse="KAN i emotion-laget over 4.0",
                check=lambda m, s: get_score(m, 'KAN', 'EMOTION') >= 4.0,
                vaegt=1.0
            ),
            ScreeningKriterie(
                navn="Sensorisk vs. kognitiv gap",
                beskrivelse="Stor forskel mellem biologi og kognition i TRYGHED (mindst 2 point)",
                check=lambda m, s: get_score(m, 'TRYGHED', 'BIOLOGI') - get_score(m, 'TRYGHED', 'KOGNITION') >= 2,
                vaegt=1.5
            ),
        ]
    ),

    'borderline': DiagnoseScreening(
        navn="Emotionelt ustabilt mønster",
        kort_navn="Borderline",
        beskrivelse="Moenster med ustabil TRYGHED i alle lag, høj emotionel intensitet, og lav indre forankring.",
        min_match_for_visning=0.5,
        kriterier=[
            ScreeningKriterie(
                navn="Høj TRYGHED generelt",
                beskrivelse="TRYGHED-gennemsnit over 3.5",
                check=lambda m, s: avg_felt(m, 'TRYGHED') >= 3.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Høj TRYGHED i indre",
                beskrivelse="TRYGHED i indre-laget over 4.0 (ustabil selvoplevelse)",
                check=lambda m, s: get_score(m, 'TRYGHED', 'INDRE') >= 4.0,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Høj TRYGHED i emotion",
                beskrivelse="TRYGHED i emotion-laget over 4.0",
                check=lambda m, s: get_score(m, 'TRYGHED', 'EMOTION') >= 4.0,
                vaegt=1.5
            ),
            ScreeningKriterie(
                navn="Intens emotionalitet",
                beskrivelse="Høj emotion-score i flere felter (gennemsnit over 3.5)",
                check=lambda m, s: avg_lag(m, 'EMOTION') >= 3.5,
                vaegt=1.0
            ),
            ScreeningKriterie(
                navn="Lav indre forankring",
                beskrivelse="MENING i indre-laget under 2.5 (ustabil retning)",
                check=lambda m, s: get_score(m, 'MENING', 'INDRE') <= 2.5,
                vaegt=1.0
            ),
        ]
    ),

    'angst': DiagnoseScreening(
        navn="Angst-lignende mønster",
        kort_navn="Angst",
        beskrivelse="Moenster med dominerende TRYGHED-friktion men relativt normale KAN og BESVAER.",
        min_match_for_visning=0.5,
        kriterier=[
            ScreeningKriterie(
                navn="Høj TRYGHED",
                beskrivelse="TRYGHED-gennemsnit over 3.5",
                check=lambda m, s: avg_felt(m, 'TRYGHED') >= 3.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="TRYGHED dominerer",
                beskrivelse="TRYGHED er højeste felt (mindst 0.5 over gennemsnit)",
                check=lambda m, s: avg_felt(m, 'TRYGHED') >= total_friktion(m) + 0.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Moderat KAN",
                beskrivelse="KAN-gennemsnit under 4.0 (ikke saa udtalt som ADHD)",
                check=lambda m, s: avg_felt(m, 'KAN') < 4.0,
                vaegt=1.5
            ),
            ScreeningKriterie(
                navn="Moderat BESVAER",
                beskrivelse="BESVAER-gennemsnit under 3.5",
                check=lambda m, s: avg_felt(m, 'BESVÆR') < 3.5,
                vaegt=1.5
            ),
            ScreeningKriterie(
                navn="Fysisk anspændthed",
                beskrivelse="TRYGHED i biologi over 3.5",
                check=lambda m, s: get_score(m, 'TRYGHED', 'BIOLOGI') >= 3.5,
                vaegt=1.0
            ),
        ]
    ),

    'depression': DiagnoseScreening(
        navn="Depressions-lignende mønster",
        kort_navn="Depression",
        beskrivelse="Moenster med høj friktion i MENING og KAN, lav energi, og tab af retning.",
        min_match_for_visning=0.5,
        kriterier=[
            ScreeningKriterie(
                navn="Høj KAN-biologi",
                beskrivelse="KAN i biologi-laget over 3.5 (energifald)",
                check=lambda m, s: get_score(m, 'KAN', 'BIOLOGI') >= 3.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Høj BESVAER-biologi",
                beskrivelse="BESVAER i biologi-laget over 3.5 (alt føles tungt)",
                check=lambda m, s: get_score(m, 'BESVÆR', 'BIOLOGI') >= 3.5,
                vaegt=2.0
            ),
            ScreeningKriterie(
                navn="Høj MENING-biologi",
                beskrivelse="MENING i biologi-laget over 3.5 (føles fysisk forkert)",
                check=lambda m, s: get_score(m, 'MENING', 'BIOLOGI') >= 3.5,
                vaegt=1.5
            ),
            ScreeningKriterie(
                navn="Tabt retning",
                beskrivelse="MENING i indre-laget under 2.5 (mistet retning)",
                check=lambda m, s: get_score(m, 'MENING', 'INDRE') <= 2.5,
                vaegt=1.5
            ),
            ScreeningKriterie(
                navn="Generelt høj friktion",
                beskrivelse="Total friktion over 3.0",
                check=lambda m, s: total_friktion(m) >= 3.0,
                vaegt=1.0
            ),
        ]
    ),
}


# ========================================
# SCREENING FUNKTION
# ========================================

def screen_profil(session_id: str) -> Optional[Dict]:
    """
    Screen en profil mod alle diagnose-screeninger.
    Returns kun matches over minimum threshold.
    """
    analysis = get_full_analysis(session_id)
    if not analysis:
        return None

    score_matrix = analysis['score_matrix']
    summary = analysis['summary']

    matches = []
    for key, screening in SCREENINGS.items():
        # Evaluer alle kriterier
        matched_kriterier = []
        total_vaegt = 0
        matched_vaegt = 0

        for kriterie in screening.kriterier:
            total_vaegt += kriterie.vaegt
            try:
                if kriterie.check(score_matrix, summary):
                    matched_vaegt += kriterie.vaegt
                    matched_kriterier.append({
                        'navn': kriterie.navn,
                        'beskrivelse': kriterie.beskrivelse,
                        'vaegt': kriterie.vaegt
                    })
            except Exception as e:
                # Ignorer fejl i check-funktioner
                pass

        # Beregn match procent
        match_procent = (matched_vaegt / total_vaegt) if total_vaegt > 0 else 0

        # Kun tilføj hvis over minimum threshold
        if match_procent >= screening.min_match_for_visning:
            match = {
                'key': key,
                'diagnose': screening.kort_navn,
                'diagnose_fuld': screening.navn,
                'beskrivelse': screening.beskrivelse,
                'match_procent': round(match_procent * 100, 1),
                'matched_kriterier': matched_kriterier,
                'total_kriterier': len(screening.kriterier),
                'matched_antal': len(matched_kriterier),
            }

            # Klassificer niveau
            if match_procent >= 0.75:
                match['niveau'] = 'høj'
                match['niveau_tekst'] = 'Stærk indikation'
                match['farve'] = 'orange'
            elif match_procent >= 0.55:
                match['niveau'] = 'moderat'
                match['niveau_tekst'] = 'Moderat indikation'
                match['farve'] = 'yellow'
            else:
                match['niveau'] = 'svag'
                match['niveau_tekst'] = 'Svag indikation'
                match['farve'] = 'green'

            matches.append(match)

    # Sorter efter match procent
    matches.sort(key=lambda x: x['match_procent'], reverse=True)

    return {
        'session': analysis['session'],
        'summary': summary,
        'matches': matches,
        'top_match': matches[0] if matches else None,
        'has_significant_match': any(m['match_procent'] >= 55 for m in matches),
        'disclaimer': """
VIGTIGT: Dette er et eksperimentelt screeningsværktøj baseret påteoretiske
friktionsmoenstre. Det er IKKE en diagnose og kan ikke erstatte en klinisk
vurdering. Match-procenten viser hvor mange af de forventede kendetegn der
er til stede i din profil - det bekræfter ikke en diagnose.

Hvis resultaterne resonerer med din oplevelse, kan det være værd at tale
med en fagperson.
        """.strip()
    }


def get_screening_summary(session_id: str) -> str:
    """Generer en tekstuel opsummering af screening-resultater."""
    result = screen_profil(session_id)
    if not result:
        return "Kunne ikke screene profil."

    lines = [
        f"## Screening for {result['session'].get('person_name', 'Unavngivet')}",
        "",
    ]

    if not result['matches']:
        lines.append("Ingen tydelige moenstre fundet.")
    else:
        lines.append("### Fundne moenstre:")
        for match in result['matches']:
            lines.append(f"- **{match['diagnose']}**: {match['match_procent']}% ({match['niveau_tekst']})")
            for k in match['matched_kriterier'][:2]:
                lines.append(f"  - {k['navn']}")

    lines.extend([
        "",
        "---",
        result['disclaimer']
    ])

    return "\n".join(lines)


# ========================================
# TEST
# ========================================

if __name__ == "__main__":
    from db_profil import list_sessions

    sessions = list_sessions(include_incomplete=True)
    print(f"Fandt {len(sessions)} profiler\n")

    for s in sessions:
        name = s.get('person_name', 'Unavngivet')
        result = screen_profil(s['id'])

        if result and result['matches']:
            print(f"=== {name} ===")
            for match in result['matches']:
                pct = match['match_procent']
                niveau = match['niveau_tekst']
                matched = match['matched_antal']
                total = match['total_kriterier']
                print(f"  {match['diagnose']:12} {pct:5.1f}% ({matched}/{total} kriterier) - {niveau}")
            print()
