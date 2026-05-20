import json
import os
import shutil
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from pathlib import Path
from email.utils import formatdate

ET.register_namespace('itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
ET.register_namespace('content', 'http://purl.org/rss/1.0/modules/content/')

BASE_DIR = Path.home() / "tw-gov-video"
OUTPUT_DIR = BASE_DIR / "output"
DOCS_DIR = BASE_DIR / "docs"
PODCASTS_DIR = DOCS_DIR / "podcasts"
RSS_FILE = DOCS_DIR / "podcast.xml"

BASE_URL = "https://float-ben.github.io/GovClaw-taipei-daily-news/"
PODCASTS_URL = BASE_URL + "podcasts/"

def format_rfc2822(dt):
    return formatdate(dt.timestamp(), usegmt=True)

def generate_rss_skeleton():
    rss = ET.Element('rss', {
        'version': '2.0',
        'xmlns:itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
        'xmlns:content': 'http://purl.org/rss/1.0/modules/content/'
    })
    channel = ET.SubElement(rss, 'channel')
    
    ET.SubElement(channel, 'title').text = '臺北每日新聞 (Taipei Daily News)'
    ET.SubElement(channel, 'link').text = BASE_URL
    ET.SubElement(channel, 'language').text = 'zh-TW'
    ET.SubElement(channel, 'description').text = '每日為您提供臺北市政府最新鮮、最重要的市政新聞摘要。由 AI 自動精選與配音。'
    ET.SubElement(channel, 'itunes:author').text = 'CiviClaw AI'
    
    owner = ET.SubElement(channel, 'itunes:owner')
    ET.SubElement(owner, 'itunes:name').text = 'CiviClaw AI'
    ET.SubElement(owner, 'itunes:email').text = 'govclaw@gmail.com'
    
    ET.SubElement(channel, 'itunes:explicit').text = 'no'
    
    image = ET.SubElement(channel, 'itunes:image')
    image.set('href', BASE_URL + 'line_qr.png')  # Can be updated to a proper cover art later
    
    category = ET.SubElement(channel, 'itunes:category', {'text': 'News'})
    ET.SubElement(category, 'itunes:category', {'text': 'Daily News'})
    
    return rss, channel

def get_audio_size(file_path):
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0

def main():
    PODCASTS_DIR.mkdir(exist_ok=True)
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    json_path = OUTPUT_DIR / "selected_articles.json"
    audio_path = OUTPUT_DIR / "temp_audio.mp3"
    
    if not json_path.exists() or not audio_path.exists():
        print("Missing required files for podcast generation.")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    articles = data.get("selected", [])
    if not articles:
        print("No articles found in json.")
        return
        
    # Generate descriptions
    desc_lines = ["今日臺北市政重點新聞摘要：", ""]
    for idx, item in enumerate(articles, 1):
        desc_lines.append(f"{idx}. {item.get('title', '')}")
        desc_lines.append(f"{item.get('script', '')}")
        desc_lines.append("")
        
    episode_desc = "\n".join(desc_lines)
    episode_title = f"每日市政摘要 {today_str}"
    
    # Copy audio file
    episode_filename = f"episode_{today_str}.mp3"
    target_audio_path = PODCASTS_DIR / episode_filename
    shutil.copy2(audio_path, target_audio_path)
    
    audio_url = PODCASTS_URL + episode_filename
    audio_size = str(get_audio_size(target_audio_path))
    
    # Load or create RSS
    if RSS_FILE.exists():
        try:
            tree = ET.parse(RSS_FILE)
            rss = tree.getroot()
            channel = rss.find('channel')
        except ET.ParseError:
            rss, channel = generate_rss_skeleton()
    else:
        rss, channel = generate_rss_skeleton()
        
    # Check if episode already exists
    for item in channel.findall('item'):
        title = item.find('title')
        if title is not None and title.text == episode_title:
            channel.remove(item) # Remove old entry to replace with updated one
            
    # Add new episode
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = episode_title
    ET.SubElement(item, 'description').text = episode_desc
    ET.SubElement(item, 'pubDate').text = format_rfc2822(datetime.now())
    ET.SubElement(item, 'guid', {'isPermaLink': 'false'}).text = episode_filename
    ET.SubElement(item, 'itunes:episodeType').text = 'full'
    ET.SubElement(item, 'enclosure', {
        'url': audio_url,
        'length': audio_size,
        'type': 'audio/mpeg'
    })
    
    # Write formatted XML
    xmlstr = minidom.parseString(ET.tostring(rss)).toprettyxml(indent="  ")
    # Clean up empty lines from toprettyxml
    xmlstr = os.linesep.join([s for s in xmlstr.splitlines() if s.strip()])
    
    with open(RSS_FILE, 'w', encoding='utf-8') as f:
        f.write(xmlstr)
        
    print(f"Podcast episode {episode_title} generated successfully.")
    print(f"RSS Feed updated at {RSS_FILE}")

if __name__ == '__main__':
    main()
