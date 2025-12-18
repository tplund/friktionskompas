/**
 * Analytics Event Tracking
 * Pushes events to dataLayer for GTM/GA4
 *
 * Events respect user consent via Google Consent Mode v2
 * (GTM will only send if analytics_storage is granted)
 */

const Analytics = (function() {
    'use strict';

    /**
     * Push event to dataLayer
     * @param {string} eventName - GA4 event name
     * @param {object} params - Event parameters
     */
    function track(eventName, params = {}) {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({
            'event': eventName,
            ...params
        });
        console.log('[Analytics] Event:', eventName, params);
    }

    return {
        /**
         * Track profile/survey start
         * @param {string} type - Assessment type (screening, profil_fuld, etc.)
         * @param {string} source - Where user came from (landing, direct, etc.)
         */
        profileStart: function(type, source = 'direct') {
            track('profile_start', {
                'profile_type': type,
                'traffic_source': source
            });
        },

        /**
         * Track profile/survey completion
         * @param {string} type - Assessment type
         * @param {number} duration - Time to complete in seconds
         * @param {object} scores - Result scores (optional, aggregated)
         */
        profileComplete: function(type, duration = null, scores = null) {
            const params = {
                'profile_type': type
            };
            if (duration) params['completion_time_seconds'] = duration;
            if (scores) {
                // Only send aggregated/anonymized data
                params['result_avg_score'] = Object.values(scores).reduce((a, b) => a + b, 0) / Object.values(scores).length;
            }
            track('profile_complete', params);
        },

        /**
         * Track user registration
         * @param {string} method - Registration method (email, google, microsoft)
         */
        signUp: function(method = 'email') {
            track('sign_up', {
                'method': method
            });
        },

        /**
         * Track user login
         * @param {string} method - Login method (email, google, microsoft, code)
         */
        login: function(method = 'email') {
            track('login', {
                'method': method
            });
        },

        /**
         * Track page view (if not using automatic GTM page view)
         * @param {string} pagePath - Page path
         * @param {string} pageTitle - Page title
         */
        pageView: function(pagePath, pageTitle) {
            track('page_view', {
                'page_path': pagePath,
                'page_title': pageTitle
            });
        },

        /**
         * Track button/CTA click
         * @param {string} buttonId - Button identifier
         * @param {string} buttonText - Button text
         * @param {string} location - Where on page (hero, nav, footer, etc.)
         */
        ctaClick: function(buttonId, buttonText, location = 'unknown') {
            track('cta_click', {
                'button_id': buttonId,
                'button_text': buttonText,
                'click_location': location
            });
        },

        /**
         * Track form submission
         * @param {string} formId - Form identifier
         * @param {boolean} success - Whether submission succeeded
         */
        formSubmit: function(formId, success = true) {
            track('form_submit', {
                'form_id': formId,
                'form_success': success
            });
        },

        /**
         * Track outbound link click
         * @param {string} url - Destination URL
         */
        outboundClick: function(url) {
            track('outbound_click', {
                'link_url': url
            });
        },

        /**
         * Track scroll depth milestone
         * @param {number} percent - Scroll depth percentage (25, 50, 75, 100)
         */
        scrollDepth: function(percent) {
            track('scroll_depth', {
                'scroll_percent': percent
            });
        },

        /**
         * Generic event tracking
         * @param {string} eventName - Custom event name
         * @param {object} params - Event parameters
         */
        track: track
    };
})();

// Auto-export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Analytics;
}
