from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
BASE_URL = "http://127.0.0.1:8765"
SERVER_LOG = ROOT / "verification-server.log"
TEMP_DIR = Path(tempfile.gettempdir())
TOP_SCREENSHOT = TEMP_DIR / "kimi-outdoor-dashboard-top.png"
API_SCREENSHOT = TEMP_DIR / "kimi-outdoor-dashboard-api.png"
HTTP = requests.Session()
HTTP.trust_env = False


def wait_for_health(timeout: int = 45) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = HTTP.get(f"{BASE_URL}/_stcore/health", timeout=2)
            if response.ok and response.text.strip() == "ok":
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError("Il server Streamlit non è diventato disponibile entro 45 secondi")


def main() -> None:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        "--server.port=8765",
        "--server.enableAgentApi=true",
    ]
    with SERVER_LOG.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_for_health()
            openapi = HTTP.get(f"{BASE_URL}/_stcore/agent/openapi.json", timeout=10)
            openapi.raise_for_status()
            protocol = openapi.json()
            print("Agent API:", protocol.get("info", {}).get("x-streamlit-agent-api", "sconosciuta"))

            interaction = HTTP.post(
                f"{BASE_URL}/_stcore/agent/interact",
                json={},
                timeout=45,
            )
            interaction.raise_for_status()
            snapshot = interaction.json()
            print("Stato applicazione:", snapshot.get("status"))
            if snapshot.get("status") != "ready":
                print(json.dumps(snapshot, ensure_ascii=False)[:4000])
                raise RuntimeError("Snapshot Streamlit non pronto")

            browser_errors: list[str] = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.on(
                    "console",
                    lambda message: browser_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error: browser_errors.append(str(error)))
                page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
                page.get_by_text("Outdoor decision monitor", exact=True).wait_for(timeout=30000)
                page.get_by_text("Migliore finestra per località e giorno", exact=True).wait_for(
                    timeout=30000
                )
                page.get_by_text("100%", exact=True).wait_for(timeout=30000)
                page.wait_for_timeout(7000)
                page.screenshot(path=str(TOP_SCREENSHOT), full_page=False)

                page.set_viewport_size({"width": 1440, "height": 6000})
                page.wait_for_timeout(2500)
                page.screenshot(path=str(API_SCREENSHOT), full_page=True)
                print("Titolo e sezioni principali: visibili")
                print("Canvas/grafici presenti:", page.locator("canvas").count())
                print("Errori browser:", browser_errors)
                browser.close()

            if browser_errors:
                raise RuntimeError("Errori browser rilevati")
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                console_output, _ = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                console_output, _ = process.communicate(timeout=10)
            print("Server di verifica arrestato")

    print("--- Console Streamlit ---")
    print(console_output)


if __name__ == "__main__":
    main()
