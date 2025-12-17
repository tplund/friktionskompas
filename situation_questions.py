"""
Situationsmåling spørgsmål - 4 indirekte spørgsmål (1 per felt)

Disse spørgsmål er designet til at undgå Kahneman substitution:
- Folk svarer på det lette spørgsmål i stedet for det svære
- "Jeg kan ikke" → dække for "jeg tør ikke"
- "Det giver ikke mening" → dække for "jeg gider ikke"

Løsning: Spørg indirekte om oplevelsen, beregn friktionen.
"""

SITUATION_QUESTIONS = [
    {
        'field': 'TRYGHED',
        'sequence': 1,
        'text_da': 'Hvor ubehageligt ville det være at lave en fejl i denne handling?',
        'text_en': 'How uncomfortable would it be to make a mistake in this action?',
        'reverse_scored': True,  # Høj score (meget ubehageligt) = høj friktion
        'scale_labels_da': ['Slet ikke ubehageligt', 'Meget ubehageligt'],
        'scale_labels_en': ['Not uncomfortable at all', 'Very uncomfortable']
    },
    {
        'field': 'MENING',
        'sequence': 2,
        'text_da': 'Hvor tydeligt kan du se, hvem denne handling hjælper?',
        'text_en': 'How clearly can you see who this action helps?',
        'reverse_scored': False,  # Lav score (ikke tydeligt) = høj friktion
        'scale_labels_da': ['Slet ikke tydeligt', 'Meget tydeligt'],
        'scale_labels_en': ['Not clear at all', 'Very clear']
    },
    {
        'field': 'KAN',
        'sequence': 3,
        'text_da': 'Hvor sikkert ved du, hvad første skridt er i denne handling?',
        'text_en': 'How certain are you about what the first step is in this action?',
        'reverse_scored': False,  # Lav score (usikker) = høj friktion
        'scale_labels_da': ['Slet ikke sikkert', 'Helt sikkert'],
        'scale_labels_en': ['Not certain at all', 'Completely certain']
    },
    {
        'field': 'BESVÆR',
        'sequence': 4,
        'text_da': 'Hvor mange mentale stop er der typisk i denne handling?',
        'text_en': 'How many mental stops are there typically in this action?',
        'reverse_scored': True,  # Høj score (mange stop) = høj friktion
        'scale_labels_da': ['Ingen stop', 'Mange stop'],
        'scale_labels_en': ['No stops', 'Many stops']
    }
]

# Felt-navne for visning
FIELD_NAMES = {
    'da': {
        'TRYGHED': 'Tryghed',
        'MENING': 'Mening',
        'KAN': 'Kunnen',
        'BESVÆR': 'Besvær'
    },
    'en': {
        'TRYGHED': 'Safety',
        'MENING': 'Purpose',
        'KAN': 'Ability',
        'BESVÆR': 'Friction'
    }
}

# Felt-beskrivelser for hjælpetekst
FIELD_DESCRIPTIONS = {
    'da': {
        'TRYGHED': 'Psykologisk sikkerhed - tør du lave fejl?',
        'MENING': 'Formål og relevans - giver handlingen mening?',
        'KAN': 'Kompetence og klarhed - ved du hvad du skal gøre?',
        'BESVÆR': 'Kompleksitet og friktion - er det nemt eller besværligt?'
    },
    'en': {
        'TRYGHED': 'Psychological safety - do you dare to make mistakes?',
        'MENING': 'Purpose and relevance - does the action make sense?',
        'KAN': 'Competence and clarity - do you know what to do?',
        'BESVÆR': 'Complexity and friction - is it easy or difficult?'
    }
}


def get_questions(language: str = 'da') -> list:
    """Hent spørgsmål i det angivne sprog"""
    text_key = f'text_{language}'
    scale_key = f'scale_labels_{language}'

    result = []
    for q in SITUATION_QUESTIONS:
        result.append({
            'field': q['field'],
            'sequence': q['sequence'],
            'text': q.get(text_key, q['text_da']),
            'reverse_scored': q['reverse_scored'],
            'scale_labels': q.get(scale_key, q['scale_labels_da'])
        })
    return result


def get_field_name(field: str, language: str = 'da') -> str:
    """Hent feltets visningsnavn"""
    return FIELD_NAMES.get(language, FIELD_NAMES['da']).get(field, field)


def get_field_description(field: str, language: str = 'da') -> str:
    """Hent feltets beskrivelse"""
    return FIELD_DESCRIPTIONS.get(language, FIELD_DESCRIPTIONS['da']).get(field, '')


def adjust_score(raw_score: int, reverse_scored: bool) -> int:
    """Juster score baseret på reverse_scored flag

    For reverse_scored spørgsmål: høj raw score = høj friktion
    Vi inverterer så alle scores følger: høj score = lav friktion
    """
    if reverse_scored:
        return 6 - raw_score  # 1→5, 2→4, 3→3, 4→2, 5→1
    return raw_score
