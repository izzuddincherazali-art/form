let sessions = [];
let token = sessionStorage.getItem('live-token') || '';
const $ = id => document.getElementById(id);
const money = value => new Intl.NumberFormat('en-MY', {style:'currency',currency:'MYR'}).format(value);
const number = value => new Intl.NumberFormat('en-MY').format(value);
const duration = row => (new Date(row.end + '+08:00') - new Date(row.start + '+08:00')) / 3600000;
const filtered = () => sessions.filter(row => row.host.toLowerCase().includes($('search').value.toLowerCase()));
function cell(row, text, sub) { const td = document.createElement('td'); td.textContent = text; if(sub) { const small = document.createElement('small'); small.textContent = sub; td.append(small); } row.append(td); }
function render() {
 $('gmv').textContent = money(sessions.reduce((s,r)=>s+r.gmv_cents,0)/100);
 $('views').textContent = number(sessions.reduce((s,r)=>s+r.views,0));
 $('count').textContent = number(sessions.length);
 $('hours').textContent = sessions.reduce((s,r)=>s+duration(r),0).toFixed(1)+' hrs';
 const rows = filtered(); $('records').replaceChildren();
 for(const record of rows) { const tr = document.createElement('tr'); cell(tr,record.host,new Date(record.start+'+08:00').toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur',dateStyle:'medium',timeStyle:'short'})); cell(tr,money(record.gmv_cents/100)); cell(tr,number(record.views)); cell(tr,duration(record).toFixed(2)+' hrs'); cell(tr,record.notes || '—'); $('records').append(tr); }
 $('results').textContent = rows.length+' sessions'; $('empty').hidden = rows.length > 0;
 $('empty').textContent = sessions.length ? 'No hosts match your search.' : 'No sessions yet. Record your first live above.';
 $('export').disabled = rows.length === 0;
}
async function load() {
 try { const response = await fetch('/api/sessions',{headers:{Authorization:'Bearer '+token}}); if(!response.ok) throw new Error((await response.json()).error); sessions = await response.json(); render(); }
 catch(error) { $('empty').hidden=false; $('empty').textContent=error.message; $('export').disabled=true; $('login').showModal(); }
}
$('session-form').addEventListener('submit',async event=>{
 event.preventDefault(); const form=event.target; const data=Object.fromEntries(new FormData(form));
 if(data.end<=data.start) { $('form-status').textContent='End time must be after start time.'; return; }
 $('save').disabled=true; $('form-status').textContent='Saving session…';
 try { const response=await fetch('/api/sessions',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(data)}); const result=await response.json(); if(!response.ok) throw new Error(result.error); sessions.push(result); sessions.sort((a,b)=>b.start.localeCompare(a.start)||b.id-a.id); render(); form.reset(); $('form-status').textContent='Session saved successfully.'; }
 catch(error) { $('form-status').textContent=error.message; }
 finally { $('save').disabled=false; }
});
$('search').addEventListener('input',render);
$('access').addEventListener('click',()=>$('login').showModal());
$('login').addEventListener('close',()=>{if($('login').returnValue==='connect'){token=$('password').value;sessionStorage.setItem('live-token',token);$('password').value='';load();}});
$('export').addEventListener('click',()=>{
 const safe = value => { let text=String(value); if(/^[=+@\-\t\r]/.test(text)) text="'"+text; return '"'+text.replaceAll('"','""')+'"'; };
 const rows=[['Host','Start (Malaysia)','End (Malaysia)','GMV (MYR)','Views','Hours','Notes'],...filtered().map(r=>[r.host,r.start,r.end,(r.gmv_cents/100).toFixed(2),r.views,duration(r).toFixed(2),r.notes])];
 const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(r=>r.map(safe).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'})); const a=document.createElement('a'); a.href=url;a.download='live-sessions.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
load();
