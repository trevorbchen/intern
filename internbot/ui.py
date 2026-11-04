"""Generate out/dashboard.html (self-contained) and out/deadlines.ics from the database."""
import json, os
from datetime import date, datetime
from .filters import PROGRAM_RX

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Internbot</title>
<style>
:root{--bg:#fafaf7;--card:#fff;--ink:#1c1b19;--mut:#6b6860;--line:#e6e3db;--acc:#2f5d50;--hot:#b4432b;--ok:#2f7d4f}
@media(prefers-color-scheme:dark){:root{--bg:#161614;--card:#201f1d;--ink:#ece9e1;--mut:#9a968b;--line:#34322e;--acc:#7fc2ad;--hot:#e8866d;--ok:#6cc08b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
header{padding:20px 16px 0;max-width:980px;margin:auto}h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--mut);font-size:13px}nav{display:flex;gap:4px;flex-wrap:wrap;margin:16px 0 0;border-bottom:1px solid var(--line)}
nav button{background:none;border:0;padding:9px 12px;color:var(--mut);font:inherit;cursor:pointer;border-bottom:2px solid transparent}
nav button.on{color:var(--ink);border-color:var(--acc)}main{max-width:980px;margin:auto;padding:16px}
input[type=search]{width:100%;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);margin-bottom:12px;font:inherit}
.row{display:flex;gap:12px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:8px}
.row.done{opacity:.5}.row h3{margin:0;font-size:15px}.row p{margin:2px 0 0;color:var(--mut);font-size:13px}
.grow{flex:1;min-width:0}a{color:var(--acc)}.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:99px;border:1px solid var(--line);color:var(--mut);margin-right:4px}
.tag.open{color:var(--ok);border-color:var(--ok)}.tag.hot{color:var(--hot);border-color:var(--hot)}
button.act{border:1px solid var(--line);background:none;color:var(--ink);border-radius:6px;padding:4px 9px;font:inherit;font-size:12px;cursor:pointer}
.empty{color:var(--mut);padding:24px 0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:20px 0 8px}
pre{white-space:pre-wrap;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px;font:13px/1.45 inherit;margin:8px 0 0}
@media(max-width:560px){.row{flex-direction:column}}
</style></head><body>
<header><h1>Internbot</h1><div class="sub" id="gen"></div>
<nav id="nav"></nav></header><main id="main"></main>
<script>
const D=__DATA__;
const TABS=[["hand","Apply by hand"],["open","Openings"],["apps","Applications"],["res","Researchers"],["cal","Calendar"]];
let tab=(location.hash||"#hand").slice(1),q="";
const S=(()=>{try{return JSON.parse(localStorage.getItem("ib")||"{}")}catch(e){return{}}})();
const save=()=>{try{localStorage.setItem("ib",JSON.stringify(S))}catch(e){}};
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const dl=d=>d?Math.ceil((new Date(d)-new Date())/864e5):null;
function chip(d){const n=dl(d);if(n===null)return"";return `<span class="tag ${n<=14?"hot":""}">${n<0?"passed":n+" days left"} · ${d}</span>`}
function row(key,title,sub,link,tags=""){const done=S[key];
 return `<div class="row ${done?"done":""}"><input type="checkbox" ${done?"checked":""} onchange="tog('${esc(key)}')" title="mark done"><div class="grow"><h3><a href="${esc(link)}" target="_blank" rel="noopener">${esc(title)}</a></h3><p>${tags}${sub}</p></div></div>`}
