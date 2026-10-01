from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import json, re, time
from urllib.parse import urlparse
import httpx

app = FastAPI(title='AgentMatch API', version='0.2')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

with open('people.json', encoding='utf-8') as f:
    people = json.load(f)

class ImportRequest(BaseModel):
    linkedin: HttpUrl
    instagram: HttpUrl

def normalize_url(value):
    u = str(value).strip()
    if not u.startswith(('http://','https://')):
        raise HTTPException(400, 'URLs must start with http:// or https://')
    return u.rstrip('/') + '/'

def platform(url):
    host=urlparse(url).netloc.lower().replace('www.','')
    if host.endswith('linkedin.com'): return 'linkedin'
    if host.endswith('instagram.com'): return 'instagram'
    return None

def seeded_match(li, ig):
    for p in people:
        if normalize_url(p.get('linkedin','')) == li and normalize_url(p.get('instagram','')) == ig:
            return p
    return None


@app.get('/api/health')
def health(): return {'status':'ok'}

@app.get('/api/people')
def get_people(): return people

@app.get('/api/people/{person_id}')
def get_person(person_id: int):
    p = next((x for x in people if x['id'] == person_id), None)
    if not p: raise HTTPException(404, 'Person not found')
    return p

@app.post('/api/people/import')
def import_person(req: ImportRequest):
    li=normalize_url(req.linkedin); ig=normalize_url(req.instagram)
    if platform(li) != 'linkedin': raise HTTPException(400,'LinkedIn URL required.')
    if platform(ig) != 'instagram': raise HTTPException(400,'Instagram URL required.')
    existing=seeded_match(li,ig)
    if existing:
        return existing
    new_id = max([p['id'] for p in people] or [0]) + 1
    p = {
        'id': new_id, 'name': 'Imported profile', 'location': '',
        'linkedin': li, 'instagram': ig,
        'headline': 'Source links supplied — analysis pending',
        'interests': [], 'hobbies': [], 'needs': [],
        'source_analysis': {'linkedin': ['Official LinkedIn URL supplied.'], 'instagram': ['Public Instagram URL supplied.']},
        'source_status': {'linkedin':'url_validated','instagram':'url_validated'},
        'analysis_status': 'pending'
    }
    people.append(p)
    return p

@app.post('/api/analyze/{person_id}')
def analyze(person_id: int):
    p = next((x for x in people if x['id'] == person_id), None)
    if not p: raise HTTPException(404, 'Person not found')
    # For the bundled 25-person demo, the normalized public-source dataset is already present.
    # For newly pasted arbitrary LinkedIn URLs, we do not bypass LinkedIn access controls or scrape profiles.
    # LinkedIn explicitly prohibits unauthorized automated scraping of member profiles.
    if not p.get('interests') and not p.get('hobbies') and p.get('analysis_status') == 'pending':
        p['analysis_status']='source_access_required'
        p['source_analysis']={
          'linkedin':[
            'URL validated as LinkedIn.',
            'Live profile extraction requires an authorized LinkedIn integration or user-provided profile data.'
          ],
          'instagram':[
            'URL validated as Instagram.',
            'Only public information may be used; no login or access-control bypass is attempted.'
          ]
        }
        return {'status':'source_access_required','person':p}
    p['analysis_status'] = 'complete'
    return {'status':'complete', 'person':p}

def score(a,b):
    ai=set(a.get('interests',[])+a.get('hobbies',[])); bi=set(b.get('interests',[])+b.get('hobbies',[]))
    shared=sorted(ai & bi)
    score = min(97, 58 + len(shared)*8)
    if a.get('location') and a.get('location') == b.get('location'): score = min(97, score + 5)
    return score, shared

@app.post('/api/date/{a_id}/{b_id}')
def date(a_id:int,b_id:int):
    a=next((x for x in people if x['id']==a_id),None); b=next((x for x in people if x['id']==b_id),None)
    if not a or not b: raise HTTPException(404, 'Agent not found')
    s,shared=score(a,b)
    topic=shared[0] if shared else 'work and interests'
    ah=(a.get('hobbies') or ['projects'])[0]; bh=(b.get('hobbies') or ['personal interests'])[0]
    conversation=[
      {'speaker':a['name'],'message':f"I noticed a shared signal around {topic}. What do you enjoy most about it?"},
      {'speaker':b['name'],'message':f"I like learning through it and trying new things. Your profile also mentions {a.get('headline','your work')}."},
      {'speaker':a['name'],'message':f"That sounds like a good overlap. I also spend time on {ah}. What do you enjoy outside work?"},
      {'speaker':b['name'],'message':f"I enjoy {bh}. There seems to be a nice mix of shared interests and different perspectives here."},
      {'speaker':a['name'],'message':'I think we have enough common ground for another conversation.'}
    ]
    return {'a':a,'b':b,'score':s,'shared_interests':shared,'conversation':conversation,'reason':f"The agents found overlap in {', '.join(shared) if shared else 'general interests'}, with additional complementary signals."}


@app.get('/api/date-options/{person_id}')
def date_options(person_id:int):
    a=next((x for x in people if x['id']==person_id),None)
    if not a: raise HTTPException(404, 'Agent not found')
    options=[]
    for b in people:
        if b['id']==person_id: continue
        s,shared=score(a,b)
        options.append({'person':b,'preview_score':s,'shared_interests':shared})
    options.sort(key=lambda x:(-x['preview_score'],x['person']['name']))
    return {'person':a,'options':options}

@app.post('/api/dates/demo')
def demo_dates(limit:int=12):
    pairs=[]
    seen=set()
    ordered=sorted(people,key=lambda x:x['id'])
    for a in ordered:
        candidates=[]
        for b in ordered:
            if a['id']==b['id']: continue
            key=tuple(sorted((a['id'],b['id'])))
            if key in seen: continue
            s,shared=score(a,b)
            candidates.append((s,b,shared,key))
        candidates.sort(key=lambda x:-x[0])
        if candidates:
            s,b,shared,key=candidates[0]
            seen.add(key)
            pairs.append(date(a['id'],b['id']))
            if len(pairs)>=limit: break
    return {'count':len(pairs),'dates':pairs}

@app.post('/api/rankings/all')
def all_rankings():
    # Deterministic full-pool ranking: every agent receives a personalized
    # ordering of every other eligible demo agent.
    result=[]
    for a in people:
        rows=[]
        for b in people:
            if b['id']==a['id']: continue
            s,shared=score(a,b)
            rows.append({'person':b,'score':s,'shared_interests':shared,
                         'reason':f"Shared signals: {', '.join(shared) if shared else 'limited direct overlap'}"})
        rows.sort(key=lambda x:(-x['score'],x['person']['name']))
        for i,r in enumerate(rows,1): r['rank']=i
        result.append({'person':a,'rankings':rows})
    return {'people_count':len(people),'ranking_count':len(result),'results':result}

@app.get('/api/rankings/{person_id}')
def rankings(person_id:int):
    a=next((x for x in people if x['id']==person_id),None)
    if not a: raise HTTPException(404, 'Person not found')
    rows=[]
    for b in people:
      if b['id']==person_id: continue
      s,shared=score(a,b)
      rows.append({'person':b,'score':s,'shared_interests':shared,'reason':f"Shared signals: {', '.join(shared) if shared else 'limited direct overlap'}"})
    rows.sort(key=lambda x:(-x['score'], x['person']['name']))
    for i,r in enumerate(rows,1): r['rank']=i
    return {'person':a,'rankings':rows}
