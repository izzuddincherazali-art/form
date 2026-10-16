let sessions = [];
let currentUser = null;
let hosts = [];
sessionStorage.removeItem('live-token');
const $ = id => document.getElementById(id);
const money = value => new Intl.NumberFormat('en-MY', {style:'currency',currency:'MYR'}).format(value);
const number = value => new Intl.NumberFormat('en-MY').format(value);
const duration = row => (new Date(row.end + '+08:00') - new Date(row.start + '+08:00')) / 3600000;
const selectedSessions = () => sessions.filter(row => !$('host-filter').value || String(row.user_id) === $('host-filter').value);
const filtered = () => selectedSessions().filter(row => row.host.toLowerCase().includes($('search').value.toLowerCase()));
function cell(row, text, sub) { const td = document.createElement('td'); td.textContent = text; if(sub) { const small = document.createElement('small'); small.textContent = sub; td.append(small); } row.append(td); }
function render() {
 $('gmv').textContent = money(selectedSessions().reduce((s,r)=>s+r.gmv_cents,0)/100);
 $('views').textContent = number(selectedSessions().reduce((s,r)=>s+r.views,0));
 $('count').textContent = number(selectedSessions().length);
 $('hours').textContent = selectedSessions().reduce((s,r)=>s+duration(r),0).toFixed(1)+' hrs';
 const rows = filtered(); $('records').replaceChildren();
 for(const record of rows) { const tr = document.createElement('tr'); cell(tr,record.host,new Date(record.start+'+08:00').toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur',dateStyle:'medium',timeStyle:'short'})); cell(tr,money(record.gmv_cents/100)); cell(tr,number(record.views)); cell(tr,duration(record).toFixed(2)+' hrs'); cell(tr,record.notes || '—'); if(currentUser?.can_view_all && record.user_id === null) { const select=document.createElement('select'); const option=document.createElement('option'); option.textContent='Assign legacy record…';option.value='';select.append(option);for(const host of hosts){const op=document.createElement('option');op.value=host.id;op.textContent=host.name;select.append(op);}select.addEventListener('change',async()=>{if(!select.value)return;try{await api('/api/assign',{id:record.id,user_id:Number(select.value)});await load();}catch(e){$('form-status').textContent=e.message;}});tr.lastChild.append(select); } $('records').append(tr); }
 $('results').textContent = rows.length+' sessions'; $('empty').hidden = rows.length > 0;
 $('empty').textContent = sessions.length ? 'No hosts match your search.' : 'No sessions yet. Record your first live above.';
 $('export').disabled = rows.length === 0;
 drawChart();
}
async function api(path, data) {
 const response=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const result=await response.json(); if(!response.ok){const error=new Error(result.error || 'Request failed');error.status=response.status;throw error;}return result;
}
function clearPrivateData(){$('change-password').hidden=true;$('password-form').reset();$('password-dialog').close();sessions=[];hosts=[];currentUser=null;$('host-name').value='';$('host-credentials').textContent='';$('host-credentials').hidden=true;$('admin-panel').hidden=true;$('host-filter').hidden=true;$('access').textContent='Sign in';render();}
async function load() {
 try {
 currentUser=await api('/api/me');
 $('access').textContent=currentUser.name+' · Sign out';$('change-password').hidden=false;
 $('host-name').value=currentUser.name;
 document.querySelector('h1').textContent=currentUser.can_view_all?'Team performance':'My performance';
 $('admin-panel').hidden=!currentUser.is_admin;
 hosts=currentUser.is_admin?await api('/api/users'):[];
 $('host-filter').replaceChildren(new Option('All hosts',''));
 for(const host of hosts) $('host-filter').add(new Option(host.name,String(host.id)));
 $('host-filter').hidden=!currentUser.can_view_all;
 sessions=await api('/api/sessions'); render();
 }catch(error){clearPrivateData();$('empty').textContent=error.message;if(error.status===401 && !$('login').open)$('login').showModal();}
}
$('session-form').addEventListener('submit',async event=>{
 event.preventDefault(); const form=event.target; const data=Object.fromEntries(new FormData(form));
 if(data.end<=data.start) { $('form-status').textContent='End time must be after start time.'; return; }
 $('save').disabled=true; $('form-status').textContent='Saving session…';
 try { const result=await api('/api/sessions',data); sessions.push(result); sessions.sort((a,b)=>b.start.localeCompare(a.start)||b.id-a.id); render(); form.reset(); $('host-name').value=currentUser.name; $('form-status').textContent='Session saved successfully.'; }
 catch(error) { $('form-status').textContent=error.message; }
 finally { $('save').disabled=false; }
});
$('search').addEventListener('input',render);
$('access').addEventListener('click',async()=>{if(currentUser){try{await api('/api/logout',{});}catch(e){$('form-status').textContent=e.message;return;}clearPrivateData();}if(!$('login').open)$('login').showModal();});
$('login').addEventListener('cancel',event=>{event.preventDefault();});
$('login-form').addEventListener('submit',async event=>{event.preventDefault();$('login-button').disabled=true;$('login-status').textContent='Signing in…';try{await api('/api/login',{username:$('username').value,password:$('password').value});$('password').value='';$('login-status').textContent='';$('login').close();await load();}catch(error){$('login-status').textContent=error.message;}finally{$('login-button').disabled=false;}});
$('create-host').addEventListener('submit',async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;$('host-credentials').hidden=true;$('host-credentials').textContent='';try{const result=await api('/api/users',Object.fromEntries(new FormData(event.target)));$('host-credentials').textContent='Username: '+result.username+'\nPassword: '+result.password;$('host-credentials').hidden=false;$('account-status').textContent='Account created. Copy these credentials and share privately with this host.';event.target.reset();hosts=await api('/api/users');$('host-filter').replaceChildren(new Option('All hosts',''));for(const host of hosts)$('host-filter').add(new Option(host.name,String(host.id)));render();}catch(error){$('account-status').textContent=error.message;}finally{button.disabled=false;}});
$('host-filter').addEventListener('change',render);
$('metric').addEventListener('change',drawChart);
$('period').addEventListener('change',drawChart);
$('export').addEventListener('click',()=>{
 const safe = value => { let text=String(value); if(/^[=+@\-\t\r]/.test(text)) text="'"+text; return '"'+text.replaceAll('"','""')+'"'; };
 const rows=[['Host','Start (Malaysia)','End (Malaysia)','GMV (MYR)','Views','Hours','Notes'],...filtered().map(r=>[r.host,r.start,r.end,(r.gmv_cents/100).toFixed(2),r.views,duration(r).toFixed(2),r.notes])];
 const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(r=>r.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'})); const a=document.createElement('a'); a.href=url;a.download='live-sessions.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});

function drawChart(){
 const days=Number($('period').value),metric=$('metric').value;
 const today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kuala_Lumpur'});
 const anchor=new Date(today+'T12:00:00+08:00');
 const points=Array.from({length:days},(_,i)=>{const d=new Date(anchor);d.setUTCDate(d.getUTCDate()-(days-1-i));return {date:d.toLocaleDateString('en-CA',{timeZone:'Asia/Kuala_Lumpur'}),value:0};});
 for(const row of selectedSessions()){const point=points.find(p=>p.date===row.start.slice(0,10));if(point)point.value+=metric==='gmv'?row.gmv_cents/100:row.views;}
 const total=points.reduce((s,p)=>s+p.value,0),max=Math.max(1,...points.map(p=>p.value));
 const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 1000 250');svg.setAttribute('aria-hidden','true');
 function element(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;svg.append(e);return e;}
 const x=i=>75+i/(days-1)*900,y=value=>205-value/max*170;
 for(let i=0;i<=4;i++){const value=max*i/4;const pos=y(value);element('line',{x1:75,y1:pos,x2:975,y2:pos,stroke:'#e8ece8'});element('text',{x:65,y:pos+4,'text-anchor':'end',fill:'#777','font-size':11},number(Math.round(value*100)/100));}
 const line=points.map((p,i)=>(i?'L':'M')+x(i)+','+y(p.value)).join(' ');
 element('path',{d:line+' L975,205 L75,205 Z',fill:'#edf5ef'});
 element('path',{d:line,fill:'none',stroke:'#008060','stroke-width':3,'stroke-linejoin':'round'});
 points.forEach((p,i)=>{const c=element('circle',{cx:x(i),cy:y(p.value),r:4,fill:'#008060'});const title=document.createElementNS(ns,'title');title.textContent=p.date+': '+(metric==='gmv'?money(p.value):number(p.value)+' views');c.append(title);if(i===0||i===days-1||i%Math.ceil(days/5)===0)element('text',{x:x(i),y:233,'text-anchor':'middle',fill:'#777','font-size':11},p.date.slice(5));});
 $('chart').replaceChildren(svg);$('chart').setAttribute('aria-label',points.map(p=>p.date+': '+p.value).join('; '));
 $('chart-summary').textContent=(metric==='gmv'?money(total):number(total)+' views')+' across the last '+days+' days. Hover a point for its daily total.';
}

$('change-password').addEventListener('click',()=>{$('password-form').reset();$('password-status').textContent='';$('password-dialog').showModal();});
$('cancel-password').addEventListener('click',()=>{$('password-form').reset();$('password-dialog').close();});
$('password-dialog').addEventListener('cancel',()=>{$('password-form').reset();});
$('password-form').addEventListener('submit',async event=>{
 event.preventDefault();const data=Object.fromEntries(new FormData(event.target));
 if(data.new_password!==data.confirm_password){$('password-status').textContent='New passwords do not match.';return;}
 $('save-password').disabled=true;$('password-status').textContent='Saving…';
 try{await api('/api/change-password',data);clearPrivateData();$('login-status').textContent='Password changed. Sign in with your new password.';$('login').showModal();}
 catch(error){$('password-status').textContent=error.message;}
 finally{$('save-password').disabled=false;}
});
load();
