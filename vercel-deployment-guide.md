# Vercel Deployment Guide

## ❌ Why It Was Failing With 404
Initially, the React (Vite) frontend was inside a subfolder named `webui/`. When Vercel built your project, it scanned the root directory, saw no `index.html` or build script, and essentially served a blank page (Error 404).

## ✅ What We Fixed
1. **Frontend Elevated**: Moved all files from `webui/` into the root directory. Vercel automatically detects Vite configurations when they are in the root directory!
2. **Directory Cleanups**: Renamed existing `src/` to `python_scripts/` so it wouldn't overwrite the React `src/` folder.
3. **Routing Configuration**: Added `vercel.json` to handle React-Router SPA pages natively. 
4. **Deploy Status Badge**: Added a UI indicator to show when Vercel successfully deployed the frontend!

---

## 🚀 Step-by-Step Vercel Redeployment
Since I've automated the code restructures and pushed them to GitHub, your Vercel project might automatically deploy and fix itself! If it doesn't, follow these simple steps to ensure Vercel sees the new changes:

1. Open your Vercel Dashboard and click on your project.
2. Go to **Settings** -> **General**.
3. Scroll down to **Build & Development Settings**.
4. Set the **Framework Preset** to **Vite** (Vercel may have already detected this).
5. Ensure the **Build Command** is set to `npm run build` and the **Output Directory** is set to `dist`. (Leave blank if you selected the Vite preset, as it sets these automatically).
6. Go back to your dashboard and hit **Deploy** or **Redeploy**.

It should instantly succeed without the 404 error!

---

## ⚠️ Important Note: The Python Backend
Your FastAPI backend (`backend/main.py`) expects to run on `http://localhost:8000` and proxy messages to a local Ollama instance (`http://localhost:11434`). 

**Vercel is primarily a Frontend platform** designed for serverless functions, not long-running servers or native desktop applications. Thus, a backend relying on local hardware features like `Ollama` cannot simply be pushed to Vercel without extensive cloud API integration. 

If you want the deployed Vercel frontend to correctly chat with an AI:
1. **Host Ollama externally** (e.g. AWS, Render, RunPod) and update the FastAPI backend to point to that online address.
2. **Deploy the FastAPI backend** onto Render or Railway (a platform meant for Dockerized / Python instances) rather than Vercel. 
3. **Set the environment variable** `VITE_API_URL` inside your Vercel Environment Variables settings to point to the newly deployed backend so Vercel hooks up to it! 

*For now, your live Vercel frontend will only be able to communicate with your backend if you run `localhost` locally alongside the open browser, or use proxy tools like Ngrok.*
