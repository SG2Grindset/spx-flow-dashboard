# ============================================================
# alerts.py
# Discord Alert Sender with Optional Image Attachment
# ============================================================

import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def send_discord_alert(message: str, image_path: str | None = None):
    if not DISCORD_WEBHOOK_URL:
        return False, "Missing DISCORD_WEBHOOK_URL in .env"

    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                data={"content": message},
                files={"file": (os.path.basename(image_path), f, "image/png")},
                timeout=20
            )
    else:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message},
            timeout=10
        )

    if response.status_code not in [200, 204]:
        return False, f"Discord error {response.status_code}: {response.text}"

    return True, "Discord alert sent"