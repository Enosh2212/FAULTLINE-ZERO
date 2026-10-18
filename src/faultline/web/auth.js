import {announceSignIn} from './session-state.js';
// Authentication flow is unchanged; visual backdrop is mounted independently.

const $ = id => document.getElementById(id);

const card = document.querySelector('.auth-card');

const buttons = [...document.querySelectorAll('[data-provider]')];

const reduced = matchMedia('(prefers-reduced-motion: reduce)');

const destinations = new Set(['/workspace','/#saas','/#investigation','/#project','/#landing']);

const requestedNext = new URLSearchParams(location.search).get('next');

const next = destinations.has(requestedNext) ? requestedNext : '/workspace';

const modeFromURL = () => location.pathname === '/register' || new URLSearchParams(location.search).get('mode') === 'register' ? 'register' : 'login';

let mode = modeFromURL(), busy = false, switching = false, config = null, client = null, redirectProvider = null, resetMode = false, verificationUser = null;

function setState(state, message, provider = null) {

  busy = ['initializing','loading','authenticating','session','success'].includes(state);

  card.dataset.state = state;

  document.querySelectorAll('#auth-email-form input,#auth-email-form button,#auth-verification button').forEach(el=>el.disabled=busy);

  $('auth-email-submit').disabled ||= !config?.email_password;

  card.setAttribute('aria-busy', String(busy));

  $('auth-feedback').setAttribute('role', state === 'error' ? 'alert' : 'status');

  $('auth-status').textContent = message;

  buttons.forEach(button => {

    const selected = button.dataset.provider === provider;

    button.disabled = busy;

    button.classList.toggle('is-busy', busy && selected && state !== 'success');

    button.querySelector('.provider-label').textContent = selected && busy ? ({loading:'Preparing sign-in…',authenticating:`Waiting for ${provider === 'github' ? 'GitHub' : 'Google'}…`,session:'Securing your workspace…',success:'Signed in'}[state] || 'Connecting…') : `Continue with ${button.dataset.provider === 'github' ? 'GitHub' : 'Google'}`;

    button.setAttribute('aria-disabled', String(busy));

    if (!config?.providers?.[button.dataset.provider]) button.setAttribute('aria-describedby','auth-status');

    else button.removeAttribute('aria-describedby');

  });

}

function applyMode() {

  const register = mode === 'register';

  resetMode = false;

  $('auth-email-form').hidden = !!verificationUser;

  $('auth-email-submit').textContent = register ? 'Create account' : 'Sign in with email';

  $('auth-password').autocomplete = register ? 'new-password' : 'current-password';

  $('auth-password').hidden = $('auth-password-label').hidden = false;

  $('auth-password').required = true;

  $('auth-forgot').hidden = register;

  $('auth-reset-back').hidden = true;

  $('auth-title').textContent = register ? 'Create\naccount' : 'Sign\nin';

  $('auth-description').textContent = register ? 'Investigate code changes before merge, with evidence.' : 'Return to your investigations and connected workflow.';

  document.title = `${register ? 'Create account' : 'Sign in'} · FAULTLINE ZERO`;

  document.querySelector('.auth-top-switch span').textContent = register ? 'Sign in' : 'Create account';

  $('auth-mode-prompt').innerHTML = register ? 'Already have an account? <a data-mode-link href="/login">Sign in <span aria-hidden="true">→</span></a>' : 'New to FAULTLINE? <a data-mode-link href="/register">Create an account <span aria-hidden="true">→</span></a>';

  document.querySelectorAll('[data-mode-link]').forEach(link => link.href = `${register ? '/login' : '/register'}${requestedNext && destinations.has(requestedNext) ? `?next=${encodeURIComponent(next)}` : ''}`);

}

async function switchMode(url, push = true) {

  if (busy || switching) return;

  switching = true;

  if (!reduced.matches) await card.animate([{opacity:1,transform:'translateY(0)'},{opacity:0,transform:'translateY(5px)'}],{duration:130,easing:'ease-out'}).finished;

  if (push) history.pushState(null,'',url);

  mode = modeFromURL(); applyMode();

  if (!reduced.matches) card.animate([{opacity:0,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}],{duration:300,easing:'cubic-bezier(.22,1,.36,1)'});

  $('auth-title').focus({preventScroll:true});

  switching = false;

}

document.addEventListener('click', event => {

  const modeLink = event.target.closest('[data-mode-link]');

  if (modeLink && !event.metaKey && !event.ctrlKey && !event.shiftKey) { event.preventDefault(); switchMode(modeLink.href); }

  const legal = event.target.closest('[data-legal]');

  if (legal) { $('auth-legal-title').textContent = legal.dataset.legal === 'terms' ? 'Terms of Service' : 'Privacy Policy'; $('auth-legal-dialog').showModal(); }

});

addEventListener('popstate', () => switchMode(location.href,false));

applyMode();

