import json
from config import OUTPUT_DIR, INPUT_JSON

CANDIDATES_JSON = OUTPUT_DIR / "llm_candidates.json"

def main():
    if not INPUT_JSON.exists() or not CANDIDATES_JSON.exists():
        print("Missing files.")
        return
        
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    candidates = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))
    
    # Create lookup map
    sn_to_url = {}
    for c in candidates:
        sn = c.get("DataSN", "")
        if sn:
            sn_to_url[sn] = c.get("source_url", "")
            
    items = data.get("selected", [])
    for item in items:
        sn = item.get("DataSN", "")
        if sn in sn_to_url and sn_to_url[sn]:
            item["source_url"] = sn_to_url[sn]
            
    INPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Fixed source_urls in selected_articles.json")

if __name__ == "__main__":
    main()
