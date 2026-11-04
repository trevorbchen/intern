"""Probe extra ATS systems (Workable, SmartRecruiters, Recruitee) for companies with no Greenhouse/Lever/Ashby board."""
import requests, concurrent.futures as cf, sys, yaml
miss={"Mistral AI":["mistralai","mistral-ai","mistral"],"Safe Superintelligence":["ssi","safe-superintelligence"],"Skild AI":["skild","skild-ai"],
"Weights & Biases":["wandb","weights-biases"],"Hugging Face":["huggingface","hugging-face"],"Sakana AI":["sakana","sakana-ai"],"Luma AI":["lumalabs","luma-ai","luma"],
"General Intuition":["generalintuition","general-intuition"],"Applied Intuition":["appliedintuition","applied-intuition"],"Anduril":["anduril","andurilindustries"],"Groq":["groq","groq-inc"],
"Hippocratic AI":["hippocraticai","hippocratic-ai"],"EvolutionaryScale":["evolutionaryscale"],"Contextual AI":["contextualai","contextual-ai"],"Hebbia":["hebbia"],"Surge AI":["surgeai","surge-ai"],
"Adept":["adept"],"Covariant":["covariant"],"Canva":["canva"],"Revolut":["revolut"],"Cyera":["cyera"],"Clay":["clay","clayrun"]}
T=lambda s:[("greenhouse",f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs",lambda j:len(j.get("jobs",[]))),
 ("lever",f"https://api.lever.co/v0/postings/{s}?mode=json",lambda j:len(j) if isinstance(j,list) else 0),
 ("ashby",f"https://api.ashbyhq.com/posting-api/job-board/{s}",lambda j:len(j.get("jobs",[]))),
 ("workable",f"https://apply.workable.com/api/v1/widget/accounts/{s}",lambda j:len(j.get("jobs",[]))),
 ("smartrecruiters",f"https://api.smartrecruiters.com/v1/companies/{s}/postings",lambda j:j.get("totalFound",0)),
 ("recruitee",f"https://{s}.recruitee.com/api/offers/",lambda j:len(j.get("offers",[])))]
def probe(item):
    name,slugs=item
    for s in slugs:
        for ats,url,cnt in T(s):
            try:
                r=requests.get(url,timeout=8)
                if r.ok and cnt(r.json())>0: return name,ats,s,cnt(r.json())
            except Exception: pass
    return name,None,None,0
with cf.ThreadPoolExecutor(8) as ex: res=list(ex.map(probe,miss.items()))
for r in res: print(r[0].ljust(24),r[1:] if r[1] else "-")
if "--write" in sys.argv:
    d=yaml.safe_load(open("targets.yaml")); have={c["name"] for c in d["companies"]}
    for n,a,t,_ in res:
        if a and n not in have: d["companies"].append({"name":n,"ats":a,"token":t})
    d["no_public_board_found"]=[n for n,a,*_ in res if not a]
    yaml.safe_dump(d,open("targets.yaml","w"),sort_keys=False); print("targets.yaml updated")
