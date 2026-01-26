/**
 * Friktionskompasset Page Transitions
 * Nordic Clarity Design System
 *
 * Handles:
 * - Lucide icon initialization
 * - Stagger reveal animations
 * - Scroll-triggered animations
 * - Page load animations
 */

(function() {
  'use strict';

  // ============================================
  // LUCIDE ICONS INITIALIZATION
  // ============================================

  /**
   * Initialize Lucide icons
   * Call this after DOM is ready and after any dynamic content loads
   */
  function initLucideIcons() {
    if (typeof lucide !== 'undefined' && lucide.createIcons) {
      lucide.createIcons();
    }
  }

  // ============================================
  // SCROLL-TRIGGERED ANIMATIONS
  // ============================================

  /**
   * Set up IntersectionObserver for scroll animations
   */
  function initScrollAnimations() {
    // Check for reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      // Make all elements visible immediately
      document.querySelectorAll('.reveal-on-scroll, .reveal-on-scroll-left, .reveal-on-scroll-right')
        .forEach(function(el) {
          el.classList.add('is-visible');
        });
      return;
    }

    // Create observer
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          // Optionally unobserve after animation
          // observer.unobserve(entry.target);
        }
      });
    }, {
      root: null,
      rootMargin: '0px 0px -50px 0px',
      threshold: 0.1
    });

    // Observe all scroll-animated elements
    document.querySelectorAll('.reveal-on-scroll, .reveal-on-scroll-left, .reveal-on-scroll-right')
      .forEach(function(el) {
        observer.observe(el);
      });
  }

  // ============================================
  // STAGGER REVEAL TIMING
  // ============================================

  /**
   * Manually trigger stagger animations on a container
   * Useful for dynamically loaded content
   */
  function triggerStaggerReveal(container) {
    if (!container) return;

    var children = container.children;
    var delay = 0;
    var increment = 50; // ms between each child

    Array.from(children).forEach(function(child) {
      child.style.animationDelay = delay + 'ms';
      child.classList.add('animate', 'animate-fade-in-up');
      delay += increment;
    });
  }

  // ============================================
  // PAGE LOAD ANIMATION
  // ============================================

  /**
   * Animate main content on page load
   */
  function initPageLoadAnimation() {
    // Check for reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    // Find main content area
    var mainContent = document.querySelector('.main-content, main, [role="main"]');
    if (mainContent && !mainContent.classList.contains('no-animate')) {
      mainContent.classList.add('animate', 'animate-fade-in-up', 'animate-fast');
    }
  }

  // ============================================
  // DYNAMIC CONTENT HELPERS
  // ============================================

  /**
   * Re-initialize all animations and icons
   * Call after AJAX/dynamic content loads
   */
  window.reinitAnimations = function() {
    initLucideIcons();
    initScrollAnimations();
  };

  /**
   * Expose stagger reveal for manual triggering
   */
  window.triggerStaggerReveal = triggerStaggerReveal;

  // ============================================
  // INITIALIZATION
  // ============================================

  function init() {
    initLucideIcons();
    initPageLoadAnimation();
    initScrollAnimations();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Re-initialize icons on Turbo/HTMX page loads (if used)
  document.addEventListener('turbo:load', initLucideIcons);
  document.addEventListener('htmx:afterSettle', initLucideIcons);

})();
