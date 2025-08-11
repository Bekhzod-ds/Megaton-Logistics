import os
import json
import tempfile
import requests
from flask import Flask, request, jsonify
import base64
from datetime import datetime

from google_drive import DriveHelper
from google_sheets import SheetsHelper

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # required
SHEET_ID = os.environ.get("SHEET_ID")    # required
GSERVICE_JSON_B64 = os.environ.get("GSERVICE_JSON_B64")  # required (base64 encoded service account JSON)
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")  # optional
PORT = int(os.environ.get("PORT", 5000))

if not BOT_TOKEN or not SHEET_ID or not GSERVICE_JSON_B64:
    raise RuntimeError("BOT_TOKEN, SHEET_ID and GSERVICE_JSON_B64 env vars are required")

service_json = json.loads(base64.b64decode(GSERVICE_JSON_B64).decode("utf-8"))

app = Flask(__name__)

drive = DriveHelper(service_json, folder_id=DRIVE_FOLDER_ID)
sheets = SheetsHelper(service_json, sheet_id=SHEET_ID)

TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{file_path}"
TELEGRAM_GETFILE_URL = "https://api.telegram.org/bot{token}/getFile"

# Store temporary state: which user is entering ID
user_states = {}  # chat_id -> {"awaiting_id": bool, "id": str}

def send_message(chat_id, text):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

def download_telegram_file(file_id):
    r = requests.get(TELEGRAM_GETFILE_URL.format(token=BOT_TOKEN), params={"file_id": file_id})
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError("getFile failed: " + str(data))
    file_path = data["result"]["file_path"]
    url = TELEGRAM_FILE_URL.format(token=BOT_TOKEN, file_path=file_path)
    r2 = requests.get(url, stream=True)
    r2.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(delete=False)
    with open(tmp.name, "wb") as f:
        for chunk in r2.iter_content(chunk_size=8192):
            f.write(chunk)
    return tmp.name

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update:
        return jsonify({"status": "no json"}), 400

    message = update.get("message") or update.get("edited_message")
    if not message:
        return jsonify({"status": "no message"}), 200

    chat_id = message.get("chat", {}).get("id")

    # 1️⃣ Handle text messages
    if "text" in message:
        text = message["text"].strip()

        # /start command
        if text == "/start":
            user_states[chat_id] = {"awaiting_id": True, "id": None}
            send_message(chat_id, "Assalomu alaykum! Iltimos, ID raqamingizni kiriting (Google Sheet A ustunidagi raqam).")
            return "ok"

        # If awaiting ID
        if user_states.get(chat_id, {}).get("awaiting_id"):
            user_states[chat_id] = {"awaiting_id": False, "id": text}
            send_message(chat_id, f"Rahmat! Endi {text} ID uchun skrinshot yuboring.")
            return "ok"

        send_message(chat_id, "Iltimos, avval /start buyrug‘ini yuboring yoki skrinshot jo‘nating.")
        return "ok"

    # 2️⃣ Handle photos (must have ID in state)
    if "photo" in message:
        if not user_states.get(chat_id, {}).get("id"):
            send_message(chat_id, "Avval /start buyrug‘i orqali ID raqamingizni kiriting.")
            return "ok"

        file_id = message["photo"][-1]["file_id"]
        try:
            # Download
            local_path = download_telegram_file(file_id)
            filename = os.path.basename(local_path)

            # Upload to Google Drive
            uploaded = drive.upload_file(local_path, filename)
            drive.make_file_public(uploaded["id"])
            link = uploaded.get("webViewLink") or uploaded.get("webContentLink") or uploaded.get("id")

            # Find row by ID (A column == "ID")
            id_value = user_states[chat_id]["id"].strip()
            match_row = sheets.find_row_by_column_value("ID", id_value)
            if not match_row:
                send_message(chat_id, f"Kechirasiz, '{id_value}' ID topilmadi.")
                return "ok"

            # Update Skrinshot column
            sheets.update_cell_by_header(match_row, "Skrinshot", link)
            send_message(chat_id, f"✅ Skrinshot muvaffaqiyatli yuklandi! (ID: {id_value})")

            # Cleanup
            os.remove(local_path)
            return "ok"
        except Exception as e:
            print("ERROR:", e)
            send_message(chat_id, f"❌ Xatolik: {e}")
            return "ok"

    return jsonify({"status": "ignored"}), 200

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    if not WEBHOOK_URL:
        return "Set WEBHOOK_URL env var (must include /webhook)", 400
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook", json={"url": WEBHOOK_URL})
    return jsonify(r.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
