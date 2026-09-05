import json
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


TARGET_URL = "https://toffeelive.com/en"

requests_data = []
responses_data = []


def timestamp():
    return datetime.now(timezone.utc).isoformat()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    context = browser.new_context(
        record_har_path="network.har",
        record_har_content="omit",
    )

    page = context.new_page()

    def on_request(request):
        requests_data.append({
            "time": timestamp(),
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
        })

        print(
            f"[REQUEST] "
            f"{request.method} "
            f"{request.resource_type} "
            f"{request.url}"
        )

    def on_response(response):
        responses_data.append({
            "time": timestamp(),
            "status": response.status,
            "status_text": response.status_text,
            "url": response.url,
            "resource_type": response.request.resource_type,
        })

        print(
            f"[RESPONSE] "
            f"{response.status} "
            f"{response.url}"
        )

    page.on("request", on_request)
    page.on("response", on_response)

    print(f"Opening: {TARGET_URL}")

    try:
        page.goto(
            TARGET_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        # Wait for additional network activity.
        page.wait_for_timeout(10000)

    except Exception as e:
        print(f"Navigation error: {e}")

    result = {
        "target_url": TARGET_URL,
        "captured_at": timestamp(),
        "request_count": len(requests_data),
        "response_count": len(responses_data),
        "requests": requests_data,
        "responses": responses_data,
    }

    with open(
        "network.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False,
        )

    context.close()
    browser.close()


print()
print("================================")
print("Network analysis completed")
print("================================")
print(f"Requests : {len(requests_data)}")
print(f"Responses: {len(responses_data)}")
print("Created  : network.json")
print("Created  : network.har")
