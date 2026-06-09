import os
import json
import time
from bs4 import BeautifulSoup
from groq import Groq
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

# ==========================================
# PART 1: SETUP & INITIALIZATION
# ==========================================

app = FastAPI(title="AI Website Auditor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class AuditRequest(BaseModel):
    url: str

# ==========================================
# PART 2: SCRAPER (Playwright + richer data)
# ==========================================

def extract_website_data(url: str) -> dict:
    try:
        start_time = time.time()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=20000)
            html_content = page.content()
            load_time_ms = round((time.time() - start_time) * 1000)
            browser.close()

        soup = BeautifulSoup(html_content, "html.parser")

        # Basic SEO fields
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        description = meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""

        # Canonical URL
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        canonical = canonical_tag["href"] if canonical_tag else ""

        # Open Graph
        og_title = soup.find("meta", property="og:title")
        og_desc = soup.find("meta", property="og:description")
        og_image = soup.find("meta", property="og:image")

        # Headings
        headings = {
            "h1": [h.get_text(strip=True) for h in soup.find_all("h1")],
            "h2": [h.get_text(strip=True) for h in soup.find_all("h2")],
            "h3": [h.get_text(strip=True) for h in soup.find_all("h3")],
        }

        # Body text (first 15 paragraphs)
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        body_text = " ".join(paragraphs[:15])

        # Links
        all_links = soup.find_all("a", href=True)
        internal_links = [a["href"] for a in all_links if a["href"].startswith("/") or url in a["href"]]
        external_links = [a["href"] for a in all_links if a["href"].startswith("http") and url not in a["href"]]

        # Images
        all_images = soup.find_all("img")
        images_missing_alt = [img.get("src", "") for img in all_images if not img.get("alt")]

        # Structured data (Schema.org)
        schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        has_schema = len(schema_scripts) > 0

        # Mobile viewport
        viewport_tag = soup.find("meta", attrs={"name": "viewport"})
        has_viewport = viewport_tag is not None

        return {
            "success": True,
            "title": title,
            "description": description,
            "canonical": canonical,
            "og_title": og_title["content"] if og_title else "",
            "og_description": og_desc["content"] if og_desc else "",
            "og_image": og_image["content"] if og_image else "",
            "headings": headings,
            "body_text": body_text,
            "internal_link_count": len(internal_links),
            "external_link_count": len(external_links),
            "total_images": len(all_images),
            "images_missing_alt": len(images_missing_alt),
            "has_schema_markup": has_schema,
            "has_viewport_meta": has_viewport,
            "load_time_ms": load_time_ms,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ==========================================
# PART 3: AI PROCESSING (upgraded model + richer scoring)
# ==========================================

def run_ai_audit(site_data: dict) -> dict:
    if not site_data["success"]:
        return {"error": "No data to analyze"}

    system_prompt = """
You are an elite UX, SEO, and Performance Website Auditor. Analyze the scraped website data and return a strict JSON audit.

Scoring rules:

1. homepage_clarity (1-10):
   - Score below 5 if a visitor cannot tell what the site offers within the first 3 lines.
   - Consider H1, title, and body text.

2. cta_strength (1-10):
   - Score below 4 if no action-oriented words ("Buy", "Sign Up", "Get Started", "Try", "Download") appear in headings or body.

3. seo_basics (1-10, start at 10 and deduct):
   - Missing title: -3
   - Missing meta description: -4
   - No H1 tag: -2
   - No canonical URL: -1

4. technical_health (1-10, start at 10 and deduct):
   - No viewport meta tag: -3
   - No Open Graph tags: -2
   - No schema markup: -2
   - More than 20% of images missing alt text: -2
   - Load time > 5000ms: -1

5. content_quality (1-10):
   - Evaluate H2/H3 structure, paragraph depth, and keyword coherence.

6. overall_score: weighted average → clarity×0.25 + cta×0.20 + seo×0.25 + technical×0.20 + content×0.10

Return ONLY this JSON, no extra text:
{
    "overall_score": <float 1-10, 1 decimal>,
    "homepage_clarity": { "score": <int>, "feedback": "<1-2 sentences>" },
    "cta_strength": { "score": <int>, "feedback": "<1-2 sentences>" },
    "seo_basics": { "score": <int>, "feedback": "<1-2 sentences>" },
    "technical_health": { "score": <int>, "feedback": "<1-2 sentences>" },
    "content_quality": { "score": <int>, "feedback": "<1-2 sentences>" },
    "recommended_fixes": ["<fix 1>", "<fix 2>", "<fix 3>", "<fix 4>"]
}
"""

    user_content = f"""
Title: {site_data['title']}
Meta Description: {site_data['description']}
Canonical URL: {site_data['canonical']}
OG Title: {site_data['og_title']}
OG Description: {site_data['og_description']}
OG Image: {"Present" if site_data['og_image'] else "Missing"}
Has Schema Markup: {site_data['has_schema_markup']}
Has Viewport Meta: {site_data['has_viewport_meta']}
Headings: {site_data['headings']}
Sample Body Text: {site_data['body_text']}
Total Images: {site_data['total_images']} ({site_data['images_missing_alt']} missing alt text)
Internal Links: {site_data['internal_link_count']} | External Links: {site_data['external_link_count']}
Page Load Time: {site_data['load_time_ms']}ms
"""

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # Upgraded from 8b
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    result = json.loads(completion.choices[0].message.content)

    # Attach raw scraped stats so the frontend can display them
    result["_meta"] = {
        "load_time_ms": site_data["load_time_ms"],
        "total_images": site_data["total_images"],
        "images_missing_alt": site_data["images_missing_alt"],
        "internal_links": site_data["internal_link_count"],
        "external_links": site_data["external_link_count"],
        "has_schema": site_data["has_schema_markup"],
        "has_viewport": site_data["has_viewport_meta"],
        "has_og": bool(site_data["og_title"]),
    }

    return result


# ==========================================
# PART 4: API ENDPOINT
# ==========================================

@app.post("/api/audit")
def perform_audit(request: AuditRequest):
    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

    scraped_data = extract_website_data(request.url)

    if not scraped_data["success"]:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to scrape website: {scraped_data['error']}"
        )

    audit_result = run_ai_audit(scraped_data)
    return audit_result


# ==========================================
# PART 5: SERVE FRONTEND
# ==========================================

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")