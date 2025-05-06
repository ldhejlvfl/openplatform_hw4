from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import requests
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 設定 LINE BOT 憑證
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "YOUR_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 初始化 SQLite
def init_db():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, msg TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    message = event.message.text
    user_id = event.source.user_id
    reply_text = ask_gemini(message)

    # 回傳id給使用者
    if message == 'id':
        reply_text = TextSendMessage(text=f"{user_id}")
        line_bot_api.reply_message(event.reply_token, reply_text)
        return  # 回傳後就結束，不再執行其他邏輯


    # 將 Gemini 的回覆裁切為最多 5000 字
    if len(reply_text) > 5000:
        reply_text = reply_text[:4997] + "..."

    # 貼圖
    if message == 'sticker':
        reply_text = StickerSendMessage(
            package_id='1070',
            sticker_id='17843'
        )

    # 圖片或影片
    if message == 'image':
        reply_text = ImageSendMessage(
            original_content_url="https://image1.gamme.com.tw/news2/2020/40/12/qJeZpqWbkKWcqqQ.jpg",
            preview_image_url="https://image1.gamme.com.tw/news2/2020/40/12/qJeZpqWbkKWcqqQ.jpg"
        )
    if message == 'video':
        reply_text = VideoSendMessage(
            original_content_url="https://videos.pexels.com/video-files/31532164/13439846_1920_1080_25fps.mp4",
            preview_image_url="https://i0.wp.com/travelfinder.blog/wp-content/uploads/2023/12/img_3643949441866512.jpg?fit=1000%2C667&ssl=1"
        )
    
    # 位置訊息
    if message == 'location':
        reply_text = LocationSendMessage(
            title='Taipei 101',
            address='Taipei',
            latitude=25.03363,
            longitude=121.56481
        )

    else:
        reply_text = TextSendMessage(text=reply_text)

    line_bot_api.reply_message(
        event.reply_token,
        reply_text
    )

    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("INSERT INTO history (user, msg) VALUES (?, ?)", (user_id, message))
    conn.commit()
    conn.close()

def ask_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        return response_data["candidates"][0]["content"]["parts"][0]["text"]
    except requests.exceptions.RequestException as e:
        return f"Gemini 請求失敗: {e}"
    except KeyError as e:
        return f"Gemini 回應結構異常: {e}"




@app.route("/history/<user_id>", methods=["GET", "DELETE"])
def chat_history(user_id):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    if request.method == "GET":
        c.execute("SELECT msg, id FROM history WHERE user = ? ORDER BY id DESC", (user_id,))
        data = c.fetchall()
        conn.close()
        return jsonify([
            {"id": row[1], "msg": row[0]} for row in data
        ])
    elif request.method == "DELETE":
        c.execute("DELETE FROM history WHERE user = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "deleted", "user": user_id})


@app.route("/", methods=["GET"])
def index():
    return "LINE Gemini Bot is running."

if __name__ == "__main__":
    app.run(debug=True)
