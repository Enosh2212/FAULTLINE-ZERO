// The HttpOnly, Admin-verified server session is the only application identity.
let current = null, pending = null, status = 'loading', sequence = 0;
const listeners = new Set();
const channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('faultline-session') : null;
function publish(next, value = null) {
  status = next; current = value;
  listeners.forEach(fn => fn({status, session: current}));
  window.dispatchEvent(new CustomEvent('fz-session', {detail:{status, session:current}}));
}
export function observeSession(fn) { listeners.add(fn); fn({status,session:current}); return () => listeners.delete(fn); }
export function clearSession() { ++sequence; pending=null; publish('signed-out'); }
export async function verifySession({fresh = false} = {}) {
  if(pending) return pending;
  if(!fresh && status === 'authenticated') return current;
  const run = ++sequence;
  publish('loading');
  pending = (async () => {
    try {
      const response = await fetch('/api/v1/auth/me', {credentials:'include', cache:'no-store'});
      if(run !== sequence) return null;
      if(response.status === 401) { publish('signed-out'); return null; }
      if(!response.ok) throw Error('Session verification is unavailable');
      const data = await response.json();
      if(!data.user?.id || !data.csrf_token) throw Error('Invalid server session response');
      if(run !== sequence) return null;
      publish('authenticated', data); return data;
    } catch(error) { if(run === sequence) publish('unavailable'); throw error; }
    finally { if(run === sequence) pending = null; }
  })();
  return pending;
}
export async function logout() {
  const session = await verifySession();
  if(session) {
    const response = await fetch('/api/v1/auth/logout', {method:'POST', credentials:'include', cache:'no-store', headers:{'X-CSRF-Token':session.csrf_token}});
    if(!response.ok && response.status !== 401) throw Error('Sign-out failed. Please retry.');
  }
  clearSession(); channel?.postMessage({type:'signed-out'});
  sessionStorage.removeItem('fz_token');
  location.replace('/#landing');
}
export function announceSignIn() { channel?.postMessage({type:'refresh'}); }
channel?.addEventListener('message', event => {
  if(event.data?.type === 'signed-out') clearSession();
  if(event.data?.type === 'refresh') verifySession({fresh:true}).catch(()=>{});
});
window.addEventListener('pagehide', () => { ++sequence; pending=null; publish('loading'); });
window.addEventListener('pageshow', event => {
  if(event.persisted) verifySession({fresh:true}).then(()=>window.dispatchEvent(new HashChangeEvent('hashchange'))).catch(()=>{});
});
