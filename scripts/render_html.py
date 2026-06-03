from pathlib import Path
import json
from datetime import datetime
import os
import urllib.request

BASE = Path.home() / "tw-gov-video"
OUTPUT_DIR = BASE / "output"
INPUT_JSON = OUTPUT_DIR / "selected_articles.json"
HTML_FILE = OUTPUT_DIR / "slides_playwright.html"

def download_image(url, local_path):
    if not url or url.startswith("/"):
        return url
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open(local_path, "wb") as f:
                f.write(response.read())
        return f"file://{local_path}"
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return ""

def generate_html():
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    items = data.get("selected", [])
    today = datetime.now().strftime("%Y-%m-%d")

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1920, height=1080, initial-scale=1.0">
    <title>News Slides</title>
    <link href="https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Noto+Sans+TC:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        @font-face {{
            font-family: 'Dela Local';
            src: url('file:///home/benliangcs/tw-gov-video/output/DelaGothicOne-Regular.ttf');
        }}
        
        body, html {{
            margin: 0;
            padding: 0;
            width: 1920px;
            height: 1080px;
            background-color: #f8f9fa;
            background-image: radial-gradient(#bdc3c7 2px, transparent 2px);
            background-size: 40px 40px;
            font-family: 'Noto Sans TC', sans-serif;
            overflow: hidden;
            color: #2c3e50;
            position: relative;
        }}
        
        .bg-circle {{
            position: absolute;
            border-radius: 50%;
            background: linear-gradient(135deg, #e0eafc 0%, #cfdef3 100%);
            opacity: 0.6;
            z-index: -1;
        }}
        .bg-c1 {{ width: 800px; height: 800px; top: -200px; right: -200px; }}
        .bg-c2 {{ width: 600px; height: 600px; bottom: -150px; left: -100px; }}
        
        .slide {{
            width: 1920px;
            height: 1080px;
            position: absolute;
            top: 0;
            left: 0;
            display: none;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 80px;
            box-sizing: border-box;
            opacity: 1; 
        }}

        .slide.active {{
            display: flex;
        }}

        .title-slide h1 {{
            font-family: 'Dela Local', 'Dela Gothic One', cursive;
            font-size: 210px;
            font-weight: normal;
            color: #2c3e50;
            margin: 0;
            text-shadow: 6px 6px 0px rgba(52, 152, 219, 0.2);
        }}
        .title-slide h2 {{
            font-family: 'Noto Sans TC', sans-serif;
            font-weight: 900;
            font-size: 80px;
            color: #e74c3c;
            margin-top: 20px;
        }}
        .title-slide .badge {{
            background: #2c3e50;
            color: white;
            padding: 15px 40px;
            border-radius: 5px;
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 40px;
            letter-spacing: 2px;
            text-transform: uppercase;
        }}

        .content-box {{
            background: white;
            border-radius: 20px;
            padding: 60px 80px;
            width: 90%;
            height: 85%;
            box-shadow: 0 25px 60px rgba(0,0,0,0.08);
            display: flex;
            flex-direction: column;
            position: relative;
            z-index: 10;
        }}

        .slide-title {{
            font-family: 'Noto Sans TC', sans-serif;
            font-weight: 900;
            font-size: 55px; 
            color: #2980b9;
            margin: 0 0 40px 0;
            line-height: 1.3;
            border-bottom: 4px solid #f1c40f;
            padding-bottom: 20px;
        }}

        .layout-split {{
            display: flex;
            flex: 1;
            gap: 60px;
            height: calc(100% - 150px);
        }}

        .text-column {{
            flex: 1.2;
            display: flex;
            flex-direction: column;
        }}

        .image-column {{
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            border-radius: 15px;
            overflow: hidden;
            position: relative;
            background: #ecf0f1;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.05);
        }}

        .content-img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 15px;
            border: 3px solid rgba(189, 195, 199, 0.4);
            box-sizing: border-box;
        }}

        .ai-watermark {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            font-size: 18px;
            z-index: 10;
        }}

        .label {{
            font-weight: 900;
            color: #e74c3c;
            font-size: 28px;
            margin-bottom: 15px;
            display: inline-block;
            border-left: 8px solid #e74c3c;
            padding-left: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .reason {{
            font-size: 38px;
            color: #7f8c8d;
            margin: 0 0 40px 0;
            font-weight: bold;
            line-height: 1.5;
        }}

        .script-text {{
            font-size: 38px;
            line-height: 1.6;
            color: #34495e;
            margin: 0;
            font-weight: 400;
        }}

        .outro-slide h1 {{
            font-family: 'Noto Sans TC', sans-serif;
            font-weight: 900;
            font-size: 120px;
            color: #2c3e50;
            margin: 0 0 30px 0;
        }}
        
        .headlines-list {{
            list-style: none;
            padding: 0;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 20px;
            justify-content: center;
            height: 100%;
        }}
        
        .headlines-list li {{
            font-size: 38px;
            font-weight: 700;
            color: #34495e;
            display: flex;
            align-items: center;
            background: #f8f9fa;
            padding: 15px 30px;
            border-radius: 15px;
            border-left: 10px solid #3498db;
            box-shadow: 0 10px 20px rgba(0,0,0,0.03);
        }}
        
        .headlines-list li .num {{
            font-family: 'Dela Local', 'Dela Gothic One', cursive;
            font-size: 60px;
            color: #3498db;
            margin-right: 30px;
            min-width: 60px;
        }}
    </style>
</head>
<body>
    <div class="bg-circle bg-c1"></div>
    <div class="bg-circle bg-c2"></div>

    <!-- Intro Slide -->
    <div id="slide_intro" class="slide title-slide">
        <div class="badge">Taipei City News</div>
        <h1>每日新聞</h1>
        <h2>{today}</h2>
        <h3 style="font-family: 'Noto Sans TC', sans-serif; font-size: 40px; color: #7f8c8d; margin-top: 30px;">本影片與配音由 AI 自動生成</h3>
    </div>
"""
    
    # Generate Headlines Slide (Only create if we have actual items to show)
    if items:
        html += f"""
        <!-- Headlines Slide -->
        <div id="slide_headlines" class="slide">
            <div class="content-box">
                <h2 class="slide-title">今日頭條重點摘要</h2>
                <ul class="headlines-list">
"""
        for idx, item in enumerate(items):
            html += f"""                    <li><span class="num">{idx+1}</span>{item.get('title', '')}</li>\n"""
        html += """
                </ul>
            </div>
        </div>
"""

    for idx, item in enumerate(items):
        title = item.get("title", "")
        reason = item.get("reason", "")
        script = item.get("script", "")
        image_url = item.get("image_url", "")
        is_ai = item.get("is_ai_generated", False)
        
        if image_url and not image_url.startswith("/"):
            local_img = OUTPUT_DIR / f"dl_img_{idx}.jpg"
            image_url = download_image(image_url, local_img)
        elif image_url.startswith("/"):
            image_url = f"file://{image_url}"

        html += f"""
    <div id="slide_{idx}" class="slide">
        <div class="content-box">
            <h2 class="slide-title">{title}</h2>
            <div class="layout-split">
                <div class="text-column">
                    <div class="label">推薦原因</div>
                    <p class="reason">{reason}</p>
                    <div class="label">播報稿</div>
                    <p class="script-text">{script}</p>
                </div>
"""
        if image_url:
            watermark_html = '<div class="ai-watermark">本圖片由AI自動生成</div>' if is_ai else ''
            html += f"""
                <div class="image-column">
                    <img src="{image_url}" class="content-img" onerror="this.style.display='none'">
                    {watermark_html}
                </div>
"""
        else:
            html = html.replace('class="text-column"', 'class="text-column" style="flex: none; width: 100%;"')
            
        html += """
            </div>
        </div>
    </div>
"""

    html += """
    <div id="slide_outro" class="slide outro-slide">
        <h1>感謝您的收看</h1>
        <h2 style="color: #e74c3c; font-size: 60px; margin:0;">喜歡請按讚、訂閱並分享！</h2>
    </div>

    <script>
        function showSlide(slideId) {
            document.querySelectorAll('.slide').forEach(el => {
                el.classList.remove('active');
            });
            const target = document.getElementById(slideId);
            if (target) {
                target.classList.add('active');
                
                // Auto-shrink text if it overflows the text-column
                const col = target.querySelector('.text-column');
                if (col) {
                    const elements = target.querySelectorAll('.slide-title, .script-text, .reason, .label');
                    let reduce = 0;
                    while (col.scrollHeight > col.clientHeight && reduce < 30) {
                        reduce++;
                        elements.forEach(el => {
                            const style = window.getComputedStyle(el);
                            const size = parseFloat(style.fontSize);
                            el.style.fontSize = (size - 1) + 'px';
                        });
                    }
                }
            }
        }
    </script>
</body>
</html>
"""
    
    HTML_FILE.write_text(html, encoding="utf-8")
    print(f"Generated HTML template: {HTML_FILE}")

if __name__ == "__main__":
    generate_html()
