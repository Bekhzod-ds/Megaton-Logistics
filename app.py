import os
import json
import tempfile
import requests
import base64
from flask import Flask, request, jsonify
from datetime import datetime

from google_drive import DriveHelper
from google_sheets import SheetsHelper

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GSERVICE_JSON_B64 = os.environ.get("GSERVICE_JSON_B64")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")  # Shared Drive folder ID
PORT = int(os.environ.get("PORT", 5000))

if not BOT_TOKEN or not SHEET_ID or not GSERVICE_JSON_B64:
    raise RuntimeError("BOT_TOKEN, SHEET_ID and GSERVICE_JSON_B64 env vars are required")

service_json = json.loads(base64.b64decode(GSERVICE_JSON_B64).decode("utf-8"))

app = Flask(__name__)

drive = DriveHelper(service_json, folder_id=DRIVE_FOLDER_ID)
sheets = SheetsHelper(service_json, sheet_id=SHEET_ID)

TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{file_path}"
TELEGRAM_GETFILE_URL = "https://api.telegram.org/bot{token}/getFile"

# Conversation state tracking
user_states = {}  # {chat_id: {"step": str, "id": str}}

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
        raise RuntimeError("Failed to getFile: " + str(data))
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
    text_msg = message.get("text")
    photo_msg = message.get("photo")

    # Step 1: Handle /start
    if text_msg and text_msg.strip().lower() == "/start":
        user_states[chat_id] = {"step": "awaiting_id"}
        send_message(chat_id, "Assalomu alaykum! Iltimos, transport ID raqamini yuboring (Google Sheet A ustuni).")
        return jsonify({"status": "awaiting_id"}), 200

    # Step 2: If awaiting ID
    if chat_id in user_states and user_states[chat_id]["step"] == "awaiting_id":
        if text_msg:
            user_states[chat_id]["id"] = text_msg.strip()
            user_states[chat_id]["step"] = "awaiting_photo"
            send_message(chat_id, f"Rahmat! Endi transport ID `{text_msg.strip()}` uchun skrinshot yuboring.")
        return jsonify({"status": "id_received"}), 200

    # Step 3: If awaiting photo
    if chat_id in user_states and user_states[chat_id]["step"] == "awaiting_photo":
        if photo_msg:
            try:
                file_id = photo_msg[-1]["file_id"]
                local_path = download_telegram_file(file_id)
                filename = os.path.basename(local_path)

                # Upload to Drive
                uploaded = drive.upload_file(local_path, filename)
                drive.make_file_public(uploaded["id"])
                link = uploaded.get("webViewLink") or uploaded.get("webContentLink")

                # Update Sheets
                match_row = sheets.find_row_by_column_value("ID", user_states[chat_id]["id"])
                if match_row:
                    sheets.update_cell_by_header(match_row, "Skrinshot", link)
                    send_message(chat_id, "✅ Skrinshot muvaffaqiyatli yuklandi va Google Sheet yangilandi.")
                else:
                    send_message(chat_id, "❌ Bunday ID topilmadi. Iltimos, qaytadan /start bosing.")

                os.remove(local_path)
                # Reset state
                user_states.pop(chat_id, None)
            except Exception as e:
                send_message(chat_id, f"❌ Xatolik: {e}")
        else:
            send_message(chat_id, "Iltimos, skrinshot yuboring.")
        return jsonify({"status": "photo_processed"}), 200

    return jsonify({"status": "ignored"}), 200

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    if not WEBHOOK_URL:
        return "Set WEBHOOK_URL env var (must include /webhook)", 400
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    r = requests.post(url, json={"url": WEBHOOK_URL})
    return jsonify(r.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
