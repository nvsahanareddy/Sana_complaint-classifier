/**
 * Smart Complaint Assistant — Modern UI Utilities & Enhancements
 * - Theme Switcher (System / Dark / Light) with smooth transition
 * - Stat Counter Animations
 * - Password Visibility Toggles
 * - Accessible Dialog Backdrop Dismissal & Keyboard Navigation
 * - Active Navigation ScrollSpy
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. THEME SWITCHER (Dark / Light)
  // =========================================================================
  const THEME_KEY = 'civic_theme_preference';

  function getSystemPreference() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
  }

  function getStoredTheme() {
    return localStorage.getItem(THEME_KEY) || getSystemPreference();
  }

  function applyTheme(theme, save = true) {
    document.documentElement.setAttribute('data-theme', theme);
    if (save) {
      try {
        localStorage.setItem(THEME_KEY, theme);
      } catch (e) {
        // LocalStorage might be disabled in private mode
      }
    }
    updateThemeToggleButtons(theme);
  }

  function updateThemeToggleButtons(theme) {
    const btns = document.querySelectorAll('.theme-toggle, [data-action="toggle-theme"]');
    btns.forEach(btn => {
      const isDark = theme === 'dark';
      btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
      btn.setAttribute('title', isDark ? 'Switch to light mode' : 'Switch to dark mode');
      // Update SVG or inner icon if present
      const icon = btn.querySelector('.theme-icon') || btn;
      if (isDark) {
        // High-visibility golden sun with filled center and radiant rays
        icon.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FBBF24" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 0 6px rgba(251, 191, 36, 0.6));" aria-hidden="true"><circle cx="12" cy="12" r="5" fill="#FBBF24" stroke="#FBBF24"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;
      } else {
        // High-visibility deep navy filled crescent moon
        icon.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="#1F3A5F" stroke="#1F3A5F" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 1px 3px rgba(31, 58, 95, 0.3));" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
      }
    });
  }

  function initTheme() {
    const initialTheme = getStoredTheme();
    applyTheme(initialTheme, false);

    // Watch for OS preference changes
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem(THEME_KEY)) {
          applyTheme(e.matches ? 'dark' : 'light', false);
        }
      });
    }

    // Attach click listeners
    document.addEventListener('click', e => {
      const toggle = e.target.closest('.theme-toggle, [data-action="toggle-theme"]');
      if (toggle) {
        e.preventDefault();
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next, true);
      }
    });
  }

  // =========================================================================
  // 2. NUMBER COUNT-UP ANIMATION
  // =========================================================================
  function animateCount(el, target, duration = 800) {
    if (!el) return;
    const startVal = parseInt(el.textContent, 10) || 0;
    const endVal = parseInt(target, 10) || 0;
    if (startVal === endVal) {
      el.textContent = endVal;
      return;
    }

    const startTime = performance.now();
    function step(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const easeProgress = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(startVal + (endVal - startVal) * easeProgress);
      el.textContent = current;

      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = endVal;
      }
    }
    requestAnimationFrame(step);
  }

  function setupStatsObserver() {
    const statIds = ['sNeeds', 'sChecks', 'sClosed', 'navCount'];
    statIds.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      let lastVal = el.textContent;
      const observer = new MutationObserver(mutations => {
        mutations.forEach(m => {
          if (m.type === 'childList' || m.type === 'characterData') {
            const raw = el.textContent.trim();
            const num = parseInt(raw, 10);
            if (!isNaN(num) && String(num) !== lastVal && !el.dataset.animating) {
              lastVal = String(num);
              el.dataset.animating = 'true';
              animateCount(el, num);
              setTimeout(() => {
                delete el.dataset.animating;
              }, 850);
            }
          }
        });
      });
      observer.observe(el, { childList: true, characterData: true, subtree: true });
    });
  }

  // =========================================================================
  // 3. DIALOG ACCESSIBILITY & BACKDROP CLICK TO CLOSE
  // =========================================================================
  function setupDialogHelpers() {
    document.querySelectorAll('dialog').forEach(dlg => {
      // Backdrop click closes dialog
      dlg.addEventListener('click', e => {
        const rect = dlg.getBoundingClientRect();
        const isInDialog = (
          rect.top <= e.clientY &&
          e.clientY <= rect.top + rect.height &&
          rect.left <= e.clientX &&
          e.clientX <= rect.left + rect.width
        );
        if (!isInDialog) {
          dlg.close();
        }
      });

      // Escape key handles graceful close
      dlg.addEventListener('cancel', () => {
        // Native cancel event fires on Escape
      });
    });
  }

  // =========================================================================
  // 4. PASSWORD VISIBILITY TOGGLE HELPER
  // =========================================================================
  function setupPasswordToggles() {
    document.addEventListener('click', e => {
      const toggle = e.target.closest('[data-toggle-password]');
      if (!toggle) return;
      const targetId = toggle.getAttribute('data-toggle-password');
      const input = document.getElementById(targetId);
      if (!input) return;

      const isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';
      toggle.setAttribute('aria-pressed', isPassword ? 'true' : 'false');
      toggle.setAttribute('title', isPassword ? 'Hide password' : 'Show password');

      const icon = toggle.querySelector('svg');
      if (icon) {
        if (isPassword) {
          // Slash / hide eye
          icon.innerHTML = `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>`;
        } else {
          // Open eye
          icon.innerHTML = `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>`;
        }
      }
    });
  }

  // =========================================================================
  // 5. NAV SCROLLSPY & SMOOTH BEHAVIOR
  // =========================================================================
  function setupScrollSpy() {
    const navLinks = document.querySelectorAll('.top nav a[href^="#"]');
    if (!navLinks.length) return;

    const sections = Array.from(navLinks).map(link => {
      const target = document.querySelector(link.getAttribute('href'));
      return { link, target };
    }).filter(item => item.target !== null);

    window.addEventListener('scroll', () => {
      const scrollPos = window.scrollY + 120;
      let current = sections[0];
      for (const s of sections) {
        if (s.target.offsetTop <= scrollPos) {
          current = s;
        }
      }
      if (current) {
        navLinks.forEach(l => l.classList.remove('active'));
        current.link.classList.add('active');
      }
    }, { passive: true });
  }

  // =========================================================================
  // INITIALIZATION ON DOMContentLoaded
  // =========================================================================
  function init() {
    initTheme();
    setupStatsObserver();
    setupDialogHelpers();
    setupPasswordToggles();
    setupScrollSpy();
    setupMobileMenu();
    setupReportModalInteractions();
  }

  // =========================================================================
  // 6. MOBILE HAMBURGER MENU NAVIGATION
  // =========================================================================
  function setupMobileMenu() {
    const hamburgerBtns = document.querySelectorAll('.hamburger-btn, [data-action="toggle-mobile-menu"]');
    if (!hamburgerBtns.length) return;

    hamburgerBtns.forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const header = btn.closest('header.top, header.topbar, header');
        if (!header) return;
        const isOpen = header.classList.toggle('nav-open');
        btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        btn.classList.toggle('is-active', isOpen);
      });
    });

    // Close when clicking outside header or on navigation links / actions
    document.addEventListener('click', e => {
      const activeHeader = document.querySelector('header.nav-open');
      if (!activeHeader) return;

      const isInsideHeader = activeHeader.contains(e.target);
      const isNavLink = e.target.closest('a, button:not(.hamburger-btn):not(.mobile-theme-toggle)');

      if (!isInsideHeader || isNavLink) {
        activeHeader.classList.remove('nav-open');
        const activeBtn = activeHeader.querySelector('.hamburger-btn');
        if (activeBtn) {
          activeBtn.setAttribute('aria-expanded', 'false');
          activeBtn.classList.remove('is-active');
        }
      }
    });

    // Close on Escape key
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        const activeHeader = document.querySelector('header.nav-open');
        if (activeHeader) {
          activeHeader.classList.remove('nav-open');
          const activeBtn = activeHeader.querySelector('.hamburger-btn');
          if (activeBtn) {
            activeBtn.setAttribute('aria-expanded', 'false');
            activeBtn.classList.remove('is-active');
            activeBtn.focus();
          }
        }
      }
    });
  }

  // =========================================================================
  // 7. NEW REPORT MODAL INTERACTIVE ENHANCEMENTS
  // =========================================================================
  function setupReportModalInteractions() {
    const reportDlg = document.getElementById('reportDlg');
    if (!reportDlg) return;

    const fCategory = document.getElementById('fCategory');
    const catChips = document.querySelectorAll('#quickCategoryChips .cat-chip');
    const fTitle = document.getElementById('fTitle');
    const fText = document.getElementById('fText');
    const promptChips = document.querySelectorAll('.prompt-chip');
    const descCharCount = document.getElementById('descCharCount');
    const descCharHint = document.getElementById('descCharHint');
    const locText = document.getElementById('locText');
    const locationCard = document.getElementById('locationCard');
    const locStatusBadge = document.getElementById('locStatusBadge');

    // 1. Sync Category Chips with <select id="fCategory">
    if (fCategory && catChips.length) {
      catChips.forEach(chip => {
        chip.addEventListener('click', () => {
          const cat = chip.getAttribute('data-cat') || '';
          fCategory.value = cat;
          fCategory.dispatchEvent(new Event('change', { bubbles: true }));
          catChips.forEach(c => c.classList.toggle('active', c === chip));
        });
      });

      fCategory.addEventListener('change', () => {
        const val = fCategory.value;
        catChips.forEach(c => {
          c.classList.toggle('active', (c.getAttribute('data-cat') || '') === val);
        });
      });
    }

    // 2. Quick prompt templates
    if (promptChips.length && fTitle && fText) {
      promptChips.forEach(chip => {
        chip.addEventListener('click', () => {
          const pTitle = chip.getAttribute('data-prompt-title') || '';
          const pDesc = chip.getAttribute('data-prompt-desc') || '';
          if (pTitle) {
            fTitle.value = pTitle;
            fTitle.dispatchEvent(new Event('input', { bubbles: true }));
          }
          if (pDesc) {
            fText.value = pDesc;
            fText.dispatchEvent(new Event('input', { bubbles: true }));
          }
        });
      });
    }

    // 3. Live character count & validation indicator
    if (fText && descCharCount && descCharHint) {
      function updateCharCount() {
        const len = (fText.value || '').length;
        descCharCount.textContent = `${len} / 2000`;
        if (len >= 10) {
          descCharHint.textContent = '✓ Description ready';
          descCharHint.classList.add('valid');
        } else {
          descCharHint.textContent = len === 0 ? 'Min 10 characters' : `Min 10 characters (${10 - len} more)`;
          descCharHint.classList.remove('valid');
        }
      }
      fText.addEventListener('input', updateCharCount);
      updateCharCount();
    }

    // 4. Geolocation status badge tracker (Observer for locText updates)
    if (locText && (locationCard || locStatusBadge)) {
      function checkPinStatus() {
        const txt = (locText.textContent || '').trim();
        const hasPin = txt !== '' && txt !== 'No pin yet';
        if (locStatusBadge) {
          locStatusBadge.textContent = hasPin ? '📍 Pin Dropped' : 'Pin Required';
          locStatusBadge.classList.toggle('pinned', hasPin);
        }
        if (locationCard) {
          locationCard.classList.toggle('pinned', hasPin);
        }
      }

      const observer = new MutationObserver(checkPinStatus);
      observer.observe(locText, { childList: true, characterData: true, subtree: true });
      checkPinStatus();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose global helpers under window.CivicUI
  window.CivicUI = {
    applyTheme,
    animateCount
  };
})();
