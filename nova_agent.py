import os
import json
import boto3
import pyttsx3
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-1",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN")
)

# Feature 2: Remember context
conversation_context = {
    "last_site": None,
    "last_query": None,
    "history": []
}


def speak(text: str):
    """Feature 1: Read text aloud to user"""
    print(f"🔊 Speaking: {text}")
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"⚠️ Speech error: {e}")


def ask_nova(instruction: str):
    """Feature 2: Pass conversation context to Nova"""
    
    context_str = ""
    if conversation_context["last_site"]:
        context_str = f"""
    Previous context:
    - Last site used: {conversation_context["last_site"]}
    - Last search: {conversation_context["last_query"]}
    - Use this context if the new instruction seems to continue from before
    """

    prompt = f"""
    You are a browser automation assistant for visually impaired users.
    The user said: "{instruction}"
    {context_str}

    Return a JSON object with:
    - "site": which website (google, youtube, facebook, twitter, instagram, wikipedia, reddit, amazon, direct)
    - "query": what to search for (empty string if just opening the site)
    - "url": only if site is "direct", provide the full URL
    - "summary": a SHORT one sentence description of what you are about to do (for text to speech)

    IMPORTANT RULES:
    - If no site is mentioned but there is context, use the last site
    - If no site is mentioned and no context, default to "google"
    - If user mentions YouTube or video, use youtube
    - If user mentions shopping or product, use amazon
    - If user mentions news or discussion, use reddit
    - Always capture the full search intent
    - summary should be natural spoken English e.g. "Opening YouTube and searching for chicken recipe"

    Examples:
    "open YouTube and search for chicken recipe"
    {{"site": "youtube", "query": "chicken recipe", "summary": "Opening YouTube and searching for chicken recipe"}}

    "search for weather in Karachi"
    {{"site": "google", "query": "weather in Karachi", "summary": "Searching Google for weather in Karachi"}}

    "open Facebook"
    {{"site": "facebook", "query": "", "summary": "Opening Facebook for you"}}

    "Python tutorial on YouTube"
    {{"site": "youtube", "query": "Python tutorial", "summary": "Opening YouTube and searching for Python tutorial"}}

    "Wikipedia artificial intelligence"
    {{"site": "wikipedia", "query": "artificial intelligence", "summary": "Opening Wikipedia and searching for artificial intelligence"}}

    "jobs in karachi"
    {{"site": "google", "query": "jobs in karachi", "summary": "Searching Google for jobs in Karachi"}}

    "amazon wireless headphones"
    {{"site": "amazon", "query": "wireless headphones", "summary": "Opening Amazon and searching for wireless headphones"}}

    "reddit best programming languages"
    {{"site": "reddit", "query": "best programming languages", "summary": "Opening Reddit and searching for best programming languages"}}

    Return ONLY the JSON object, nothing else.
    """

    response = bedrock.invoke_model(
        modelId="us.amazon.nova-2-lite-v1:0",
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"max_new_tokens": 200}
        })
    )

    result = json.loads(response["body"].read())
    text = result["output"]["message"]["content"][0]["text"].strip()

    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    plan = json.loads(text.strip())

    # Feature 2: Update context
    conversation_context["last_site"] = plan.get("site")
    conversation_context["last_query"] = plan.get("query")
    conversation_context["history"].append(instruction)

    return plan


def get_page_summary(page, site: str, query: str) -> str:
    """Feature 1 & 3: Extract page content and create summary"""
    try:
        if site == "google":
            # Get search result titles and snippets
            results = page.query_selector_all("h3")
            titles = []
            for r in results[:5]:
                text = r.inner_text().strip()
                if text:
                    titles.append(text)
            if titles:
                return f"Found {len(titles)} results. Top results include: {', '.join(titles[:3])}"

        elif site == "youtube":
            # Get video titles
            results = page.query_selector_all("yt-formatted-string#video-title")
            titles = []
            for r in results[:5]:
                text = r.inner_text().strip()
                if text:
                    titles.append(text)
            if titles:
                return f"Found {len(titles)} videos. Top videos include: {titles[0]} and {titles[1] if len(titles) > 1 else ''}"

        elif site == "wikipedia":
            # Get first paragraph
            result = page.query_selector("p")
            if result:
                text = result.inner_text().strip()
                # Limit to first 200 characters
                return text[:200] + "..." if len(text) > 200 else text

        elif site == "amazon":
            # Get product names
            results = page.query_selector_all("span.a-text-normal")
            titles = []
            for r in results[:3]:
                text = r.inner_text().strip()
                if text and len(text) > 10:
                    titles.append(text)
            if titles:
                return f"Found products including: {titles[0]}"

        elif site == "reddit":
            # Get post titles
            results = page.query_selector_all("h3")
            titles = []
            for r in results[:3]:
                text = r.inner_text().strip()
                if text:
                    titles.append(text)
            if titles:
                return f"Found {len(titles)} posts. Top post: {titles[0]}"

    except Exception as e:
        print(f"⚠️ Could not extract page content: {e}")

    return ""


