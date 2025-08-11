import os
import json
import tempfile
import requests
import base64
from flask import Flask, request, jsonify
from datetime import datetime

from google_drive import DriveHelper
from google_sheets import SheetsHelper

# ==== ENV VARS ====
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # required
SHEET_ID = os.environ.get("SHEET_ID")    # required
GSERVICE_JSON_B64 = os.environ.get("GSERVICE_JSON_B64")  # required
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")  # optional
PORT = int(os.environ.get("PORT", 5000))

if not BOT_TOKEN or not SHEET_ID or not GSERVICE_JSON_B64:
    raise RuntimeError("BOT_TOKEN, SHEET_ID and GSERVICE_JSON_B64 env vars are required")

# decode service account JSON
service_json = json.loads(base64.b64decode(GSERVICE_JSON_B64).decode("utf-8"))

app = Flask(__name__)

drive = DriveHelper(service_json, folder_id=DRIVE_FOLDER_ID)
sheets = SheetsHelper(service_json, sheet_id=SHEET_ID)

# Telegram URLs
TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{file_path}"
TELEGRAM_GETFILE_URL = "https://api.telegram.org/bot{token}/getFile"

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

    # handle /start
    if "text" in message and message["text"].strip() == "/start":
        send_message(chat_id, "Salom! 📸 Iltimos, ID raqamingizni yozgan holda rasm yuboring.\n\n"
                              "Masalan: \n1️⃣ Rasm tanlang\n2️⃣ Caption qismida ID kiriting\n3️⃣ Yuboring ✅")
        return jsonify({"status": "start sent"}), 200

    # only handle images with caption
    caption = message.get("caption", "").strip()
    if not caption:
        send_message(chat_id, "⚠️ Iltimos, rasmni yuborishda caption (izoh) qismiga ID raqamingizni yozing.")
        return jsonify({"status": "no caption"}), 200

    if "photo" in message:
        file_id = message["photo"][-1]["file_id"]
    elif "document" in message and message["document"]["mime_type"].startswith("image"):
        file_id = message["document"]["file_id"]
    else:
        return jsonify({"status": "ignored"}), 200

    try:
        # download
        local_path = download_telegram_file(file_id)
        filename = os.path.basename(local_path)

        # upload to drive
        uploaded = drive.upload_file(local_path, filename)
        drive.make_file_public(uploaded["id"])
        link = uploaded.get("webViewLink") or uploaded.get("webContentLink")

        # find row in Google Sheets by "A" column (assumed header is "ID")
        row_num = sheets.find_row_by_column_value("ID", caption)
        if not row_num:
            send_message(chat_id, f"❌ ID {caption} topilmadi. Iltimos, tekshirib qayta yuboring.")
            return jsonify({"status": "id not found"}), 200

        sheets.update_cell_by_header(row_num, "Skrinshot", link)
        send_message(chat_id, f"✅ ID {caption} uchun rasm muvaffaqiyatli yuklandi!")
        os.remove(local_path)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        send_message(chat_id, f"❌ Xatolik: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    if not WEBHOOK_URL:
        return "WEBHOOK_URL env var kerak", 400
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    r = requests.post(url, json={"url": WEBHOOK_URL})
    return jsonify(r.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
