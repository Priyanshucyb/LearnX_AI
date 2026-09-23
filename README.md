# LearnX AI — Adaptive Learning Copilot

LearnX is an adaptive learning system rather than a generic chatbot. It connects **Learn → Practice → Measure → Adapt** and keeps a lightweight learner state so future recommendations change with performance.

## What is included
- AI Tutor with Beginner / Medium / Advanced modes
- Adaptive MCQ generator
- Quiz result → mastery update → next recommendation loop
- Topic-level mastery dashboard
- Weak/strong topic detection
- Adaptive 7-day study planner
- Doubt Solver upload flow with OCR/vision-ready backend endpoint
- Persistent `learning_state.json` for demo learner data
- Responsive modern EdTech UI

## Run backend
```bash
cd backend
python -m venv venv
# macOS/Linux
source venv/bin/activate
# Windows: venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# Add GROQ_API_KEY to .env for live LLM responses
uvicorn main:app --reload --port 8000
```

## Run frontend
Open a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open the Vite URL, usually `http://localhost:5173`.

## Optional environment variable
Create `frontend/.env` if the backend is deployed somewhere else:
```env
VITE_API_URL=http://localhost:8000
```

## Adaptive loop
1. Student learns a topic.
2. LearnX generates a quiz at the learner's current difficulty.
3. The submitted score is blended with previous mastery.
4. The weakest topic is detected.
5. The dashboard recommends the next learning activity.
6. The next quiz/planner can use the updated state.

This is the core differentiator: **the system does not only answer; it uses performance to decide what the student should do next.**
