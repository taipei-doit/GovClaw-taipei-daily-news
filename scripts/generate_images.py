import json
import os
import base64
import urllib.request
import urllib.error
from pathlib import Path
import google.auth
import google.auth.transport.requests

from config import BASE_DIR as BASE, OUTPUT_DIR, INPUT_JSON

credentials, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
PROJECT_ID = project or os.getenv("GCP_PROJECT_ID")
LOCATION = "us-central1"

def get_clean_visual_prompt(title, token):
    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"
    
    # We ask Gemini to generate a purely visual, generic stock-photo style subject 
    # based on the headline, completely avoiding any news/text implications.
    system_instruction = "You are a stock photo assistant. Read the news headline and output a very short 2 to 5 word English description of a purely visual, generic background scene or macro object related to the topic. CRITICAL RULES: The scene MUST NOT contain people, screens, text, banners, or signs. Just a clean landscape, architectural detail, or object. Examples: 'empty modern hospital hallway', 'close up of green leaves', 'electric car charging plug', 'empty city intersection'. Output ONLY the short English phrase, nothing else."
    
    payload = {
        "contents": [{"role": "user", "parts": [{"text": f"Headline: {title}"}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]}
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Gemini prompt generation failed: {e}")
        return "beautiful nature landscape"

def generate_image(title, idx):
    credentials.refresh(google.auth.transport.requests.Request())
    token = credentials.token
    
    # Get the clean, text-free visual subject from Gemini
    clean_subject = get_clean_visual_prompt(title, token)
    print(f"Gemini decided the visual subject for '{title}' is: '{clean_subject}'")
    
    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/imagen-3.0-generate-002:predict"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    
    # Now we just ask Imagen to render that specific clean subject.
    strict_prompt = f"A photorealistic, highly detailed 8k photography wallpaper of: {clean_subject}. Pure imagery, no text, no characters, no logos."
    
    payload = {
        "instances": [{"prompt": strict_prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",
            "outputOptions": {"mimeType": "image/png"}
        }
    }
    
    data = json.dumps(payload).encode('utf-8')
    try:
        with urllib.request.urlopen(req, data=data) as response:
            result = json.loads(response.read().decode('utf-8'))
            b64_img = result['predictions'][0]['bytesBase64Encoded']
            image_data = base64.b64decode(b64_img)
            
            file_path = OUTPUT_DIR / f"ai_article_{idx}.png"
            with open(file_path, "wb") as f:
                f.write(image_data)
            print(f"Generated and permanently saved: {file_path}")
            return str(file_path)
    except urllib.error.HTTPError as e:
        print(f"Failed to generate image for slide {idx}: HTTP {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Failed to generate image for slide {idx}: {e}")
        return None

def main():
    if not INPUT_JSON.exists():
        print("No JSON found.")
        return

    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    items = data.get("selected", [])
    
    for idx, item in enumerate(items):
        current_image = item.get("image_url", "").strip()
        
        # If no official image, or it's an AI path from a previous test run
        if not current_image or "ai_article" in current_image or current_image.startswith("/home"):
            title = item.get("title", "Taiwan Taipei News")
            print(f"Slide {idx} is missing an official image. Triggering Gemini -> Imagen pipeline...")
            img_path = generate_image(title, idx)
            if img_path: 
                item['image_url'] = img_path
                item['is_ai_generated'] = True
        else:
            print(f"Slide {idx} already has an official image from the article. Skipping AI generation.")
            item['is_ai_generated'] = False
            
    INPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Updated JSON with AI images only for missing slots.")

if __name__ == "__main__":
    main()
