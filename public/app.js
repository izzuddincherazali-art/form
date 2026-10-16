let sessions = [];
let currentUser = null;
let hosts = [];
let cohosts = [];
let editingId=null;
const recoveryFragment=new URLSearchParams(location.hash.slice(1));
const resetToken=recoveryFragment.get("reset"),verifyToken=recoveryFragment.get("verify");
if(resetToken||verifyToken)history.replaceState(null,"",location.pathname);
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
 for(const record of rows) { const tr = document.createElement('tr'); cell(tr,record.host,new Date(record.start+'+08:00').toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur',dateStyle:'medium',timeStyle:'short'})+(record.cohost_name?' · With '+record.cohost_name:'')); cell(tr,money(record.gmv_cents/100)); cell(tr,number(record.views)); cell(tr,duration(record).toFixed(2)+' hrs'); cell(tr,record.notes || '—'); if(currentUser?.can_view_all && record.user_id === null) { const select=document.createElement('select'); const option=document.createElement('option'); option.textContent='Assign legacy record…';option.value='';select.append(option);for(const host of hosts){const op=document.createElement('option');op.value=host.id;op.textContent=host.name;select.append(op);}select.addEventListener('change',async()=>{if(!select.value)return;try{await api('/api/assign',{id:record.id,user_id:Number(select.value)});await load();}catch(e){$('form-status').textContent=e.message;}});tr.lastChild.append(select); } const actions=document.createElement('td');if(record.user_id===currentUser?.id){const edit=document.createElement('button');edit.type='button';edit.className='button';edit.textContent='Edit';edit.addEventListener('click',()=>{editingId=record.id;const form=$('session-form');for(const field of ['start','end','views','notes'])form.elements[field].value=record[field];form.elements.cohost_id.value=record.cohost_id||'';form.elements.gmv.value=(record.gmv_cents/100).toFixed(2);$('entry-title').textContent='Edit live session';$('save').textContent='Save changes';$('cancel-edit').hidden=false;$('form-status').textContent='Editing your session.';$('entry').scrollIntoView({behavior:'smooth'});});actions.append(edit);}tr.append(actions);$('records').append(tr); }
 $('results').textContent = rows.length+' sessions'; $('empty').hidden = rows.length > 0;
 $('empty').textContent = sessions.length ? 'No hosts match your search.' : 'No sessions yet. Record your first live above.';
 $('export').disabled = rows.length === 0;
 drawChart();
}
async function api(path, data) {
 const response=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const result=await response.json(); if(!response.ok){const error=new Error(result.error || 'Request failed');error.status=response.status;throw error;}return result;
}
function clearPrivateData(){cohosts=[];$('cohost').replaceChildren(new Option('Solo live · no co-host',''));$('my-rank-card').hidden=true;$('my-rank').textContent='—';cancelEdit();$('email-settings').hidden=true;$('email-form').reset();$('email-dialog').close();$('change-password').hidden=true;$('password-form').reset();$('password-dialog').close();sessions=[];hosts=[];currentUser=null;$('host-name').value='';$('host-credentials').textContent='';$('host-credentials').hidden=true;$('admin-panel').hidden=true;$('host-filter').hidden=true;$('access').textContent='Sign in';render();}
async function load() {
 try {
 currentUser=await api('/api/me');
 $('access').textContent=currentUser.name+' · Sign out';$('change-password').hidden=false;$('email-settings').hidden=false;
 $('host-name').value=currentUser.name;
 cohosts=await api('/api/cohosts');$('cohost').replaceChildren(new Option('Solo live · no co-host',''));for(const host of cohosts)$('cohost').add(new Option(host.name,String(host.id)));
 document.querySelector('h1').textContent=currentUser.can_view_all?'Team performance':'My performance';
 $('admin-panel').hidden=!currentUser.is_admin;
 hosts=currentUser.is_admin?await api('/api/users'):[];
 $('host-filter').replaceChildren(new Option('All hosts',''));
 for(const host of hosts) $('host-filter').add(new Option(host.name,String(host.id)));
 $('host-filter').hidden=!currentUser.can_view_all;
 sessions=await api('/api/sessions'); render();await loadRank();
 }catch(error){clearPrivateData();$('empty').textContent=error.message;if(error.status===401 && !resetToken && !verifyToken && !$('login').open)$('login').showModal();}
}
$('session-form').addEventListener('submit',async event=>{
 event.preventDefault(); const form=event.target; const data=Object.fromEntries(new FormData(form));
 if(data.end<=data.start) { $('form-status').textContent='End time must be after start time.'; return; }
 $('save').disabled=true; $('form-status').textContent='Saving session…';
 try { const result=await api(editingId?'/api/edit-session':'/api/sessions',editingId?{...data,id:editingId}:data);sessions=sessions.filter(r=>r.id!==result.id); sessions.push(result); sessions.sort((a,b)=>b.start.localeCompare(a.start)||b.id-a.id); render(); form.reset(); $('host-name').value=currentUser.name; cancelEdit();$('form-status').textContent='Session saved successfully.';await loadRank(); }
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
 const rows=[['Host','Co-host','Start (Malaysia)','End (Malaysia)','GMV (MYR)','Views','Hours','Notes'],...filtered().map(r=>[r.host,r.cohost_name||'',r.start,r.end,(r.gmv_cents/100).toFixed(2),r.views,duration(r).toFixed(2),r.notes])];
 const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(r=>r.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'})); const a=document.createElement('a'); a.href=url;a.download='live-sessions.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});

function drawChart(){
 const days=Number($('period').value),metric=$('metric').value;
 const today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kuala_Lumpur'});
 const anchor=new Date(today+'T12:00:00+08:00');
 const dates=Array.from({length:days},(_,i)=>{const d=new Date(anchor);d.setUTCDate(d.getUTCDate()-(days-1-i));return d.toLocaleDateString('en-CA',{timeZone:'Asia/Kuala_Lumpur'});});
 const colours=['#008060','#2c6ecb','#9c4ac4','#c05717','#bf3b65','#527b18','#007f91','#72523c'];
 const multi=Boolean(currentUser?.can_view_all),series=new Map();
 function add(key,name,colour){if(!series.has(key))series.set(key,{name,colour,points:dates.map(date=>({date,value:0}))});return series.get(key);}
 if(multi){for(const [i,host] of hosts.entries()){if(!$('host-filter').value||String(host.id)===$('host-filter').value)add('user:'+host.id,host.name,colours[i%colours.length]);}}
 for(const row of selectedSessions()){
  const key=multi?(row.user_id===null?'legacy:'+row.host:'user:'+row.user_id):'self';
  const line=add(key,multi?(row.host+(row.user_id===null?' (unassigned)':'')):'My performance',colours[series.size%colours.length]);
  const point=line.points.find(p=>p.date===row.start.slice(0,10));if(point)point.value+=metric==='gmv'?row.gmv_cents/100:row.views;
 }
 if(!multi&&!series.size)add('self','My performance',colours[0]);
 const lines=[...series.values()],total=lines.reduce((sum,line)=>sum+line.points.reduce((s,p)=>s+p.value,0),0);
 const max=Math.max(1,...lines.flatMap(line=>line.points.map(p=>p.value)));
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 1000 250');svg.setAttribute('aria-hidden','true');
 function element(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;svg.append(e);return e;}
 const x=i=>75+i/(days-1)*900,y=value=>205-value/max*170;
 for(let i=0;i<=4;i++){const value=max*i/4,pos=y(value);element('line',{x1:75,y1:pos,x2:975,y2:pos,stroke:'#e8ece8'});element('text',{x:65,y:pos+4,'text-anchor':'end',fill:'#777','font-size':11},number(Math.round(value*100)/100));}
 lines.forEach((line,index)=>{
  const path=line.points.map((p,i)=>(i?'L':'M')+x(i)+','+y(p.value)).join(' ');
  if(!multi)element('path',{d:path+' L975,205 L75,205 Z',fill:'#edf5ef'});
  const attrs={d:path,fill:'none',stroke:line.colour,'stroke-width':3,'stroke-linejoin':'round'};
  if(index>=colours.length)attrs['stroke-dasharray']=index%2?'7 4':'3 3';
  element('path',attrs);
  line.points.forEach((p,i)=>{const c=element('circle',{cx:x(i),cy:y(p.value),r:3.5,fill:line.colour});const title=document.createElementNS(ns,'title');title.textContent=line.name+' · '+p.date+': '+(metric==='gmv'?money(p.value):number(p.value)+' views');c.append(title);});
 });
 dates.forEach((date,i)=>{if(i===0||i===days-1||i%Math.ceil(days/5)===0)element('text',{x:x(i),y:233,'text-anchor':'middle',fill:'#777','font-size':11},date.slice(5));});
 $('chart').replaceChildren(svg);$('chart').setAttribute('aria-label',lines.map(line=>line.name+': '+line.points.map(p=>p.date+' '+p.value).join(', ')).join('; ')||'No host data');
 $('chart-legend').replaceChildren();$('chart-legend').hidden=!multi;
 for(const line of multi?lines:[]){const li=document.createElement('li'),swatch=document.createElementNS(ns,'svg');swatch.setAttribute('viewBox','0 0 24 10');swatch.setAttribute('aria-hidden','true');const mark=document.createElementNS(ns,'line');mark.setAttribute('x1','0');mark.setAttribute('x2','24');mark.setAttribute('y1','5');mark.setAttribute('y2','5');mark.setAttribute('stroke',line.colour);mark.setAttribute('stroke-width','3');const idx=lines.indexOf(line);if(idx>=colours.length)mark.setAttribute('stroke-dasharray',idx%2?'7 4':'3 3');swatch.append(mark);li.append(swatch,document.createTextNode(line.name));$('chart-legend').append(li);}
 $('chart-summary').textContent=(metric==='gmv'?money(total):number(total)+' views')+' across the last '+days+' days.'+(multi?' Each line shows one host’s personal results.':'')+' Hover a point for its daily total.';
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
async function loadRank(){
 $('my-rank-card').hidden=!currentUser||Boolean(currentUser.is_admin);
 if(!currentUser||currentUser.is_admin)return;
 try{const result=await api('/api/my-rank');$('my-rank').textContent=result.rank===null?'Not ranked yet':'#'+number(result.rank);$('rank-caption').textContent=result.rank===null?'Record your first live session to receive your rank.':'Based on all-time recorded GMV. Equal totals share a rank.';}
 catch(error){$('my-rank').textContent='Unavailable';$('rank-caption').textContent='Your rank could not load. Refresh to try again.';}
}
function cancelEdit(){editingId=null;$('session-form').reset();$('host-name').value=currentUser?.name||'';$('entry-title').textContent='Record a live session';$('save').textContent='Save session';$('cancel-edit').hidden=true;}
$('cancel-edit').addEventListener('click',cancelEdit);
$('forgot-password').addEventListener('click',()=>{$('forgot-status').textContent='';$('forgot-dialog').showModal();});
$('close-forgot').addEventListener('click',()=>{$('forgot-dialog').close();$('forgot-form').reset();});
$('forgot-form').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('.primary');b.disabled=true;try{const result=await api('/api/forgot-password',Object.fromEntries(new FormData(e.target)));$('forgot-status').textContent=result.message;}catch(error){$('forgot-status').textContent=error.message;}finally{b.disabled=false;}});
$('email-settings').addEventListener('click',()=>{$('email-form').reset();$('email-status').textContent='';$('email-current').textContent=currentUser.email?'Verified email: '+currentUser.email:'No verified recovery email yet.';$('email-dialog').showModal();});
$('close-email').addEventListener('click',()=>{$('email-form').reset();$('email-dialog').close();});
$('email-dialog').addEventListener('cancel',()=>{$('email-form').reset();});
$('email-form').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('.primary');b.disabled=true;try{await api('/api/recovery-email',Object.fromEntries(new FormData(e.target)));e.target.reset();$('email-status').textContent='Verification link sent. Check your inbox.';}catch(error){$('email-status').textContent=error.message;}finally{b.disabled=false;}});
$('reset-form').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{await api('/api/reset-password',{...Object.fromEntries(new FormData(e.target)),token:resetToken});e.target.reset();$('reset-dialog').close();clearPrivateData();$('login-status').textContent='Password reset. Sign in with your new password.';if(!$('login').open)$('login').showModal();}catch(error){$('reset-status').textContent=error.message;}finally{b.disabled=false;}});
$('verify-form').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{await api('/api/verify-email',{token:verifyToken});$('verify-status').textContent='Email verified. You can now use Forgot password.';b.hidden=true;}catch(error){$('verify-status').textContent=error.message;b.disabled=false;}});
if(resetToken)$('reset-dialog').showModal();
if(verifyToken)$('verify-dialog').showModal();
load();
