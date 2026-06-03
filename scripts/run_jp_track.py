import json
import base64
import time
import subprocess
import urllib.request
import urllib.error
import google.auth
import google.auth.transport.requests
from datetime import datetime
from pathlib import Path
import os
from playwright.sync_api import sync_playwright

BASE = Path.home() / "tw-gov-video"
OUTPUT_DIR = BASE / "output"
INPUT_JSON = OUTPUT_DIR / "selected_articles.json"
JP_JSON = OUTPUT_DIR / "selected_articles_jp.json"
JP_VIDEO = OUTPUT_DIR / "video_jp.mp4"

# 11Labs
API_KEY = "sk_dab768322eb97d8789551989fba23b6ce5ddbdf3e85d847e"
VOICE_ID = "4mU4AFOhdaBEWGnnBxL8"

# GCP 
credentials, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
PROJECT_ID = project or "doit-dic-itteam"

def translate_to_jp(text, is_title=False):
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    token = credentials.token

    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"

    prompt = "Translate the following Traditional Chinese news summary into natural, professional Japanese suitable for a government news broadcast. Output ONLY the Japanese translation, nothing else.\n\n"
    if is_title:
        prompt = "Translate the following Traditional Chinese news title into professional Japanese. Output ONLY the translation, nothing else.\n\n"
    
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt + text}]}],
        "generationConfig": {"temperature": 0.2}
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode('utf-8'))
        return res['candidates'][0]['content']['parts'][0]['text'].strip()

def translate_to_en(text):
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    token = credentials.token

    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"

    prompt = "Translate the following Traditional Chinese news summary into professional English suitable for news subtitles. Output ONLY the English translation, nothing else.\n\n"
    
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt + text}]}],
        "generationConfig": {"temperature": 0.2}
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode('utf-8'))
        return res['candidates'][0]['content']['parts'][0]['text'].strip()

