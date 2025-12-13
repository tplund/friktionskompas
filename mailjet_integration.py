"""
Mailjet integration for Friktionskompasset
Send emails og SMS via Mailjet
"""
import os
import sqlite3
from typing import List, Dict, Optional
from dotenv import load_dotenv
from mailjet_rest import Client
from datetime import datetime

# Load .env file
load_dotenv()

# Mailjet API credentials (sæt som environment variables)
MAILJET_API_KEY = os.getenv('MAILJET_API_KEY', '')
MAILJET_API_SECRET = os.getenv('MAILJET_API_SECRET', '')
DEFAULT_FROM_EMAIL = os.getenv('FROM_EMAIL', 'info@friktionskompasset.dk')
DEFAULT_FROM_NAME = os.getenv('FROM_NAME', 'Friktionskompasset')
BASE_URL = os.getenv('BASE_URL', 'https://friktionskompas.onrender.com')

# Legacy aliases for backwards compatibility
FROM_EMAIL = DEFAULT_FROM_EMAIL
FROM_NAME = DEFAULT_FROM_NAME


def get_email_sender(customer_id: str = None) -> Dict[str, str]:
    """
    Hent email-afsender for en kunde.
    Returnerer {'email': '...', 'name': '...'} dict til Mailjet.
    """
    if customer_id:
        try:
            from db_multitenant import get_customer_email_config
            config = get_customer_email_config(customer_id)
            return {
                'Email': config['from_address'],
                'Name': config['from_name']
            }
        except Exception as e:
            print(f"[Mailjet] Error getting customer email config: {e}")

    return {
        'Email': DEFAULT_FROM_EMAIL,
        'Name': DEFAULT_FROM_NAME
    }

# Initialize Mailjet client
mailjet = Client(auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version='v3.1')

# Database path (same logic as db_hierarchical.py)
RENDER_DISK_PATH = "/var/data"
if os.path.exists(RENDER_DISK_PATH):
    DB_PATH = os.path.join(RENDER_DISK_PATH, "friktionskompas_v3.db")
else:
    DB_PATH = "friktionskompas_v3.db"


def ensure_email_logs_table():
    """Opret email_logs tabel hvis den ikke findes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                to_email TEXT NOT NULL,
                subject TEXT,
                email_type TEXT DEFAULT 'invitation',
                status TEXT DEFAULT 'sent',
                assessment_id TEXT,
                token TEXT,
                error_message TEXT,
                delivered_at TIMESTAMP,
                opened_at TIMESTAMP,
                clicked_at TIMESTAMP,
                bounced_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creating email_logs table: {e}")


def log_email(to_email: str, subject: str, email_type: str, status: str,
              message_id: str = None, assessment_id: str = None, token: str = None,
              error_message: str = None) -> int:
    """Log email til database for tracking"""
    try:
        ensure_email_logs_table()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("""
            INSERT INTO email_logs (message_id, to_email, subject, email_type, status,
                                   assessment_id, token, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (message_id, to_email, subject, email_type, status, assessment_id, token, error_message))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id
    except Exception as e:
        print(f"Error logging email: {e}")
        return None


def update_email_status(message_id: str, status: str, timestamp_field: str = None):
    """Opdater email status (kaldt fra webhook)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        if timestamp_field:
            conn.execute(f"""
                UPDATE email_logs SET status = ?, {timestamp_field} = ?
                WHERE message_id = ?
            """, (status, datetime.now().isoformat(), message_id))
        else:
            conn.execute("""
                UPDATE email_logs SET status = ? WHERE message_id = ?
            """, (status, message_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating email status: {e}")


def get_email_stats(assessment_id: str = None) -> Dict:
    """Hent email statistik"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        if assessment_id:
            stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
                    SUM(CASE WHEN status = 'opened' THEN 1 ELSE 0 END) as opened,
                    SUM(CASE WHEN status = 'clicked' THEN 1 ELSE 0 END) as clicked,
                    SUM(CASE WHEN status = 'bounced' THEN 1 ELSE 0 END) as bounced,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                FROM email_logs WHERE assessment_id = ?
            """, (assessment_id,)).fetchone()
        else:
            stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
                    SUM(CASE WHEN status = 'opened' THEN 1 ELSE 0 END) as opened,
                    SUM(CASE WHEN status = 'clicked' THEN 1 ELSE 0 END) as clicked,
                    SUM(CASE WHEN status = 'bounced' THEN 1 ELSE 0 END) as bounced,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                FROM email_logs
            """).fetchone()

        conn.close()
        return dict(stats) if stats else {}
    except Exception as e:
        print(f"Error getting email stats: {e}")
        return {}


