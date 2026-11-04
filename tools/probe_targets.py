"""Find which ATS (Greenhouse / Lever / Ashby) each target company uses and write targets.yaml."""
import concurrent.futures as cf, requests, yaml, re

CANDIDATES = {  # display name -> slug guesses
 "Anthropic": ["anthropic"], "OpenAI": ["openai"], "Cursor (Anysphere)": ["anysphere", "cursor"],
 "Perplexity": ["perplexity", "perplexityai"], "Scale AI": ["scaleai", "scale"], "Databricks": ["databricks"],
 "Cohere": ["cohere"], "Mistral AI": ["mistral", "mistralai"], "Runway": ["runway", "runwayml"],
 "ElevenLabs": ["elevenlabs"], "Harvey": ["harvey"], "Glean": ["glean", "gleanwork"], "Sierra": ["sierra", "sierraai"],
 "Decagon": ["decagon"], "Cognition": ["cognition", "cognitionai"], "Thinking Machines Lab": ["thinkingmachines", "thinking-machines"],
 "Safe Superintelligence": ["ssi", "safesuperintelligence"], "Reflection AI": ["reflectionai", "reflection"],
 "Periodic Labs": ["periodiclabs", "periodic-labs"], "Physical Intelligence": ["physicalintelligence", "pi", "physical-intelligence"],
 "Figure AI": ["figure", "figureai"], "Skild AI": ["skild", "skildai"], "1X": ["1x", "1xtechnologies"],
 "World Labs": ["worldlabs", "world-labs"], "Black Forest Labs": ["blackforestlabs", "black-forest-labs"],
 "Midjourney": ["midjourney"], "Suno": ["suno"], "Together AI": ["togetherai", "together"], "Fireworks AI": ["fireworksai", "fireworks"],
 "Baseten": ["baseten"], "Modal": ["modal"], "Anyscale": ["anyscale"], "Weights & Biases": ["wandb", "weightsandbiases"],
 "Hugging Face": ["huggingface", "hugging-face"], "Imbue": ["imbue"], "Sakana AI": ["sakana", "sakanaai"],
 "Magic": ["magic", "magicdev"], "Poolside": ["poolside"], "Luma AI": ["lumalabs", "luma-ai", "luma"],
 "Pika": ["pika"], "xAI": ["xai"], "General Intuition": ["generalintuition", "general-intuition"],
 "Applied Intuition": ["appliedintuition"], "Anduril": ["anduril"], "Shield AI": ["shieldai", "shield-ai"],
 "Saronic": ["saronic"], "Cerebras": ["cerebrassystems", "cerebras"], "Groq": ["groq"], "Etched": ["etched"],
 "Ramp": ["ramp"], "Notion": ["notion"], "Vercel": ["vercel"], "Replit": ["replit"], "Lovable": ["lovable"],
 "Abridge": ["abridge"], "OpenEvidence": ["openevidence"], "Hippocratic AI": ["hippocraticai", "hippocratic-ai"],
 "Chai Discovery": ["chaidiscovery", "chai-discovery"], "Xaira": ["xaira", "xairatherapeutics"], "EvolutionaryScale": ["evolutionaryscale"],
 "Profluent": ["profluent"], "Liquid AI": ["liquid", "liquidai"], "Contextual AI": ["contextualai", "contextual-ai"],
 "Writer": ["writer"], "Hebbia": ["hebbia"], "Mercor": ["mercor"], "Surge AI": ["surgeai", "surge"],
 "Hume AI": ["hume", "humeai"], "Cartesia": ["cartesia"], "Deepgram": ["deepgram"], "Pinecone": ["pinecone"],
 "Sesame": ["sesame"], "Genmo": ["genmo"], "Ideogram": ["ideogram"], "Character.AI": ["characterai", "character"],
 "Adept": ["adept"], "Inflection": ["inflection", "inflectionai"], "Reka": ["reka", "rekaai"], "Essential AI": ["essentialai", "essential"],
 "Lila Sciences": ["lilasciences", "lila-sciences"], "Isomorphic Labs": ["isomorphiclabs"], "Waymo": ["waymo"],
 "Nuro": ["nuro"], "Covariant": ["covariant"], "Kalshi": ["kalshi"], "Polymarket": ["polymarket"], "Canva": ["canva"],
 "Revolut": ["revolut"], "Cyera": ["cyera"], "Vanta": ["vanta"], "Metropolis": ["metropolis"], "Apptronik": ["apptronik"],
 "Island": ["island"], "Gamma": ["gamma"], "EliseAI": ["eliseai"], "Rogo": ["rogo"], "Clay": ["clay", "clayrun"],
}

def probe(item):
    name, slugs = item
    for s in slugs:
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs", timeout=10)
            if r.ok and r.json().get("jobs"): return name, "greenhouse", s, len(r.json()["jobs"])
            r = requests.get(f"https://api.lever.co/v0/postings/{s}?mode=json", timeout=10)
            if r.ok and isinstance(r.json(), list) and r.json(): return name, "lever", s, len(r.json())
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{s}", timeout=10)
            if r.ok and r.json().get("jobs"): return name, "ashby", s, len(r.json()["jobs"])
        except Exception:
            pass
    return name, None, None, 0

with cf.ThreadPoolExecutor(10) as ex:
    res = list(ex.map(probe, CANDIDATES.items()))
found = [r for r in res if r[1]]
out = {"companies": [{"name": n, "ats": a, "token": t} for n, a, t, _ in found],
       "no_public_board_found": [n for n, a, *_ in res if not a]}
yaml.safe_dump(out, open("targets.yaml", "w"), sort_keys=False)
print(len(found), "boards found of", len(res))
for n, a, t, c in found: print(f"  {n:24} {a:10} {t} ({c} jobs)")
print("not found:", ", ".join(out["no_public_board_found"]))