async function requestJSON(path, options = {}) {

  const controller = new AbortController();

  const timer = setTimeout(() => controller.abort(), 20000);

  try {

    const response = await fetch(path,{...options,credentials:'include',cache:'no-store',signal:controller.signal});

    if (!response.ok) { const error = new Error('Session request failed'); error.status = response.status; throw error; }

    return await response.json();

  } finally { clearTimeout(timer); }

}

export function friendlyAuthError(error) {

  const messages = {

    'auth/popup-closed-by-user':'Sign-in was closed. You can try again when you’re ready.',

    'auth/cancelled-popup-request':'Another sign-in window was opened. Please use the latest one.',

    'auth/popup-blocked':'Your browser blocked the sign-in window. Allow pop-ups or open sign-in in this tab.',

    'auth/operation-not-supported-in-this-environment':'This browser cannot open a sign-in window. Try signing in in this tab.',

    'auth/operation-not-allowed':'This sign-in provider is not available in this environment yet.',

    'auth/unauthorized-domain':'Sign-in is not enabled for this website address yet.',

    'auth/account-exists-with-different-credential':'This account uses a different sign-in provider. Please continue with your original provider.',

    'auth/invalid-credential':'The email or password is incorrect. Please try again.',

    'auth/email-already-in-use':'An account already uses this email. Sign in or reset your password.',

    'auth/weak-password':'Choose a stronger password with at least six characters.',

    'auth/password-does-not-meet-requirements':'This password does not meet the project password policy. Choose a stronger password.',

    'auth/invalid-email':'Enter a valid email address.',

    'auth/user-not-found':'The email or password is incorrect. Please try again.',

    'auth/wrong-password':'The email or password is incorrect. Please try again.',

    'auth/user-disabled':'This account has been disabled. Contact your workspace administrator.',

    'auth/network-request-failed':'The connection was interrupted. Check your internet connection and try again.',

    'auth/redirect-cancelled-by-user':'Sign-in was interrupted. Please try again.',

    'auth/too-many-requests':'Too many sign-in attempts. Please wait a moment and try again.',

  };

  if (messages[error.code]) return messages[error.code];

  if (error.status === 503) return 'Server sessions are awaiting secure backend configuration. Please try again after setup.';

  if (error.status === 401 || error.status === 403) return 'Your sign-in could not be verified. Please try again.';

  if (error.name === 'AbortError' || error instanceof TypeError) return 'Unable to connect. Check your connection and try again.';

  return 'Sign-in is unavailable right now. Please try again shortly.';

}

async function initializeFirebase(firebase) {

  const sdkRoot = 'https://www.gstatic.com/firebasejs/12.19.0';

  const [appSDK,authSDK] = await Promise.all([import(`${sdkRoot}/firebase-app.js`),import(`${sdkRoot}/firebase-auth.js`)]);

  const app = appSDK.initializeApp(firebase, 'faultline-auth');

  const auth = authSDK.getAuth(app);

  await authSDK.setPersistence(auth, authSDK.inMemoryPersistence);

  return {sdk:authSDK,auth};

}

async function exchangeSession(credential, provider) {

  setState('session','Verifying your sign-in and creating your workspace session.',provider);

  try {

    const idToken = await credential.user.getIdToken(true);

    const csrf = await requestJSON('/api/v1/auth/csrf');

    const session = await requestJSON('/api/v1/auth/session',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf.csrf_token},body:JSON.stringify({id_token:idToken})});

    if (!session.user?.id || !session.csrf_token || session.user.firebase_uid !== credential.user.uid) throw new Error('Invalid session response');

    // A success response alone is insufficient: confirm the HttpOnly cookie is usable.

    const me = await requestJSON('/api/v1/auth/me');

    if (me.user?.firebase_uid !== credential.user.uid) throw new Error('Session cookie unavailable');

    announceSignIn();
    setState('success','Signed in. Opening your workspace…',provider);

    sessionStorage.removeItem('fz_auth_redirect_provider');

    verificationUser = null;

    setTimeout(() => location.replace(next), reduced.matches ? 0 : 650);

  } finally {

    // Server cookie owns the session. Do not retain a second client identity/token.

    await client.sdk.signOut(client.auth).catch(()=>{});

  }

}

function providerFor(name) {

  const provider = name === 'github' ? new client.sdk.GithubAuthProvider() : new client.sdk.GoogleAuthProvider();

  if (name === 'google') provider.setCustomParameters({prompt:'select_account'});

  // Sign-in requests identity only. Repository access remains a separate GitHub App flow.

  return provider;

}

async function signIn(provider, redirect = false) {

  if (busy) return;

  $('auth-redirect').hidden = true;

  if (!config?.providers?.[provider] || !client) {

    setState('error',`${provider === 'github' ? 'GitHub' : 'Google'} sign-in is not available in this environment yet. You can explore the controlled sample demo below.`);

    return;

  }

  redirectProvider = provider;

  setState('authenticating',`Complete sign-in with ${provider === 'github' ? 'GitHub' : 'Google'}. Your workspace will open after verification.`,provider);

  try {

    if (redirect) {

      sessionStorage.setItem('fz_auth_redirect_provider',provider);

      await client.sdk.signInWithRedirect(client.auth,providerFor(provider));

    } else {

      const credential = await client.sdk.signInWithPopup(client.auth,providerFor(provider));

      await finishIdentity(credential,provider);

    }

  } catch (error) {

    setState('error',friendlyAuthError(error));

    $('auth-redirect').hidden = !['auth/popup-blocked','auth/operation-not-supported-in-this-environment'].includes(error.code);

    await client.sdk.signOut(client.auth).catch(()=>{});

  }

}

