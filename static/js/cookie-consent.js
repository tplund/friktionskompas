/**
 * Cookie/Storage Consent Module
 * GDPR-compliant consent with Google Consent Mode v2 integration
 *
 * Version: 2.0
 */

const CookieConsent = (function() {
    'use strict';

    const CONSENT_KEY = 'friktionsprofil_consent';
    const CONSENT_VERSION = '2.0';

    // Consent categories
    const CATEGORIES = {
        necessary: {
            name: 'Nødvendige',
            name_en: 'Necessary',
            description: 'Nødvendige for at siden fungerer (session, sprog)',
            description_en: 'Required for the site to function (session, language)',
            required: true
        },
        functional: {
            name: 'Funktionelle',
            name_en: 'Functional',
            description: 'Gemmer dine profilresultater lokalt i din browser',
            description_en: 'Stores your profile results locally in your browser',
            required: false
        },
        analytics: {
            name: 'Statistik',
            name_en: 'Analytics',
            description: 'Hjælper os med at forstå hvordan siden bruges (Google Analytics)',
            description_en: 'Helps us understand how the site is used (Google Analytics)',
            required: false
        },
        marketing: {
            name: 'Marketing',
            name_en: 'Marketing',
            description: 'Bruges til at vise relevante annoncer',
            description_en: 'Used to show relevant advertisements',
            required: false
        }
    };

    // ========================================
    // Google Consent Mode v2
    // ========================================

    /**
     * Initialize Google Consent Mode with default denied state
     * MUST be called before GTM loads
     */
    function initGoogleConsentMode() {
        // Initialize dataLayer
        window.dataLayer = window.dataLayer || [];
        function gtag() { dataLayer.push(arguments); }
        window.gtag = gtag;

        // Set default consent state (denied for all)
        gtag('consent', 'default', {
            'ad_storage': 'denied',
            'ad_user_data': 'denied',
            'ad_personalization': 'denied',
            'analytics_storage': 'denied',
            'functionality_storage': 'denied',
            'personalization_storage': 'denied',
            'security_storage': 'granted',  // Always granted for security
            'wait_for_update': 500  // Wait up to 500ms for consent update
        });

        // Set region-specific defaults (EU requires consent)
        gtag('consent', 'default', {
            'ad_storage': 'denied',
            'ad_user_data': 'denied',
            'ad_personalization': 'denied',
            'analytics_storage': 'denied',
            'region': ['DK', 'DE', 'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'EE', 'FI',
                       'FR', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
                       'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'GB', 'NO', 'IS', 'LI', 'CH']
        });

        console.log('[CookieConsent] Google Consent Mode initialized with default: denied');
    }

    /**
     * Update Google Consent Mode based on user choices
     */
    function updateGoogleConsent(categories) {
        if (typeof gtag !== 'function') {
            console.warn('[CookieConsent] gtag not available, skipping consent update');
            return;
        }

        const consentUpdate = {
            'security_storage': 'granted',  // Always granted
            'functionality_storage': categories.functional ? 'granted' : 'denied',
            'personalization_storage': categories.functional ? 'granted' : 'denied',
            'analytics_storage': categories.analytics ? 'granted' : 'denied',
            'ad_storage': categories.marketing ? 'granted' : 'denied',
            'ad_user_data': categories.marketing ? 'granted' : 'denied',
            'ad_personalization': categories.marketing ? 'granted' : 'denied'
        };

        gtag('consent', 'update', consentUpdate);

        // Push consent event to dataLayer for GTM triggers
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({
            'event': 'cookie_consent_update',
            'cookie_consent': {
                'necessary': true,
                'functional': !!categories.functional,
                'analytics': !!categories.analytics,
                'marketing': !!categories.marketing
            }
        });

        console.log('[CookieConsent] Google Consent Mode updated:', consentUpdate);
    }

    // ========================================
    // Consent Management
    // ========================================

    function getConsent() {
        try {
            const raw = localStorage.getItem(CONSENT_KEY);
            if (!raw) return null;
            const consent = JSON.parse(raw);
            // Check version - if outdated, ask again
            if (consent.version !== CONSENT_VERSION) return null;
            return consent;
        } catch (e) {
            return null;
        }
    }

    function saveConsent(categories) {
        const consent = {
            version: CONSENT_VERSION,
            timestamp: new Date().toISOString(),
            categories: categories
        };
        try {
            localStorage.setItem(CONSENT_KEY, JSON.stringify(consent));
            return true;
        } catch (e) {
            console.error('CookieConsent: Could not save consent', e);
            return false;
        }
    }

    function hasConsent(category) {
        const consent = getConsent();
        if (!consent) return false;
        if (CATEGORIES[category]?.required) return true;
        return consent.categories?.[category] === true;
    }

    function hasAnyConsent() {
        return getConsent() !== null;
    }

    /**
     * Apply existing consent on page load
     */
    function applyExistingConsent() {
        const consent = getConsent();
        if (consent && consent.categories) {
            updateGoogleConsent(consent.categories);
        }
    }

    // ========================================
    // UI Components
    // ========================================

    function createBanner(lang) {
        const isDanish = lang === 'da';

        const banner = document.createElement('div');
        banner.id = 'cookie-consent-banner';
        banner.setAttribute('role', 'dialog');
        banner.setAttribute('aria-labelledby', 'cookie-consent-title');
        banner.setAttribute('aria-describedby', 'cookie-consent-desc');

        banner.innerHTML = `
            <div class="cookie-consent-content">
                <div class="cookie-consent-text">
                    <h3 id="cookie-consent-title">
                        ${isDanish ? '🔒 Privatlivsindstillinger' : '🔒 Privacy Settings'}
                    </h3>
                    <p id="cookie-consent-desc">
                        ${isDanish
                            ? 'Vi bruger cookies og lokal lagring til at forbedre din oplevelse. Du kan vælge hvilke typer du accepterer.'
                            : 'We use cookies and local storage to improve your experience. You can choose which types you accept.'}
                    </p>
                </div>
                <div class="cookie-consent-actions">
                    <button type="button" class="cookie-btn cookie-btn-settings" id="cookie-settings-btn">
                        ${isDanish ? 'Indstillinger' : 'Settings'}
                    </button>
                    <button type="button" class="cookie-btn cookie-btn-reject" id="cookie-reject-btn">
                        ${isDanish ? 'Kun nødvendige' : 'Necessary only'}
                    </button>
                    <button type="button" class="cookie-btn cookie-btn-accept" id="cookie-accept-btn">
                        ${isDanish ? 'Accepter alle' : 'Accept all'}
                    </button>
                </div>
            </div>
        `;

        return banner;
    }

    function createSettingsModal(lang) {
        const isDanish = lang === 'da';

        const modal = document.createElement('div');
        modal.id = 'cookie-consent-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-labelledby', 'cookie-modal-title');

        let categoriesHtml = '';
        for (const [key, cat] of Object.entries(CATEGORIES)) {
            const name = isDanish ? cat.name : cat.name_en;
            const desc = isDanish ? cat.description : cat.description_en;
            categoriesHtml += `
                <div class="cookie-category">
                    <div class="cookie-category-header">
                        <label class="cookie-category-label">
                            <input type="checkbox"
                                   name="cookie-cat-${key}"
                                   ${cat.required ? 'checked disabled' : ''}>
                            <span class="cookie-category-name">${name}</span>
                            ${cat.required ? `<span class="cookie-required">(${isDanish ? 'påkrævet' : 'required'})</span>` : ''}
                        </label>
                    </div>
                    <p class="cookie-category-desc">${desc}</p>
                </div>
            `;
        }

        modal.innerHTML = `
            <div class="cookie-modal-backdrop"></div>
            <div class="cookie-modal-content">
                <h3 id="cookie-modal-title">
                    ${isDanish ? 'Privatlivsindstillinger' : 'Privacy Settings'}
                </h3>
                <p class="cookie-modal-intro">
                    ${isDanish
                        ? 'Vælg hvilke typer cookies og data du vil tillade:'
                        : 'Choose which types of cookies and data you allow:'}
                </p>
                <div class="cookie-categories">
                    ${categoriesHtml}
                </div>
                <div class="cookie-modal-actions">
                    <button type="button" class="cookie-btn cookie-btn-secondary" id="cookie-modal-cancel">
                        ${isDanish ? 'Annuller' : 'Cancel'}
                    </button>
                    <button type="button" class="cookie-btn cookie-btn-accept" id="cookie-modal-save">
                        ${isDanish ? 'Gem indstillinger' : 'Save settings'}
                    </button>
                </div>
            </div>
        `;

        return modal;
    }

    function injectStyles() {
        if (document.getElementById('cookie-consent-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'cookie-consent-styles';
        styles.textContent = `
            #cookie-consent-banner {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: #1f2937;
                color: white;
                padding: 20px;
                z-index: 99999;
                box-shadow: 0 -4px 20px rgba(0,0,0,0.3);
                animation: slideUp 0.3s ease-out;
            }
            @keyframes slideUp {
                from { transform: translateY(100%); }
                to { transform: translateY(0); }
            }
            .cookie-consent-content {
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                align-items: center;
                gap: 30px;
                flex-wrap: wrap;
            }
            .cookie-consent-text {
                flex: 1;
                min-width: 300px;
            }
            .cookie-consent-text h3 {
                margin-bottom: 8px;
                font-size: 1.1rem;
            }
            .cookie-consent-text p {
                font-size: 0.9rem;
                color: #d1d5db;
                line-height: 1.5;
            }
            .cookie-consent-text strong {
                color: #22c55e;
            }
            .cookie-consent-actions {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }
            .cookie-btn {
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 0.9rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }
            .cookie-btn:focus {
                outline: 2px solid #3b82f6;
                outline-offset: 2px;
            }
            .cookie-btn-accept {
                background: #15803d;
                color: white;
            }
            .cookie-btn-accept:hover {
                background: #166534;
            }
            .cookie-btn-reject {
                background: #6b7280;
                color: white;
            }
            .cookie-btn-reject:hover {
                background: #4b5563;
            }
            .cookie-btn-settings {
                background: transparent;
                color: white;
                border: 1px solid #6b7280;
            }
            .cookie-btn-settings:hover {
                background: rgba(255,255,255,0.1);
            }
            .cookie-btn-secondary {
                background: #374151;
                color: white;
            }
            .cookie-btn-secondary:hover {
                background: #4b5563;
            }

            /* Modal */
            #cookie-consent-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 100000;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .cookie-modal-backdrop {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.6);
            }
            .cookie-modal-content {
                position: relative;
                background: white;
                border-radius: 16px;
                padding: 30px;
                max-width: 500px;
                width: 100%;
                max-height: 80vh;
                overflow-y: auto;
                color: #1f2937;
            }
            .cookie-modal-content h3 {
                margin-bottom: 10px;
                font-size: 1.25rem;
            }
            .cookie-modal-intro {
                color: #6b7280;
                margin-bottom: 20px;
                font-size: 0.9rem;
            }
            .cookie-categories {
                margin-bottom: 20px;
            }
            .cookie-category {
                padding: 15px;
                background: #f9fafb;
                border-radius: 8px;
                margin-bottom: 10px;
            }
            .cookie-category-header {
                display: flex;
                align-items: center;
            }
            .cookie-category-label {
                display: flex;
                align-items: center;
                gap: 10px;
                cursor: pointer;
            }
            .cookie-category-label input {
                width: 18px;
                height: 18px;
            }
            .cookie-category-name {
                font-weight: 600;
            }
            .cookie-required {
                font-size: 0.75rem;
                color: #6b7280;
            }
            .cookie-category-desc {
                margin-top: 8px;
                font-size: 0.85rem;
                color: #6b7280;
                padding-left: 28px;
            }
            .cookie-modal-actions {
                display: flex;
                justify-content: flex-end;
                gap: 10px;
            }

            /* Mobile */
            @media (max-width: 600px) {
                .cookie-consent-content {
                    flex-direction: column;
                    text-align: center;
                }
                .cookie-consent-actions {
                    width: 100%;
                    justify-content: center;
                }
                .cookie-btn {
                    padding: 10px 16px;
                    font-size: 0.85rem;
                }
            }
        `;
        document.head.appendChild(styles);
    }

    // ========================================
    // Event Handlers
    // ========================================

    function showBanner(lang) {
        if (hasAnyConsent()) return; // Already consented

        injectStyles();
        const banner = createBanner(lang);
        document.body.appendChild(banner);

        // Accept all
        document.getElementById('cookie-accept-btn').addEventListener('click', function() {
            const categories = {};
            for (const key of Object.keys(CATEGORIES)) {
                categories[key] = true;
            }
            saveConsent(categories);
            hideBanner();
            onConsentGiven(categories);
        });

        // Reject (only necessary)
        document.getElementById('cookie-reject-btn').addEventListener('click', function() {
            const categories = { necessary: true };
            saveConsent(categories);
            hideBanner();
            onConsentGiven(categories);
        });

        // Settings
        document.getElementById('cookie-settings-btn').addEventListener('click', function() {
            showSettingsModal(lang);
        });
    }

    function hideBanner() {
        const banner = document.getElementById('cookie-consent-banner');
        if (banner) {
            banner.style.animation = 'slideDown 0.3s ease-in forwards';
            setTimeout(() => banner.remove(), 300);
        }
    }

    function showSettingsModal(lang) {
        const modal = createSettingsModal(lang);
        document.body.appendChild(modal);

        // Focus trap
        const firstButton = modal.querySelector('button');
        if (firstButton) firstButton.focus();

        // Cancel
        document.getElementById('cookie-modal-cancel').addEventListener('click', function() {
            modal.remove();
        });

        // Backdrop click
        modal.querySelector('.cookie-modal-backdrop').addEventListener('click', function() {
            modal.remove();
        });

        // Save
        document.getElementById('cookie-modal-save').addEventListener('click', function() {
            const categories = { necessary: true };
            for (const key of Object.keys(CATEGORIES)) {
                if (!CATEGORIES[key].required) {
                    const checkbox = modal.querySelector(`input[name="cookie-cat-${key}"]`);
                    categories[key] = checkbox?.checked || false;
                }
            }
            saveConsent(categories);
            modal.remove();
            hideBanner();
            onConsentGiven(categories);
        });

        // Escape key
        modal.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                modal.remove();
            }
        });
    }

    function onConsentGiven(categories) {
        // Update Google Consent Mode
        updateGoogleConsent(categories);

        // Dispatch custom event for other scripts to listen to
        window.dispatchEvent(new CustomEvent('cookieConsentGiven', {
            detail: categories
        }));

        // If functional cookies rejected, clear localStorage profil data
        if (!categories.functional) {
            try {
                localStorage.removeItem('friktionsprofil_data');
            } catch (e) {
                // Ignore
            }
        }
    }

    // ========================================
    // Public API
    // ========================================

    return {
        /**
         * Initialize Google Consent Mode defaults
         * MUST be called BEFORE GTM script loads
         */
        initConsentMode: initGoogleConsentMode,

        /**
         * Initialize consent banner
         * @param {string} lang - Language code ('da' or 'en')
         */
        init: function(lang = 'da') {
            // Apply existing consent if any (updates Google Consent Mode)
            applyExistingConsent();

            // Show banner if no consent given
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => showBanner(lang));
            } else {
                showBanner(lang);
            }
        },

        /**
         * Check if user has given consent for a category
         * @param {string} category - Category name
         * @returns {boolean}
         */
        hasConsent: hasConsent,

        /**
         * Check if user has given any consent
         * @returns {boolean}
         */
        hasAnyConsent: hasAnyConsent,

        /**
         * Get full consent object
         * @returns {object|null}
         */
        getConsent: getConsent,

        /**
         * Show settings modal (for "Manage cookies" link)
         * @param {string} lang
         */
        showSettings: showSettingsModal,

        /**
         * Revoke consent and show banner again
         */
        revokeConsent: function() {
            try {
                localStorage.removeItem(CONSENT_KEY);
            } catch (e) {}
            // Reset Google Consent Mode to denied
            if (typeof gtag === 'function') {
                gtag('consent', 'update', {
                    'ad_storage': 'denied',
                    'ad_user_data': 'denied',
                    'ad_personalization': 'denied',
                    'analytics_storage': 'denied',
                    'functionality_storage': 'denied',
                    'personalization_storage': 'denied'
                });
            }
            showBanner('da');
        }
    };
})();

// Auto-export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CookieConsent;
}