def get_email_logs(assessment_id: str = None, limit: int = 100) -> List[Dict]:
    """Hent email logs"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        if assessment_id:
            logs = conn.execute("""
                SELECT * FROM email_logs WHERE assessment_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (assessment_id, limit)).fetchall()
        else:
            logs = conn.execute("""
                SELECT * FROM email_logs ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()

        conn.close()
        return [dict(row) for row in logs]
    except Exception as e:
        print(f"Error getting email logs: {e}")
        return []


def check_mailjet_status(message_id: str) -> Optional[Dict]:
    """Tjek delivery status via Mailjet API"""
    if not message_id:
        return None
    try:
        mailjet_v3 = Client(auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version='v3')
        result = mailjet_v3.message.get(id=message_id)
        if result.status_code == 200:
            return result.json()
    except Exception as e:
        print(f"Error checking Mailjet status: {e}")
    return None


# ========================================
# EMAIL TEMPLATES (Multi-language)
# ========================================

# Danish templates
DEFAULT_TEMPLATES_DA = {
    'invitation': {
        'subject': 'Hjælp os fjerne friktioner (5 min, anonymt)',
        'html': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {primary_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: {primary_color}; color: white;
                  padding: 12px 30px; text-decoration: none; border-radius: 6px;
                  margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;
                  font-size: 0.875rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>{header_text}</h2>
        </div>
        <div class="content">
            <p>Hej!</p>

            <p><strong>{sender_name}</strong> vil gerne høre om de små ting der står i vejen
            i hverdagen - friktioner som dobbeltarbejde, procedurer der tager for lang tid,
            eller opgaver der føles meningsløse.</p>

            <p><strong>Det tager 5 minutter</strong> og er <strong>fuldstændig anonymt</strong>.</p>

            <a href="{survey_url}" class="button">
                Besvar spørgsmål (5 min)
            </a>

            <p style="margin-top: 20px;">Eller kopier dette link til din browser:<br>
            <a href="{survey_url}">{survey_url}</a></p>

            <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 15px;
                       margin: 20px 0; border-radius: 4px;">
                <strong>Anonymitet:</strong><br>
                {anonymity_text}
            </div>

            <p>{closing_text}</p>

            <p>Mvh<br>
            {sender_name}</p>

            <div class="footer">
                <p>Dette er en del af målingen: <strong>{assessment_name}</strong></p>
                <p>Spørgsmål? Kontakt {contact_email}</p>
            </div>
        </div>
    </div>
</body>
</html>
''',
        'text': '''
{header_text}

{sender_name} vil gerne høre om de små ting der står i vejen i hverdagen.

Det tager 5 minutter og er fuldstændig anonymt.

Besvar her: {survey_url}

Anonymitet:
{anonymity_text}

{closing_text}

Mvh
{sender_name}

---
Måling: {assessment_name}
'''
    },
    'reminder': {
        'subject': 'Reminder: Friktionsmåling ({responses_count} har svaret)',
        'html': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .content {{ background: #fef3c7; padding: 20px; border-left: 4px solid #f59e0b; border-radius: 4px; }}
        .button {{ display: inline-block; background: {primary_color}; color: white;
                  padding: 12px 30px; text-decoration: none; border-radius: 6px;
                  margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h3>Husk at svare på friktionsmålingen</h3>
        <div class="content">
            <p>Hej igen!</p>

            <p>Vi mangler stadig dit svar til friktionsmålingen.</p>

            <p><strong>Status:</strong> {responses_count} personer har svaret.
            Vi skal have mindst 5 for at kunne vise resultater (pga. anonymitet).</p>

            <a href="{survey_url}" class="button">
                Besvar nu (5 min)
            </a>

            <p>Det tager 5 minutter og er fuldstændig anonymt.</p>

            <p>Mvh<br>
            {sender_name}</p>
        </div>
    </div>
</body>
</html>
''',
        'text': '''
Husk at svare på friktionsmålingen

Hej igen!

Vi mangler stadig dit svar til friktionsmålingen.

Status: {responses_count} personer har svaret. Vi skal have mindst 5.

Besvar her: {survey_url}

Det tager 5 minutter og er anonymt.

Mvh
{sender_name}
'''
    },
    'profil_invitation': {
        'subject': 'Din Friktionsprofil venter',
        'html': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
                  color: white; padding: 25px; border-radius: 8px 8px 0 0; text-align: center; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: #0f3460; color: white;
                  padding: 14px 35px; text-decoration: none; border-radius: 6px;
                  margin: 20px 0; font-weight: bold; }}
        .info-box {{ background: #e8eaf6; border-left: 4px solid #3949ab;
                    padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;
                  font-size: 0.875rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Din Friktionsprofil</h2>
            <p style="opacity: 0.9; margin: 0;">Forstå hvordan pres bevæger sig gennem dig</p>
        </div>
        <div class="content">
            <p>{greeting}</p>

            <p>Du er inviteret til at udfylde din personlige friktionsprofil som en del af
            <strong>{context_text}</strong>.</p>

            <div class="info-box">
                <strong>Hvad er en friktionsprofil?</strong><br>
                En friktionsprofil viser hvordan du reagerer på pres i fire områder:
                Tryghed, Mening, Kan og Besvær - og på tværs af fire lag:
                Krop, Emotion, Indre og Kognition.
            </div>

            <p><strong>Det tager 5-7 minutter</strong> og giver dig et visuelt overblik
            over din personlige reguleringsarkitektur.</p>

            <div style="text-align: center;">
                <a href="{survey_url}" class="button">
                    Start din friktionsprofil
                </a>
            </div>

            <p style="margin-top: 20px; font-size: 0.9rem;">Eller kopier dette link:<br>
            <a href="{survey_url}">{survey_url}</a></p>

            <p>Mvh<br>
            {sender_name}</p>

            <div class="footer">
                <p>Spørgsmål? Kontakt {contact_email}</p>
            </div>
        </div>
    </div>
</body>
</html>
''',
        'text': '''
Din Friktionsprofil

{greeting}

Du er inviteret til at udfylde din personlige friktionsprofil som en del af {context_text}.

Hvad er en friktionsprofil?
En friktionsprofil viser hvordan du reagerer på pres i fire områder:
Tryghed, Mening, Kan og Besvær.

Det tager 5-7 minutter.

Start her: {survey_url}

Mvh
{sender_name}
'''
    },
    'assessment_completed': {
        'subject': 'Måling afsluttet: {assessment_name} - Resultater klar',
        'html': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                  color: white; padding: 25px; border-radius: 8px 8px 0 0; text-align: center; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: #3b82f6; color: white;
                  padding: 14px 35px; text-decoration: none; border-radius: 6px;
                  margin: 20px 0; font-weight: bold; }}
        .stats {{ background: #ecfdf5; border-left: 4px solid #10b981;
                 padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;
                  font-size: 0.875rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Måling Afsluttet</h2>
            <p style="opacity: 0.9; margin: 0;">Resultaterne er nu tilgængelige</p>
        </div>
        <div class="content">
            <p>Hej {recipient_name}!</p>

            <p>Friktionsmålingen <strong>{assessment_name}</strong> er nu afsluttet og resultaterne er klar til gennemgang.</p>

            <div class="stats">
                <strong>Statistik:</strong><br>
                Besvarelser: {responses_count} af {tokens_sent}<br>
                Svarprocent: {response_rate}%<br>
                Organisation: {organization_name}
            </div>

            <a href="{results_url}" class="button">
                Se Resultater
            </a>

            <p>Du kan nu se den detaljerede analyse med:</p>
            <ul>
                <li>Friktionskompas (radar chart)</li>
                <li>Sammenligning mellem medarbejdere og ledere</li>
                <li>KKC-anbefalinger</li>
                <li>Fritekst kommentarer</li>
            </ul>

            <p>Mvh<br>
            Friktionskompasset</p>

            <div class="footer">
                <p>Du modtager denne email fordi du er administrator for denne måling.</p>
            </div>
        </div>
    </div>
</body>
</html>
''',
        'text': '''
Måling Afsluttet: {assessment_name}

Hej {recipient_name}!

Friktionsmålingen "{assessment_name}" er nu afsluttet og resultaterne er klar.

Statistik:
- Besvarelser: {responses_count} af {tokens_sent}
- Svarprocent: {response_rate}%
- Organisation: {organization_name}

Se resultater her: {results_url}

Mvh
Friktionskompasset
'''
    }
}

# English templates
DEFAULT_TEMPLATES_EN = {
    'invitation': {
        'subject': 'Help us remove friction (5 min, anonymous)',
        'html': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {primary_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: {primary_color}; color: white;
                  padding: 12px 30px; text-decoration: none; border-radius: 6px;
                  margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;
                  font-size: 0.875rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>{header_text}</h2>
        </div>
        <div class="content">
            <p>Hi!</p>

            <p><strong>{sender_name}</strong> would like to hear about the small things that get in the way
            in everyday work - friction like duplicate work, procedures that take too long,
            or tasks that feel meaningless.</p>

            <p><strong>It takes 5 minutes</strong> and is <strong>completely anonymous</strong>.</p>

            <a href="{survey_url}" class="button">
                Answer questions (5 min)
            </a>

            <p style="margin-top: 20px;">Or copy this link to your browser:<br>
            <a href="{survey_url}">{survey_url}</a></p>

            <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 15px;
                       margin: 20px 0; border-radius: 4px;">
                <strong>Anonymity:</strong><br>
                {anonymity_text}
            </div>

            <p>{closing_text}</p>

            <p>Best regards,<br>
            {sender_name}</p>

            <div class="footer">
                <p>This is part of the survey: <strong>{assessment_name}</strong></p>
                <p>Questions? Contact {contact_email}</p>
            </div>
        </div>
    </div>
</body>
</html>
''',
        'text': '''
{header_text}

{sender_name} would like to hear about the small things that get in the way in everyday work.

It takes 5 minutes and is completely anonymous.

Answer here: {survey_url}

Anonymity:
{anonymity_text}

{closing_text}

Best regards,
{sender_name}

---
Survey: {assessment_name}
'''
    },
    'reminder': {
        'subject': 'Reminder: Friction survey ({responses_count} have responded)',
        'html': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .content {{ background: #fef3c7; padding: 20px; border-left: 4px solid #f59e0b; border-radius: 4px; }}
        .button {{ display: inline-block; background: {primary_color}; color: white;
                  padding: 12px 30px; text-decoration: none; border-radius: 6px;
                  margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h3>Remember to answer the friction survey</h3>
        <div class="content">
            <p>Hi again!</p>

            <p>We are still missing your response to the friction survey.</p>

            <p><strong>Status:</strong> {responses_count} people have responded.
            We need at least 5 to show results (due to anonymity).</p>

            <a href="{survey_url}" class="button">
                Answer now (5 min)
            </a>

            <p>It takes 5 minutes and is completely anonymous.</p>

            <p>Best regards,<br>
            {sender_name}</p>
        </div>
    </div>
</body>
</html>
''',
        'text': '''
Remember to answer the friction survey

Hi again!

We are still missing your response to the friction survey.

Status: {responses_count} people have responded. We need at least 5.

Answer here: {survey_url}

It takes 5 minutes and is anonymous.

Best regards,
{sender_name}
'''
    },
    'profil_invitation': {
        'subject': 'Your Friction Profile is waiting',
        'html': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
                  color: white; padding: 25px; border-radius: 8px 8px 0 0; text-align: center; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: #0f3460; color: white;
                  padding: 14px 35px; text-decoration: none; border-radius: 6px;
                  margin: 20px 0; font-weight: bold; }}
        .info-box {{ background: #e8eaf6; border-left: 4px solid #3949ab;
                    padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;
                  font-size: 0.875rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Your Friction Profile</h2>
            <p style="opacity: 0.9; margin: 0;">Understand how pressure moves through you</p>
        </div>
        <div class="content">
            <p>{greeting}</p>

            <p>You are invited to complete your personal friction profile as part of
            <strong>{context_text}</strong>.</p>

            <div class="info-box">
                <strong>What is a friction profile?</strong><br>
                A friction profile shows how you respond to pressure in four areas:
                Security, Meaning, Capability and Effort - and across four layers:
                Body, Emotion, Inner and Cognition.
            </div>

            <p><strong>It takes 5-7 minutes</strong> and gives you a visual overview
            of your personal regulation architecture.</p>

            <div style="text-align: center;">
                <a href="{survey_url}" class="button">
                    Start your friction profile
                </a>
            </div>

            <p style="margin-top: 20px; font-size: 0.9rem;">Or copy this link:<br>
            <a href="{survey_url}">{survey_url}</a></p>

            <p>Best regards,<br>
            {sender_name}</p>

            <div class="footer">
                <p>Questions? Contact {contact_email}</p>
            </div>
        </div>
    </div>
</body>
</html>
''',
        'text': '''
Your Friction Profile

{greeting}

You are invited to complete your personal friction profile as part of {context_text}.

What is a friction profile?
A friction profile shows how you respond to pressure in four areas:
Security, Meaning, Capability and Effort.

It takes 5-7 minutes.

Start here: {survey_url}

Best regards,
{sender_name}
'''
    },
    'assessment_completed': {
        'subject': 'Survey Complete: {assessment_name} - Results Ready',
        'html': '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                  color: white; padding: 25px; border-radius: 8px 8px 0 0; text-align: center; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: #3b82f6; color: white;
                  padding: 14px 35px; text-decoration: none; border-radius: 6px;
                  margin: 20px 0; font-weight: bold; }}
        .stats {{ background: #ecfdf5; border-left: 4px solid #10b981;
                 padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;
                  font-size: 0.875rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Survey Complete</h2>
            <p style="opacity: 0.9; margin: 0;">Results are now available</p>
        </div>
        <div class="content">
            <p>Hi {recipient_name}!</p>

            <p>The friction survey <strong>{assessment_name}</strong> is now complete and results are ready for review.</p>

            <div class="stats">
                <strong>Statistics:</strong><br>
                Responses: {responses_count} of {tokens_sent}<br>
                Response rate: {response_rate}%<br>
                Organization: {organization_name}
            </div>

            <a href="{results_url}" class="button">
                View Results
            </a>

            <p>You can now see the detailed analysis with:</p>
            <ul>
                <li>Friction compass (radar chart)</li>
                <li>Comparison between employees and managers</li>
                <li>KKC recommendations</li>
                <li>Free-text comments</li>
            </ul>

            <p>Best regards,<br>
            Friktionskompasset</p>

            <div class="footer">
                <p>You received this email because you are the administrator for this survey.</p>
            </div>
        </div>
    </div>
</body>
</html>
''',
        'text': '''
Survey Complete: {assessment_name}

Hi {recipient_name}!

The friction survey "{assessment_name}" is now complete and results are ready.

Statistics:
- Responses: {responses_count} of {tokens_sent}
- Response rate: {response_rate}%
- Organization: {organization_name}

View results here: {results_url}

Best regards,
Friktionskompasset
'''
    }
}

# Combined templates dict for backwards compatibility
DEFAULT_TEMPLATES = DEFAULT_TEMPLATES_DA

def get_templates_for_language(language: str = 'da') -> dict:
    """Get templates for a specific language"""
    if language == 'en':
        return DEFAULT_TEMPLATES_EN
    return DEFAULT_TEMPLATES_DA


def get_template(template_type: str, customer_id: int = None, language: str = 'da') -> Dict:
    """Hent email template - først kunde-specifik, ellers default for sprog"""
    if customer_id:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            template = conn.execute("""
                SELECT * FROM email_templates
                WHERE customer_id = ? AND template_type = ? AND is_active = 1
                ORDER BY updated_at DESC LIMIT 1
            """, (customer_id, template_type)).fetchone()
            conn.close()
            if template:
                return {
                    'subject': template['subject'],
                    'html': template['html_content'],
                    'text': template['text_content']
                }
        except Exception as e:
            print(f"Error getting template: {e}")

    # Get default template for the specified language
    templates = get_templates_for_language(language)
    return templates.get(template_type, templates['invitation'])


def save_template(customer_id: int, template_type: str, subject: str,
                 html_content: str, text_content: str = None) -> bool:
    """Gem eller opdater email template for kunde"""
    try:
        conn = sqlite3.connect(DB_PATH)
        # Check if exists
        existing = conn.execute("""
            SELECT id FROM email_templates
            WHERE customer_id = ? AND template_type = ?
        """, (customer_id, template_type)).fetchone()

        if existing:
            conn.execute("""
                UPDATE email_templates
                SET subject = ?, html_content = ?, text_content = ?, updated_at = ?
                WHERE customer_id = ? AND template_type = ?
            """, (subject, html_content, text_content, datetime.now().isoformat(),
                  customer_id, template_type))
        else:
            conn.execute("""
                INSERT INTO email_templates (customer_id, template_type, subject, html_content, text_content)
                VALUES (?, ?, ?, ?, ?)
            """, (customer_id, template_type, subject, html_content, text_content))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving template: {e}")
        return False


def list_templates(customer_id: int = None) -> List[Dict]:
    """List alle templates for en kunde"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        if customer_id:
            templates = conn.execute("""
                SELECT * FROM email_templates WHERE customer_id = ? ORDER BY template_type
            """, (customer_id,)).fetchall()
        else:
            templates = conn.execute("""
                SELECT * FROM email_templates ORDER BY customer_id, template_type
            """).fetchall()
        conn.close()
        return [dict(t) for t in templates]
    except Exception as e:
        print(f"Error listing templates: {e}")
        return []


def render_template(template: Dict, variables: Dict, language: str = 'da') -> Dict:
    """Render en template med variabler"""
    # Language-specific default variables
    if language == 'en':
        defaults = {
            'primary_color': '#3b82f6',
            'header_text': 'Help us remove friction',
            'anonymity_text': '• No one can see who wrote what\n• Results are only shown when at least 5 have responded\n• Your link only works once',
            'closing_text': 'Your honest answers help us remove barriers and make everyday work better.',
            'contact_email': FROM_EMAIL
        }
    else:
        defaults = {
            'primary_color': '#3b82f6',
            'header_text': 'Hjælp os med at fjerne friktioner',
            'anonymity_text': '• Ingen kan se hvem der skrev hvad\n• Resultater vises kun når mindst 5 har svaret\n• Dit link virker kun én gang',
            'closing_text': 'Dine ærlige svar hjælper os med at fjerne barrierer og gøre hverdagen bedre.',
            'contact_email': FROM_EMAIL
        }
    # Merge defaults with provided variables
    all_vars = {**defaults, **variables}

    return {
        'subject': template['subject'].format(**all_vars),
        'html': template['html'].format(**all_vars),
        'text': template['text'].format(**all_vars) if template.get('text') else None
    }


def send_email_invitation(to_email: str, token: str, assessment_name: str,
                         sender_name: str = "HR", customer_id: str = None,
                         language: str = 'da') -> bool:
    """
    Send email invitation med magic link

    Args:
        to_email: Recipient email
        token: Survey token
        assessment_name: Name of the assessment
        sender_name: Name of sender (default "HR")
        customer_id: Optional customer ID for custom templates and email sender
        language: Language code ('da' or 'en', default 'da')
    """
    survey_url = f"{BASE_URL}/s/{token}"

    # Get template for the specified language
    template = get_template('invitation', customer_id, language)

    # Render template with variables
    rendered = render_template(template, {
        'sender_name': sender_name,
        'survey_url': survey_url,
        'assessment_name': assessment_name
    }, language)

    # Get customer-specific email sender
    email_sender = get_email_sender(customer_id)

    data = {
        'Messages': [
            {
                "From": email_sender,
                "To": [
                    {
                        "Email": to_email
                    }
                ],
                "Subject": rendered['subject'],
                "TextPart": rendered['text'],
                "HTMLPart": rendered['html']
            }
        ]
    }

    try:
        result = mailjet.send.create(data=data)
        if result.status_code == 200:
            # Extract message ID for tracking
            response_data = result.json()
            message_id = None
            if 'Messages' in response_data and len(response_data['Messages']) > 0:
                msg = response_data['Messages'][0]
                if 'To' in msg and len(msg['To']) > 0:
                    message_id = str(msg['To'][0].get('MessageID', ''))
            log_email(to_email, rendered['subject'], 'invitation', 'sent', message_id, token=token)
            return True
        else:
            log_email(to_email, rendered['subject'], 'invitation', 'error',
                     error_message=f"Status {result.status_code}")
            return False
    except Exception as e:
        print(f"Error sending email to {to_email}: {e}")
        log_email(to_email, rendered['subject'], 'invitation', 'error', error_message=str(e))
        return False


def send_sms_invitation(phone: str, token: str, assessment_name: str,
                       sender_name: str = "HR") -> bool:
    """
    Send SMS invitation (kræver SMS-gateway integration)
    
    Note: Mailjet har SMS-funktionalitet, men den kræver separat opsætning.
    Alternativt kan bruges CPSMS (dansk SMS-gateway) eller lignende.
    """
    survey_url = f"https://frikt.dk/s/{token}"  # Kort URL
    
    message = f"""Hej! {sender_name} vil gerne høre om friktioner i arbejdet.

5 min, anonymt: {survey_url}

Dit link virker kun én gang.

Mvh {sender_name}"""
    
    # TODO: Implementer SMS-gateway (CPSMS, SMS1919 eller Mailjet SMS)
    # For nu: Print til console
    print(f"SMS til {phone}:")
    print(message)
    print()
    
    return True  # Mock success


def send_reminder_email(to_email: str, token: str, assessment_name: str,
                       responses_so_far: int, sender_name: str = "HR",
                       customer_id: str = None, language: str = 'da') -> bool:
    """
    Send reminder email hvis folk ikke har svaret endnu

    Args:
        to_email: Recipient email
        token: Survey token
        assessment_name: Name of the assessment
        responses_so_far: Number of responses received
        sender_name: Name of sender (default "HR")
        customer_id: Optional customer ID for email sender
        language: Language code ('da' or 'en', default 'da')
    """
    survey_url = f"{BASE_URL}/s/{token}"

    # Get template for the specified language
    template = get_template('reminder', language=language)

    # Render template with variables
    rendered = render_template(template, {
        'sender_name': sender_name,
        'survey_url': survey_url,
        'responses_count': responses_so_far
    }, language)

    # Get customer-specific email sender
    email_sender = get_email_sender(customer_id)

    data = {
        'Messages': [
            {
                "From": email_sender,
                "To": [
                    {
                        "Email": to_email
                    }
                ],
                "Subject": rendered['subject'],
                "TextPart": rendered['text'],
                "HTMLPart": rendered['html']
            }
        ]
    }

    try:
        result = mailjet.send.create(data=data)
        if result.status_code == 200:
            response_data = result.json()
            message_id = None
            if 'Messages' in response_data and len(response_data['Messages']) > 0:
                msg = response_data['Messages'][0]
                if 'To' in msg and len(msg['To']) > 0:
                    message_id = str(msg['To'][0].get('MessageID', ''))
            log_email(to_email, rendered['subject'], 'reminder', 'sent', message_id, token=token)
            return True
        else:
            log_email(to_email, rendered['subject'], 'reminder', 'error',
                     error_message=f"Status {result.status_code}", token=token)
            return False
    except Exception as e:
        print(f"Error sending reminder to {to_email}: {e}")
        log_email(to_email, rendered['subject'], 'reminder', 'error', error_message=str(e), token=token)
        return False


def send_assessment_batch(contacts: List[Dict], tokens: List[str],
                       assessment_name: str, sender_name: str = "HR",
                       language: str = 'da') -> Dict:
    """
    Send måling til hele batch af kontakter

    contacts: List[{'email': '...', 'phone': '...'}]
    tokens: List[str] - samme længde som contacts
    language: Language code ('da' or 'en', default 'da')

    Returns: {'emails_sent': X, 'sms_sent': Y, 'errors': Z}
    """
    results = {
        'emails_sent': 0,
        'sms_sent': 0,
        'errors': 0
    }

    for i, contact in enumerate(contacts):
        token = tokens[i]

        # Send email hvis vi har en
        if contact.get('email'):
            success = send_email_invitation(
                contact['email'],
                token,
                assessment_name,
                sender_name,
                language=language
            )
            if success:
                results['emails_sent'] += 1
            else:
                results['errors'] += 1

        # Send SMS hvis vi har et nummer
        if contact.get('phone'):
            success = send_sms_invitation(
                contact['phone'],
                token,
                assessment_name,
                sender_name
            )
            if success:
                results['sms_sent'] += 1
            else:
                results['errors'] += 1

    return results


# ========================================
# FRIKTIONSPROFIL INVITATIONS
# ========================================

def send_profil_invitation(to_email: str, session_id: str, person_name: str = None,
                          context: str = "general", sender_name: str = "HR",
                          customer_id: str = None, language: str = 'da') -> bool:
    """
    Send email invitation til friktionsprofil

    Args:
        to_email: Recipient email
        session_id: Profile session ID
        person_name: Optional name for personalized greeting
        context: Context type (general, mus, coaching, konflikt, onboarding)
        sender_name: Name of sender (default "HR")
        customer_id: Optional customer ID for email sender
        language: Language code ('da' or 'en', default 'da')
    """
    survey_url = f"{BASE_URL}/profil/{session_id}"

    # Context texts in both languages
    context_texts = {
        'da': {
            'general': 'en personlig indsigt i hvordan du håndterer pres og friktion',
            'mus': 'forberedelse til din MUS-samtale',
            'coaching': 'et coaching-forløb',
            'konflikt': 'at forstå forskellige måder at håndtere pres på',
            'onboarding': 'din onboarding i organisationen'
        },
        'en': {
            'general': 'a personal insight into how you handle pressure and friction',
            'mus': 'preparation for your performance review',
            'coaching': 'a coaching program',
            'konflikt': 'understanding different ways to handle pressure',
            'onboarding': 'your onboarding in the organization'
        }
    }

    context_dict = context_texts.get(language, context_texts['da'])
    context_text = context_dict.get(context, context_dict['general'])

    if language == 'en':
        greeting = f"Hi {person_name}!" if person_name else "Hi!"
    else:
        greeting = f"Hej {person_name}!" if person_name else "Hej!"

    # Get template for the specified language
    template = get_template('profil_invitation', language=language)

    # Render template with variables
    rendered = render_template(template, {
        'sender_name': sender_name,
        'survey_url': survey_url,
        'greeting': greeting,
        'context_text': context_text
    }, language)

    # Get customer-specific email sender
    email_sender = get_email_sender(customer_id)

    data = {
        'Messages': [
            {
                "From": email_sender,
                "To": [
                    {
                        "Email": to_email
                    }
                ],
                "Subject": rendered['subject'],
                "TextPart": rendered['text'],
                "HTMLPart": rendered['html']
            }
        ]
    }

    try:
        result = mailjet.send.create(data=data)
        if result.status_code == 200:
            # Extract message ID for tracking
            response_data = result.json()
            message_id = None
            if 'Messages' in response_data and len(response_data['Messages']) > 0:
                msg = response_data['Messages'][0]
                if 'To' in msg and len(msg['To']) > 0:
                    message_id = str(msg['To'][0].get('MessageID', ''))
            log_email(to_email, rendered['subject'], 'profil_invitation', 'sent', message_id)
            return True
        else:
            log_email(to_email, rendered['subject'], 'profil_invitation', 'error',
                     error_message=f"Status {result.status_code}")
            return False
    except Exception as e:
        print(f"Error sending profil invitation to {to_email}: {e}")
        log_email(to_email, rendered['subject'], 'profil_invitation', 'error', error_message=str(e))
        return False


def send_profil_batch(invitations: List[Dict], sender_name: str = "HR",
                     language: str = 'da') -> Dict:
    """
    Send profil-invitationer til batch af personer

    invitations: List[{'email': '...', 'session_id': '...', 'name': '...', 'context': '...'}]
    language: Language code ('da' or 'en', default 'da')

    Returns: {'sent': X, 'errors': Y}
    """
    results = {'sent': 0, 'errors': 0}

    for inv in invitations:
        success = send_profil_invitation(
            to_email=inv['email'],
            session_id=inv['session_id'],
            person_name=inv.get('name'),
            context=inv.get('context', 'general'),
            sender_name=sender_name,
            language=language
        )
        if success:
            results['sent'] += 1
        else:
            results['errors'] += 1

    return results


# ========================================
# CAMPAIGN COMPLETED NOTIFICATIONS
# ========================================

def send_assessment_completed_notification(
    to_email: str,
    recipient_name: str,
    assessment_id: str,
    assessment_name: str,
    responses_count: int,
    tokens_sent: int,
    organization_name: str,
    customer_id: str = None,
    language: str = 'da'
) -> bool:
    """
    Send email notification when a assessment/survey is completed.

    Args:
        to_email: Recipient email (typically the manager/admin)
        recipient_name: Name of the recipient
        assessment_id: Assessment ID for building the results URL
        assessment_name: Name of the assessment
        responses_count: Number of responses received
        tokens_sent: Total number of invitations sent
        organization_name: Name of the target organization
        customer_id: Optional customer ID for email sender
        language: Language code ('da' or 'en', default 'da')
    """
    results_url = f"{BASE_URL}/admin/assessment/{assessment_id}/detailed"
    response_rate = round((responses_count / tokens_sent * 100), 1) if tokens_sent > 0 else 0

    # Get template for the specified language
    template = get_template('assessment_completed', language=language)

    # Render template with variables
    rendered = render_template(template, {
        'recipient_name': recipient_name,
        'assessment_name': assessment_name,
        'responses_count': responses_count,
        'tokens_sent': tokens_sent,
        'response_rate': response_rate,
        'organization_name': organization_name,
        'results_url': results_url
    }, language)

    # Get customer-specific email sender
    email_sender = get_email_sender(customer_id)

    data = {
        'Messages': [
            {
                "From": email_sender,
                "To": [
                    {
                        "Email": to_email
                    }
                ],
                "Subject": rendered['subject'],
                "TextPart": rendered['text'],
                "HTMLPart": rendered['html']
            }
        ]
    }

    try:
        result = mailjet.send.create(data=data)
        if result.status_code == 200:
            response_data = result.json()
            message_id = None
            if 'Messages' in response_data and len(response_data['Messages']) > 0:
                msg = response_data['Messages'][0]
                if 'To' in msg and len(msg['To']) > 0:
                    message_id = str(msg['To'][0].get('MessageID', ''))
            log_email(to_email, rendered['subject'], 'assessment_completed', 'sent',
                     message_id, assessment_id=assessment_id)
            return True
        else:
            log_email(to_email, rendered['subject'], 'assessment_completed', 'error',
                     error_message=f"Status {result.status_code}", assessment_id=assessment_id)
            return False
    except Exception as e:
        print(f"Error sending assessment completed notification to {to_email}: {e}")
        log_email(to_email, rendered['subject'], 'assessment_completed', 'error',
                 error_message=str(e), assessment_id=assessment_id)
        return False


def check_and_notify_assessment_completed(assessment_id: str, threshold_percent: float = 100.0) -> bool:
    """
    Check if a assessment has reached the completion threshold and send notification.

    A assessment is considered "complete" when:
    - All tokens have been used (100% response rate), OR
    - The assessment has reached a custom threshold (e.g., 80%)

    This function checks if notification has already been sent to avoid duplicates.

    Args:
        assessment_id: Assessment ID to check
        threshold_percent: Percentage of responses needed to trigger notification (default 100%)

    Returns:
        True if notification was sent, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        # Get assessment info
        assessment = conn.execute("""
            SELECT c.*, ou.name as org_name, ou.customer_id
            FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ?
        """, (assessment_id,)).fetchone()

        if not assessment:
            conn.close()
            return False

        # Get token stats
        stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN used = 1 THEN 1 ELSE 0 END) as used
            FROM tokens
            WHERE assessment_id = ?
        """, (assessment_id,)).fetchone()

        tokens_sent = stats['total'] or 0
        tokens_used = stats['used'] or 0

        if tokens_sent == 0:
            conn.close()
            return False

        response_rate = (tokens_used / tokens_sent) * 100

        # Check if threshold reached
        if response_rate < threshold_percent:
            conn.close()
            return False

        # Check if notification already sent
        existing = conn.execute("""
            SELECT id FROM email_logs
            WHERE assessment_id = ? AND email_type = 'assessment_completed'
        """, (assessment_id,)).fetchone()

        if existing:
            conn.close()
            return False  # Already notified

        # Get the manager/admin to notify
        # First try: get users associated with this customer
        customer_id = assessment['customer_id']
        users = conn.execute("""
            SELECT email, username FROM users
            WHERE customer_id = ? OR role = 'admin'
            ORDER BY role ASC
            LIMIT 5
        """, (customer_id,)).fetchall()

        conn.close()

        # Send notification to each relevant user
        sent_count = 0
        for user in users:
            success = send_assessment_completed_notification(
                to_email=user['email'],
                recipient_name=user['username'],
                assessment_id=assessment_id,
                assessment_name=assessment['name'],
                responses_count=tokens_used,
                tokens_sent=tokens_sent,
                organization_name=assessment['org_name']
            )
            if success:
                sent_count += 1

        return sent_count > 0

    except Exception as e:
        print(f"Error checking assessment completion: {e}")
        return False


