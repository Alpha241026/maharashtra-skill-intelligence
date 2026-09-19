/**
 * Maharashtra Skill Intelligence Platform — Environment Configuration
 *
 * Controls environment detection, API base URL routing, and static host adaptation.
 * Loaded before auth.js and app.js so window.SIH_ENV is universally accessible.
 *
 * MODES:
 *   local  -> localhost/127.0.0.1 with FastAPI backend or local proxy
 *   static -> GitHub Pages (calls Render backend when RENDER_API is configured)
 *
 * TO CONNECT GITHUB PAGES TO YOUR RENDER BACKEND:
 *   Set RENDER_API = "https://your-service.onrender.com"  (line 22 below)
 */

(function () {
  'use strict';

  // ── Render backend URL ───────────────────────────────────────────────────
  // Replace with your Render service URL after deploying the backend.
  // Leave as empty string "" to use verified MSSDS/DVET static baselines.
  var RENDER_API = "";   // e.g. "https://maharashtra-skill-api.onrender.com"

  var hostname = window.location.hostname;

  var isLocal = (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    window.location.protocol === 'file:'
  );

  var isStaticHost = (
    hostname.endsWith('.github.io') ||
    hostname.endsWith('.netlify.app') ||
    hostname.endsWith('.vercel.app') ||
    hostname.endsWith('.pages.dev') ||
    (!isLocal && !window.__SIH_FORCE_API__)
  );

  // Allow runtime override via localStorage or window global
  var customApiUrl = window.SIH_API_URL || RENDER_API || null;
  try {
    if (!customApiUrl && window.localStorage) {
      customApiUrl = window.localStorage.getItem('SIH_API_URL');
    }
  } catch (e) {}

  if (customApiUrl) {
    customApiUrl = customApiUrl.replace(/\/+$/, '');
  }

  window.SIH_ENV = {
    /** 'local' | 'static' */
    MODE: isLocal ? 'local' : 'static',

    /**
     * Base URL for API calls.
     *   customApiUrl set  -> calls Render/cloud backend from any host
     *   isLocal           -> same-origin proxy through server.js ('')
     *   static, no URL   -> null -> app uses verified MSSDS/DVET static baselines
     */
    API_BASE_URL: customApiUrl
      ? customApiUrl
      : (isLocal ? '' : null),

    /** True when on a static host AND no cloud API is configured */
    IS_STATIC: isStaticHost && !customApiUrl,

    IS_LOCAL: isLocal,

    /** Firebase Web Client Configuration (public client keys) */
    FIREBASE: {
      apiKey:            'AIzaSyBOw8GbxDMV_gZzaeMezRcimDKdaAa4qpc',
      authDomain:        'neural-os-platform.firebaseapp.com',
      projectId:         'neural-os-platform',
      storageBucket:     'neural-os-platform.firebasestorage.app',
      messagingSenderId: '669082244060',
      appId:             '1:669082244060:web:e678d9a32514612cf63519',
      measurementId:     'G-DFFYZ5V244'
    },

    VERSION:   '1.3.0',
    BUILD_ENV: isLocal ? 'development' : 'production'
  };

  console.log(
    '[SIH] Environment:',
    'Mode=' + window.SIH_ENV.MODE,
    '| Static=' + window.SIH_ENV.IS_STATIC,
    '| API=' + (
      window.SIH_ENV.API_BASE_URL !== null
        ? (window.SIH_ENV.API_BASE_URL || '(same-origin proxy)')
        : '(offline static baselines)'
    )
  );
})();