def generate_11labs_tts(text, filename):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_v3",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method="POST")
    raw_path = OUTPUT_DIR / f"raw_jp_{filename}"
    out_path = OUTPUT_DIR / filename
    try:
        with urllib.request.urlopen(req) as response:
            with open(raw_path, "wb") as f:
                f.write(response.read())
        subprocess.run(f"ffmpeg -y -i {raw_path} -af 'apad=pad_dur=0.4' {out_path}", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_path
    except Exception as e:
        print(f"TTS Error for {filename}:", e)
        return None

def create_single_slide_html(slide_type, data, img_path=""):
    font_family = "'Noto Sans JP', sans-serif"
    
    if slide_type == "intro":
        body_content = f"""
        <div class="slide title-slide" style="display: flex;">
            <div class="badge">FOCUS NEWS</div>
            <h1>{data['title']}</h1>
            <h2>{data.get('date', '')}</h2>
            <h3 style="font-family: 'Noto Sans JP', sans-serif; font-size: 40px; color: #7f8c8d; margin-top: 30px;">本動画と音声はAIによって自動生成されました</h3>
        </div>
        """
    elif slide_type == "headlines":
        # Need to gather the headlines. We can just read the JSON file again or pass it. 
        # But wait, we can just inject the list. Let's do it hacky since we have 'items' in main, but not here.
        # Actually, let's just make it a static slide for now if we can't easily pass items.
        # Wait, I can read it!
        with open("/home/benliangcs/tw-gov-video/output/selected_articles_jp.json", "r") as f:
            try:
                jp_data = json.load(f)
                content_items = [i for i in jp_data.get("selected", []) if i.get("type") == "content"]
            except:
                content_items = []
        
        list_html = ""
        for i, c_item in enumerate(content_items):
            list_html += f"<li><span class='num'>{i+1}</span>{c_item.get('title', '')}</li>"
            
        body_content = f"""
        <div class="slide" style="display: flex; width: 100%;">
            <div class="content-box" style="width: 80%; height: auto;">
                <h2 class="slide-title">{data['title']}</h2>
                <ul class="headlines-list" style="list-style: none; padding: 0; margin: 0; font-size: 38px; line-height: 1.6; font-weight: 700;">
                    {list_html}
                </ul>
            </div>
        </div>
        """
        
    elif slide_type == "content":
        # We need to render local image base64 if it's local
        if img_path.startswith("http"):
            src = img_path
        else:
            try:
                with open(img_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode()
                    src = f"data:image/jpeg;base64,{b64_data}"
            except:
                src = ""
                
        body_content = f"""
        <div class="slide content-slide" style="display: flex;">
            <div class="content-box">
                <h2 class="slide-title">{data['title']}</h2>
                <div class="layout-split">
                    <div class="text-column">
                        <div class="label" style="font-size: 20px; margin-bottom: 8px;">推薦原因</div>
                        <p class="script-text" style="font-size: 22px; color: #555; margin-bottom: 15px;">{data.get('reason', '')}</p>
                        <div class="label" style="font-size: 20px; margin-bottom: 8px;">播報稿</div>
                        <p class="script-text">{data['script']}</p>
                    </div>
                    <div class="image-column">
                        <img src="{src}" class="content-img">
                    </div>
                </div>
            </div>
        </div>
        """
    else:
        body_content = f"""
        <div class="slide outro-slide" style="display: flex;">
            <h1>{data['title']}</h1>
            <h2>{data['script']}</h2>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1920, height=1080, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Noto+Sans+JP:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        body, html {{
            margin: 0; padding: 0; width: 1920px; height: 1080px;
            background-color: #f8f9fa;
            background-image: radial-gradient(#bdc3c7 2px, transparent 2px);
            background-size: 40px 40px;
            font-family: {font_family};
            overflow: hidden; color: #2c3e50; position: relative;
        }}
        .bg-circle {{ position: absolute; border-radius: 50%; background: linear-gradient(135deg, #e0eafc 0%, #cfdef3 100%); opacity: 0.6; z-index: -1; }}
        .bg-c1 {{ width: 800px; height: 800px; top: -200px; right: -200px; }}
        .bg-c2 {{ width: 600px; height: 600px; bottom: -150px; left: -100px; }}
        .slide {{ width: 1920px; height: 1080px; position: absolute; top: 0; left: 0; flex-direction: column; align-items: center; justify-content: center; padding: 80px; box-sizing: border-box; }}
        
        .title-slide h1 {{ font-family: 'Dela Gothic One', sans-serif; font-size: 160px; font-weight: normal; color: #2c3e50; margin: 0; text-align: center; text-shadow: 6px 6px 0px rgba(52, 152, 219, 0.2); }}
        .title-slide h2 {{ font-size: 80px; font-weight: bold; color: #34495e; margin: 20px 0 0 0; }}
        .title-slide .badge {{ background: #2c3e50; color: white; padding: 15px 40px; border-radius: 5px; font-size: 36px; font-weight: bold; margin-bottom: 40px; letter-spacing: 2px; text-transform: uppercase; }}

        .content-box {{ background: white; border-radius: 20px; padding: 50px 70px; width: 90%; height: 80%; box-shadow: 0 25px 60px rgba(0,0,0,0.08); display: flex; flex-direction: column; position: relative; z-index: 10; margin-bottom: 50px; }}
        .slide-title {{ font-weight: 900; font-size: 36px; color: #2980b9; margin: 0 0 15px 0; line-height: 1.3; border-bottom: 4px solid #f1c40f; padding-bottom: 10px; }}
        .headlines-list li {{ margin-bottom: 25px; display: flex; align-items: center; color: #2c3e50; }}
        .headlines-list .num {{ background: #e74c3c; color: white; border-radius: 50%; width: 60px; height: 60px; display: inline-flex; justify-content: center; align-items: center; margin-right: 25px; font-size: 30px; font-weight: bold; flex-shrink: 0; }}
        .layout-split {{ display: flex; flex: 1; gap: 50px; height: calc(100% - 100px); }}
        .text-column {{ flex: 1.2; display: flex; flex-direction: column; justify-content: center; }}
        .image-column {{ flex: 1; display: flex; justify-content: center; align-items: center; border-radius: 15px; overflow: hidden; position: relative; background: #ecf0f1; box-shadow: inset 0 0 20px rgba(0,0,0,0.05); }}
        .content-img {{ width: 100%; height: 100%; object-fit: cover; border-radius: 15px; border: 3px solid rgba(189, 195, 199, 0.4); box-sizing: border-box; }}
        .label {{ font-weight: 900; color: #e74c3c; font-size: 20px; margin-bottom: 10px; display: inline-block; border-left: 8px solid #e74c3c; padding-left: 15px; text-transform: uppercase; letter-spacing: 1px; }}
        .script-text {{ font-size: 28px; line-height: 1.5; color: #34495e; margin: 0; font-weight: 700; }}

        .outro-slide h1 {{ font-weight: 900; font-size: 140px; color: #2c3e50; margin: 0 0 30px 0; text-align: center; }}
        .outro-slide h2 {{ color: #e74c3c; font-size: 70px; margin:0; text-align: center; }}
        
        .subtitle-box {{ position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.85); color: #fff; font-size: 38px; font-weight: 700; padding: 15px 40px; border-radius: 10px; width: 85%; text-align: center; line-height: 1.4; font-family: sans-serif; box-shadow: 0 10px 20px rgba(0,0,0,0.2); z-index: 100; border: 2px solid rgba(255,255,255,0.2); }}
    </style>
</head>
<body>
    <div class="bg-circle bg-c1"></div>
    <div class="bg-circle bg-c2"></div>
    {body_content}
    <script>
        window.addEventListener('load', function() {{
            const col = document.querySelector('.text-column');
            if (!col) return;
            const elements = document.querySelectorAll('.slide-title, .script-text, .label');
            let reduce = 0;
            // The layout-split parent has a fixed height, so if text-column overflows its height, scrollHeight will be greater.
            // Let's also check if any specific text element is overflowing horizontally if we want, but height is the main issue.
            while (col.scrollHeight > col.clientHeight && reduce < 30) {{
                reduce++;
                elements.forEach(el => {{
                    const style = window.getComputedStyle(el);
                    const size = parseFloat(style.fontSize);
                    el.style.fontSize = (size - 1) + 'px';
                    const lineHeight = parseFloat(style.lineHeight);
                    if (!isNaN(lineHeight)) {{
                        el.style.lineHeight = (lineHeight - 1) + 'px';
                    }}
                }});
            }}
        }});
    </script>
</body>
</html>
"""
    out_html = OUTPUT_DIR / f"slide_jp_{slide_type}.html"
    out_html.write_text(html, encoding="utf-8")
    return out_html

def make_clip(img_path, audio_path, out_path):
    cmd = f"ffmpeg -y -loop 1 -framerate 25 -i {img_path} -i {audio_path} -c:v libx264 -preset veryfast -tune stillimage -c:a aac -b:a 192k -pix_fmt yuv420p -shortest -fflags +shortest -max_muxing_queue_size 1024 {out_path}"
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    if not INPUT_JSON.exists():
        print("No articles found.")
        return

    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    items = data.get("selected", [])

    print("Translating articles to Japanese...")
    jp_items = []
    
    # 1. Intro
    jp_items.append({
        "type": "intro",
        "title": f"台北市政ニュース",
        "date": f"{datetime.now().strftime('%Y-%m-%d')}",
        "script": "",
        "tts": "台北市政ニュース。本動画はAIによって自動生成されました。"
    })
    
    # 2. Headlines
    headlines_text = "今日の主なニュースです。"
    jp_items.append({
        "type": "headlines",
        "title": "今日のヘッドライン",
        "script": "",
        "tts": headlines_text
    })
    
    # 3. Content
    for idx, item in enumerate(items):
        print(f"Translating article {idx+1}...")
        jp_title = translate_to_jp(item.get("title", ""), is_title=True)
        jp_script = translate_to_jp(item.get("script", ""))
        jp_reason = translate_to_jp(item.get("reason", ""))
        
        # Local image or fallback
        img_url = item.get("image_url", "")
        
        jp_items.append({
            "type": "content",
            "title": jp_title,
            "script": jp_script,
            "reason": jp_reason,
            "tts": jp_script,
            "image_url": img_url,
            "source_url": item.get("source_url", "")
        })
        time.sleep(2) # Prevent rate limits
        
    # 3. Outro
    jp_items.append({
        "type": "outro",
        "title": "おわり",
        "script": "ご視聴ありがとうございました",
        "tts": "本日の台北市政ニュースは以上です。ご視聴ありがとうございました。また明日お会いしましょう！"
    })

    # Save translation for youtube upload metadata
    JP_JSON.write_text(json.dumps({"selected": jp_items}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Generating Japanese TTS and rendering video...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        clips = []
        for idx, slide in enumerate(jp_items):
            audio_path = generate_11labs_tts(slide["tts"], f"voice_jp_{idx}.mp3")
            
            html_path = create_single_slide_html(slide["type"], slide, slide.get("image_url", ""))
            page.goto(f"file://{os.path.abspath(html_path)}")
            page.wait_for_timeout(500)
            
            img_path = OUTPUT_DIR / f"frame_jp_{idx}.png"
            page.screenshot(path=str(img_path))
            
            clip_path = OUTPUT_DIR / f"clip_jp_{idx}.mp4"
            make_clip(img_path, audio_path, clip_path)
            clips.append(f"file '{clip_path.name}'")
                
        concat_file = OUTPUT_DIR / f"jp_concat.txt"
        concat_file.write_text("\n".join(clips))
        
        concat_cmd = f"cd {OUTPUT_DIR} && ffmpeg -y -f concat -safe 0 -i {concat_file.name} -c copy {JP_VIDEO.name}"
        subprocess.run(concat_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print(f"Generated {JP_VIDEO}")
        browser.close()

if __name__ == "__main__":
    main()
