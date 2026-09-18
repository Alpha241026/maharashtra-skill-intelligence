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
  GoogleAuthProvider,
  signOut,
  onAuthStateChanged
} from 'https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js';

// ============================================================================
// FIREBASE CONFIGURATION
// ============================================================================
// Paste your Firebase web app configuration from Firebase Console below.
// Location in Console: Project Settings -> General -> Your apps -> Web app (</>)
//
// NOTE: Firebase Web config keys identify your Firebase project in Google Cloud.
// Never place server secrets, service-account keys, or Admin credentials here.
// ============================================================================
const firebaseConfig = {
  apiKey: "AIzaSyBOw8GbxDMV_gZzaeMezRcimDKdaAa4qpc",
  authDomain: "neural-os-platform.firebaseapp.com",
  projectId: "neural-os-platform",
  storageBucket: "neural-os-platform.firebasestorage.app",
  messagingSenderId: "669082244060",
  appId: "1:669082244060:web:e678d9a32514612cf63519",
  measurementId: "G-DFFYZ5V244"
};

let app = null;
let auth = null;

/**
 * Initializes the Firebase App and Auth service.
 * Safe to call multiple times; returns existing auth instance if already initialized.
 */
export function initializeAuth() {
  if (!auth) {
    // initialize firebase app with project configuration
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
  }
  return auth;
}

/**
 * Subscribes to Firebase authentication state changes.
 * Invokes callback immediately with initial state once determined.
 * 
 * @param {function(user: object|null)} callback
 * @returns {function()} unsubscribe function
 */
export function subscribeToAuthState(callback) {
  const authInstance = initializeAuth();
  return onAuthStateChanged(authInstance, (user) => {
    callback(user);
  }, (error) => {
    console.error('[Auth] State observer error:', error);
    callback(null);
  });
}

/**
 * Signs in user with email and password.
 * Maps raw Firebase error codes to user-friendly messages.
 *
 * @param {string} email
 * @param {string} password
 * @returns {Promise<object>} Firebase user credential
 */
export async function signIn(email, password) {
  const authInstance = initializeAuth();
  try {
    const userCredential = await signInWithEmailAndPassword(authInstance, email.trim(), password);
    return userCredential.user;
  } catch (error) {
    const friendlyMessage = mapAuthError(error.code);
    const mappedError = new Error(friendlyMessage);
    mappedError.code = error.code;
    throw mappedError;
  }
}

/**
 * Signs out the currently authenticated user.
 *
 * @returns {Promise<void>}
 */
export async function signOutUser() {
  const authInstance = initializeAuth();
  await signOut(authInstance);
}

/**
 * Converts Firebase error codes to simple, user-facing error text.
 * Avoids leaking raw stack traces or internal mechanics.
 */
function mapAuthError(code) {
  switch (code) {
    case 'auth/invalid-credential':
    case 'auth/user-not-found':
    case 'auth/wrong-password':
    case 'auth/invalid-email':
      return 'Email or password is incorrect';
    case 'auth/user-disabled':
      return 'This account has been disabled. Please contact an administrator';
    case 'auth/too-many-requests':
      return 'Too many attempts. Please wait and try again';
    case 'auth/network-request-failed':
      return 'Unable to reach authentication service. Check your connection';
    default:
      return 'Unable to sign in. Please try again';
  }
}

/**
 * Signs in user using Google OAuth via Firebase popup.
 *
 * @returns {Promise<object>} Firebase user credential
 */
export async function signInWithGoogle() {
  const authInstance = initializeAuth();
  const provider = new GoogleAuthProvider();
  // Optional: prompt user to select account each time
  provider.setCustomParameters({ prompt: 'select_account' });
  try {
    const result = await signInWithPopup(authInstance, provider);
    return result.user;
  } catch (error) {
    if (error.code === 'auth/popup-closed-by-user') {
      throw new Error('Google sign-in was cancelled');
    }
    if (error.code === 'auth/popup-blocked') {
      throw new Error('Sign-in popup was blocked by your browser. Please allow popups');
    }
    const friendlyMessage = mapAuthError(error.code);
    const mappedError = new Error(friendlyMessage);
    mappedError.code = error.code;
    throw mappedError;
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