def open_and_search(page, url, selector, query):
    print(f"  → Opening: {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
    except Exception:
        print("  ⚠️ Slow load, continuing...")

    if query:
        print(f"  → Waiting for search box...")
        try:
            page.wait_for_selector(selector, timeout=30000)
            page.click(selector)
            page.wait_for_timeout(800)
            print(f"  → Typing: {query}")
            page.fill(selector, query)
            page.wait_for_timeout(500)
            page.press(selector, "Enter")
            page.wait_for_load_state("domcontentloaded")
            print("  ✅ Search done!")
        except Exception as e:
            print(f"  ⚠️ Search box failed, using direct URL: {e}")
            if "google" in url:
                page.goto(f"https://www.google.com/search?q={query.replace(' ', '+')}", timeout=60000)
            elif "youtube" in url:
                page.goto(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}", timeout=60000)
            elif "amazon" in url:
                page.goto(f"https://www.amazon.com/s?k={query.replace(' ', '+')}", timeout=60000)
            elif "reddit" in url:
                page.goto(f"https://www.reddit.com/search/?q={query.replace(' ', '+')}", timeout=60000)
            elif "wikipedia" in url:
                page.goto(f"https://en.wikipedia.org/wiki/Special:Search?search={query.replace(' ', '+')}", timeout=60000)


def run_browser_task(instruction: str):
    print(f"\n🤖 Received: {instruction}")
    print("🧠 Asking Nova 2 Lite to plan actions...")

    plan = ask_nova(instruction)
    print(f"📋 Plan: {json.dumps(plan, indent=2)}")

    site = plan.get("site", "google")
    query = plan.get("query", "")
    url = plan.get("url", "")
    summary = plan.get("summary", f"Opening {site}")

    # Feature 1: Speak what we are about to do
    speak(summary)

    chromium_path = "E:\\playwright-browsers\\chromium-1194\\chrome-win\\chrome.exe"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            executable_path=chromium_path,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.bring_to_front()

        if site == "google":
            open_and_search(page, "https://www.google.com", "input[name='q']", query)
        elif site == "youtube":
            open_and_search(page, "https://www.youtube.com", "input[name='search_query']", query)
        elif site == "wikipedia":
            open_and_search(page, "https://www.wikipedia.org", "input[name='search']", query)
        elif site == "amazon":
            open_and_search(page, "https://www.amazon.com", "input[id='twotabsearchtextbox']", query)
        elif site == "reddit":
            open_and_search(page, "https://www.reddit.com", "input[name='q']", query)
        elif site == "twitter":
            print("  → Opening Twitter/X...")
            try:
                page.goto("https://www.twitter.com", wait_until="domcontentloaded", timeout=120000)
            except Exception:
                print("  ⚠️ Slow load, continuing...")
            if query:
                try:
                    search_url = f"https://twitter.com/search?q={query.replace(' ', '+')}&src=typed_query"
                    page.goto(search_url, wait_until="domcontentloaded", timeout=120000)
                except Exception as e:
                    print(f"  ⚠️ Error: {e}")
        elif site == "instagram":
            print("  → Opening Instagram...")
            try:
                page.goto("https://www.instagram.com", wait_until="domcontentloaded", timeout=120000)
            except Exception:
                print("  ⚠️ Slow load, continuing...")
        elif site == "facebook":
            print("  → Opening Facebook...")
            try:
                page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=120000)
            except Exception:
                print("  ⚠️ Slow load, continuing...")
        elif site == "direct" and url:
            print(f"  → Going to: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=120000)
            except Exception:
                print("  ⚠️ Slow load, continuing...")

        # Feature 1 & 3: Read page summary aloud
        page.wait_for_timeout(3000)
        page_summary = get_page_summary(page, site, query)
        if page_summary:
            print(f"\n📊 Page Summary: {page_summary}")
            speak(page_summary)

        print("\n✅ Done! Close the browser when finished.")
        try:
            page.wait_for_event("close", timeout=300000)
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        print("👋 Browser closed.")


if __name__ == "__main__":
    run_browser_task("open YouTube and search for chicken recipe")