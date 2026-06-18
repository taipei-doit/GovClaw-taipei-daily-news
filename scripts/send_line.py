import urllib.request
import urllib.error
import json
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "tw-gov-video"
OUTPUT_DIR = BASE / "output"
INPUT_JSON = OUTPUT_DIR / "selected_articles.json"
YOUTUBE_URL_FILE = OUTPUT_DIR / "latest_youtube_url.txt"

# The long-lived channel access token you provided
LINE_ACCESS_TOKEN = "OzxY2CAnLdr+y7+5CYXPz+zmn/AzGd8HWK3zMNhwp70zOzLY67nbNAVM4tqlHQCwTiYEKNGQy/t5R9rSR9nB4ba3bcOEMFE8vhduey7UkCIgo8/AXEPewVLwarVDtsYciQukhcCb3rA1Dig+84lbOAdB04t89/1O/w1cDnyilFU="

WEB_PORTAL_URL = "https://taipei-doit.github.io/GovClaw-taipei-daily-news/"
SPOTIFY_URL = "https://open.spotify.com/show/033jJtZiN097aPxw99mHYW"

def build_message_text():
    if not INPUT_JSON.exists():
        return "今日無重點新聞摘要更新。"
        
    try:
        data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
        items = data.get("selected", [])
        today = datetime.now().strftime("%Y-%m-%d")
        
        msg = f"📣 臺北市政府新聞摘要 | {today}\n"
        msg += "為您整理今日五大市政重點：\n\n"
        
        for idx, item in enumerate(items, 1):
            title = item.get("title", "")
            msg += f"[{idx}] {title}\n"
            
        msg += "\n🌐 觀看完整影片與新聞圖文：\n"
        msg += f"{WEB_PORTAL_URL}"
        
        return msg
    except Exception as e:
        print(f"Error building message text: {e}")
        return "新聞摘要產生失敗，請稍後再試。"

def build_flex_message():
    alt_text = build_message_text()
    
    youtube_url = "https://www.youtube.com/@CiviClaw" # fallback
    if YOUTUBE_URL_FILE.exists():
        youtube_url = YOUTUBE_URL_FILE.read_text().strip()

    if not INPUT_JSON.exists():
        return [{"type": "text", "text": "今日無重點新聞摘要更新。"}]
        
    try:
        data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
        items = data.get("selected", [])
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Build article list for the flex body
        body_contents = [
            {
                "type": "text",
                "text": "今日重點新聞提要",
                "weight": "bold",
                "size": "md",
                "margin": "md",
                "color": "#e74c3c"
            }
        ]
        
        for idx, item in enumerate(items, 1):
            title = item.get("title", "")
            body_contents.append({
                "type": "box",
                "layout": "horizontal",
                "margin": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{idx}.",
                        "size": "sm",
                        "color": "#888888",
                        "flex": 1
                    },
                    {
                        "type": "text",
                        "text": title,
                        "size": "sm",
                        "color": "#333333",
                        "wrap": True,
                        "flex": 9
                    }
                ]
            })

        flex_payload = {
            "type": "flex",
            "altText": alt_text,
            "contents": {
                "type": "bubble",
                "size": "mega",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#2c3e50",
                    "paddingAll": "20px",
                    "contents": [
                        {
                            "type": "text",
                            "text": "臺北市政府新聞摘要",
                            "weight": "bold",
                            "size": "xl",
                            "color": "#ffffff"
                        },
                        {
                            "type": "text",
                            "text": today,
                            "color": "#ffffffcc",
                            "size": "sm",
                            "margin": "sm"
                        }
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": body_contents
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#3498db",
                            "height": "sm",
                            "action": {
                                "type": "uri",
                                "label": "🌐 閱讀圖文摘要",
                                "uri": WEB_PORTAL_URL
                            }
                        },
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#e74c3c",
                            "height": "sm",
                            "action": {
                                "type": "uri",
                                "label": "📺 YouTube 影片",
                                "uri": youtube_url
                            }
                        },
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#1DB954",
                            "height": "sm",
                            "action": {
                                "type": "uri",
                                "label": "🎧 Spotify 收聽",
                                "uri": SPOTIFY_URL
                            }
                        }
                    ]
                }
            }
        }
        return [flex_payload]
        
    except Exception as e:
        print(f"Error building flex message: {e}")
        return [{"type": "text", "text": alt_text}]

def broadcast_message(messages):
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {
        "messages": messages
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            res = response.read().decode('utf-8')
            print("LINE Broadcast Success:", res)
    except urllib.error.HTTPError as e:
        print("LINE Broadcast Failed:", e.code, e.read().decode('utf-8'))
    except Exception as e:
        print("LINE Broadcast Error:", e)

if __name__ == "__main__":
    msgs = build_flex_message()
    broadcast_message(msgs)
    
    # Safely update heartbeat-state.json to prevent duplicate pipeline runs
    state_file = Path.home() / ".openclaw" / "workspace" / "memory" / "heartbeat-state.json"
    try:
        if state_file.exists():
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
        else:
            state_data = {}
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        state_data["5pm_pipeline_date"] = today_str
        if "lastChecks" not in state_data:
            state_data["lastChecks"] = {}
        
        state_file.write_text(json.dumps(state_data, indent=2), encoding="utf-8")
        print(f"Successfully marked 5pm_pipeline_date as completed for {today_str}")
    except Exception as e:
        print(f"Failed to update heartbeat state: {e}")
