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


def t(key, default=None, **kwargs):
    """
    Oversæt en streng baseret på brugerens sprog.

    Brug:
        t('nav.dashboard')
        t('nav.planlagte', 'Planlagte')  # med default værdi
        t('welcome', name='John')
    """
    lang = get_user_language()
    translation = get_translation(key, lang)

    # Brug default hvis oversættelse ikke fundet (returnerer [key])
    if (translation == key or translation == f"[{key}]") and default:
        translation = default

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
    # Navigation - Main menu items
    'nav.noegletal': {'da': 'Nøgletal', 'en': 'Key Metrics'},
    'nav.dashboard': {'da': 'Dashboard', 'en': 'Dashboard'},
    'nav.analyser': {'da': 'Analyser', 'en': 'Analyses'},
    'nav.alle_maalinger': {'da': 'Alle målinger', 'en': 'All assessments'},
    'nav.organisationer': {'da': 'Organisationer', 'en': 'Organizations'},
    'nav.friktionsprofiler': {'da': 'Friktionsprofiler', 'en': 'Friction Profiles'},
    'nav.kunder_brugere': {'da': 'Kunder & Brugere', 'en': 'Customers & Users'},
    'nav.indstillinger': {'da': 'Indstillinger', 'en': 'Settings'},
    'nav.logout': {'da': 'Log ud', 'en': 'Log out'},
    'nav.trend': {'da': 'Trend', 'en': 'Trend'},

    # Navigation - Dropdown groups
    'nav.maalinger': {'da': 'Målinger', 'en': 'Assessments'},
    'nav.planlagte': {'da': 'Planlagte', 'en': 'Scheduled'},
    'nav.ny_maaling': {'da': 'Ny måling', 'en': 'New assessment'},
    'nav.friktionsprofil': {'da': 'Friktionsprofil', 'en': 'Friction Profile'},
    'nav.alle_profiler': {'da': 'Alle profiler', 'en': 'All profiles'},
    'nav.tag_test': {'da': 'Tag profil-test', 'en': 'Take profile test'},
    'nav.organisation': {'da': 'Organisation', 'en': 'Organization'},
    'nav.domaener': {'da': 'Domæner', 'en': 'Domains'},
    'nav.branding': {'da': 'Min Branding', 'en': 'My Branding'},
    'nav.auth_config': {'da': 'Auth Konfiguration', 'en': 'Auth Configuration'},
    'nav.profil_spoergsmaal': {'da': 'Profil-spørgsmål', 'en': 'Profile questions'},
    'nav.email_status': {'da': 'Email Status', 'en': 'Email Status'},
    'nav.email_templates': {'da': 'Email Templates', 'en': 'Email Templates'},
    'nav.backup': {'da': 'Backup & Restore', 'en': 'Backup & Restore'},
    'nav.dev_tools': {'da': 'Dev Tools', 'en': 'Dev Tools'},
    'nav.assessment_types': {'da': 'Målingstyper', 'en': 'Assessment Types'},

    # Customer settings
    'customers.assessment_types': {'da': 'Målinger', 'en': 'Assessments'},

    # Trend Analysis
    'trend.title': {'da': 'Trend Analyse', 'en': 'Trend Analysis'},
    'trend.subtitle': {'da': 'Sammenlign friktionsscores over tid', 'en': 'Compare friction scores over time'},
    'trend.filter_unit': {'da': 'Filtrer efter enhed', 'en': 'Filter by unit'},
    'trend.all_units': {'da': 'Alle enheder', 'en': 'All units'},
    'trend.total_assessments': {'da': 'Målinger', 'en': 'Assessments'},
    'trend.date_range': {'da': 'Periode', 'en': 'Period'},
    'trend.chart_title': {'da': 'Score udvikling', 'en': 'Score development'},
    'trend.details_title': {'da': 'Detaljer per måling', 'en': 'Details per assessment'},
    'trend.col_date': {'da': 'Dato', 'en': 'Date'},
    'trend.col_assessment': {'da': 'Måling', 'en': 'Assessment'},
    'trend.col_unit': {'da': 'Enhed', 'en': 'Unit'},
    'trend.col_responses': {'da': 'Svar', 'en': 'Responses'},
    'trend.no_data': {'da': 'Ingen målinger fundet. Opret en måling for at se trends.', 'en': 'No assessments found. Create an assessment to see trends.'},
    'trend.create_assessment': {'da': 'Opret måling', 'en': 'Create assessment'},
    'trend.score_axis': {'da': 'Score (1-5)', 'en': 'Score (1-5)'},
    'trend.date_axis': {'da': 'Dato', 'en': 'Date'},

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
    'login.forgot_password': {'da': 'Glemt password?', 'en': 'Forgot password?'},
    'login.email_code': {'da': 'Log ind med email-kode i stedet', 'en': 'Log in with email code instead'},
    'login.no_account': {'da': 'Har du ikke en konto?', 'en': "Don't have an account?"},
    'login.register_link': {'da': 'Opret konto', 'en': 'Create account'},
    'login.need_help': {'da': 'Brug for hjælp?', 'en': 'Need help?'},
    'login.or': {'da': 'eller', 'en': 'or'},
    'login.microsoft': {'da': 'Log ind med Microsoft', 'en': 'Log in with Microsoft'},
    'login.google': {'da': 'Log ind med Google', 'en': 'Log in with Google'},
    'login.apple': {'da': 'Log ind med Apple', 'en': 'Log in with Apple'},
    'login.facebook': {'da': 'Log ind med Facebook', 'en': 'Log in with Facebook'},

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

    # Assessments/Målinger
    'assessment.title': {'da': 'Målinger', 'en': 'Assessments'},
    'assessment.create': {'da': 'Opret måling', 'en': 'Create assessment'},
    'assessment.responses': {'da': 'besvarelser', 'en': 'responses'},

    # Confirmations
    'confirm.delete': {'da': 'Er du sikker på at du vil slette?', 'en': 'Are you sure you want to delete?'},
    'confirm.delete_warning': {'da': 'Dette kan ikke fortrydes!', 'en': 'This cannot be undone!'},

    # Loading / Status
    'loading': {'da': 'Arbejder...', 'en': 'Working...'},

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

    # Customers & Users
    'customers.title': {'da': 'Kunder & Brugere', 'en': 'Customers & Users'},
    'customers.customers': {'da': 'Kunder', 'en': 'Customers'},
    'customers.create_customer': {'da': 'Opret ny kunde', 'en': 'Create new customer'},
    'customers.customer_name': {'da': 'Kunde navn', 'en': 'Customer name'},
    'customers.contact_email': {'da': 'Kontakt email', 'en': 'Contact email'},
    'customers.org_count': {'da': 'Antal organisationer', 'en': 'Number of organizations'},
    'customers.created_at': {'da': 'Oprettet', 'en': 'Created'},
    'customers.actions': {'da': 'Handlinger', 'en': 'Actions'},
    'customers.view_as_manager': {'da': 'Se som Leder', 'en': 'View as Manager'},
    'customers.no_customers': {'da': 'Ingen kunder endnu.', 'en': 'No customers yet.'},

    'users.users': {'da': 'Brugere', 'en': 'Users'},
    'users.create_user': {'da': 'Opret ny bruger', 'en': 'Create new user'},
    'users.username': {'da': 'Brugernavn', 'en': 'Username'},
    'users.password': {'da': 'Password', 'en': 'Password'},
    'users.name': {'da': 'Navn', 'en': 'Name'},
    'users.email': {'da': 'Email', 'en': 'Email'},
    'users.role': {'da': 'Rolle', 'en': 'Role'},
    'users.customer': {'da': 'Kunde', 'en': 'Customer'},
    'users.last_login': {'da': 'Sidst logget ind', 'en': 'Last login'},
    'users.never': {'da': 'Aldrig', 'en': 'Never'},
    'users.no_users': {'da': 'Ingen brugere endnu.', 'en': 'No users yet.'},
    'users.role_manager': {'da': 'Leder', 'en': 'Manager'},
    'users.role_admin': {'da': 'Admin', 'en': 'Admin'},
    'users.select_customer': {'da': 'Vælg kunde...', 'en': 'Select customer...'},

    # Analyser
    'analyser.title': {'da': 'Analyser', 'en': 'Analyses'},
    'analyser.new_analysis': {'da': 'Ny Måling', 'en': 'New Assessment'},
    'analyser.org_unit': {'da': 'Organisationsenhed', 'en': 'Organizational unit'},
    'analyser.responses': {'da': 'Svar', 'en': 'Responses'},
    'analyser.warnings': {'da': 'Advarsler', 'en': 'Warnings'},
    'analyser.total_score': {'da': 'Samlet Score', 'en': 'Total Score'},
    'analyser.employees': {'da': 'Medarbejdere', 'en': 'Employees'},
    'analyser.respondents': {'da': 'respondenter', 'en': 'respondents'},
    'analyser.level': {'da': 'Niveau', 'en': 'Level'},
    'analyser.no_data': {'da': 'Ingen data tilgængelig', 'en': 'No data available'},
    'analyser.no_data_desc': {'da': 'Der er ingen friktionsdata for de valgte filtre endnu', 'en': 'There is no friction data for the selected filters yet'},

    'analyser.friction_level': {'da': 'Friktionsniveau', 'en': 'Friction level'},
    'analyser.low_friction': {'da': 'Lav friktion (over 70%)', 'en': 'Low friction (over 70%)'},
    'analyser.moderate_friction': {'da': 'Moderat friktion (50-70%)', 'en': 'Moderate friction (50-70%)'},
    'analyser.high_friction': {'da': 'Høj friktion (under 50%)', 'en': 'High friction (under 50%)'},

    'analyser.alert_substitution': {'da': 'Substitution detekteret (siger "jeg mangler tid" men mener "jeg er utilfreds")', 'en': 'Substitution detected (says "I lack time" but means "I am dissatisfied")'},
    'analyser.alert_gap': {'da': 'Leder/medarbejder gap (stor forskel i opfattelse)', 'en': 'Leader/employee gap (large difference in perception)'},
    'analyser.alert_blocked': {'da': 'Leder blokeret (lederens egne friktioner kan blokere for hjælp)', 'en': 'Leader blocked (leader\'s own frictions may block their ability to help)'},

    # Dashboard
    'dashboard.org_dashboard': {'da': 'Organisations Dashboard', 'en': 'Organization Dashboard'},
    'dashboard.see_analyses': {'da': 'Se Analyser', 'en': 'View Analyses'},
    'dashboard.units': {'da': 'enheder', 'en': 'units'},
    'dashboard.measurements': {'da': 'målinger', 'en': 'assessments'},
    'dashboard.avg_score': {'da': 'Gns. Score', 'en': 'Avg. Score'},
    'dashboard.no_data': {'da': 'Ingen data', 'en': 'No data'},
    'dashboard.subunits': {'da': 'underenheder', 'en': 'subunits'},
    'dashboard.see_analysis': {'da': 'Se analyse', 'en': 'View analysis'},
    'dashboard.responses': {'da': 'besvarelser', 'en': 'responses'},
    'dashboard.profiles': {'da': 'profiler', 'en': 'profiles'},
    'dashboard.individual_profiles': {'da': 'Individuelle Friktionsprofiler', 'en': 'Individual Friction Profiles'},
    'dashboard.see_profile': {'da': 'Se profil', 'en': 'View profile'},
    'dashboard.no_subunits': {'da': 'Ingen underenheder', 'en': 'No subunits'},
    'dashboard.no_subunits_desc': {'da': 'Der er ingen underenheder på dette niveau.', 'en': 'There are no subunits at this level.'},

    # Unit forms
    'unit.create': {'da': 'Opret ny Organisation', 'en': 'Create New Organization'},
    'unit.back_to_overview': {'da': 'Tilbage til oversigt', 'en': 'Back to overview'},
    'unit.parent_org': {'da': 'Overordnet Organisation', 'en': 'Parent Organization'},
    'unit.parent_none': {'da': '-- Ingen (Top-level) --', 'en': '-- None (Top-level) --'},
    'unit.name': {'da': 'Navn', 'en': 'Name'},
    'unit.leader_name': {'da': 'Leder Navn', 'en': 'Leader Name'},
    'unit.leader_email': {'da': 'Leder Email', 'en': 'Leader Email'},
    'unit.employee_count': {'da': 'Antal Medarbejdere', 'en': 'Number of Employees'},
    'unit.sick_leave': {'da': 'Sygefravær', 'en': 'Sick Leave'},
    'unit.create_button': {'da': 'Opret Organisation', 'en': 'Create Organization'},
    'unit.tip_csv': {'da': 'Tip: Upload CSV', 'en': 'Tip: Upload CSV'},
    'unit.tip_csv_desc': {'da': 'Hvis du skal oprette mange organisationer på én gang, er det nemmere at bruge Upload CSV.', 'en': 'If you need to create many organizations at once, it is easier to use Upload CSV.'},
    'unit.info': {'da': 'Organisation Information', 'en': 'Organization Information'},
    'unit.level': {'da': 'Niveau', 'en': 'Level'},
    'unit.subunits_under': {'da': 'Afdelinger under', 'en': 'Departments under'},
    'unit.leader': {'da': 'Leder', 'en': 'Leader'},
    'unit.update_sick_leave': {'da': 'Opdater sygefravær', 'en': 'Update sick leave'},
    'unit.suborganizations': {'da': 'Underorganisationer', 'en': 'Sub-organizations'},
    'unit.see_details': {'da': 'Se detaljer', 'en': 'View details'},

    # Contacts
    'contacts.title': {'da': 'Kontakter', 'en': 'Contacts'},
    'contacts.no_contacts': {'da': 'Ingen kontakter endnu', 'en': 'No contacts yet'},
    'contacts.upload': {'da': 'Upload kontakter (CSV med kolonner: email, phone)', 'en': 'Upload contacts (CSV with columns: email, phone)'},

    # Assessments / Analyses
    'assessment.new_analysis': {'da': 'Ny Måling', 'en': 'New Assessment'},
    'assessment.analysis_name': {'da': 'Målingsnavn', 'en': 'Assessment name'},
    'assessment.period': {'da': 'Periode', 'en': 'Period'},
    'assessment.type': {'da': 'Målingstype', 'en': 'Assessment type'},
    'assessment.type_hint': {'da': 'Vælg hvilken type måling der skal gennemføres', 'en': 'Select which type of assessment to conduct'},
    'assessment.target_org': {'da': 'Target Organisation', 'en': 'Target Organization'},
    'assessment.select_org': {'da': 'Vælg organisation', 'en': 'Select organization'},
    'assessment.target_hint': {'da': 'Vælg hvilken organisation analysen skal sendes til. Alle afdelinger under denne vil modtage tokens.', 'en': 'Select which organization the analysis should be sent to. All departments under this will receive tokens.'},
    'assessment.how_it_works': {'da': 'Hvordan det virker', 'en': 'How it works'},
    'assessment.send_from': {'da': 'Send fra', 'en': 'Send from'},
    'assessment.sender_name': {'da': 'Afsender navn', 'en': 'Sender name'},
    'assessment.warning': {'da': 'Når du klikker "Send", bliver emails/SMS sendt automatisk til alle afdelinger under target organisation!', 'en': 'When you click "Send", emails/SMS will be automatically sent to all departments under the target organization!'},
    'assessment.create_and_send': {'da': 'Opret og send analyse', 'en': 'Create and send analysis'},
    'assessment.name': {'da': 'Navn', 'en': 'Name'},
    'assessment.sent': {'da': 'Sendt', 'en': 'Sent'},
    'assessment.response_rate': {'da': 'Response rate', 'en': 'Response rate'},
    'assessment.no_assessments': {'da': 'Ingen målinger endnu', 'en': 'No assessments yet'},

    # Nøgletal dashboard
    'noegletal.kunder': {'da': 'Kunder', 'en': 'Customers'},
    'noegletal.besvarelser': {'da': 'Besvarelser', 'en': 'Responses'},
    'noegletal.svarprocent': {'da': 'Svarprocent', 'en': 'Response Rate'},
    'noegletal.gennemsnit': {'da': 'gennemsnit', 'en': 'average'},
    'noegletal.friktionsfelter': {'da': 'Friktionsfelter (gennemsnit)', 'en': 'Friction Fields (average)'},
    'noegletal.skala_note': {'da': 'Skala 1-5: Lavere er mere friktion, højere er mindre friktion', 'en': 'Scale 1-5: Lower means more friction, higher means less friction'},
    'noegletal.ingen_data': {'da': 'Ingen data endnu', 'en': 'No data yet'},
    'noegletal.seneste_maalinger': {'da': 'Seneste målinger', 'en': 'Recent assessments'},
    'noegletal.ingen_maalinger': {'da': 'Ingen målinger endnu', 'en': 'No assessments yet'},
    'noegletal.per_kunde': {'da': 'Per kunde', 'en': 'Per customer'},

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

    # Email Settings
    'email_settings.title': {'da': 'Email-indstillinger', 'en': 'Email Settings'},
    'email_settings.subtitle': {'da': 'Konfigurer afsender-email for målingsinvitationer sendt til denne kundes medarbejdere.', 'en': 'Configure sender email for survey invitations sent to this customer\'s employees.'},
    'email_settings.customer': {'da': 'Kunde', 'en': 'Customer'},
    'email_settings.current_sender': {'da': 'Nuværende afsender', 'en': 'Current sender'},
    'email_settings.configured': {'da': 'Konfigureret', 'en': 'Configured'},
    'email_settings.using_default': {'da': 'Bruger standard', 'en': 'Using default'},
    'email_settings.from_address': {'da': 'Afsender email-adresse', 'en': 'Sender email address'},
    'email_settings.from_address_hint': {'da': 'F.eks. noreply@jeres-domæne.dk eller hr@jeres-virksomhed.dk', 'en': 'E.g. noreply@your-domain.com or hr@your-company.com'},
    'email_settings.from_name': {'da': 'Afsender navn', 'en': 'Sender name'},
    'email_settings.from_name_hint': {'da': 'Navnet der vises som afsender i modtagerens indbakke', 'en': 'The name shown as sender in recipient\'s inbox'},
    'email_settings.saved': {'da': 'Email-indstillinger gemt!', 'en': 'Email settings saved!'},
    'email_settings.dns_setup': {'da': 'DNS Opsætning (SPF & DKIM)', 'en': 'DNS Setup (SPF & DKIM)'},
    'email_settings.important': {'da': 'Vigtigt', 'en': 'Important'},
    'email_settings.dns_warning': {'da': 'For at emails ikke havner i spam, skal dit domæne have korrekte SPF og DKIM records. Kontakt din IT-afdeling eller domæne-administrator for at få disse tilføjet.', 'en': 'To prevent emails from going to spam, your domain needs correct SPF and DKIM records. Contact your IT department or domain administrator to add these.'},
    'email_settings.what_to_setup': {'da': 'Hvad skal konfigureres?', 'en': 'What needs to be configured?'},
    'email_settings.dns_intro': {'da': 'Vi bruger Mailjet til at sende emails. For at dit domæne kan sende via Mailjet, skal følgende DNS records tilføjes:', 'en': 'We use Mailjet to send emails. For your domain to send via Mailjet, the following DNS records need to be added:'},
    'email_settings.spf_record': {'da': 'SPF Record', 'en': 'SPF Record'},
    'email_settings.spf_description': {'da': 'SPF fortæller email-servere, at Mailjet har tilladelse til at sende emails på vegne af dit domæne.', 'en': 'SPF tells email servers that Mailjet is allowed to send emails on behalf of your domain.'},
    'email_settings.spf_note': {'da': 'Hvis du allerede har en SPF record, tilføj "include:spf.mailjet.com" før "~all" eller "-all"', 'en': 'If you already have an SPF record, add "include:spf.mailjet.com" before "~all" or "-all"'},
    'email_settings.dkim_record': {'da': 'DKIM Record', 'en': 'DKIM Record'},
    'email_settings.dkim_description': {'da': 'DKIM signerer emails digitalt og beviser, at de ikke er blevet ændret undervejs.', 'en': 'DKIM digitally signs emails and proves they haven\'t been altered in transit.'},
    'email_settings.setup_steps': {'da': 'Opsætnings-guide', 'en': 'Setup Guide'},
    'email_settings.step1_title': {'da': 'Tilføj afsender i Mailjet', 'en': 'Add sender in Mailjet'},
    'email_settings.step1_desc': {'da': 'Log ind på Mailjet og tilføj din email-adresse som godkendt afsender under "Sender domains & addresses".', 'en': 'Log in to Mailjet and add your email address as an approved sender under "Sender domains & addresses".'},
    'email_settings.step2_title': {'da': 'Verificer domænet', 'en': 'Verify domain'},
    'email_settings.step2_desc': {'da': 'Mailjet viser dig de DNS records (SPF + DKIM), du skal tilføje. Kopiér disse værdier.', 'en': 'Mailjet shows you the DNS records (SPF + DKIM) you need to add. Copy these values.'},
    'email_settings.step3_title': {'da': 'Tilføj DNS records', 'en': 'Add DNS records'},
    'email_settings.step3_desc': {'da': 'Log ind hos din domæne-udbyder (f.eks. One.com, Simply, GoDaddy) og tilføj TXT records for SPF og DKIM.', 'en': 'Log in to your domain provider (e.g. GoDaddy, Cloudflare, Namecheap) and add TXT records for SPF and DKIM.'},
    'email_settings.step4_title': {'da': 'Bekræft i Mailjet', 'en': 'Confirm in Mailjet'},
    'email_settings.step4_desc': {'da': 'Gå tilbage til Mailjet og klik "Check DNS" for at verificere, at records er korrekt konfigureret. Dette kan tage op til 24 timer.', 'en': 'Go back to Mailjet and click "Check DNS" to verify records are correctly configured. This can take up to 24 hours.'},
    'email_settings.step5_title': {'da': 'Konfigurer her', 'en': 'Configure here'},
    'email_settings.step5_desc': {'da': 'Når domænet er verificeret i Mailjet, indtast email-adressen i formularen ovenfor.', 'en': 'Once the domain is verified in Mailjet, enter the email address in the form above.'},
    'email_settings.tips': {'da': 'Tips', 'en': 'Tips'},
    'email_settings.tip1': {'da': 'Brug en "noreply@" adresse hvis I ikke vil modtage svar', 'en': 'Use a "noreply@" address if you don\'t want to receive replies'},
    'email_settings.tip2': {'da': 'Brug et genkendeligt navn som afsender, f.eks. "HR Afdeling" eller virksomhedsnavnet', 'en': 'Use a recognizable sender name, e.g. "HR Department" or company name'},
    'email_settings.tip3': {'da': 'Test altid ved at sende en test-invitation til dig selv efter opsætning', 'en': 'Always test by sending a test invitation to yourself after setup'},
    'customers.email_settings': {'da': 'Email', 'en': 'Email'},

    # Landing page
    'landing.brand': {'da': 'Friktionskompasset', 'en': 'Friction Compass'},
    'landing.nav.what_is_friction': {'da': 'Hvad er friktion?', 'en': 'What is friction?'},
    'landing.nav.how_it_works': {'da': 'Sådan virker det', 'en': 'How it works'},
    'landing.nav.for_business': {'da': 'For virksomheder', 'en': 'For business'},
    'landing.nav.help': {'da': 'Hjælp', 'en': 'Help'},
    'landing.nav.login': {'da': 'Log ind', 'en': 'Sign in'},

    'landing.hero.badge': {'da': '🔒 100% privat - data gemmes kun i din browser', 'en': '🔒 100% private - data stored only in your browser'},
    'landing.hero.title': {'da': 'Find ud af hvad der dræner din energi', 'en': 'Discover what drains your energy'},
    'landing.hero.subtitle': {'da': 'Tag en gratis friktionsprofil på 5 minutter og få indsigt i de små ting der slider på dig - uden at vi gemmer dine data.', 'en': 'Take a free friction profile in 5 minutes and gain insight into the small things wearing you down - without us storing your data.'},
    'landing.hero.cta_primary': {'da': 'Tag gratis profil →', 'en': 'Take free profile →'},
    'landing.hero.cta_secondary': {'da': 'Læs mere', 'en': 'Learn more'},

    'landing.friction.title': {'da': 'Hvad er friktioner?', 'en': 'What is friction?'},
    'landing.friction.subtitle': {'da': 'Friktioner er de små ting der føles bøvlede eller meningsløse - ikke store konflikter, men daglige irritationer der slider.', 'en': 'Frictions are the small things that feel cumbersome or meaningless - not big conflicts, but daily irritations that wear you down.'},
    'landing.friction.mening.title': {'da': 'Mening', 'en': 'Meaning'},
    'landing.friction.mening.desc': {'da': 'Opgaver der ikke føles umagen værd. Registreringer ingen læser. Møder uden formål.', 'en': 'Tasks that don\'t feel worth the effort. Reports no one reads. Meetings without purpose.'},
    'landing.friction.tryghed.title': {'da': 'Tryghed', 'en': 'Safety'},
    'landing.friction.tryghed.desc': {'da': 'Usikkerhed om forventninger. Uklare spilleregler. Følelsen af at være på tynd is.', 'en': 'Uncertainty about expectations. Unclear rules. The feeling of being on thin ice.'},
    'landing.friction.kan.title': {'da': 'Kan', 'en': 'Capability'},
    'landing.friction.kan.desc': {'da': 'Systemer der er langsomme. Processer der tager unødigt lang tid. For mange bolde i luften.', 'en': 'Slow systems. Processes that take unnecessarily long. Too many balls in the air.'},
    'landing.friction.besvaer.title': {'da': 'Besvær', 'en': 'Hassle'},
    'landing.friction.besvaer.desc': {'da': 'Dobbeltarbejde. Overflødige godkendelser. Omveje for at få tingene gjort.', 'en': 'Double work. Redundant approvals. Detours to get things done.'},

    'landing.how.title': {'da': 'Sådan virker det', 'en': 'How it works'},
    'landing.how.subtitle': {'da': 'På 5 minutter får du indsigt i dine friktionsmønstre', 'en': 'In 5 minutes you\'ll gain insight into your friction patterns'},
    'landing.how.step1.title': {'da': 'Besvar spørgsmål', 'en': 'Answer questions'},
    'landing.how.step1.desc': {'da': '16 korte spørgsmål om hvordan du oplever forskellige situationer i hverdagen.', 'en': '16 short questions about how you experience different situations in daily life.'},
    'landing.how.step2.title': {'da': 'Se din profil', 'en': 'See your profile'},
    'landing.how.step2.desc': {'da': 'Få et visuelt overblik over hvor friktionerne rammer dig hårdest.', 'en': 'Get a visual overview of where frictions hit you hardest.'},
    'landing.how.step3.title': {'da': 'Forstå mønstrene', 'en': 'Understand patterns'},
    'landing.how.step3.desc': {'da': 'Læs fortolkninger der hjælper dig med at forstå dine reaktioner.', 'en': 'Read interpretations that help you understand your reactions.'},
    'landing.how.step4.title': {'da': 'Tag action', 'en': 'Take action'},
    'landing.how.step4.desc': {'da': 'Brug indsigterne til samtaler med din leder, coach eller bare dig selv.', 'en': 'Use the insights for conversations with your manager, coach, or just yourself.'},

    'landing.privacy.title': {'da': 'Privacy by design', 'en': 'Privacy by design'},
    'landing.privacy.subtitle': {'da': 'Dine data tilhører dig. Vi har bygget Friktionskompasset så dine svar aldrig forlader din browser.', 'en': 'Your data belongs to you. We built Friction Compass so your answers never leave your browser.'},
    'landing.privacy.feature1': {'da': 'Alt gemmes lokalt i din browser (localStorage)', 'en': 'Everything is stored locally in your browser (localStorage)'},
    'landing.privacy.feature2': {'da': 'Ingen data sendes til vores servere', 'en': 'No data is sent to our servers'},
    'landing.privacy.feature3': {'da': 'Ingen cookies til tracking', 'en': 'No tracking cookies'},
    'landing.privacy.feature4': {'da': 'Du kan eksportere og slette dine data når som helst', 'en': 'You can export and delete your data at any time'},
    'landing.privacy.feature5': {'da': 'Open source og gennemsigtigt', 'en': 'Open source and transparent'},

    'landing.business.title': {'da': 'For virksomheder', 'en': 'For business'},
    'landing.business.subtitle': {'da': 'Friktionskompasset hjælper teams og organisationer med at identificere og fjerne de friktioner der sænker produktiviteten.', 'en': 'Friction Compass helps teams and organizations identify and remove frictions that reduce productivity.'},
    'landing.business.cta': {'da': 'Kom i gang →', 'en': 'Get started →'},
    'landing.business.feature1.title': {'da': 'Anonyme målinger', 'en': 'Anonymous assessments'},
    'landing.business.feature1.desc': {'da': 'Få ærlige svar uden at kompromittere medarbejdernes privatliv', 'en': 'Get honest answers without compromising employee privacy'},
    'landing.business.feature2.title': {'da': 'Team-analyser', 'en': 'Team analyses'},
    'landing.business.feature2.desc': {'da': 'Se mønstre på tværs af afdelinger og teams', 'en': 'See patterns across departments and teams'},
    'landing.business.feature3.title': {'da': 'Trend-tracking', 'en': 'Trend tracking'},
    'landing.business.feature3.desc': {'da': 'Følg udviklingen over tid', 'en': 'Follow development over time'},
    'landing.business.feature4.title': {'da': 'Handlingsanbefalinger', 'en': 'Action recommendations'},
    'landing.business.feature4.desc': {'da': 'Konkrete forslag baseret på jeres data', 'en': 'Concrete suggestions based on your data'},

    'landing.cta.title': {'da': 'Klar til at finde dine friktioner?', 'en': 'Ready to find your frictions?'},
    'landing.cta.subtitle': {'da': 'Det tager kun 5 minutter - og vi gemmer intet.', 'en': 'It only takes 5 minutes - and we store nothing.'},

    'landing.footer.tagline': {'da': 'Et værktøj til at identificere og fjerne friktioner der dræner din energi.', 'en': 'A tool to identify and remove frictions that drain your energy.'},
    'landing.footer.product': {'da': 'Produkt', 'en': 'Product'},
    'landing.footer.free_profile': {'da': 'Gratis profil', 'en': 'Free profile'},
    'landing.footer.for_business': {'da': 'For virksomheder', 'en': 'For business'},
    'landing.footer.account': {'da': 'Konto', 'en': 'Account'},
    'landing.footer.create_account': {'da': 'Opret konto', 'en': 'Create account'},
    'landing.footer.legal': {'da': 'Juridisk', 'en': 'Legal'},
    'landing.footer.privacy_settings': {'da': 'Privatlivsindstillinger', 'en': 'Privacy settings'},
    'landing.footer.made_with_love': {'da': 'Lavet med ❤️ i Danmark', 'en': 'Made with ❤️ in Denmark'},
    'landing.footer.copyright': {'da': '© 2025 Friktionskompasset', 'en': '© 2025 Friction Compass'},

    'landing.meta.title': {'da': 'Friktionskompasset - Find og fjern dine friktioner', 'en': 'Friction Compass - Find and remove your frictions'},
    'landing.meta.og_title': {'da': 'Friktionskompasset - Find og fjern dine friktioner', 'en': 'Friction Compass - Find and remove your frictions'},
    'landing.meta.description': {'da': 'Friktionskompasset hjælper dig med at identificere og fjerne friktioner der dræner din energi - på arbejdet og i livet.', 'en': 'Friction Compass helps you identify and remove frictions that drain your energy - at work and in life.'},
    'landing.meta.og_description': {'da': 'Tag en gratis friktionsprofil og få indsigt i hvad der dræner din energi.', 'en': 'Take a free friction profile and gain insight into what drains your energy.'},
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
