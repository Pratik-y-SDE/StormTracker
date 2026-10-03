import re
import os

def check_frontend():
    print("Checking frontend files...")
    html_path = os.path.join("frontend", "index.html")
    js_path = os.path.join("frontend", "js", "app.js")
    css_path = os.path.join("frontend", "css", "style.css")

    assert os.path.exists(html_path), "index.html missing!"
    assert os.path.exists(js_path), "app.js missing!"
    assert os.path.exists(css_path), "style.css missing!"

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Verify no absolute static links in HTML
    assert "/static/css/style.css" not in html, "Found /static/css/style.css in index.html"
    assert "/static/js/app.js" not in html, "Found /static/js/app.js in index.html"
    assert "css/style.css" in html, "Relative css/style.css link missing from index.html"
    assert "js/app.js" in html, "Relative js/app.js script missing from index.html"

    # Verify no raw un-prefixed /api/ fetch calls
    raw_fetches = re.findall(r'fetch\([\'"`]/api', js)
    print(f"Raw un-prefixed /api fetch calls found: {len(raw_fetches)}")
    assert len(raw_fetches) == 0, f"Found un-prefixed fetch calls: {raw_fetches}"

    # Verify API_BASE is used
    api_base_fetches = re.findall(r'apiFetch\(`\$\{API_BASE\}/api', js)
    print(f"API_BASE fetch calls found: {len(api_base_fetches)}")
    assert len(api_base_fetches) >= 10, "Not all fetch calls use API_BASE"

    print("ALL FRONTEND VERIFICATIONS PASSED!")

if __name__ == "__main__":
    check_frontend()
