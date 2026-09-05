import json
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

TARGET_URL = "https://toffeelive.com/en"
OUTPUT_FILE = "network.json"


def main():
    edge_cookie_detected = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context()
        page = context.new_page()

        def check_request(request):
            nonlocal edge_cookie_detected

            for name in request.headers:
                if name.lower() == "edge-cache-cookie":
                    edge_cookie_detected = True
                    print("Edge-Cache-Cookie detected in request")

        def check_response(response):
            nonlocal edge_cookie_detected

            for name in response.headers:
                if name.lower() == "edge-cache-cookie":
                    edge_cookie_detected = True
                    print("Edge-Cache-Cookie detected in response")

        page.on("request", check_request)
        page.on("response", check_response)

        print(f"Opening: {TARGET_URL}")

        try:
            page.goto(
                TARGET_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )
        except Exception as e:
            print(f"Navigation warning: {e}")

        # Wait for client-side requests/cookies.
        page.wait_for_timeout(10000)

        context.close()
        browser.close()

    result = {
        "Edge-Cache-Cookie": (
            "[REDACTED]"
            if edge_cookie_detected
            else None
        )
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Saved {OUTPUT_FILE}")

    if edge_cookie_detected:
        print("Edge-Cache-Cookie: [REDACTED]")
    else:
        print("Edge-Cache-Cookie not detected.")


if __name__ == "__main__":
    main()
