import os
import json
import tempfile
import requests
from flask import Flask, request, jsonify

from google_drive import DriveHelper
from google_sheets import SheetsHelper

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # required
SHEET_ID = os.environ.get("SHEET_ID")    # required
GSERVICE_JSON_B64 = os.environ.get("GSERVICE_JSON_B64")  # required (base64 encoded service account JSON)
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")  # optional: folder to store images (recommended)
PORT = int(os.environ.get("PORT", 5000))

if not BOT_TOKEN or not SHEET_ID or not GSERVICE_JSON_B64:
    raise RuntimeError("BOT_TOKEN, SHEET_ID and GSERVICE_JSON_B64 env vars are required")

# decode service account json
import base64
service_json = json.loads(base64.b64decode(GSERVICE_JSON_B64).decode("utf-8"))

app = Flask(__name__)

drive = DriveHelper(service_json, folder_id=DRIVE_FOLDER_ID)
sheets = SheetsHelper(service_json, sheet_id=SHEET_ID)

TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{file_path}"
TELEGRAM_GETFILE_URL = "https://api.telegram.org/bot{token}/getFile"

def download_telegram_file(file_id):
    # get file_path
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

    # Only handle photos (telegram gives photos array) or document
    message = update.get("message") or update.get("edited_message")
    if not message:
        return jsonify({"status": "no message"}), 200

    chat_id = message.get("chat", {}).get("id")
    caption = message.get("caption") or ""
    # choose highest resolution photo if exists
    photo = None
    if "photo" in message:
        photo = message["photo"][-1]  # last one is biggest
        file_id = photo.get("file_id")
    elif "document" in message and message["document"].get("mime_type", "").startswith("image"):
        file_id = message["document"]["file_id"]
    else:
        # ignore non-image messages
        return jsonify({"status": "ignored - not image"}), 200

    try:
        # download file from Telegram
        local_path = download_telegram_file(file_id)
        filename = os.path.basename(local_path)

        # upload to Google Drive
        uploaded = drive.upload_file(local_path, filename)
        # make shareable
        drive.make_file_public(uploaded["id"])
        link = uploaded.get("webViewLink") or uploaded.get("webContentLink") or uploaded.get("id")

        # handle caption to decide which row to update
        # caption rules:
        #  - if caption is integer -> treat as row number (1-based indexing including header row)
        #  - else try to find row where column "Transport Raqami" == caption (exact match)
        #  - else append a new row with the link in Skrinshot column
        updated = False
        try:
            row_num = int(caption.strip())
            # do not allow writing header row
            if row_num <= 1:
                row_num = 2
            sheets.update_cell_by_header(row_num, "Skrinshot", link)
            updated = True
            msg = f"Updated row {row_num} Skrinshot."
        except Exception:
            # try matching Transport Raqami
            if caption.strip():
                match_row = sheets.find_row_by_column_value("Transport Raqami", caption.strip())
                if match_row:
                    sheets.update_cell_by_header(match_row, "Skrinshot", link)
                    updated = True
                    msg = f"Updated Skrinshot for Transport Raqami '{caption.strip()}' (row {match_row})."

        if not updated:
            # append new row: try to keep columns order: use header list
            headers = sheets.get_headers()
            # populate default values: Date/time in Sana if exists
            from datetime import datetime
            row = [""] * len(headers)
            # set Sana to current date if column exists
            if "Sana" in headers:
                row[headers.index("Sana")] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if "Skrinshot" in headers:
                row[headers.index("Skrinshot")] = link
            sheets.append_row(row)
            msg = "Appended new row with Skrinshot link."

        # cleanup
        try:
            os.remove(local_path)
        except Exception:
            pass

        # optionally notify user (send message back) — use sendMessage
        send_resp = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": chat_id,
            "text": msg
        })
        return jsonify({"status": "ok", "msg": msg}), 200
    except Exception as e:
        # log
        print("ERROR:", str(e))
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": chat_id,
            "text": "Error processing image: " + str(e)
        })
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    # helper route to set webhook from browser (provide WEBHOOK_URL env pointing to /webhook)
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    if not WEBHOOK_URL:
        return "Set WEBHOOK_URL env var (must include /webhook)", 400
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    r = requests.post(url, json={"url": WEBHOOK_URL})
    return jsonify(r.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
