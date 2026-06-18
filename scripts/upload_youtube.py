from pathlib import Path
import json
from datetime import datetime
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google_auth_oauthlib.flow
import google.oauth2.credentials
import google.auth.transport.requests

import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]

BASE = Path.home() / "tw-gov-video"
OUTPUT_DIR = BASE / "output"
SCRIPTS_DIR = BASE / "scripts"

INPUT_JSON = OUTPUT_DIR / "selected_articles.json"
VIDEO_FILE = OUTPUT_DIR / "video.mp4"
PLAYLIST_ID = "PLYfurwYZZk24nXcwyqPkY6_mUI0W4xP8E"
IS_JAPANESE = False

if len(sys.argv) >= 2:
    INPUT_JSON = Path(sys.argv[1])
if len(sys.argv) >= 3:
    VIDEO_FILE = Path(sys.argv[2])
if len(sys.argv) >= 4:
    PLAYLIST_ID = sys.argv[3]
if "jp" in str(INPUT_JSON):
    IS_JAPANESE = True


THUMBNAIL_FILE = OUTPUT_DIR / "frame_intro.png"
TIMESTAMPS_FILE = OUTPUT_DIR / "youtube_timestamps.txt"
CLIENT_SECRETS_FILE = SCRIPTS_DIR / "client_secrets.json"
CREDENTIALS_FILE = SCRIPTS_DIR / "youtube_credentials.json"
YOUTUBE_URL_FILE = OUTPUT_DIR / "latest_youtube_url.txt"

WEB_PORTAL_URL = "https://taipei-doit.github.io/GovClaw-taipei-daily-news/"
LINE_FRIEND_LINK = "https://page.line.me/290wqpej"

def get_video_metadata():
    if not INPUT_JSON.exists():
        return "每日新聞", "No description available."
    try:
        data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
        items = data.get("selected", [])
        
        if IS_JAPANESE:
            title = f"台北市政ニュース {datetime.now().strftime('%Y-%m-%d')}"
            description_lines = []
            description_lines.append(f"📱 LINE公式アカウントを追加して、毎日のハイライトを自動受信:")
            description_lines.append(f"{LINE_FRIEND_LINK}\n")
            description_lines.append(f"🌐 ウェブサイト版 (ニュースのハイライトと元のリンク):\n{WEB_PORTAL_URL}jp/\n")
            description_lines.append("-" * 30 + "\n")
            description_lines.append("今日の台北市政ニュースのハイライト：\n")
            
            if TIMESTAMPS_FILE.exists():
                description_lines.append("【タイムスタンプ】")
                description_lines.append(TIMESTAMPS_FILE.read_text().strip())
                description_lines.append("\n" + "-" * 30 + "\n")
        else:
            title = f"每日新聞 {datetime.now().strftime('%Y-%m-%d')}"
            description_lines = []
            description_lines.append(f"📱 加入 LINE 官方帳號，每日自動接收圖文摘要:")
            description_lines.append(f"{LINE_FRIEND_LINK}\n")
            description_lines.append(f"🌐 網站版 (新聞重點摘要與原出處連結):\n{WEB_PORTAL_URL}\n")
            description_lines.append("-" * 30 + "\n")
            description_lines.append("今日臺北市政重點新聞摘要：\n")
            
            if TIMESTAMPS_FILE.exists():
                description_lines.append("【新聞段落時間軸】")
                description_lines.append(TIMESTAMPS_FILE.read_text().strip())
                description_lines.append("\n" + "-" * 30 + "\n")
        
        for idx, item in enumerate(items, 1):
            art_title = item.get('title', '')
            art_script = item.get('script', '')
            source_url = item.get('source_url', '')
            description_lines.append(f"{idx}. {art_title}\n{art_script}")
            if source_url:
                if IS_JAPANESE:
                    description_lines.append(f"🔗 リンク:\n{source_url}")
                else:
                    description_lines.append(f"🔗 原文與聯絡資訊連結:\n{source_url}")
            description_lines.append("\n")
            
        return title, "\n".join(description_lines)
    except Exception as e:
        print("Error parsing json metadata:", e)
        return "每日新聞" if not IS_JAPANESE else "台北市政ニュース", "Error formatting description."

def get_authenticated_service():
    creds = None
    if os.path.exists(CREDENTIALS_FILE):
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file(CREDENTIALS_FILE, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=False)
            
            with open(CREDENTIALS_FILE, 'w') as token:
                token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def main():
    print("Starting YouTube Upload Process...")
    youtube = get_authenticated_service()
    if not youtube: return

    title, desc = get_video_metadata()
    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": desc, "categoryId": "25"},
                "status": {"privacyStatus": "unlisted"}
            },
            media_body=MediaFileUpload(str(VIDEO_FILE), chunksize=-1, resumable=True)
        )
        print("Uploading Video...")
        response = request.execute()
        video_id = response.get('id')
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"Video Success! URL: {video_url}")
        
        # Save URL so deploy_web.py can read it and embed it
        if not IS_JAPANESE:
            YOUTUBE_URL_FILE.write_text(video_url)
        
        if IS_JAPANESE:
            jp_thumb = OUTPUT_DIR / "frame_jp_0.png"
            if jp_thumb.exists():
                print(f"Uploading Custom Thumbnail for Japanese: {jp_thumb}")
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(jp_thumb))
                ).execute()
                print("Japanese Thumbnail successfully applied!")
        elif THUMBNAIL_FILE.exists():
            print(f"Uploading Custom Thumbnail: {THUMBNAIL_FILE}")
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(THUMBNAIL_FILE))
            ).execute()
            print("Thumbnail successfully applied!")
            
        # Add to playlist
        if PLAYLIST_ID:
            print(f"Adding video to playlist {PLAYLIST_ID}...")
            try:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": PLAYLIST_ID,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id
                            }
                        }
                    }
                ).execute()
                print("Successfully added to playlist!")
            except Exception as pe:
                print(f"Warning: Failed to add to playlist (Scope might need refresh): {pe}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
