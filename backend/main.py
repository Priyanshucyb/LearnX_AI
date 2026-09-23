from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from datetime import date, datetime
from pathlib import Path
import os, json, re, urllib.request

load_dotenv()
app = FastAPI(title='LearnX AI Adaptive Learning API', version='2.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

DATA = Path(__file__).parent / 'learning_state.json'
DEFAULT = {
    'student': {'name':'Vedant', 'level':'Beginner', 'goal':'Build strong fundamentals'},
    'subjects': {
        'Mathematics': {
            'mastery': {'Probability':72, 'Conditional Probability':42, 'Bayes Theorem':58, 'Random Variables':74},
            'trend':[52,58,61,66,69,72]
        },
        'Computer Science': {'mastery': {'Python':82, 'DSA':64, 'OOP':71}, 'trend':[55,59,63,68,73,82]}
    },
    'quiz_history': [],
    'study_minutes': 310,
    'streak': 7,
    'last_recommendation': 'Review Conditional Probability, then take a targeted 5-question quiz.'
}

def load_state():
    if not DATA.exists():
        DATA.write_text(json.dumps(DEFAULT, indent=2))
    try: return json.loads(DATA.read_text())
    except Exception: return DEFAULT.copy()

def save_state(state): DATA.write_text(json.dumps(state, indent=2))

state = load_state()

class ChatReq(BaseModel):
    message: str
    level: str = 'Beginner'
    subject: str = 'Mathematics'
    topic: str = 'Probability'

class QuizReq(BaseModel):
    topic: str
    difficulty: str = 'Medium'
    subject: str = 'Mathematics'
    count: int = Field(default=5, ge=3, le=10)

class ResultReq(BaseModel):
    subject: str
    topic: str
    score: int = Field(ge=0, le=100)
    total: int = Field(default=5, ge=1)

class PlanReq(BaseModel):
    subject: str
    exam_date: str
    hours_per_day: float = 2
    weak_topics: str = ''

class ProfileReq(BaseModel):
    name: str
    level: str
    goal: str

def llm(prompt):
    key = os.getenv('GROQ_API_KEY')
    if not key: return None
    body = json.dumps({'model':'llama-3.1-8b-instant','messages':[{'role':'system','content':'You are LearnX, an adaptive learning copilot. Be accurate, encouraging, concise and educational.'},{'role':'user','content':prompt}], 'temperature':0.35}).encode()
    req = urllib.request.Request('https://api.groq.com/openai/v1/chat/completions', data=body, headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.loads(r.read())['choices'][0]['message']['content']
    except Exception:
        return None

def subject_state(subject):
    if subject not in state['subjects']:
        state['subjects'][subject] = {'mastery':{}, 'trend':[0]}
    return state['subjects'][subject]

def weakest(subject):
    mastery = subject_state(subject)['mastery']
    if not mastery: return {'topic':'New topic','score':0}
    topic, score = min(mastery.items(), key=lambda x:x[1])
    return {'topic':topic,'score':score}

def difficulty_for(score):
    if score < 45: return 'Beginner'
    if score < 70: return 'Medium'
    return 'Advanced'

@app.get('/')
def root(): return {'status':'LearnX AI running','version':'2.0'}

@app.get('/api/state')
def get_state():
    w = weakest('Mathematics')
    return {'state':state, 'weakest':w, 'recommendation':state['last_recommendation']}

@app.post('/api/profile')
def profile(x: ProfileReq):
    state['student'] = x.model_dump(); save_state(state); return {'student':state['student']}

@app.post('/api/tutor')
def tutor(x: ChatReq):
    prompt = f'''Student level: {x.level}. Subject: {x.subject}. Topic: {x.topic}. Student asks: {x.message}
Explain at the student's level using: 1) intuition, 2) simple example, 3) key idea/formula if relevant, 4) one quick check question. Do not overcomplicate.'''
    ans = llm(prompt)
    if not ans:
        ans = f'''Let's learn {x.topic} step by step.\n\n1. Intuition\nThink of {x.topic} as a concept you can break into a small rule and an example.\n\n2. Simple example\nStart with a small, concrete case and identify what is known, what is required, and which rule connects them.\n\n3. Practice\nTry one similar question without looking at the answer.\n\nQuick check: Explain the main idea of {x.topic} in one sentence.'''
    return {'answer':ans}

@app.post('/api/quiz')
def quiz(x: QuizReq):
    # Give the model the learner's current mastery so difficulty can adapt.
    mastery = subject_state(x.subject)['mastery'].get(x.topic)
    difficulty = x.difficulty
    if mastery is not None and x.difficulty == 'Adaptive': difficulty = difficulty_for(mastery)
    prompt = f'''Create exactly {x.count} MCQs for {x.topic} in {x.subject} at {difficulty} difficulty. Return ONLY a JSON array. Each object must contain question, options (exactly 4 strings), answer (0-3), explanation. Mix conceptual and applied questions. Avoid duplicate questions.'''
    raw = llm(prompt)
    if raw:
        try:
            match = re.search(r'\[.*\]', raw, re.S)
            if match: return {'questions':json.loads(match.group(0)), 'difficulty':difficulty}
        except Exception: pass
    qs = []
    for i in range(x.count):
        qs.append({'question':f'{x.topic} — adaptive practice question {i+1}: Which approach best helps you solve an unfamiliar problem?', 'options':['Identify the concept and known values first','Guess immediately','Skip the question','Memorize the question'], 'answer':0, 'explanation':'Start by identifying the concept, known information and what the question asks.', 'topic':x.topic})
    return {'questions':qs, 'difficulty':difficulty, 'demo':True}

@app.post('/api/quiz/result')
def quiz_result(x: ResultReq):
    subj = subject_state(x.subject)
    old = subj['mastery'].get(x.topic, 50)
    # Smooth update: recent evidence matters, but one quiz does not erase history.
    new = round(old * 0.55 + x.score * 0.45)
    subj['mastery'][x.topic] = new
    subj['trend'] = (subj.get('trend') or [50])[-5:] + [new]
    state['quiz_history'].append({'subject':x.subject,'topic':x.topic,'score':x.score,'date':datetime.now().isoformat(timespec='seconds')})
    state['quiz_history'] = state['quiz_history'][-12:]
    state['study_minutes'] += 15
    w = weakest(x.subject)
    if x.score < 60:
        rec = f'Revisit {x.topic} with a targeted explanation, then retry a {difficulty_for(new)} quiz.'
    else:
        rec = f'Good progress in {x.topic}. Next, practice {w["topic"]} to raise your lowest mastery.'
    state['last_recommendation'] = rec
    save_state(state)
    return {'new_mastery':new,'weakest':w,'recommendation':rec}

@app.post('/api/planner')
def planner(x: PlanReq):
    w = weakest(x.subject)
    weak = x.weak_topics or w['topic']
    ans = llm(f'''Create a practical 7-day adaptive study plan for {x.subject}. Exam date: {x.exam_date}. Available time: {x.hours_per_day} hours/day. Weak topics: {weak}. Include daily learning, targeted practice, revision and one checkpoint. Format as Day 1..Day 7.''')
    if not ans:
        ans = '\n'.join([f'Day {i}: {x.subject} — {x.hours_per_day:g}h | 45% concept learning · 40% targeted practice · 15% review/checkpoint.' for i in range(1,8)])
    return {'plan':ans,'focus':weak,'generated_for':x.exam_date}

@app.post('/api/doubt')
async def doubt(file: UploadFile = File(...), subject: str='Mathematics'):
    # OCR can be plugged into this endpoint later; current version gives a graceful workflow response.
    content = await file.read()
    return {'filename':file.filename,'bytes':len(content),'answer': 'Image received. Connect an OCR/vision model (or a multimodal LLM) here to extract the question and return a step-by-step solution.', 'next_step':'OCR → concept detection → solution → targeted practice'}
