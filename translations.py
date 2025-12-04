"""
Translation helper for Friktionskompasset i18n support.
"""
from functools import lru_cache
from flask import session, g, request
from db_multitenant import get_db

SUPPORTED_LANGUAGES = ['da', 'en']
DEFAULT_LANGUAGE = 'da'


def get_user_language():
    """Hent brugerens valgte sprog fra session eller browser"""
    # 1. Check session
    if 'language' in session:
        return session['language']

    # 2. Check logged in user
    if 'user' in session and session['user'].get('language'):
        return session['user']['language']

    # 3. Check browser Accept-Language header
    if request and request.accept_languages:
        for lang in request.accept_languages.values():
            lang_code = lang[:2].lower()
            if lang_code in SUPPORTED_LANGUAGES:
                return lang_code

    # 4. Default
    return DEFAULT_LANGUAGE


def t(key, **kwargs):
    """
    Oversæt en streng baseret på brugerens sprog.

    Brug:
        t('nav.dashboard')
        t('welcome', name='John')
    """
    lang = get_user_language()
    translation = get_translation(key, lang)

    if kwargs:
        try:
            return translation.format(**kwargs)
        except KeyError:
            return translation
    return translation


@lru_cache(maxsize=1000)
def get_translation(key, lang):
    """Hent oversættelse fra database (cached)"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM translations WHERE key = ? AND language = ?",
            (key, lang)
        ).fetchone()

        if row:
            return row[0]

        # Fallback til dansk hvis engelsk mangler
        if lang != DEFAULT_LANGUAGE:
            row = conn.execute(
                "SELECT value FROM translations WHERE key = ? AND language = ?",
                (key, DEFAULT_LANGUAGE)
            ).fetchone()
            if row:
                return row[0]

        # Fallback til key hvis ikke fundet
        return f"[{key}]"


def clear_translation_cache():
    """Ryd cache når oversættelser opdateres"""
    get_translation.cache_clear()


def set_language(lang):
    """Sæt brugerens sprogpræference i session"""
    if lang in SUPPORTED_LANGUAGES:
        session['language'] = lang

        # Opdater også i database hvis bruger er logget ind
        if 'user' in session:
            user_id = session['user'].get('id')
            if user_id:
                with get_db() as conn:
                    conn.execute(
                        "UPDATE users SET language = ? WHERE id = ?",
                        (lang, user_id)
                    )
                session['user']['language'] = lang


def get_question_translation(question_id, lang=None):
    """Hent oversat spørgsmålstekst"""
    if lang is None:
        lang = get_user_language()

    with get_db() as conn:
        row = conn.execute(
            "SELECT question_text FROM question_translations WHERE question_id = ? AND language = ?",
            (question_id, lang)
        ).fetchone()

        if row:
            return row[0]

        # Fallback til original spørgsmålstekst
        row = conn.execute(
            "SELECT question_text FROM questions WHERE id = ?",
            (question_id,)
        ).fetchone()

        return row[0] if row else None


# Initial translations for seeding
INITIAL_TRANSLATIONS = {
    # Navigation
    'nav.dashboard': {'da': 'Dashboard', 'en': 'Dashboard'},
    'nav.analyser': {'da': 'Analyser', 'en': 'Analyses'},
    'nav.organisationer': {'da': 'Organisationer', 'en': 'Organizations'},
    'nav.friktionsprofiler': {'da': 'Friktionsprofiler', 'en': 'Friction Profiles'},
    'nav.kunder_brugere': {'da': 'Kunder & Brugere', 'en': 'Customers & Users'},
    'nav.indstillinger': {'da': 'Indstillinger', 'en': 'Settings'},
    'nav.logout': {'da': 'Log ud', 'en': 'Log out'},

    # Common buttons
    'btn.save': {'da': 'Gem', 'en': 'Save'},
    'btn.cancel': {'da': 'Annuller', 'en': 'Cancel'},
    'btn.delete': {'da': 'Slet', 'en': 'Delete'},
    'btn.edit': {'da': 'Rediger', 'en': 'Edit'},
    'btn.create': {'da': 'Opret', 'en': 'Create'},
    'btn.back': {'da': 'Tilbage', 'en': 'Back'},
    'btn.next': {'da': 'Næste', 'en': 'Next'},
    'btn.submit': {'da': 'Indsend', 'en': 'Submit'},
    'btn.upload': {'da': 'Upload', 'en': 'Upload'},

    # Login
    'login.title': {'da': 'Log ind', 'en': 'Log in'},
    'login.username': {'da': 'Brugernavn', 'en': 'Username'},
    'login.password': {'da': 'Adgangskode', 'en': 'Password'},
    'login.button': {'da': 'Log ind', 'en': 'Log in'},
    'login.error': {'da': 'Forkert brugernavn eller adgangskode', 'en': 'Invalid username or password'},

    # Dashboard
    'dashboard.title': {'da': 'Dashboard', 'en': 'Dashboard'},
    'dashboard.overview': {'da': 'Oversigt', 'en': 'Overview'},

    # Organizations
    'org.title': {'da': 'Organisationer', 'en': 'Organizations'},
    'org.tree': {'da': 'Organisationstræ', 'en': 'Organization tree'},
    'org.create': {'da': 'Opret organisation', 'en': 'Create organization'},
    'org.employees': {'da': 'medarbejdere', 'en': 'employees'},
    'org.subunits': {'da': 'underenheder', 'en': 'subunits'},
    'org.details': {'da': 'Detaljer', 'en': 'Details'},
    'org.empty': {'da': '(tom)', 'en': '(empty)'},

    # Campaigns/Målinger
    'campaign.title': {'da': 'Målinger', 'en': 'Measurements'},
    'campaign.create': {'da': 'Opret måling', 'en': 'Create measurement'},
    'campaign.responses': {'da': 'besvarelser', 'en': 'responses'},

    # Confirmations
    'confirm.delete': {'da': 'Er du sikker på at du vil slette?', 'en': 'Are you sure you want to delete?'},
    'confirm.delete_warning': {'da': 'Dette kan ikke fortrydes!', 'en': 'This cannot be undone!'},

    # Flash messages
    'flash.saved': {'da': 'Gemt', 'en': 'Saved'},
    'flash.deleted': {'da': 'Slettet', 'en': 'Deleted'},
    'flash.error': {'da': 'Der opstod en fejl', 'en': 'An error occurred'},
    'flash.no_access': {'da': 'Ingen adgang', 'en': 'Access denied'},

    # Survey
    'survey.title': {'da': 'Spørgeskema', 'en': 'Survey'},
    'survey.progress': {'da': 'Spørgsmål {current} af {total}', 'en': 'Question {current} of {total}'},
    'survey.completed': {'da': 'Tak for din besvarelse!', 'en': 'Thank you for your response!'},

    # Profil
    'profil.title': {'da': 'Friktionsprofil', 'en': 'Friction Profile'},
    'profil.your_profile': {'da': 'Din profil', 'en': 'Your profile'},
    'profil.print': {'da': 'Print rapport', 'en': 'Print report'},
    'profil.new': {'da': 'Tag ny profil', 'en': 'Take new profile'},

    # Layers
    'layer.biologi': {'da': 'Biologi', 'en': 'Biology'},
    'layer.emotion': {'da': 'Emotion', 'en': 'Emotion'},
    'layer.indre': {'da': 'Indre', 'en': 'Inner'},
    'layer.kognition': {'da': 'Kognition', 'en': 'Cognition'},

    # Fields
    'field.tryghed': {'da': 'Tryghed', 'en': 'Safety'},
    'field.mening': {'da': 'Mening', 'en': 'Meaning'},
    'field.kan': {'da': 'Kan', 'en': 'Capability'},
    'field.besvaer': {'da': 'Besvær', 'en': 'Difficulty'},
}


def seed_translations():
    """Seed initial translations to database"""
    with get_db() as conn:
        for key, translations in INITIAL_TRANSLATIONS.items():
            for lang, value in translations.items():
                conn.execute("""
                    INSERT OR REPLACE INTO translations (key, language, value)
                    VALUES (?, ?, ?)
                """, (key, lang, value))
        conn.commit()
    clear_translation_cache()
