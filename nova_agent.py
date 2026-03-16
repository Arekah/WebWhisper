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

conversation_context = {
    "last_site": None,
    "last_query": None,
    "history": []
}


def speak(text: str):
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
    - "summary": a SHORT one sentence description of what you are about to do
    - "scroll": true if user wants to scroll down, false otherwise
    - "open_first": true if user wants to open first result, false otherwise

    IMPORTANT RULES:
    - If no site is mentioned but there is context, use the last site
    - If no site is mentioned and no context, default to "google"
    - If user mentions YouTube or video, use youtube
    - If user mentions shopping or product, use amazon
    - If user mentions news or discussion, use reddit
    - If user says "scroll down" or "scroll", set scroll to true
    - If user says "open first", "click first", "open first video", "open first result", set open_first to true
    - summary should be natural spoken English

    Examples:
    "open YouTube search for Python tutorials and open first video"
    {{"site": "youtube", "query": "Python tutorials", "summary": "Opening YouTube, searching for Python tutorials and opening the first video", "scroll": false, "open_first": true}}

    "open Wikipedia search for machine learning and scroll down"
    {{"site": "wikipedia", "query": "machine learning", "summary": "Opening Wikipedia, searching for machine learning and scrolling down", "scroll": true, "open_first": false}}

    "search for weather in Karachi"
    {{"site": "google", "query": "weather in Karachi", "summary": "Searching Google for weather in Karachi", "scroll": false, "open_first": false}}

    "open Facebook"
    {{"site": "facebook", "query": "", "summary": "Opening Facebook for you", "scroll": false, "open_first": false}}

    "amazon wireless headphones open first"
    {{"site": "amazon", "query": "wireless headphones", "summary": "Opening Amazon, searching for wireless headphones and opening the first product", "scroll": false, "open_first": true}}

    Return ONLY the JSON object, nothing else.
    """

    response = bedrock.invoke_model(
        modelId="us.amazon.nova-2-lite-v1:0",
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"max_new_tokens": 300}
        })
    )

    result = json.loads(response["body"].read())
    text = result["output"]["message"]["content"][0]["text"].strip()

    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    plan = json.loads(text.strip())

    conversation_context["last_site"] = plan.get("site")
    conversation_context["last_query"] = plan.get("query")
    conversation_context["history"].append(instruction)

    return plan


def get_page_summary(page, site: str, query: str) -> str:
    try:
        if site == "google":
            results = page.query_selector_all("h3")
            titles = []
            for r in results[:5]:
                text = r.inner_text().strip()
                if text:
                    titles.append(text)
            if titles:
                return f"Found {len(titles)} results. Top results include: {', '.join(titles[:3])}"

        elif site == "youtube":
            results = page.query_selector_all("yt-formatted-string#video-title")
            titles = []
            for r in results[:5]:
                text = r.inner_text().strip()
                if text:
                    titles.append(text)
            if titles:
                return f"Found {len(titles)} videos. Top videos include: {titles[0]} and {titles[1] if len(titles) > 1 else ''}"

        elif site == "wikipedia":
            result = page.query_selector("p")
            if result:
                text = result.inner_text().strip()
                return text[:200] + "..." if len(text) > 200 else text

        elif site == "amazon":
            results = page.query_selector_all("span.a-text-normal")
            titles = []
            for r in results[:3]:
                text = r.inner_text().strip()
                if text and len(text) > 10:
                    titles.append(text)
            if titles:
                return f"Found products including: {titles[0]}"

        elif site == "reddit":
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


def click_first_result(page, site: str):
    print("  → Clicking first result...")
    try:
        if site == "youtube":
            first = page.query_selector("ytd-video-renderer #video-title")
            if not first:
                first = page.query_selector("a#video-title")
            if first:
                first.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)
                speak("Opening the first video now")
                print("  ✅ First video opened!")

        elif site == "google":
            first = page.query_selector("h3")
            if first:
                first.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)
                speak("Opening the first result now")
                print("  ✅ First result opened!")

        elif site == "wikipedia":
            first = page.query_selector(".mw-search-result-heading a")
            if first:
                first.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)
                speak("Opening the first Wikipedia article now")
                print("  ✅ First Wikipedia result opened!")

        elif site == "amazon":
            first = page.query_selector("h2 a.a-link-normal")
            if first:
                first.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)
                speak("Opening the first product now")
                print("  ✅ First product opened!")

        elif site == "reddit":
            first = page.query_selector("h3")
            if first:
                first.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)
                speak("Opening the first post now")
                print("  ✅ First post opened!")

    except Exception as e:
        print(f"  ⚠️ Could not click first result: {e}")


def scroll_down(page):
    print("  → Scrolling down...")
    speak("Scrolling down for you")
    for i in range(5):
        page.evaluate("window.scrollBy(0, 300)")
        page.wait_for_timeout(300)
    print("  ✅ Scrolled down!")


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
            page.wait_for_timeout(2000)
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
    should_scroll = plan.get("scroll", False)
    should_open_first = plan.get("open_first", False)

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

        page.wait_for_timeout(2000)
        page_summary = get_page_summary(page, site, query)
        if page_summary:
            print(f"\n📊 Page Summary: {page_summary}")
            speak(page_summary)

        if should_scroll:
            page.wait_for_timeout(1000)
            scroll_down(page)

        if should_open_first:
            page.wait_for_timeout(1000)
            click_first_result(page, site)
            page.wait_for_timeout(3000)
            new_summary = get_page_summary(page, site, query)
            if new_summary:
                speak(new_summary)

        print("\n✅ Done! Close the browser when finished.")
        try:
            # Check every second if browser is still open
            while browser.is_connected():
                page.wait_for_timeout(1000)
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        print("👋 Browser closed.")

if __name__ == "__main__":
    run_browser_task("open YouTube search for Python tutorials and open first video")