# Test function
def test_mailjet_connection():
    """Test at Mailjet credentials virker"""
    if not MAILJET_API_KEY or not MAILJET_API_SECRET:
        print("❌ Mailjet credentials mangler!")
        print("Sæt MAILJET_API_KEY og MAILJET_API_SECRET som environment variables")
        return False

    try:
        # Test med en simpel GET request
        result = mailjet.contactslist.get()
        print("✅ Mailjet connection virker!")
        return True
    except Exception as e:
        print(f"❌ Mailjet connection fejlede: {e}")
        return False


# ========================================
# LOGIN CODE EMAILS (Passwordless)
# ========================================

def send_login_code(to_email: str, code: str, code_type: str = 'login',
                   language: str = 'da') -> bool:
    """
    Send login-kode til bruger (passwordless login).

    Args:
        to_email: Brugerens email
        code: 6-cifret verifikationskode
        code_type: 'login', 'register', eller 'reset'
        language: 'da' eller 'en'

    Returns:
        True ved succes
    """
    # Email subjects og titler baseret på type
    if language == 'en':
        subjects = {
            'login': 'Your login code',
            'register': 'Complete your registration',
            'reset': 'Reset your password'
        }
        titles = {
            'login': 'Here is your login code',
            'register': 'Complete your registration',
            'reset': 'Reset your password'
        }
        descriptions = {
            'login': 'Use this code to log in to Friktionskompasset.',
            'register': 'Use this code to complete your registration.',
            'reset': 'Use this code to reset your password.'
        }
        expires_text = 'The code expires in 15 minutes.'
        ignore_text = "If you didn't request this code, you can safely ignore this email."
    else:
        subjects = {
            'login': 'Din loginkode',
            'register': 'Fuldfør din registrering',
            'reset': 'Nulstil dit password'
        }
        titles = {
            'login': 'Her er din loginkode',
            'register': 'Fuldfør din registrering',
            'reset': 'Nulstil dit password'
        }
        descriptions = {
            'login': 'Brug denne kode til at logge ind på Friktionskompasset.',
            'register': 'Brug denne kode til at færdiggøre din registrering.',
            'reset': 'Brug denne kode til at nulstille dit password.'
        }
        expires_text = 'Koden udløber om 15 minutter.'
        ignore_text = 'Hvis du ikke har anmodet om denne kode, kan du trygt ignorere denne email.'

    subject = subjects.get(code_type, subjects['login'])
    title = titles.get(code_type, titles['login'])
    description = descriptions.get(code_type, descriptions['login'])

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #1f2937; }}
            .container {{ max-width: 500px; margin: 40px auto; padding: 40px; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .logo {{ text-align: center; margin-bottom: 30px; }}
            .logo h1 {{ font-size: 1.5rem; color: #1f2937; margin: 0; }}
            .code-box {{ background: linear-gradient(135deg, #475569 0%, #334155 100%); color: white; padding: 30px; text-align: center; border-radius: 12px; margin: 30px 0; }}
            .code {{ font-size: 2.5rem; font-weight: bold; letter-spacing: 8px; font-family: monospace; }}
            .description {{ color: #4b5563; margin-bottom: 20px; }}
            .expires {{ color: #9ca3af; font-size: 0.875rem; text-align: center; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 0.75rem; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">
                <h1>🏢 Friktionskompasset</h1>
            </div>

            <h2>{title}</h2>
            <p class="description">{description}</p>

            <div class="code-box">
                <div class="code">{code}</div>
            </div>

            <p class="expires">{expires_text}</p>

            <div class="footer">
                {ignore_text}
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"{title}\n\n{description}\n\nDin kode: {code}\n\n{expires_text}\n\n{ignore_text}"

    try:
        data = {
            'Messages': [
                {
                    'From': {'Email': FROM_EMAIL, 'Name': FROM_NAME},
                    'To': [{'Email': to_email}],
                    'Subject': subject,
                    'HTMLPart': html_content,
                    'TextPart': text_content
                }
            ]
        }

        result = mailjet.send.create(data=data)

        if result.status_code == 200:
            log_email(to_email, subject, f'{code_type}_code', 'sent')
            return True
        else:
            log_email(to_email, subject, f'{code_type}_code', 'failed',
                     error_message=str(result.json()))
            print(f"Mailjet error: {result.status_code} - {result.json()}")
            return False

    except Exception as e:
        log_email(to_email, subject, f'{code_type}_code', 'failed', error_message=str(e))
        print(f"Error sending login code: {e}")
        return False


if __name__ == "__main__":
    # Test connection
    test_mailjet_connection()
