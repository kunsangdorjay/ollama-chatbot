# AI Assistant

A Gemini-style AI chat interface with:
- Streaming responses
- Model selection
- Chat history
- Light / dark mode
- Polished chat UI

## Tech
- React + Vite
- FastAPI

## Run locally

### Frontend
cd webui
npm install
npm run dev

### Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
