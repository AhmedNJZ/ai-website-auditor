# AI Website Auditor

An AI-powered web app that audits any website for UX, SEO, and technical health.

## What it does
- Scrapes any URL using a headless Chromium browser (Playwright)
- Analyzes SEO, Open Graph, schema markup, images, load time, and more
- Uses Groq (Llama 3.3 70B) to score the site across 5 categories
- Displays results in a clean dashboard UI

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOURUSERNAME/YOURREPONAME.git
cd YOURREPONAME
```

### 2. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Add your Groq API key
Create a `.env` file in the project root:
GROQ_API_KEY=your_key_here
Get a free key at https://console.groq.com

### 5. Run the app
```bash
uvicorn main:app --reload
```
Then open http://127.0.0.1:8000
Save it, then let me know and we'll do the GitHub push.