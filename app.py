import os
import json
import base64
import tempfile
import requests
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from google_drive import DriveHelper
from google_sheets import SheetsHelper

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GSERVICE_JSON_B64 = os.environ.get("GSERVICE_JSON_B64")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")
PORT = int(os.environ.get("PORT", 5000))

if not BOT_TOKEN or not SHEET_ID or not GSERVICE_JSON_B64 or not DRIVE_FOLDER_ID:
    raise RuntimeError("BOT_TOKEN, SHEET_ID, GSERVICE_JSON_B64, DRIVE_FOLDER_ID are required")

# Decode service account JSON and create credentials
service_json_dict = json.loads(base64.b64decode(GSERVICE_JSON_B64).decode("utf-8"))
credentials = service_account.Credentials.from_service_account_info(service_json_dict)

app = Flask(__name__)

drive = DriveHelper(credentials, folder_id=DRIVE_FOLDER_ID)
sheets = SheetsHelper(credentials, sheet_id=SHEET_ID)

# Track conversation state
user_states = {}  # {chat_id: {"step": "awaiting_id", "row_id": None}}

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" not in data:
        return jsonify({"status": "no_message"}), 200

    chat_id = data["message"]["chat"]["id"]

    # Handle /start
    if "text" in data["message"] and data["message"]["text"] == "/start":
        user_states[chat_id] = {"step": "awaiting_id", "row_id": None}
        send_message(chat_id, "Salom! Iltimos, qaysi ID uchun skrinshot yuklamoqchisiz, ID raqamini yuboring.")
        return jsonify({"status": "awaiting_id"}), 200

    # Awaiting ID
    if chat_id in user_states and user_states[chat_id]["step"] == "awaiting_id":
        if "text" in data["message"]:
            row_id = data["message"]["text"].strip()
            user_states[chat_id]["row_id"] = row_id
            user_states[chat_id]["step"] = "awaiting_photo"
            send_message(chat_id, f"Rahmat! Endi ID {row_id} uchun skrinshot rasmini yuboring.")
            return jsonify({"status": "awaiting_photo"}), 200

    # Awaiting photo
    if chat_id in user_states and user_states[chat_id]["step"] == "awaiting_photo":
        if "photo" in data["message"]:
            file_id = data["message"]["photo"][-1]["file_id"]

            # Get file path
            file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]

            # Download
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            tmp_file = tempfile.NamedTemporaryFile(delete=False)
            tmp_file.write(requests.get(file_url).content)
            tmp_file.close()

            # Upload to Drive
            uploaded_file = drive.upload_file(tmp_file.name, f"{user_states[chat_id]['row_id']}_screenshot.jpg")
            drive.make_file_public(uploaded_file["id"])
            file_link = uploaded_file["webViewLink"]

            # Update Sheets
            sheets.update_screenshot_link(user_states[chat_id]["row_id"], file_link)

            send_message(chat_id, f"Skrinshot yuklandi va Google Sheets-ga qo‘shildi!\nKo‘rish: {file_link}")

            # Reset state
            del user_states[chat_id]
            return jsonify({"status": "photo_uploaded"}), 200

    send_message(chat_id, "Iltimos, /start buyrug‘i bilan boshlang.")
    return jsonify({"status": "unknown"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
