"""
ICAI Monitor - Uses real browser via Playwright
Install: pip install playwright requests && playwright install chromium

Phone notifications via ntfy:
1. Install "ntfy" app from Play Store
2. Subscribe to topic: icai-sohil-monitor
"""

import time
import subprocess
import sys
import requests
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)

CHECK_INTERVAL_MINUTES = 1
TARGET_URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
NTFY_TOPIC = "icai-sohil-monitor"

def fetch_batches():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(TARGET_URL, timeout=30000)

            page.select_option("select[name='ddl_reg']", value="3")
            page.wait_for_timeout(2000)

            pou_options = page.locator("select[name='ddlPou'] option").all_text_contents()
            delhi_val = None
            for opt in pou_options:
                if "DELHI" in opt.upper():
                    delhi_val = opt.strip()
                    break

            if not delhi_val:
                browser.close()
                return [], "DELHI not found in POU. Options: " + str(pou_options)

            page.select_option("select[name='ddlPou']", label=delhi_val)
            page.wait_for_timeout(1000)

            page.select_option("select[name='ddl_course']", value="47")
            page.wait_for_timeout(500)

            page.click("input[name='btn_getlist']")
            page.wait_for_timeout(3000)

            batches = []
            rows = page.locator("table tr").all()
            header_found = False
            for row in rows:
                cells = row.locator("td,th").all_text_contents()
                cells = [c.strip() for c in cells]
                if not cells:
                    continue
                if any("batch" in c.lower() for c in cells):
                    header_found = True
                    continue
                if header_found and len(cells) >= 4:
                    batches.append({
                        "batch_no":  cells[0],
                        "seats":     cells[1],
                        "from_date": cells[2],
                        "to_date":   cells[3],
                        "pou":       cells[5] if len(cells) > 5 else "",
                    })

            browser.close()
            return batches, None

    except Exception as e:
        return [], str(e)


def available(batches):
    out = []
    for b in batches:
        try:
            if int(b["seats"]) > 0:
                out.append(b)
        except ValueError:
            if b["seats"] not in ("0", "", "-"):
                out.append(b)
    return out


def send_phone_notification(title, body):
    try:
        r = requests.post(
            "https://ntfy.sh/" + NTFY_TOPIC,
            data=body.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": "urgent",
                "Tags": "rotating_light,calendar",
                "Click": TARGET_URL,
            },
            timeout=10
        )
        if r.status_code == 200:
            print("  Phone notification: sent OK")
        else:
            print("  Phone notification failed: " + str(r.status_code))
    except Exception as e:
        print("  ntfy error: " + str(e))


def notify_windows(title, body):
    try:
        from plyer import notification
        notification.notify(title=title, message=body, timeout=30)
    except Exception:
        pass


def open_browser():
    import webbrowser
    webbrowser.open(TARGET_URL)


def main():
    print("==================================================")
    print("  ICAI Monitor - Delhi ICITSS IT")
    print("  Interval : " + str(CHECK_INTERVAL_MINUTES) + " min")
    print("  Phone    : ntfy topic = " + NTFY_TOPIC)
    print("  Press Ctrl+C to stop")
    print("==================================================")
    print("")
    print("  ntfy app on phone -> subscribe to: " + NTFY_TOPIC)
    print("")

    seen = set()

    while True:
        now = datetime.now().strftime("%d-%m-%Y %H:%M")
        print("[" + now + "] Checking...")
        batches, error = fetch_batches()
        avail = available(batches)

        print("[" + now + "] " + str(len(batches)) + " batches | " + str(len(avail)) + " available")

        if error:
            print("  ERROR: " + error)

        for b in batches:
            tag = "OPEN" if b in avail else "full"
            print("  [" + tag + "] " + b["batch_no"] + " | seats: " + b["seats"] + " | " + b["from_date"] + " to " + b["to_date"])

        new = [b for b in avail if b["batch_no"] not in seen]
        if new:
            lines = [b["batch_no"] + " | " + b["seats"] + " seats | " + b["from_date"] + "-" + b["to_date"] for b in new]
            body = "\n".join(lines)
            print("\n*** SEATS AVAILABLE ***\n" + body)
            notify_windows("ICAI SEATS OPEN!", body)
            send_phone_notification("ICAI SEATS OPEN!", body)
            open_browser()
            seen.update(b["batch_no"] for b in new)
        elif not avail:
            seen.clear()

        print("  Next check in " + str(CHECK_INTERVAL_MINUTES) + " min...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