function tog(k){S[k]=!S[k];save();render()}
function match(...a){return !q||a.join(" ").toLowerCase().includes(q)}
const views={
 hand(){const items=[...D.programs.map(p=>({k:p.url,t:p.name,s:esc(p.note||""),l:p.url,tags:`<span class="tag ${p.status=="open"?"open":""}">${esc(p.status)}</span>${p.changed?'<span class="tag hot">page changed</span>':""}${chip(p.deadline)}`})),
   ...D.postings.filter(x=>x.program).map(x=>({k:x.url,t:x.title+" — "+x.company,s:esc(x.location||""),l:x.url,tags:`<span class="tag hot">program</span>`}))].filter(i=>match(i.t,i.s));
  return `<h2>Fellowships, residencies &amp; programs — apply to these yourself</h2>`+(items.map(i=>row(i.k,i.t,i.s,i.l,i.tags)).join("")||'<div class="empty">Nothing yet.</div>')},
 open(){const xs=D.postings.filter(x=>!x.program&&match(x.title,x.company,x.location));
  return `<h2>${xs.length} openings seen</h2>`+(xs.map(x=>row(x.url,x.title+" — "+x.company,esc(x.location||""),x.url,`<span class="tag">${esc(x.source)}</span><span class="tag">${esc((x.first_seen||"").slice(0,10))}</span>`)).join("")||'<div class="empty">No openings yet. Run the bot.</div>')},
 apps(){const xs=D.applications.filter(a=>match(a.company,a.title,a.status));
  return `<h2>${xs.length} applications</h2>`+(xs.map(a=>row("app:"+a.url,a.title+" — "+a.company,esc(a.note||""),a.url,`<span class="tag ${a.status=="submitted"?"open":""}">${esc(a.status)}</span><span class="tag">${esc((a.applied_at||"").slice(0,10))}</span>`)).join("")||'<div class="empty">None yet.</div>')},
 res(){const xs=D.researchers.filter(r=>match(r.name,r.company,r.papers.map(p=>p.title).join(" ")));
  return `<h2>Researchers whose work overlaps yours</h2>`+(xs.map(r=>`<div class="row ${S["r:"+r.id]?"done":""}"><input type="checkbox" ${S["r:"+r.id]?"checked":""} onchange="tog('r:${r.id}')" title="contacted"><div class="grow"><h3><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a> · ${esc(r.company)}</h3><p>${r.papers.map(p=>`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a> (${p.year})`).join("<br>")}</p>${r.draft?`<details><summary>Draft email</summary><pre>${esc(r.draft)}</pre></details>`:""}</div></div>`).join("")||'<div class="empty">None yet — run <code>python -m internbot.cli --researchers</code> (needs OPENALEX_API_KEY).</div>')},
 cal(){const ev=D.programs.filter(p=>p.deadline).sort((a,b)=>a.deadline.localeCompare(b.deadline));
  let m="",h="";for(const e of ev){const k=e.deadline.slice(0,7);if(k!==m){m=k;h+=`<h2>${new Date(k+"-15").toLocaleString("default",{month:"long",year:"numeric"})}</h2>`}h+=row("cal:"+e.name,e.name,"",e.url,chip(e.deadline))}
  return (h||'<div class="empty">No deadlines known yet. Add <code>deadline: YYYY-MM-DD</code> in programs.yaml.</div>')+`<p class="sub"><a href="deadlines.ics">Download .ics</a> (import into Google/Apple Calendar)</p>`}
};
function render(){document.getElementById("nav").innerHTML=TABS.map(([k,l])=>`<button class="${k==tab?"on":""}" onclick="go('${k}')">${l}</button>`).join("");
 document.getElementById("main").innerHTML=`<input type="search" placeholder="Filter…" value="${esc(q)}" oninput="q=this.value.toLowerCase();render2()"><div id="v">${views[tab]()}</div>`}
function render2(){document.getElementById("v").innerHTML=views[tab]()}
function go(k){tab=k;location.hash=k;render()}
document.getElementById("gen").textContent="Generated "+D.generated;render();
</script></body></html>"""


def build(db, out_dir="out"):
    import yaml
    os.makedirs(out_dir, exist_ok=True)
    notes = {p["name"]: p.get("note", "") for p in (yaml.safe_load(open("programs.yaml")) if os.path.exists("programs.yaml") else [])}
    programs = [dict(name=n, url=u, status=s, deadline=d, changed=bool(c), checked=lc, note=notes.get(n, ""))
                for n, u, s, d, c, lc in db.program_rows()]
    postings = [dict(first_seen=f, source=s, company=c, title=t, location=l, url=u, program=bool(PROGRAM_RX.search(t)))
                for f, s, c, t, l, u in db.all_postings()]
    apps = [dict(applied_at=a, status=s, company=c, title=t, url=u, note=n) for a, s, c, t, u, n in db.applications()]
    res = [dict(id=i, name=n, company=c, score=sc, papers=json.loads(p), url=u, draft=d, contacted=bool(ct))
           for i, n, c, sc, p, u, d, ct in db.researchers()]
    data = dict(programs=programs, postings=postings, applications=apps, researchers=res,
                generated=datetime.now().strftime("%Y-%m-%d %H:%M"))
    blob = json.dumps(data).replace("</", "<\\/")
    path = os.path.join(out_dir, "dashboard.html")
    open(path, "w").write(TEMPLATE.replace("__DATA__", blob))
    write_ics(programs, os.path.join(out_dir, "deadlines.ics"))
    return path


def write_ics(programs, path):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//internbot//EN"]
    for p in programs:
        if not p.get("deadline"):
            continue
        d = p["deadline"].replace("-", "")
        lines += ["BEGIN:VEVENT", f"UID:{abs(hash(p['name']))}@internbot", f"DTSTAMP:{date.today():%Y%m%d}T000000Z",
                  f"DTSTART;VALUE=DATE:{d}", f"SUMMARY:Deadline: {p['name']}", f"URL:{p['url']}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    open(path, "w").write("\r\n".join(lines) + "\r\n")
