import json
import os
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


TARGET_URL = os.environ.get(
    "TARGET_URL",
    "https://toffeelive.com/en"
)

HAR_FILE = "network.har"
JSON_FILE = "network.json"

requests_data = []
responses_data = []


def now():
    return datetime.now(timezone.utc).isoformat()


with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True
    )

    context = browser.new_context(
        record_har_path=HAR_FILE,
        record_har_content="omit",
    )

    page = context.new_page()

    def request_handler(request):
        data = {
            "time": now(),
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
        }

        requests_data.append(data)

        print(
            f"[REQUEST] "
            f"{request.method} "
            f"{request.resource_type} "
            f"{request.url}"
        )

    def response_handler(response):
        data = {
            "time": now(),
            "status": response.status,
            "status_text": response.status_text,
            "url": response.url,
            "resource_type": response.request.resource_type,
        }

        responses_data.append(data)

        print(
            f"[RESPONSE] "
            f"{response.status} "
            f"{response.url}"
        )

    page.on("request", request_handler)
    page.on("response", response_handler)

    print(f"Opening: {TARGET_URL}")

    try:
        page.goto(
            TARGET_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        # Allow additional network activity to finish.
        page.wait_for_timeout(10000)

    except Exception as exc:
        print(f"Navigation error: {exc}")

    result = {
        "target": TARGET_URL,
        "captured_at": now(),
        "requests": requests_data,
        "responses": responses_data,
    }

    with open(
        JSON_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )

    context.close()
    browser.close()

print()
print("================================")
print("Network analysis completed")
print("================================")
print(f"Requests : {len(requests_data)}")
print(f"Responses: {len(responses_data)}")
print(f"HAR      : {HAR_FILE}")
print(f"JSON     : {JSON_FILE}")
