# Plan: Internationalisering (i18n) af Friktionskompasset

## Oversigt

Tilføj flersproget support til systemet med dansk og engelsk fra start.

## Design Beslutninger

1. **Sprogprofil på bruger** - `language` kolonne på `users` tabel
2. **Default sprog** - dansk (`da`) som standard for nye brugere
3. **Understøttede sprog** - dansk (`da`) og engelsk (`en`)
4. **Komplet oversættelse** - alle strenge skal findes i begge sprog
5. **Survey respondenter** - får spørgsmål på det sprog der matcher deres profil

---

## Implementation Steps

### Trin 1: Database Ændringer

**Fil: `db_multitenant.py`**

```sql
-- Tilføj language kolonne til users
ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'da';

-- Opret translations tabel for UI-strenge
CREATE TABLE IF NOT EXISTS translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,           -- f.eks. 'nav.dashboard', 'btn.save'
    language TEXT NOT NULL,      -- 'da' eller 'en'
    value TEXT NOT NULL,         -- Den oversatte tekst
    context TEXT,                -- Valgfri kontekst/beskrivelse
    UNIQUE(key, language)
);

-- Opret question_translations for spørgsmål
CREATE TABLE IF NOT EXISTS question_translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    question_text TEXT NOT NULL,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    UNIQUE(question_id, language)
);

-- Email templates har allerede customer_id, tilføj language
ALTER TABLE email_templates ADD COLUMN language TEXT DEFAULT 'da';
```

### Trin 2: Translation Helper Modul

**Ny fil: `translations.py`**

```python
from functools import lru_cache
from flask import session, g
from db_multitenant import get_db

SUPPORTED_LANGUAGES = ['da', 'en']
DEFAULT_LANGUAGE = 'da'

def get_user_language():
    """Hent brugerens valgte sprog fra session"""
    if 'user' in session and session['user'].get('language'):
        return session['user']['language']
    return DEFAULT_LANGUAGE

def t(key, **kwargs):
    """
    Oversæt en streng baseret på brugerens sprog.
    Brug: t('nav.dashboard') eller t('welcome', name='John')
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

        # Fallback til key hvis ikke fundet
        return f"[{key}]"

def clear_translation_cache():
    """Ryd cache når oversættelser opdateres"""
    get_translation.cache_clear()

def get_question_text(question_id, lang=None):
    """Hent spørgsmålstekst på brugerens sprog"""
    if lang is None:
        lang = get_user_language()

    with get_db() as conn:
        # Prøv først det ønskede sprog
        row = conn.execute("""
            SELECT question_text FROM question_translations
            WHERE question_id = ? AND language = ?
        """, (question_id, lang)).fetchone()

        if row:
            return row[0]

        # Fallback til default sprog
        row = conn.execute("""
            SELECT question_text FROM question_translations
            WHERE question_id = ? AND language = ?
        """, (question_id, DEFAULT_LANGUAGE)).fetchone()

        if row:
            return row[0]

        # Sidste fallback: original question_text
        row = conn.execute(
            "SELECT question_text FROM questions WHERE id = ?",
            (question_id,)
        ).fetchone()

        return row[0] if row else f"[Question {question_id}]"
```

### Trin 3: Flask Integration

**Fil: `admin_app.py` - tilføjelser**

```python
from translations import t, get_user_language, SUPPORTED_LANGUAGES

# Gør t() tilgængelig i alle templates
@app.context_processor
def inject_translation():
    return {
        't': t,
        'current_language': get_user_language(),
        'supported_languages': SUPPORTED_LANGUAGES
    }

# Route til at ændre sprog
@app.route('/set-language/<lang>')
@login_required
def set_language(lang):
    if lang in SUPPORTED_LANGUAGES:
        # Opdater i database
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET language = ? WHERE id = ?",
                (lang, session['user']['id'])
            )
        # Opdater session
        session['user']['language'] = lang
        flash(t('language_changed'), 'success')

    return redirect(request.referrer or url_for('admin_home'))
```

### Trin 4: Template Ændringer

**Eksempel: `templates/admin/layout.html`**

```html
<!-- Sprogvælger i nav -->
<div class="language-switcher">
    <select onchange="window.location='/set-language/' + this.value">
        {% for lang in supported_languages %}
        <option value="{{ lang }}" {% if lang == current_language %}selected{% endif %}>
            {{ 'Dansk' if lang == 'da' else 'English' }}
        </option>
        {% endfor %}
    </select>
</div>

<!-- Brug t() i stedet for hardcoded tekst -->
<h2>{{ t('nav.dashboard') }}</h2>
<button>{{ t('btn.save') }}</button>
```

### Trin 5: Seed Initial Translations

**Ny fil: `seed_translations.py`**

