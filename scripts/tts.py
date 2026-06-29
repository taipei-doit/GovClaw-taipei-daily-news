import json
import os
import base64
import time
import subprocess
import urllib.request
import urllib.error
import google.auth
import google.auth.transport.requests
from datetime import datetime
from pathlib import Path

from config import BASE_DIR as BASE, OUTPUT_DIR, INPUT_JSON

credentials, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
PROJECT_ID = project or os.getenv("GCP_PROJECT_ID")

def synthesize_text(text, out_file):
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    token = credentials.token

    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/gemini-3.1-flash-tts-preview:generateContent"

    # We will use "Puck" for energetic male voice.
    # We replace the break tags as Gemini TTS does not officially support SSML <break> directly in prompt, 
    # though it might support some inline tags.
    clean_text = text.replace('<break time="3s"/>', '。')
    # Enforce Mandarin by injecting an explicit instruction
    clean_text = clean_text.replace("！", "。").replace("!", "。")
    clean_text = "請以專業的新聞主播語氣，語調平穩自然、不過度戲劇化，用流利的台灣國語朗讀以下新聞內容：" + clean_text
    
    payload = {
        "contents": [{"role": "user", "parts": [{"text": clean_text}]}],
        "generationConfig": {
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": "Puck"
                    }
                }
            }
        }
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            part = res['candidates'][0]['content']['parts'][0]
            if 'inlineData' in part:
                b64_audio = part['inlineData']['data']
                wav_path = str(out_file).replace('.mp3', '.wav')
                with open(wav_path, "wb") as f:
                    f.write(base64.b64decode(b64_audio))
                
                # Convert the returned 24kHz L16 WAV (which might be headerless or standard WAV) to MP3
                # Actually, the MIME is audio/l16. This means it's headerless raw PCM data!
                mime = part['inlineData']['mimeType']
                if 'audio/l16' in mime:
                    subprocess.run(f'ffmpeg -y -f s16le -ar 24000 -ac 1 -i "{wav_path}" -codec:a libmp3lame -qscale:a 2 "{out_file}"', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run(f'ffmpeg -y -i "{wav_path}" -codec:a libmp3lame -qscale:a 2 "{out_file}"', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                print(f"Saved TTS audio to {out_file}")
                return True
            else:
                print(f"No inline data for text: {text[:20]}")
                return False
    except Exception as e:
        print(f"Failed to synthesize audio for {out_file}: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))
        return False

def main():
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_JSON}")

    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    items = data.get("selected", [])

    if not items:
        raise ValueError("No selected items found in selected_articles.json")

    intro_text = f"歡迎收看臺北市政府每日新聞摘要。本影片由 AI 自動生成。"
    synthesize_text(intro_text, OUTPUT_DIR / "voice_intro.mp3")
    
    headlines_text = "以下是今天的重點新聞提要。<break time=\"3s\"/>"
    synthesize_text(headlines_text, OUTPUT_DIR / "voice_headlines.mp3")
    
    hq_mp3 = str(OUTPUT_DIR / "voice_headlines.mp3")
    pad_mp3 = str(OUTPUT_DIR / "voice_headlines_padded.mp3")
    subprocess.run(f'ffmpeg -y -i "{hq_mp3}" -af "apad=pad_dur=3" "{pad_mp3}" && mv "{pad_mp3}" "{hq_mp3}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    for idx, item in enumerate(items):
        text = (item.get("script") or "").strip()
        out_file = OUTPUT_DIR / f"voice_{idx}.mp3"
        if not text:
            # No script for this slide: emit 1s of silence so render_video stays index-aligned
            subprocess.run(f'ffmpeg -y -f lavfi -i anullsrc=r=24000:cl=mono -t 1 "{out_file}"', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            continue
        synthesize_text(text, out_file)
        
    outro_text = "以上是今天的臺北市政新聞摘要。感謝您的收看，我們明天見！"
    synthesize_text(outro_text, OUTPUT_DIR / "voice_outro.mp3")

if __name__ == "__main__":
    main()
