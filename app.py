import os
import json
import base64
import tempfile
import requests
from flask import Flask, request, jsonify
from datetime import datetime

from google_drive import DriveHelper
from google_sheets import SheetsHelper

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GSERVICE_JSON_B64 = os.environ.get("GSERVICE_JSON_B64")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")
PORT = int(os.environ.get("PORT", 5000))

if not BOT_TOKEN or not SHEET_ID or not GSERVICE_JSON_B64:
    raise RuntimeError("BOT_TOKEN, SHEET_ID and GSERVICE_JSON_B64 env vars are required")

service_json = json.loads(base64.b64decode(GSERVICE_JSON_B64).decode("utf-8"))

app = Flask(__name__)

drive = DriveHelper(service_json, folder_id=DRIVE_FOLDER_ID)
sheets = SheetsHelper(service_json, sheet_id=SHEET_ID)

TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{file_path}"
TELEGRAM_GETFILE_URL = "https://api.telegram.org/bot{token}/getFile"
TELEGRAM_SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# store user states in memory {chat_id: {"waiting_for_id": bool, "id": str}}
user_states = {}

def send_message(chat_id, text):
    requests.post(TELEGRAM_SEND_URL, json={"chat_id": chat_id, "text": text})

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
    text = message.get("text", "").strip() if "text" in message else None

    # Handle /start
    if text and text.lower() == "/start":
        user_states[chat_id] = {"waiting_for_id": True, "id": None}
        send_message(chat_id, "Salom! Iltimos, Google Sheet dagi ID raqamingizni kiriting (A ustuni).")
        return jsonify({"status": "ok"}), 200

    # Waiting for ID input
    if user_states.get(chat_id, {}).get("waiting_for_id") and text:
        user_states[chat_id]["id"] = text
        user_states[chat_id]["waiting_for_id"] = False
        send_message(chat_id, f"Rahmat! Endi skrinshetingizni yuboring.")
        return jsonify({"status": "ok"}), 200

    # Handle photo/document
    if "photo" in message or ("document" in message and message["document"].get("mime_type", "").startswith("image")):
        user_id = user_states.get(chat_id, {}).get("id")
        if not user_id:
            send_message(chat_id, "Iltimos, avval /start buyrug'ini yuboring va ID raqamingizni kiriting.")
            return jsonify({"status": "no id"}), 200

        file_id = None
        if "photo" in message:
            file_id = message["photo"][-1]["file_id"]
        else:
            file_id = message["document"]["file_id"]

        try:
            local_path = download_telegram_file(file_id)
            filename = os.path.basename(local_path)

            # Upload to Drive
            uploaded = drive.upload_file(local_path, filename)
            drive.make_file_public(uploaded["id"])
            link = uploaded.get("webViewLink") or uploaded.get("webContentLink") or uploaded["id"]

            # Update Google Sheet
            match_row = sheets.find_row_by_column_value("ID", user_id)
            if match_row:
                sheets.update_cell_by_header(match_row, "Skrinshot", link)
                send_message(chat_id, "✅ Skrinshot muvaffaqiyatli yuklandi!")
            else:
                headers = sheets.get_headers()
                row = [""] * len(headers)
                if "Sana" in headers:
                    row[headers.index("Sana")] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if "ID" in headers:
                    row[headers.index("ID")] = user_id
                if "Skrinshot" in headers:
                    row[headers.index("Skrinshot")] = link
                sheets.append_row(row)
                send_message(chat_id, "✅ Yangi qator qo'shildi va skrinshetingiz yuklandi!")

            os.remove(local_path)
        except Exception as e:
            send_message(chat_id, f"❌ Xatolik: {str(e)}")
        return jsonify({"status": "ok"}), 200

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