```python
TRANSLATIONS = {
    # Navigation
    'nav.dashboard': {'da': 'Dashboard', 'en': 'Dashboard'},
    'nav.analyses': {'da': 'Analyser', 'en': 'Analyses'},
    'nav.organizations': {'da': 'Organisationer', 'en': 'Organizations'},
    'nav.profiles': {'da': 'Friktionsprofiler', 'en': 'Friction Profiles'},
    'nav.customers': {'da': 'Kunder & Brugere', 'en': 'Customers & Users'},
    'nav.settings': {'da': 'Indstillinger', 'en': 'Settings'},

    # Buttons
    'btn.save': {'da': 'Gem', 'en': 'Save'},
    'btn.cancel': {'da': 'Annuller', 'en': 'Cancel'},
    'btn.delete': {'da': 'Slet', 'en': 'Delete'},
    'btn.edit': {'da': 'Rediger', 'en': 'Edit'},
    'btn.create': {'da': 'Opret', 'en': 'Create'},
    'btn.back': {'da': 'Tilbage', 'en': 'Back'},

    # Labels
    'label.name': {'da': 'Navn', 'en': 'Name'},
    'label.email': {'da': 'Email', 'en': 'Email'},
    'label.language': {'da': 'Sprog', 'en': 'Language'},
    'label.responses': {'da': 'Svar', 'en': 'Responses'},
    'label.measurements': {'da': 'Målinger', 'en': 'Measurements'},

    # Friction fields
    'field.mening': {'da': 'Mening', 'en': 'Meaning'},
    'field.tryghed': {'da': 'Tryghed', 'en': 'Safety'},
    'field.kan': {'da': 'Kan', 'en': 'Capability'},
    'field.besvaer': {'da': 'Besvær', 'en': 'Difficulty'},

    # Messages
    'msg.saved': {'da': 'Gemt!', 'en': 'Saved!'},
    'msg.deleted': {'da': 'Slettet', 'en': 'Deleted'},
    'msg.error': {'da': 'Der opstod en fejl', 'en': 'An error occurred'},
    'msg.language_changed': {'da': 'Sprog ændret', 'en': 'Language changed'},

    # Survey
    'survey.title': {'da': 'Friktionsmåling', 'en': 'Friction Survey'},
    'survey.intro': {'da': 'Din besvarelse er anonym', 'en': 'Your response is anonymous'},
    'survey.submit': {'da': 'Send svar', 'en': 'Submit'},
    'survey.thanks': {'da': 'Tak for din besvarelse!', 'en': 'Thank you for your response!'},

    # ... flere oversættelser
}

def seed_translations():
    """Indsæt alle oversættelser i database"""
    from db_multitenant import get_db

    with get_db() as conn:
        for key, langs in TRANSLATIONS.items():
            for lang, value in langs.items():
                conn.execute("""
                    INSERT OR REPLACE INTO translations (key, language, value)
                    VALUES (?, ?, ?)
                """, (key, lang, value))
        conn.commit()

    print(f"Seeded {len(TRANSLATIONS)} translation keys")

if __name__ == '__main__':
    seed_translations()
```

### Trin 6: Admin UI til Oversættelser

**Ny route i `admin_app.py`**

```python
@app.route('/admin/translations')
@admin_required
def translations_admin():
    """Admin UI til at redigere oversættelser"""
    with get_db() as conn:
        translations = conn.execute("""
            SELECT t1.key, t1.value as da_value, t2.value as en_value, t1.context
            FROM translations t1
            LEFT JOIN translations t2 ON t1.key = t2.key AND t2.language = 'en'
            WHERE t1.language = 'da'
            ORDER BY t1.key
        """).fetchall()

    return render_template('admin/translations.html', translations=translations)

@app.route('/admin/translations/update', methods=['POST'])
@admin_required
def update_translation():
    """Opdater en oversættelse"""
    key = request.form['key']
    da_value = request.form['da_value']
    en_value = request.form['en_value']

    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO translations (key, language, value) VALUES (?, 'da', ?)",
            (key, da_value)
        )
        conn.execute(
            "INSERT OR REPLACE INTO translations (key, language, value) VALUES (?, 'en', ?)",
            (key, en_value)
        )
        conn.commit()

    clear_translation_cache()
    flash(t('msg.saved'), 'success')
    return redirect(url_for('translations_admin'))
```

---

## Migreringsplan

### Fase 1: Database & Infrastruktur
1. Tilføj `language` kolonne til `users`
2. Opret `translations` og `question_translations` tabeller
3. Implementer `translations.py` modul
4. Seed initiale oversættelser

### Fase 2: Backend Integration
1. Tilføj `t()` til template context
2. Implementer `/set-language` route
3. Opdater session håndtering til at inkludere sprog

### Fase 3: Template Migrering
1. Start med `layout.html` - navigation og fælles elementer
2. Migrer side for side, erstat hardcoded tekst med `t('key')`
3. Test hver side på begge sprog

### Fase 4: Spørgsmål & Emails
1. Migrer eksisterende spørgsmål til `question_translations`
2. Opdater survey rendering til at bruge oversatte spørgsmål
3. Tilføj sprog til email templates

### Fase 5: Admin UI
1. Tilføj sprogvælger til navigation
2. Opret translations admin side
3. Tilføj spørgsmålsoversættelse til profil-questions admin

---

## Filstruktur efter implementation

```
Friktionskompasset/
├── translations.py          # Translation helper modul
├── seed_translations.py     # Initial translations data
├── translations/            # (valgfrit) JSON backup af oversættelser
│   ├── da.json
│   └── en.json
└── templates/
    └── admin/
        └── translations.html  # Admin UI for translations
```

---

## Estimeret Arbejde

- Trin 1-2: Database & modul setup
- Trin 3-4: Flask & template integration
- Trin 5: Seed translations
- Trin 6: Admin UI
- Template migrering: Afhænger af antal templates

---

## Spørgsmål til afklaring

1. Skal vi have en "eksporter/importer" funktion for oversættelser (til backup eller ekstern redigering)?
2. Skal ændringer i oversættelser logges (audit trail)?
3. Er der andre sprog på roadmap efter dansk/engelsk?
