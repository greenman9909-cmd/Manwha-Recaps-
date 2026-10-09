(function(){
"use strict";
var KEY=new URLSearchParams(location.search).get("key")||"";
var auth=function(path){return path+(path.includes("?")?"&":"?")+"key="+encodeURIComponent(KEY)};
var state={data:null,room:"group",view:"chat",signature:"",timer:0};
var find=function(id){return document.getElementById(id)};
var person=function(id){return (state.data&&state.data.departments||[]).find(function(p){return p.id===id})};
var avatar=function(id){return auth("/avatars/"+id+".svg")};
var node=function(tag,cl,txt){var e=document.createElement(tag);if(cl)e.className=cl;if(txt!==undefined)e.textContent=txt;return e};
function showToast(txt){var e=find("toast");e.textContent=txt;e.classList.add("visible");clearTimeout(state.timer);state.timer=setTimeout(function(){e.classList.remove("visible")},3400)}
function call(path,opts){return fetch(auth(path),Object.assign({cache:"no-store",headers:{"Content-Type":"application/json"}},opts||{})).then(async function(r){var d=await r.json();if(!r.ok)throw Error(d.error||("HTTP "+r.status));return d})}
function showSidebar(open){find("sidebar").classList.toggle("mobile-open",open);find("mobile-overlay").classList.toggle("visible",open)}
function chooseRoom(id){
 state.room=id;state.view="chat";
 document.querySelectorAll(".screen").forEach(function(s){s.classList.toggle("active",s.id==="chat-screen")});
 document.querySelectorAll(".room-button").forEach(function(b){b.classList.toggle("selected",b.dataset.room===id)});
 document.querySelectorAll(".menu-link").forEach(function(b){b.classList.remove("active")});
 var p=person(id);find("channel-title").textContent=id==="group"?"Studio Group":p.name+" · "+p.title.split(" · ")[0];
 find("channel-subtitle").textContent=id==="group"?"10 studio profiles · GPT-6 direction + local AI conversations":p.motto+(p.kind==="gpt6"?" · Replies when connected ChatGPT checks inbox":" · Local Ollama persona + verified checks");
 var av=find("channel-avatar");av.replaceChildren();
 if(id==="group")av.textContent="✦";else{var image=node("img");image.src=avatar(id);image.alt=p.name;av.append(image)}
 find("current-location").textContent=id==="group"?"Studio Group":p.name;
 find("message-input").placeholder=id==="group"?"Message the studio team…":"Message "+p.name+"…";
 find("composer-context").textContent=(id==="ceo"||id==="operator")?"✦ GPT-6 messages enter a review inbox. They'll be answered during a connected ChatGPT session.":id==="group"?"✦ Qwen local crew replies independently. GPT-6 directs and acts when connected; all claims need evidence.":"✦ Local Qwen persona replies here and may request predefined checks. Creative decisions belong to GPT-6.";
 renderMessages(true);showSidebar(false)
}
function view(id){
 state.view=id;
 document.querySelectorAll(".screen").forEach(function(s){s.classList.toggle("active",s.id===id+"-screen")});
 document.querySelectorAll(".menu-link").forEach(function(b){b.classList.toggle("active",b.dataset.view===id)});
 document.querySelectorAll(".room-button").forEach(function(b){b.classList.remove("selected")});
 find("current-location").textContent=({pipeline:"Production pipeline",crew:"Our team",activity:"Activity & evidence"})[id]||"Studio";
 renderExtra();showSidebar(false)
}
function sidebar(){
 if(!state.data)return;
 var list=find("room-list");list.replaceChildren();
 state.data.departments.forEach(function(p){
  var btn=node("button","room-button"),ico=node("span","room-avatar"),pic=node("img");
  btn.dataset.room=p.id;if(state.room===p.id&&state.view==="chat")btn.classList.add("selected");
  pic.alt="";pic.src=avatar(p.id);ico.append(pic);
  var copy=node("span","room-text");copy.append(node("strong",null,p.name),node("span",null,p.title));
  btn.append(ico,copy,node("span","room-glyph",p.kind==="gpt6"?"✦":"•"));btn.addEventListener("click",function(){chooseRoom(p.id)});list.append(btn)
 })
}
function renderMessages(force){
 if(!state.data)return;
 var data=state.data.messages.filter(function(m){return m.channel===state.room});
 var signature=state.room+"|"+data.map(function(m){return m.id}).join(",");
 if(!force&&signature===state.signature)return;
 state.signature=signature;
 var panel=find("messages-container"),bottom=panel.scrollTop+panel.clientHeight>=panel.scrollHeight-130;
 var root=find("messages");root.replaceChildren();
 if(!data.length)root.append(node("div","empty-placeholder","No messages in this room. Start the conversation."));
 data.forEach(function(m){
  var user=m.role==="you",p=person(m.role),row=node("article","message-row"+(user?" user":m.origin==="gpt6"?" gpt6":""));
  var pic=user?node("div","msg-avatar user-avatar","Y"):node("img","msg-avatar");
  if(!user){pic.src=avatar(m.role);pic.alt=p?p.name:"Worker"}
  var wrap=node("div","msg-column"),who=node("div","msg-author");
  who.append(node("span",null,user?"You":p?p.name:m.role));
  who.append(node("span","role-pill"+(m.origin==="gpt6"?" gpt6":m.origin==="local_ai"?" local-ai":user?" user":""),user?"OWNER":m.origin==="gpt6"?"GPT-6":m.origin==="local_ai"?"LOCAL AI":m.origin==="worker"?"VERIFIED WORKER":"SYSTEM"));
  wrap.append(who,node("div","msg-bubble",m.body));
  var meta=node("div","msg-footer"),date;
  try{date=new Date(m.ts).toLocaleString(undefined,{hour:"2-digit",minute:"2-digit"})}catch(e){date=m.ts}
  meta.append(node("time",null,date));
  if(m.evidence){var ev=node("button","msg-evidence","Copy evidence path");ev.title=m.evidence;ev.addEventListener("click",function(){navigator.clipboard.writeText(m.evidence).then(function(){showToast("Evidence path copied")}).catch(function(){showToast(m.evidence)})});meta.append(ev)}
  wrap.append(meta);row.append(pic,wrap);root.append(row)
 });
 if(force||bottom)requestAnimationFrame(function(){panel.scrollTop=panel.scrollHeight})
}
function pipeline(){
 var list=find("pipeline-grid");list.replaceChildren();var count=0;
 state.data.tasks.forEach(function(t,i){
  var card=node("article","pipeline-card"),top=node("div","stage-row");
  if(t.status==="ready")count++;
  top.append(node("span","stage-id",String(i+1).padStart(2,"0")+" / "+t.department.toUpperCase()),node("span","state-badge "+t.status,t.status.toUpperCase()));
  card.append(top,node("h3",null,t.title),node("p",null,t.note));list.append(card)
 });
 find("stage-count").textContent=count+" / "+state.data.tasks.length+" technically ready";
}
function crew(){
 var list=find("crew-grid");list.replaceChildren();
 state.data.departments.forEach(function(p){
  var card=node("article","crew-card"),top=node("div","crew-top"),image=node("img"),copy=node("div");
  image.src=avatar(p.id);image.alt=p.name+" avatar";
  copy.append(node("h3",null,p.name),node("span",null,p.title));top.append(image,copy);
  var go=node("button","crew-chat","Message "+p.name+" ↗");go.addEventListener("click",function(){chooseRoom(p.id)});
  card.append(top,node("p",null,p.tone),node("span","crew-quote","“"+p.motto+"”"),go);list.append(card)
 })
}
function activity(){
 var list=find("activity-list");list.replaceChildren();
 if(!state.data.jobs.length){list.append(node("div","empty-placeholder","No verification jobs have run yet."));return}
 state.data.jobs.forEach(function(job){
  var card=node("article","activity-card"),copy=node("div");
  copy.append(node("strong",null,job.action.replaceAll("-"," ")),node("small",null,"Started "+new Date(job.started).toLocaleString()+(job.ended?" · Finished "+new Date(job.ended).toLocaleTimeString():"")));
  card.append(node("span",null,job.status==="done"?"✓":job.status==="blocked"?"!":"◷"),copy,node("b",null,job.status.toUpperCase()));list.append(card)
 })
}
function renderExtra(){if(!state.data)return;if(state.view==="pipeline")pipeline();if(state.view==="crew")crew();if(state.view==="activity")activity()}
function renderStatus(){
 var ready=state.data.tasks.filter(function(t){return t.status==="ready"}).length;
 var pct=Math.round(100*ready/Math.max(1,state.data.tasks.length));
 find("readiness-value").textContent=pct+"%";find("readiness-bar").style.width=pct+"%";
 find("readiness-detail").textContent=ready+" / "+state.data.tasks.length+" technically ready · Creative & release QA pending";
 find("project-status").textContent=ready===state.data.tasks.length?"Review required":"In progress";
 find("project-status").classList.toggle("ready",ready===state.data.tasks.length);
 find("model-name").textContent=state.data.local_crew_online ? "LOCAL CREW ONLINE · QWEN" : "LOCAL CREW OFFLINE";
 find("model-label").classList.toggle("offline",!state.data.local_crew_online);
 find("google-status").textContent=state.data.google_tts_configured ?
  "Google AI Studio: locally configured. Kokoro remains MC by default." :
  "Google voice key not yet saved. Configure on this Windows laptop; no charges until generation.";
 var leaders=find("leadership");leaders.replaceChildren();
 ["ceo","operator","management"].forEach(function(id){var p=person(id),div=node("div","lead-item"),img=node("img"),name=node("div");img.src=avatar(id);img.alt="";name.append(node("strong",null,p.name),node("span",null,p.title));div.append(img,name);leaders.append(div)})
}
async function refresh(first){
 try{
  state.data=await call("/api/state");sidebar();renderStatus();renderMessages(!!first);renderExtra();
  find("unread-count").textContent=String(state.data.pending_gpt6||0);
  document.querySelectorAll("[data-action]").forEach(function(b){b.disabled=state.data.active.includes(b.dataset.action)})
 }catch(e){if(first)showToast("Cannot reach studio: "+e.message)}
}
async function action(id){
 try{await call("/api/run",{method:"POST",body:JSON.stringify({action:id})});showToast("Started: "+id.replaceAll("-"," "));setTimeout(function(){refresh(false)},450)}
 catch(e){showToast("Check unavailable: "+e.message)}
}
function resize(){var t=find("message-input");t.style.height="38px";t.style.height=Math.min(t.scrollHeight,130)+"px";find("message-length").textContent=t.value.length>=1600?t.value.length+"/2200":""}
async function send(ev){
 ev.preventDefault();var t=find("message-input"),msg=t.value.trim();if(!msg)return;
 find("send-message").disabled=true;
 try{await call("/api/send",{method:"POST",body:JSON.stringify({body:msg,target:state.room})});t.value="";resize();await refresh(false);find("messages-container").scrollTop=find("messages-container").scrollHeight;showToast("Message stored in the studio")}
 catch(e){showToast("Message failed: "+e.message)}
 finally{find("send-message").disabled=false;t.focus()}
}
find("composer-form").addEventListener("submit",send);
find("message-input").addEventListener("input",resize);
find("message-input").addEventListener("keydown",function(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();find("composer-form").requestSubmit()}});
find("refresh").addEventListener("click",function(){refresh(false);showToast("Studio refreshed")});
find("run-check").addEventListener("click",function(){action("readiness")});
find("copy-link").addEventListener("click",function(){navigator.clipboard.writeText(location.href).then(function(){showToast("Private link copied")}).catch(function(){showToast("Copy the URL from the browser")})});
find("open-sidebar").addEventListener("click",function(){showSidebar(true)});
find("close-sidebar").addEventListener("click",function(){showSidebar(false)});
find("mobile-overlay").addEventListener("click",function(){showSidebar(false)});
document.querySelector('[data-room="group"]').addEventListener("click",function(){chooseRoom("group")});
document.querySelectorAll("[data-view]").forEach(function(b){b.addEventListener("click",function(){view(b.dataset.view)})});
document.querySelectorAll("[data-action]").forEach(function(b){b.addEventListener("click",function(){action(b.dataset.action)})});
refresh(true).then(function(){if(state.data)chooseRoom("group")});
setInterval(function(){refresh(false)},3200);
})();