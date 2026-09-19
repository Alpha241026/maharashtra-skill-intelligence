/**
 * Maharashtra Skill Intelligence Platform — Firebase Authentication Module
 *
 * Responsibility:
 * - Owns all Firebase Web SDK initialization and authentication operations.
 * - Exposes a minimal, isolated API for the application layer.
 * - Does NOT perform DOM manipulations or hold dashboard state.
 */

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js';
import {
  getAuth,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  GoogleAuthProvider,
  signOut,
  onAuthStateChanged
} from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js';

// ============================================================================
// FIREBASE CONFIGURATION
// ============================================================================
const defaultFirebaseConfig = {
  apiKey: "AIzaSyBOw8GbxDMV_gZzaeMezRcimDKdaAa4qpc",
  authDomain: "neural-os-platform.firebaseapp.com",
  projectId: "neural-os-platform",
  storageBucket: "neural-os-platform.firebasestorage.app",
  messagingSenderId: "669082244060",
  appId: "1:669082244060:web:e678d9a32514612cf63519",
  measurementId: "G-DFFYZ5V244"
};

const firebaseConfig = (window.SIH_ENV && window.SIH_ENV.FIREBASE) || defaultFirebaseConfig;

let app = null;
let auth = null;

/**
 * Returns true when running on a static host where popup auth fails.
 * GitHub Pages, Netlify, Vercel all require redirect flow for Google Sign-In.
 */
function isStaticHost() {
  var host = window.location.hostname;
  return (
    host.endsWith('.github.io') ||
    host.endsWith('.netlify.app') ||
    host.endsWith('.vercel.app') ||
    host.endsWith('.pages.dev')
  );
}

/**
 * Initializes the Firebase App and Auth service.
 * Safe to call multiple times; returns existing auth instance if already initialized.
 */
export function initializeAuth() {
  if (!auth) {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
  }
  return auth;
}

/**
 * Subscribes to Firebase authentication state changes.
 * Also resolves any pending Google Sign-In redirect result.
 *
 * @param {function(user: object|null)} callback
 * @returns {function()} unsubscribe function
 */
export function subscribeToAuthState(callback) {
  var authInstance = initializeAuth();

  // Resolve Google redirect sign-in result (fires after page reload)
  getRedirectResult(authInstance)
    .then(function(result) {
      if (result && result.user) {
        console.log('[Auth] Google redirect sign-in resolved:', result.user.email);
      }
    })
    .catch(function(error) {
      console.warn('[Auth] Redirect result error:', error.code, error.message);
    });

  return onAuthStateChanged(authInstance, function(user) {
    callback(user);
  }, function(error) {
    console.error('[Auth] State observer error:', error);
    callback(null);
  });
}

/**
 * Signs in user with email and password.
 *
 * @param {string} email
 * @param {string} password
 * @returns {Promise<object>} Firebase user
 */
export async function signIn(email, password) {
  var authInstance = initializeAuth();
  try {
    var userCredential = await signInWithEmailAndPassword(authInstance, email.trim(), password);
    return userCredential.user;
  } catch (error) {
    console.error('[Auth] Email sign-in error:', error.code, error.message);
    var friendlyMessage = mapAuthError(error.code);
    var mappedError = new Error(friendlyMessage);
    mappedError.code = error.code;
    throw mappedError;
  }
}

/**
 * Signs out the currently authenticated user.
 */
export async function signOutUser() {
  var authInstance = initializeAuth();
  await signOut(authInstance);
}

/**
 * Signs in with Google.
 * - On GitHub Pages / static hosts: uses redirect flow (avoids popup restrictions).
 * - On localhost / custom domains: uses popup flow for faster UX.
 */
export async function signInWithGoogle() {
  var authInstance = initializeAuth();
  var provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: 'select_account' });

  try {
    // Attempt popup first (fast, keeps page state, works on both localhost and modern static hosts)
    var result = await signInWithPopup(authInstance, provider);
    return result.user;
  } catch (error) {
    // If popup was blocked by browser or environment, fallback to redirect flow
    if (error.code === 'auth/popup-blocked' || error.code === 'auth/cancelled-popup-request') {
      try {
        console.warn('[Auth] Popup blocked or cancelled, falling back to redirect flow...');
        await signInWithRedirect(authInstance, provider);
        return; // Page will redirect
      } catch (redirectError) {
        var msg = mapAuthError(redirectError.code);
        var err = new Error(msg);
        err.code = redirectError.code;
        throw err;
      }
    }

    console.error('[Auth] Google sign-in error:', error.code, error.message);
    var friendlyMessage = mapAuthError(error.code);
    var mappedError = new Error(friendlyMessage);
    mappedError.code = error.code;
    throw mappedError;
  }
}

/**
 * Maps Firebase error codes to user-facing messages.
 * The default case always shows the raw error code so you can debug.
 */
function mapAuthError(code) {
  switch (code) {
    case 'auth/invalid-credential':
    case 'auth/user-not-found':
    case 'auth/wrong-password':
      return 'Email or password is incorrect. Check your credentials and try again';
    case 'auth/invalid-email':
      return 'Please enter a valid email address';
    case 'auth/user-disabled':
      return 'This account has been disabled. Contact an administrator';
    case 'auth/too-many-requests':
      return 'Too many failed attempts. Please wait a few minutes and try again';
    case 'auth/network-request-failed':
      return 'Network error. Check your internet connection and try again';
    case 'auth/unauthorized-domain':
      return 'Domain not authorized. Go to Firebase Console → Authentication → Settings → Authorized domains → Add "' + window.location.hostname + '"';
    case 'auth/operation-not-allowed':
      return 'Sign-in method not enabled. Go to Firebase Console → Authentication → Sign-in method and enable it';
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
      return 'Sign-in was cancelled';
    case 'auth/popup-blocked':
      return 'Pop-up blocked by browser. Allow pop-ups and try again';
    case 'auth/configuration-not-found':
      return 'Firebase project misconfigured. Verify the project settings';
    default:
      // Always show the real error code for debugging
      return 'Sign-in failed (' + (code || 'unknown') + '). Open DevTools Console for details';
  }
}

// Expose on global window object for non-module integration with app.js
window.AuthModule = {
  initializeAuth,
  signIn,
  signInWithGoogle,
  signOutUser,
  subscribeToAuthState
};
