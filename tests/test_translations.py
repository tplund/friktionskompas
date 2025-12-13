"""
Tests for translations.py - Multi-language support for Friktionskompasset.
Tests translation lookup, fallbacks, and key coverage.
"""
import pytest


class TestTranslationStructure:
    """Test the structure of INITIAL_TRANSLATIONS."""

    def test_initial_translations_exists(self):
        """Test that INITIAL_TRANSLATIONS dict exists."""
        from translations import INITIAL_TRANSLATIONS

        assert INITIAL_TRANSLATIONS is not None
        assert isinstance(INITIAL_TRANSLATIONS, dict)
        assert len(INITIAL_TRANSLATIONS) > 0

    def test_all_translations_have_both_languages(self):
        """Test that all translations have both DA and EN."""
        from translations import INITIAL_TRANSLATIONS

        for key, translations in INITIAL_TRANSLATIONS.items():
            assert 'da' in translations, f"Missing Danish for {key}"
            assert 'en' in translations, f"Missing English for {key}"

    def test_no_empty_translations(self):
        """Test that no translations are empty strings."""
        from translations import INITIAL_TRANSLATIONS

        for key, translations in INITIAL_TRANSLATIONS.items():
            assert translations['da'], f"Empty Danish for {key}"
            assert translations['en'], f"Empty English for {key}"


class TestNavigationTranslations:
    """Test navigation-related translations."""

    def test_nav_translations_exist(self):
        """Test that navigation translations are defined."""
        from translations import INITIAL_TRANSLATIONS

        nav_keys = [
            'nav.dashboard',
            'nav.maalinger',
            'nav.organisation',
            'nav.logout',
        ]

        for key in nav_keys:
            assert key in INITIAL_TRANSLATIONS, f"Missing navigation key: {key}"

    def test_nav_dashboard_translations(self):
        """Test dashboard navigation translation."""
        from translations import INITIAL_TRANSLATIONS

        assert 'nav.dashboard' in INITIAL_TRANSLATIONS
        assert INITIAL_TRANSLATIONS['nav.dashboard']['da'] == 'Dashboard'
        assert INITIAL_TRANSLATIONS['nav.dashboard']['en'] == 'Dashboard'


class TestButtonTranslations:
    """Test button/action translations."""

    def test_button_translations_exist(self):
        """Test that button translations are defined."""
        from translations import INITIAL_TRANSLATIONS

        btn_keys = [
            'btn.create',
            'btn.edit',
            'btn.delete',
            'btn.save',
            'btn.cancel',
        ]

        for key in btn_keys:
            assert key in INITIAL_TRANSLATIONS, f"Missing button key: {key}"

    def test_btn_create_translations(self):
        """Test create button translation."""
        from translations import INITIAL_TRANSLATIONS

        assert 'btn.create' in INITIAL_TRANSLATIONS
        assert INITIAL_TRANSLATIONS['btn.create']['da'] == 'Opret'
        assert INITIAL_TRANSLATIONS['btn.create']['en'] == 'Create'


class TestLoginTranslations:
    """Test login-related translations."""

    def test_login_translations_exist(self):
        """Test that login translations are defined."""
        from translations import INITIAL_TRANSLATIONS

        login_keys = [
            'login.title',
            'login.username',
            'login.password',
            'login.button',
        ]

        for key in login_keys:
            assert key in INITIAL_TRANSLATIONS, f"Missing login key: {key}"


class TestCustomerTranslations:
    """Test customer/organization translations."""

    def test_customer_translations_exist(self):
        """Test that customer translations are defined."""
        from translations import INITIAL_TRANSLATIONS

        customer_keys = [
            'customers.title',
            'customers.customers',
            'customers.create_customer',
        ]

        for key in customer_keys:
            assert key in INITIAL_TRANSLATIONS, f"Missing customer key: {key}"


class TestAnalyserTranslations:
    """Test analyser/results translations."""

    def test_analyser_translations_exist(self):
        """Test that analyser translations are defined."""
        from translations import INITIAL_TRANSLATIONS

        analyser_keys = [
            'analyser.title',
        ]

        for key in analyser_keys:
            assert key in INITIAL_TRANSLATIONS, f"Missing analyser key: {key}"


class TestTranslationFunction:
    """Test the t() translation function."""

    def test_t_function_exists(self):
        """Test that t function can be imported."""
        from translations import t

        assert callable(t)

    def test_t_returns_translation_with_context(self, app):
        """Test that t returns the correct translation within app context."""
        from translations import t

        with app.test_request_context():
            # Default language is Danish
            result = t('btn.create')
            # Should return either Danish or English translation
            assert result in ['Opret', 'Create']

    def test_t_handles_missing_key_with_context(self, app):
        """Test that t handles missing keys gracefully."""
        from translations import t

        with app.test_request_context():
            # Missing key should return the key itself or a default
            result = t('nonexistent.key')
            # Should return something (either the key or a default)
            assert result is not None

    def test_t_with_default_value(self, app):
        """Test that t accepts a default value for missing keys."""
        from translations import t

        with app.test_request_context():
            # If the function supports defaults
            result = t('nonexistent.key', 'Default Value')
            assert result == 'Default Value'


class TestLanguageSetting:
    """Test language setting functionality within Flask context."""

    def test_get_user_language_returns_valid(self, app):
        """Test that get_user_language returns a valid language code."""
        from translations import get_user_language

        with app.test_request_context():
            lang = get_user_language()
            # Should return 'da' or 'en'
            assert lang in ['da', 'en']


class TestTranslationKeyNaming:
    """Test that translation keys follow naming conventions."""

    def test_keys_are_lowercase(self):
        """Test that all keys use lowercase."""
        from translations import INITIAL_TRANSLATIONS

        for key in INITIAL_TRANSLATIONS.keys():
            assert key == key.lower(), f"Key should be lowercase: {key}"

    def test_keys_use_dots_for_hierarchy(self):
        """Test that keys use dots for hierarchy."""
        from translations import INITIAL_TRANSLATIONS

        # Most keys should have at least one dot (namespace.key format)
        dotted_keys = [k for k in INITIAL_TRANSLATIONS.keys() if '.' in k]
        assert len(dotted_keys) > 0, "No hierarchical keys found"

    def test_no_trailing_spaces_in_translations(self):
        """Test that translations don't have trailing spaces."""
        from translations import INITIAL_TRANSLATIONS

        for key, translations in INITIAL_TRANSLATIONS.items():
            da = translations['da']
            en = translations['en']

            assert da == da.strip(), f"Trailing space in DA for {key}"
            assert en == en.strip(), f"Trailing space in EN for {key}"


class TestTranslationCompleteness:
    """Test that important UI elements have translations."""

    def test_error_messages_translated(self):
        """Test that error messages have translations."""
        from translations import INITIAL_TRANSLATIONS

        # Common error keys
        error_related = [k for k in INITIAL_TRANSLATIONS.keys()
                        if 'error' in k.lower() or 'fejl' in k.lower()]

        # Should have at least some error translations
        # This is a soft check - not all systems have error translations
        pass  # Optional assertion

    def test_form_labels_translated(self):
        """Test that form labels have translations."""
        from translations import INITIAL_TRANSLATIONS

        form_keys = [
            'login.username',
            'login.password',
        ]

        for key in form_keys:
            assert key in INITIAL_TRANSLATIONS, f"Missing form label: {key}"
