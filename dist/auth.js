/* Session secret is an HttpOnly cookie. CSRF value stays in memory only. */
let csrfToken='';
const nativeFetch=window.fetch.bind(window);
function signedOut(message=''){
  csrfToken='';window.clearPrivatePlan?.();
  document.querySelector('main').hidden=true;
  document.querySelector('#account-controls').hidden=true;
  document.querySelector('#sign-in').hidden=false;
  document.querySelector('#login-error').textContent=message;
}
function signedIn(data){
  csrfToken=data.csrf;
  document.querySelector('#account-name').textContent=data.username;
  document.querySelector('#sign-in').hidden=true;
  document.querySelector('#account-controls').hidden=false;
  document.querySelector('main').hidden=false;
  document.querySelector('#password').value='';
}
async function apiFetch(url,options={}){
  const method=(options.method||'GET').toUpperCase();
  const headers=new Headers(options.headers||{});
  if(!['GET','HEAD'].includes(method))headers.set('X-CSRF-Token',csrfToken);
  const response=await nativeFetch(url,{...options,headers,credentials:'same-origin'});
  if(response.status===401)signedOut('Please sign in again. Your session expired or was revoked.');
  return response;
}
window.authReady=(async()=>{
  try{const response=await nativeFetch('/api/auth/session',{cache:'no-store',credentials:'same-origin'});
    if(!response.ok){signedOut(response.status===404?'An older server is open. Use http://127.0.0.1:8003.':'');return false;}signedIn(await response.json());return true;
  }catch{signedOut('Cannot connect to the local server. Start the app and refresh.');return false;}
})();
document.querySelector('#login-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=document.querySelector('#login-button');button.disabled=true;
  try{
    const response=await nativeFetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({username:document.querySelector('#username').value,password:document.querySelector('#password').value})});
    const data=await response.json();document.querySelector('#password').value='';
    if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Could not sign in.');
    signedIn(data);await loadConfig();loadUsage();
  }catch(error){document.querySelector('#login-error').textContent=error.message;}
  finally{button.disabled=false;}
});
for(const [id,path] of [['logout','logout'],['logout-all','logout-all']])document.querySelector('#'+id).addEventListener('click',async()=>{
  try{const response=await apiFetch('/api/auth/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    if(!response.ok&&response.status!==401)throw Error();signedOut('Signed out.');
  }catch{document.querySelector('#account-message').textContent='Could not sign out on the server. Please retry.';}
});
