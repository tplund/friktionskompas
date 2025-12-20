"""
Shared template helper functions for Friktionskompasset.

These functions are used both in Jinja2 templates (via context processor)
and in Python code for consistent score formatting.
"""


def get_score_class(score):
    """Return CSS class based on friction score (0-5 scale)"""
    if score is None:
        return 'score-none'
    if score > 3.5:
        return 'score-high'
    elif score >= 2.5:
        return 'score-medium'
    else:
        return 'score-low'


def get_percent_class(score):
    """Return CSS class based on friction score as percent"""
    if score is None:
        return 'score-none'
    percent = (score / 5) * 100
    if percent > 70:
        return 'score-high'
    elif percent >= 50:
        return 'score-medium'
    else:
        return 'score-low'


def get_gap_class(employee_score, leader_score):
    """Return CSS class and icon based on gap between employee and leader"""
    if employee_score is None or leader_score is None:
        return 'gap-none', ''
    gap = abs(employee_score - leader_score)
    if gap > 1.0:  # More than 1 point difference on 0-5 scale
        return 'gap-critical', '🚨'
    elif gap > 0.5:
        return 'gap-warning', '⚠️'
    else:
        return 'gap-ok', '✓'


def to_percent(score):
    """Convert 1-5 score to percent (1=0%, 5=100%)"""
    if score is None or score == 0:
        return 0
    # Convert 1-5 scale to 0-100%
    return ((score - 1) / 4) * 100