buttons.forEach(button => button.addEventListener('click',()=>signIn(button.dataset.provider)));

$('auth-redirect').addEventListener('click',()=>signIn(redirectProvider,true));

$('auth-retry').addEventListener('click', initialize);

async function initialize() {

  setState('initializing','Checking sign-in availability…');

  $('auth-retry').hidden = true;

  try {

    config = await requestJSON('/api/v1/auth/config');

    if (!config.configured) {

      setState('unavailable','Sign-in is awaiting setup. You can explore the controlled sample demo below.');

      return;

    }

    setState('loading','Preparing a secure connection…');

    client ||= await initializeFirebase(config.firebase);

    const credential = await client.sdk.getRedirectResult(client.auth);

    if (credential) { await finishIdentity(credential,sessionStorage.getItem('fz_auth_redirect_provider') || 'github'); return; }

    if (sessionStorage.getItem('fz_auth_redirect_provider')) {

      sessionStorage.removeItem('fz_auth_redirect_provider');

      setState('error','Sign-in did not complete. Please try again, or allow sign-in pop-ups in your browser.');

      return;

    }

    setState('idle',config.server_session_ready ? 'Sign in with email or your preferred provider.' : 'Server sessions are awaiting secure backend configuration.');

  } catch (error) {

    setState('error',friendlyAuthError(error));

    $('auth-retry').hidden = false;

  }

}

async function finishIdentity(credential, provider) {

  if (!credential.user.emailVerified) {

    verificationUser = credential.user;

    $('auth-email-form').hidden = true;

    $('auth-verification').hidden = false;

    setState('idle','Verify your email to secure your workspace.');

    try { await client.sdk.sendEmailVerification(verificationUser); setState('idle','Verification email sent. Check your inbox.'); }

    catch(error) { setState('error',friendlyAuthError(error)); }

    return;

  }

  await exchangeSession(credential,provider);

}

$('auth-email-form').addEventListener('submit',async event=>{

  event.preventDefault();

  if(busy || !client || !config?.email_password) return;

  const email = $('auth-email').value.trim();

  setState('authenticating',resetMode ? 'Sending password reset instructions…' : 'Verifying your account…');

  try {

    if(resetMode) {

      try { await client.sdk.sendPasswordResetEmail(client.auth,email); }

      catch(error) { if(error.code !== 'auth/user-not-found') throw error; }

      setState('idle','If an account exists for this email, password reset instructions have been sent.');

      return;

    }

    const method = mode === 'register' ? 'createUserWithEmailAndPassword' : 'signInWithEmailAndPassword';

    const credential = await client.sdk[method](client.auth,email,$('auth-password').value);

    $('auth-password').value = '';

    await finishIdentity(credential,'email');

  } catch(error) { setState('error',friendlyAuthError(error)); await client.sdk.signOut(client.auth).catch(()=>{}); }

});

$('auth-forgot').onclick=()=>{

  if(busy) return;

  resetMode=true;

  $('auth-title').textContent='Reset your password';

  $('auth-description').textContent='We’ll send a secure reset link to your email.';

  $('auth-password').hidden=$('auth-password-label').hidden=$('auth-forgot').hidden=true;

  $('auth-password').required=false;

  $('auth-email-submit').textContent='Send reset link';

  $('auth-reset-back').hidden=false;

  setState('idle','Enter the email address you used to register.');

  $('auth-email').focus();

};

$('auth-reset-back').onclick=()=>{applyMode();setState('idle','Sign in to your workspace.');};

$('auth-resend-email').onclick=async()=>{

  if(busy || !verificationUser) return;

  setState('loading','Sending verification email…');

  try { await client.sdk.sendEmailVerification(verificationUser);setState('idle','Verification email sent. Check your inbox.'); }

  catch(error){setState('error',friendlyAuthError(error));}

};

$('auth-check-email').onclick=async()=>{

  if(busy || !verificationUser) return;

  setState('authenticating','Checking email verification…');

  try {

    await client.sdk.reload(verificationUser);

    if(!verificationUser.emailVerified){setState('idle','Your email is not verified yet. Open the link in your inbox first.');return;}

    await exchangeSession({user:verificationUser},'email');

  } catch(error){setState('error',friendlyAuthError(error));}

};

$('auth-verification-back').onclick=async()=>{

  if(busy) return;

  await client.sdk.signOut(client.auth);

  verificationUser=null;$('auth-verification').hidden=true;

  applyMode();setState('idle','Sign in to your workspace.');

};

initialize();

