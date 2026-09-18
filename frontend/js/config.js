/**
 * Maharashtra Skill Intelligence Platform — Environment Configuration
 *
 * Controls environment detection, API base URL routing, and static host adaptation.
 * Loaded before auth.js and app.js so window.SIH_ENV is universally accessible.
 *
 * MODES:
 *   local   → localhost/127.0.0.1 with FastAPI backend or local proxy
 *   static  → GitHub Pages, Netlify, Vercel (operates with verified MSSDS/DVET static baselines)
 */

(function () {
  'use strict';

  var hostname = window.location.hostname;

  // Detect local development environment
  var isLocal = (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    window.location.protocol === 'file:'
  );

  // Detect static hosting platforms
  var isStaticHost = (
    hostname.endsWith('.github.io') ||
    hostname.endsWith('.netlify.app') ||
    hostname.endsWith('.vercel.app') ||
    hostname.endsWith('.pages.dev') ||
    (!isLocal && !window.__SIH_FORCE_API__)
  );

  // Allow runtime override via localStorage or window global
  var customApiUrl = window.SIH_API_URL || null;
  try {
    if (!customApiUrl && window.localStorage) {
      customApiUrl = window.localStorage.getItem('SIH_API_URL');
    }
  } catch (e) {
    // Storage access might be restricted in some iframe/sandboxed environments
  }

  window.SIH_ENV = {
    /** 'local' | 'static' */
    MODE: isLocal ? 'local' : 'static',

    /**
     * Base URL for API calls.
     * If customApiUrl is set: uses that cloud endpoint.
     * If local: uses same-origin proxy ('').
     * If static and no custom URL: null (signals to use verified static baselines).
     */
    API_BASE_URL: customApiUrl ? customApiUrl.replace(/\/+$/, '') : (isLocal ? '' : null),

    /** True when running on a static host without a cloud API configured */
    IS_STATIC: isStaticHost && !customApiUrl,

    /** True when running locally */
    IS_LOCAL: isLocal,

    /** Groq Cloud API configuration for static host conversation synthesis */
    GROQ_API_KEY: (function () {
      try {
        return (typeof window !== 'undefined' && window.SIH_GROQ_KEY)
          || (typeof localStorage !== 'undefined' ? localStorage.getItem('SIH_GROQ_KEY') : '')
          || '';
      } catch (e) {
        return '';
      }
    })(),
    GROQ_MODEL: "openai/gpt-oss-120b",

    /** Firebase Web Client Configuration */
    FIREBASE: {
      apiKey: "AIzaSyBOw8GbxDMV_gZzaeMezRcimDKdaAa4qpc",
      authDomain: "neural-os-platform.firebaseapp.com",
      projectId: "neural-os-platform",
      storageBucket: "neural-os-platform.firebasestorage.app",
      messagingSenderId: "669082244060",
      appId: "1:669082244060:web:e678d9a32514612cf63519",
      measurementId: "G-DFFYZ5V244"
    },

    /** Platform version metadata */
    VERSION: '1.2.0',
    BUILD_ENV: isLocal ? 'development' : 'production'
  };

  console.log(
    '[SIH] Environment Initialized:',
    'Mode=' + window.SIH_ENV.MODE,
    '| StaticMode=' + window.SIH_ENV.IS_STATIC,
    '| API=' + (window.SIH_ENV.API_BASE_URL !== null ? (window.SIH_ENV.API_BASE_URL || '(same-origin proxy)') : '(offline static pilot)')
  );
})();
