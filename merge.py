import json
import os
from pathlib import Path

BASE = Path(os.getenv("TW_GOV_VIDEO_BASE") or Path(__file__).resolve().parent) / "output"
f_12 = BASE / "news_12pm.json"
f_5 = BASE / "news_5pm.json"

d12 = json.loads(f_12.read_text(encoding="utf-8-sig")) if f_12.exists() else []
d5 = json.loads(f_5.read_text(encoding="utf-8-sig")) if f_5.exists() else []

merged = {}
for item in d12 + d5:
    sn = item.get("DataSN", "")
    if sn: merged[sn] = item

with open(BASE / "to_process.json", "w", encoding="utf-8") as f:
    json.dump(list(merged.values()), f, ensure_ascii=False, indent=2)
