"""
Friction Engine - Central beregningsmotor for Friktionskompasset

Dette modul samler AL friktionsberegningslogik ét sted.
Ved ændringer i mekanikken skal KUN denne fil opdateres.

Se ANALYSELOGIK.md for dokumentation af grænseværdier og formler.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math


# ============================================
# KONSTANTER OG KONFIGURATION
# ============================================

class Severity(Enum):
    """Alvorlighedsgrad for friktioner"""
    LOW = "lav"
    MEDIUM = "medium"
    HIGH = "høj"
    CRITICAL = "kritisk"


class SpreadLevel(Enum):
    """Spredningsniveau (standardafvigelse)"""
    LOW = "lav"
    MEDIUM = "medium"
    HIGH = "høj"


# Friktionsfelter
FRICTION_FIELDS = ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']

# Spørgsmålsmapping til lag
QUESTION_LAYERS = {
    'MENING': {
        'all': [1, 2, 3, 4, 5]
    },
    'TRYGHED': {
        'ydre': [6, 7, 8],      # Social tryghed
        'indre': [9, 10]         # Emotionel tryghed
    },
    'KAN': {
        'ydre': [11, 13, 14, 15, 16, 17],  # Rammer/ressourcer
        'indre': [12, 18]                   # Evne/kompetence
    },
    'BESVÆR': {
        'mekanisk': [19, 21, 22],   # Mekanisk friktion
        'oplevet': [20, 23, 24]     # Oplevet flow
    }
}

# Substitutionsitems (Kahneman)
SUBSTITUTION_ITEMS = {
    'tid_item': 14,                    # "Jeg har tid nok..."
    'proc_items': [19, 20, 21, 22],    # Mekaniske friktioner
    'underliggende': [5, 10, 17, 18]   # Underliggende tilfredshed
}

# Grænseværdier (OPDATERET TIL 7-POINT SKALA)
THRESHOLDS = {
    # Procent-baseret farvecodning (uændret)
    'percent_green': 70,     # >= 70% = grøn (lav friktion)
    'percent_yellow': 50,    # >= 50% = gul (moderat friktion)
    # under 50% = rød (høj friktion)

    # Score-baseret severity (1-7 skala)
    'severity_high': 3.5,    # < 3.5 = høj severity (~50%)
    'severity_medium': 4.9,  # < 4.9 = medium severity (~70%)
    # >= 4.9 = lav severity

    # Gap mellem leder og medarbejder (skaleret til 7-point)
    'gap_significant': 1.4,  # > 1.4 = signifikant gap (20%)
    'gap_moderate': 0.84,    # > 0.84 = moderat gap (12%)

    # Leder blokeret (skaleret til 7-point)
    'leader_blocked': 4.9,   # Både team og leder < 4.9 (70%)

    # Substitution (Kahneman) - skaleret til 7-point
    'tid_bias': 0.84,        # TID_BIAS >= 0.84 (12%)
    'underliggende': 4.9,    # UNDERLIGGENDE >= 4.9 (70%)

    # Spredning (standardafvigelse) - skaleret til 7-point
    'spread_low': 0.7,       # < 0.7 = lav spredning
    'spread_medium': 1.4,    # < 1.4 = medium spredning
    # >= 1.4 = høj spredning
}


# ============================================
# DATAKLASSER
# ============================================

@dataclass
class FieldScore:
    """Score for et enkelt friktionsfelt"""
    field: str
    avg_score: float
    response_count: int
    std_dev: float
    spread: SpreadLevel
    layers: Dict[str, Dict] = None  # Ydre/indre breakdown

    @property
    def percent(self) -> float:
        """Konverter score til procent (0-100)"""
        return score_to_percent(self.avg_score)

    @property
    def severity(self) -> Severity:
        """Bestem severity baseret på score"""
        return get_severity(self.avg_score)

    @property
    def color_class(self) -> str:
        """CSS-klasse baseret på score"""
        return get_percent_class(self.percent)


@dataclass
class GapAnalysis:
    """Gap-analyse mellem respondenttyper"""
    field: str
    employee_score: float
    leader_assess_score: float
    leader_self_score: float
    gap: float
    gap_severity: Optional[str]
    has_misalignment: bool
    leader_blocked: bool


@dataclass
class SubstitutionResult:
    """Resultat af substitutionsanalyse"""
    response_count: int
    flagged_count: int
    flagged_pct: float
    avg_tid_bias: float
    flagged: bool


@dataclass
class Warning:
    """Advarsel om friktionsproblem"""
    type: str           # gap, blocked, substitution, spread
    field: str
    severity: Severity
    message: str
    details: Dict = None


# ============================================
# CORE BEREGNINGSFUNKTIONER
# ============================================

def score_to_percent(score: float) -> float:
    """
    Konverter score (1-7) til procent (0-100).

    Args:
        score: Score på 1-7 skala

    Returns:
        Procent 0-100

    Example:
        >>> score_to_percent(4.9)
        70.0
        >>> score_to_percent(3.5)
        50.0
        >>> score_to_percent(7)
        100.0
    """
    if score is None or score == 0:
        return 0.0
    return round((score / 7) * 100, 1)


def percent_to_score(percent: float) -> float:
    """
    Konverter procent (0-100) til score (1-7).

    Args:
        percent: Procent 0-100

    Returns:
        Score på 1-7 skala
    """
    if percent is None or percent == 0:
        return 0.0
    return round((percent / 100) * 7, 2)


def adjust_score(raw_score: int, reverse_scored: bool = False) -> int:
    """
    Justér score baseret på om spørgsmålet er reverse-scored.

    Args:
        raw_score: Rå score fra respondent (1-7)
        reverse_scored: Om spørgsmålet skal inverteres

    Returns:
        Justeret score (1-7)

    Example:
        >>> adjust_score(7, reverse_scored=True)
        1
        >>> adjust_score(7, reverse_scored=False)
        7
        >>> adjust_score(4, reverse_scored=True)
        4  # Midtpunktet forbliver det samme
    """
    if reverse_scored:
        return 8 - raw_score
    return raw_score


def get_severity(score: float) -> Severity:
    """
    Bestem severity baseret på score.

    Args:
        score: Score på 1-7 skala

    Returns:
        Severity enum

    Grænseværdier (se ANALYSELOGIK.md):
        < 3.5: høj (kritisk, ~50%)
        < 4.9: medium (problemområde, ~70%)
        >= 4.9: lav (acceptabel)
    """
    if score < THRESHOLDS['severity_high']:
        return Severity.HIGH
    elif score < THRESHOLDS['severity_medium']:
        return Severity.MEDIUM
    return Severity.LOW


def get_percent_class(percent: float) -> str:
    """
    Bestem CSS-klasse baseret på procent.

    Args:
        percent: Score i procent (0-100)

    Returns:
        CSS-klasse: 'score-high', 'score-medium', eller 'score-low'

    Grænseværdier (se ANALYSELOGIK.md):
        >= 70%: grøn (score-high)
        >= 50%: gul (score-medium)
        < 50%: rød (score-low)
    """
    if percent >= THRESHOLDS['percent_green']:
        return 'score-high'  # Grøn
    elif percent >= THRESHOLDS['percent_yellow']:
        return 'score-medium'  # Gul
    return 'score-low'  # Rød


def get_spread_level(std_dev: float) -> SpreadLevel:
    """
    Klassificer spredning baseret på standardafvigelse.

    Args:
        std_dev: Standardafvigelse

    Returns:
        SpreadLevel enum

    Grænseværdier:
        < 0.5: lav (enighed)
        < 1.0: medium
        >= 1.0: høj (uenighed)
    """
    if std_dev < THRESHOLDS['spread_low']:
        return SpreadLevel.LOW
    elif std_dev < THRESHOLDS['spread_medium']:
        return SpreadLevel.MEDIUM
    return SpreadLevel.HIGH


def calculate_std_dev(scores: List[float]) -> float:
    """
    Beregn standardafvigelse for en liste af scores.

    Args:
        scores: Liste af numeriske scores

    Returns:
        Standardafvigelse (0 hvis under 2 scores)
    """
    if len(scores) < 2:
        return 0.0

    mean = sum(scores) / len(scores)
    variance = sum((x - mean) ** 2 for x in scores) / len(scores)
    return round(math.sqrt(variance), 2)


# ============================================
# FIELD SCORE BEREGNING
# ============================================

def calculate_field_scores(responses: List[Dict]) -> Dict[str, FieldScore]:
    """
    Beregn field scores fra rå responses.

    Args:
        responses: Liste af response dicts med keys:
            - question_id: int
            - sequence: int (spørgsmålsnummer)
            - score: int (1-5)
            - reverse_scored: bool

    Returns:
        Dict med FieldScore for hvert felt

    Example:
        >>> responses = [
        ...     {'sequence': 1, 'score': 4, 'reverse_scored': False},
        ...     {'sequence': 2, 'score': 3, 'reverse_scored': False},
        ... ]
        >>> scores = calculate_field_scores(responses)
        >>> scores['MENING'].avg_score
        3.5
    """
    # Grupper scores per felt og lag
    field_data = {field: {'all_scores': [], 'layers': {}} for field in FRICTION_FIELDS}

    for resp in responses:
        seq = resp.get('sequence')
        raw_score = resp.get('score')
        reverse = resp.get('reverse_scored', False)

        if seq is None or raw_score is None:
            continue

        # Justér score
        adjusted = adjust_score(raw_score, reverse)

        # Find felt og lag
        for field, layers in QUESTION_LAYERS.items():
            for layer_name, question_ids in layers.items():
                if seq in question_ids:
                    field_data[field]['all_scores'].append(adjusted)

                    if layer_name not in field_data[field]['layers']:
                        field_data[field]['layers'][layer_name] = []
                    field_data[field]['layers'][layer_name].append(adjusted)
                    break

    # Beregn aggregerede scores
    results = {}

    for field in FRICTION_FIELDS:
        all_scores = field_data[field]['all_scores']

        if not all_scores:
            results[field] = FieldScore(
                field=field,
                avg_score=0,
                response_count=0,
                std_dev=0,
                spread=SpreadLevel.LOW,
                layers={}
            )
            continue

        avg = round(sum(all_scores) / len(all_scores), 1)
        std = calculate_std_dev(all_scores)

        # Beregn layer scores
        layer_scores = {}
        for layer_name, layer_data in field_data[field]['layers'].items():
            if layer_data:
                layer_avg = round(sum(layer_data) / len(layer_data), 1)
                layer_scores[layer_name] = {
                    'avg_score': layer_avg,
                    'response_count': len(layer_data),
                    'percent': score_to_percent(layer_avg)
                }

        results[field] = FieldScore(
            field=field,
            avg_score=avg,
            response_count=len(all_scores),
            std_dev=std,
            spread=get_spread_level(std),
            layers=layer_scores
        )

    return results


# ============================================
# GAP ANALYSE
# ============================================

def calculate_gap(
    employee_score: float,
    leader_assess_score: float,
    leader_self_score: float = None
) -> Tuple[float, str, bool]:
    """
    Beregn gap mellem medarbejder og leder.

    Args:
        employee_score: Medarbejdernes gennemsnitsscore
        leader_assess_score: Lederens vurdering af teamet
        leader_self_score: Lederens selvvurdering (optional)

    Returns:
        Tuple af (gap, gap_severity, has_misalignment)

    Grænseværdier (se ANALYSELOGIK.md):
        > 1.0: kritisk (20%+)
        > 0.6: moderat (12%+)
    """
    if not employee_score or not leader_assess_score:
        return (0, None, False)

    gap = round(abs(employee_score - leader_assess_score), 1)

    # Gap severity
    if gap >= THRESHOLDS['gap_significant']:
        gap_severity = 'kritisk'
    elif gap >= THRESHOLDS['gap_moderate']:
        gap_severity = 'moderat'
    else:
        gap_severity = None

    has_misalignment = gap >= THRESHOLDS['gap_moderate']

    return (gap, gap_severity, has_misalignment)


def check_leader_blocked(
    employee_score: float,
    leader_self_score: float
) -> bool:
    """
    Check om leder er blokeret (selv har friktioner).

    Args:
        employee_score: Medarbejdernes score
        leader_self_score: Lederens selvvurdering

    Returns:
        True hvis både team og leder har friktioner (< 3.5)

    Se ANALYSELOGIK.md sektion 4.
    """
    threshold = THRESHOLDS['leader_blocked']
    return (
        employee_score is not None and
        leader_self_score is not None and
        employee_score < threshold and
        leader_self_score < threshold
    )


def analyze_gaps(
    employee_scores: Dict[str, FieldScore],
    leader_assess_scores: Dict[str, FieldScore],
    leader_self_scores: Dict[str, FieldScore] = None
) -> Dict[str, GapAnalysis]:
    """
    Komplet gap-analyse for alle felter.

    Args:
        employee_scores: FieldScores for medarbejdere
        leader_assess_scores: FieldScores for ledervurdering
        leader_self_scores: FieldScores for leder-selv (optional)

    Returns:
        Dict med GapAnalysis per felt
    """
    results = {}

    for field in FRICTION_FIELDS:
        emp = employee_scores.get(field)
        lead_assess = leader_assess_scores.get(field) if leader_assess_scores else None
        lead_self = leader_self_scores.get(field) if leader_self_scores else None

        emp_score = emp.avg_score if emp else 0
        lead_assess_score = lead_assess.avg_score if lead_assess else 0
        lead_self_score = lead_self.avg_score if lead_self else 0

        gap, gap_severity, has_misalignment = calculate_gap(
            emp_score, lead_assess_score, lead_self_score
        )

        leader_blocked = check_leader_blocked(emp_score, lead_self_score)

        results[field] = GapAnalysis(
            field=field,
            employee_score=emp_score,
            leader_assess_score=lead_assess_score,
            leader_self_score=lead_self_score,
            gap=gap,
            gap_severity=gap_severity,
            has_misalignment=has_misalignment,
            leader_blocked=leader_blocked
        )

    return results


# ============================================
# SUBSTITUTION (KAHNEMAN)
# ============================================

def calculate_substitution_for_respondent(scores: Dict[int, int]) -> Dict:
    """
    Beregn substitution for én respondent.

    Args:
        scores: Dict med {sequence: score} for respondenten (1-7 skala)

    Returns:
        Dict med tid_mangel, proc, underliggende, tid_bias, flagged

    Formel (se ANALYSELOGIK.md sektion 1):
        TID_MANGEL = 8 - item14 (reverse scored, 1-7)
        PROC = gennemsnit(item19, 8-item20, 8-item21, 8-item22)
        UNDERLIGGENDE = max(item5, item10, item17, item18)
        TID_BIAS = TID_MANGEL - PROC
        FLAGGED = TID_BIAS >= 0.84 AND UNDERLIGGENDE >= 4.9
    """
    # TID_MANGEL = 8 - item14 (reverse scored for 1-7)
    tid_mangel = 8 - scores.get(14, 4)  # default 4 = midtpunkt på 1-7

    # PROC = gennemsnit af mekaniske friktioner
    # Item 19 er allerede reverse i DB, 20-22 skal inverteres
    proc_scores = [
        scores.get(19, 4),
        8 - scores.get(20, 4),
        8 - scores.get(21, 4),
        8 - scores.get(22, 4)
    ]
    proc = sum(proc_scores) / len(proc_scores)

    # UNDERLIGGENDE = max af tilfredshedsitems
    underliggende = max(
        scores.get(5, 1),
        scores.get(10, 1),
        scores.get(17, 1),
        scores.get(18, 1)
    )

    # TID_BIAS
    tid_bias = tid_mangel - proc

    # Flag substitution
    flagged = (
        tid_bias >= THRESHOLDS['tid_bias'] and
        underliggende >= THRESHOLDS['underliggende']
    )

    return {
        'tid_mangel': round(tid_mangel, 2),
        'proc': round(proc, 2),
        'underliggende': round(underliggende, 2),
        'tid_bias': round(tid_bias, 2),
        'flagged': flagged
    }


def calculate_substitution(respondent_scores: Dict[str, Dict[int, int]]) -> SubstitutionResult:
    """
    Beregn substitution for alle respondenter.

    Args:
        respondent_scores: Dict med {respondent_name: {sequence: score}}

    Returns:
        SubstitutionResult med aggregerede tal
    """
    if not respondent_scores:
        return SubstitutionResult(
            response_count=0,
            flagged_count=0,
            flagged_pct=0,
            avg_tid_bias=0,
            flagged=False
        )

    flagged_count = 0
    tid_biases = []

    for name, scores in respondent_scores.items():
        result = calculate_substitution_for_respondent(scores)
        tid_biases.append(result['tid_bias'])
        if result['flagged']:
            flagged_count += 1

    response_count = len(respondent_scores)
    flagged_pct = (flagged_count / response_count * 100) if response_count > 0 else 0
    avg_tid_bias = sum(tid_biases) / len(tid_biases) if tid_biases else 0

    return SubstitutionResult(
        response_count=response_count,
        flagged_count=flagged_count,
        flagged_pct=round(flagged_pct, 1),
        avg_tid_bias=round(avg_tid_bias, 2),
        flagged=flagged_count > 0
    )


# ============================================
# WARNINGS OG ANBEFALINGER
# ============================================

def get_warnings(
    field_scores: Dict[str, FieldScore],
    gap_analysis: Dict[str, GapAnalysis] = None,
    substitution: SubstitutionResult = None
) -> List[Warning]:
    """
    Generer advarsler baseret på analyseresultater.

    Args:
        field_scores: FieldScores for medarbejdere
        gap_analysis: Optional gap-analyse
        substitution: Optional substitutionsresultat

    Returns:
        Liste af Warning objekter sorteret efter severity
    """
    warnings = []

    # Check field scores
    for field, score in field_scores.items():
        if score.severity == Severity.HIGH:
            warnings.append(Warning(
                type='high_friction',
                field=field,
                severity=Severity.HIGH,
                message=f'Kritisk friktion i {field} ({score.percent:.0f}%)',
                details={'score': score.avg_score, 'percent': score.percent}
            ))

        # Høj spredning
        if score.spread == SpreadLevel.HIGH:
            warnings.append(Warning(
                type='high_spread',
                field=field,
                severity=Severity.MEDIUM,
                message=f'Stor uenighed i {field} (std.dev: {score.std_dev})',
                details={'std_dev': score.std_dev}
            ))

    # Check gaps
    if gap_analysis:
        for field, gap in gap_analysis.items():
            if gap.has_misalignment:
                warnings.append(Warning(
                    type='gap',
                    field=field,
                    severity=Severity.HIGH if gap.gap_severity == 'kritisk' else Severity.MEDIUM,
                    message=f'Gap mellem leder og medarbejdere i {field} ({gap.gap} point)',
                    details={'gap': gap.gap, 'employee': gap.employee_score, 'leader': gap.leader_assess_score}
                ))

            if gap.leader_blocked:
                warnings.append(Warning(
                    type='blocked',
                    field=field,
                    severity=Severity.HIGH,
                    message=f'Leder er blokeret i {field} - kan ikke hjælpe teamet',
                    details={'employee': gap.employee_score, 'leader_self': gap.leader_self_score}
                ))

    # Check substitution
    if substitution and substitution.flagged:
        warnings.append(Warning(
            type='substitution',
            field='TID',
            severity=Severity.MEDIUM,
            message=f'{substitution.flagged_count} respondenter ({substitution.flagged_pct:.0f}%) viser tegn på tidssubstitution',
            details={'count': substitution.flagged_count, 'pct': substitution.flagged_pct}
        ))

    # Sortér efter severity
    severity_order = {Severity.HIGH: 0, Severity.CRITICAL: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
    warnings.sort(key=lambda w: severity_order.get(w.severity, 2))

    return warnings


def get_start_here_recommendation(field_scores: Dict[str, FieldScore]) -> Optional[str]:
    """
    Find det felt der bør fokuseres på først (KKC "Start Her").

    Args:
        field_scores: FieldScores for alle felter

    Returns:
        Feltnavn at starte med, eller None hvis alt er OK

    Prioritering (se ANALYSELOGIK.md sektion 2):
        1. MENING (hvorfor)
        2. TRYGHED (tør jeg)
        3. KAN (ved jeg hvordan)
        4. BESVÆR (mekanisk flow)
    """
    priority_order = ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']

    for field in priority_order:
        score = field_scores.get(field)
        if score and score.severity in [Severity.HIGH, Severity.MEDIUM]:
            return field

    return None


def get_profile_type(field_scores: Dict[str, FieldScore]) -> str:
    """
    Bestem profiltype baseret på friktionsmønster.

    Args:
        field_scores: FieldScores for alle felter (1-7 skala)

    Returns:
        Profiltype-streng
    """
    # Find laveste og højeste scores
    scores = [(f, s.avg_score) for f, s in field_scores.items() if s.avg_score > 0]

    if not scores:
        return "ingen_data"

    scores.sort(key=lambda x: x[1])
    lowest_field, lowest_score = scores[0]
    highest_field, highest_score = scores[-1]

    # Profiltypelogik (thresholds skaleret til 1-7)
    # 2.5 på 1-5 = 50% = 3.5 på 1-7
    # 3.5 på 1-5 = 70% = 4.9 på 1-7
    # 4.0 på 1-5 = 80% = 5.6 på 1-7
    if lowest_score < 3.5:  # < 50%
        # Kritisk friktion
        if lowest_field == 'MENING':
            return "retningsløst_team"
        elif lowest_field == 'TRYGHED':
            return "utrygt_team"
        elif lowest_field == 'KAN':
            return "inkompetent_team"  # Mangler evner/ressourcer
        else:
            return "bøvlet_team"

    elif lowest_score < 4.9:  # < 70%
        # Moderat friktion
        if highest_score - lowest_score > 2.1:  # 1.5 * 1.4 skalering
            return "ubalanceret_team"
        return "udviklingspotentiale"

    else:
        # Lav friktion generelt (>= 70%)
        if all(s.avg_score >= 5.6 for s in field_scores.values()):  # >= 80%
            return "højtydende_team"
        return "velfungerende_team"


# ============================================
# HELPER TIL TEMPLATES
# ============================================

def to_percent(score: float) -> float:
    """Alias for score_to_percent - til brug i templates."""
    return score_to_percent(score)


def get_color_class(score: float) -> str:
    """Bestem CSS-klasse direkte fra score (1-5)."""
    return get_percent_class(score_to_percent(score))
