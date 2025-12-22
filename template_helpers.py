"""
Shared template helper functions for Friktionskompasset.

These functions are used both in Jinja2 templates (via context processor)
and in Python code for consistent score formatting.

OPDATERET TIL 7-POINT SKALA (2025-12-22)
"""


def get_score_class(score):
    """Return CSS class based on friction score (1-7 scale)

    Thresholds:
        > 4.9 (70%): score-high (green)
        >= 3.5 (50%): score-medium (yellow)
        < 3.5: score-low (red)
    """
    if score is None:
        return 'score-none'
    if score > 4.9:
        return 'score-high'
    elif score >= 3.5:
        return 'score-medium'
    else:
        return 'score-low'


def get_percent_class(score):
    """Return CSS class based on friction score as percent (1-7 scale)"""
    if score is None:
        return 'score-none'
    percent = (score / 7) * 100
    if percent > 70:
        return 'score-high'
    elif percent >= 50:
        return 'score-medium'
    else:
        return 'score-low'


def get_gap_class(employee_score, leader_score):
    """Return CSS class and icon based on gap between employee and leader (1-7 scale)

    Thresholds (skaleret til 7-point):
        > 1.4: critical (20%+)
        > 0.84: warning (12%+)
    """
    if employee_score is None or leader_score is None:
        return 'gap-none', ''
    gap = abs(employee_score - leader_score)
    if gap > 1.4:  # More than 20% difference on 1-7 scale
        return 'gap-critical', ''
    elif gap > 0.84:  # More than 12% difference
        return 'gap-warning', ''
    else:
        return 'gap-ok', ''


def to_percent(score):
    """Convert 1-7 score to percent (1=~14%, 7=100%)"""
    if score is None or score == 0:
        return 0
    # Convert 1-7 scale to percent
    return (score / 7) * 100
