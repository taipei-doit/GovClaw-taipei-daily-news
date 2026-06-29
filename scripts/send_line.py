"""每日將臺北市政府新聞摘要以 LINE 官方帳號 broadcast 出去。

本版為資安修復版，重點：
- 修「假成功」：唯有 broadcast 成功才寫 heartbeat；失敗回非零碼（避免失敗被誤標完成而漏送）。
- fail-closed：上游資料缺失/不合法時不發送、不標記完成（不再廣播空訊息）。
- YouTube 連結走 https + 網域白名單，並擋開放轉址（含百分比編碼繞過）。
- 新聞 JSON / 標題做型別與長度驗證，altText 截斷到 LINE 上限。
- 對外 HTTP 設 timeout；錯誤 log 不外洩 LINE 回應 body。
- 狀態檔以「暫存檔(含 PID) + 原子置換」寫入；日期一律用台北時區(UTC+8)。
- 提供 --dry-run 安全試跑；import 本模組無副作用。

沿用 scripts/config.py 既有介面（INPUT_JSON / YOUTUBE_URL_FILE / STATE_FILE）。
排程器（heartbeat）仍負責「當天是否已送」的判斷，本程式不自行去重。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from config import INPUT_JSON, STATE_FILE, YOUTUBE_URL_FILE

LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"

WEB_PORTAL_URL = "https://taipei-doit.github.io/GovClaw-taipei-daily-news/"
SPOTIFY_URL = "https://open.spotify.com/show/033jJtZiN097aPxw99mHYW"
YOUTUBE_FALLBACK_URL = "https://www.youtube.com/@CiviClaw"

# YouTube 連結白名單：只接受 https + 這些 host，並擋開放轉址路徑。
ALLOWED_YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})
BLOCKED_YOUTUBE_FIRST_SEGMENTS = frozenset({"redirect", "attribution_link"})

# 廣播內容上限（對齊 LINE 限制）
MAX_ITEMS = 5
MAX_TITLE_LEN = 100
MAX_ALT_TEXT_LEN = 400

REQUEST_TIMEOUT = 15  # 對外 HTTP 逾時（秒）
TAIPEI_TZ = timezone(timedelta(hours=8))  # 台灣無 DST，固定 +8，免 tzdata 依賴


def get_line_token() -> str:
    """讀取並驗證 LINE token；空值即明確報錯（不送出空 Bearer）。"""
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "[send_line] 錯誤：找不到 LINE_CHANNEL_ACCESS_TOKEN。\n"
            "  - 本機/主機：確認專案根目錄有 .env 且填了該變數，或環境已注入。\n"
            "  - 確認執行時 load_dotenv() 讀得到 .env。"
        )
    return token


def today_str() -> str:
    """以台北時區回傳 YYYY-MM-DD。"""
    return datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")


def safe_youtube_url(raw: str, fallback: str = YOUTUBE_FALLBACK_URL) -> str:
    """驗證 YouTube 連結；非 https、非白名單 host、或開放轉址路徑一律回退 fallback。"""
    candidate = (raw or "").strip()
    if not candidate:
        return fallback
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return fallback
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_YOUTUBE_HOSTS:
        return fallback
    # 先 unquote 再比對第一段路徑，擋掉 /redirect、/redirect%2f、/redirect/foo 等變形。
    first_segment = unquote(parsed.path or "").lower().strip("/").split("/", 1)[0]
    if first_segment in BLOCKED_YOUTUBE_FIRST_SEGMENTS:
        return fallback
    return candidate


def read_youtube_url() -> str:
    """讀取當日 YouTube 連結檔（指定 encoding），經白名單後回傳。"""
    if not YOUTUBE_URL_FILE.exists():
        return YOUTUBE_FALLBACK_URL
    try:
        raw = YOUTUBE_URL_FILE.read_text(encoding="utf-8")
    except OSError:
        return YOUTUBE_FALLBACK_URL
    return safe_youtube_url(raw)


def load_news_titles() -> list:
    """讀取並驗證當日新聞（fail-closed）。

    缺檔/格式錯誤/無有效標題 → 丟 SystemExit，使呼叫端不發送、不標記完成。
    當日 JSON 只讀一次。
    """
    if not INPUT_JSON.exists():
        raise SystemExit(f"[send_line] 上游資料缺失：找不到 {INPUT_JSON}。不發送、不標記完成。")
    try:
        data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:  # 含 JSONDecodeError 與非法 UTF-8 的 UnicodeDecodeError
        raise SystemExit(f"[send_line] 上游資料無法解析：{exc}")

    if not isinstance(data, dict):
        raise SystemExit("[send_line] 上游資料頂層不是物件（dict）；不發送。")
    selected = data.get("selected")
    if not isinstance(selected, list) or not selected:
        raise SystemExit("[send_line] 上游資料的 'selected' 不是非空陣列；不發送。")
    if len(selected) > MAX_ITEMS:
        print(f"[send_line] 注意：'selected' 有 {len(selected)} 筆，超過上限 {MAX_ITEMS}，僅取前 {MAX_ITEMS} 筆。")

    titles = []
    for item in selected[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not isinstance(title, str):
            continue
        title = title.strip()[:MAX_TITLE_LEN]
        if title:
            titles.append(title)
    if not titles:
        raise SystemExit("[send_line] 'selected' 內沒有有效標題；不發送。")
    return titles


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_message_text(titles: list, date_label: str) -> str:
    msg = f"📣 臺北市政府新聞摘要 | {date_label}\n"
    msg += "為您整理今日五大市政重點：\n\n"
    for idx, title in enumerate(titles, 1):
        msg += f"[{idx}] {title}\n"
    msg += "\n🌐 觀看完整影片與新聞圖文：\n"
    msg += f"{WEB_PORTAL_URL}"
    return msg


def build_flex_message(titles: list, date_label: str, youtube_url: str) -> list:
    alt_text = _truncate(build_message_text(titles, date_label), MAX_ALT_TEXT_LEN)

    body_contents = [
        {"type": "text", "text": "今日重點新聞提要", "weight": "bold", "size": "md", "margin": "md", "color": "#e74c3c"}
    ]
    for idx, title in enumerate(titles, 1):
        body_contents.append(
            {
                "type": "box",
                "layout": "horizontal",
                "margin": "md",
                "contents": [
                    {"type": "text", "text": f"{idx}.", "size": "sm", "color": "#888888", "flex": 1},
                    {"type": "text", "text": title, "size": "sm", "color": "#333333", "wrap": True, "flex": 9},
                ],
            }
        )

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
                    {"type": "text", "text": "臺北市政府新聞摘要", "weight": "bold", "size": "xl", "color": "#ffffff"},
                    {"type": "text", "text": date_label, "color": "#ffffffcc", "size": "sm", "margin": "sm"},
                ],
            },
            "body": {"type": "box", "layout": "vertical", "contents": body_contents},
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#3498db", "height": "sm",
                     "action": {"type": "uri", "label": "🌐 閱讀圖文摘要", "uri": WEB_PORTAL_URL}},
                    {"type": "button", "style": "primary", "color": "#e74c3c", "height": "sm",
                     "action": {"type": "uri", "label": "📺 YouTube 影片", "uri": youtube_url}},
                    {"type": "button", "style": "primary", "color": "#1DB954", "height": "sm",
                     "action": {"type": "uri", "label": "🎧 Spotify 收聽", "uri": SPOTIFY_URL}},
                ],
            },
        },
    }
    return [flex_payload]


def broadcast_message(messages: list, token: str, *, timeout: int = REQUEST_TIMEOUT) -> None:
    """送出 LINE broadcast；失敗一律 raise（呼叫端據此不寫 heartbeat）。log 不輸出回應 body。"""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = json.dumps({"messages": messages}).encode("utf-8")
    req = urllib.request.Request(LINE_BROADCAST_URL, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            print(f"[send_line] LINE broadcast 成功（HTTP {status}）")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"LINE broadcast 失敗：HTTP {exc.code} {exc.reason}（詳情請看 LINE Developers Console）"
        ) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LINE broadcast 連線錯誤：{exc.reason}") from None


def update_heartbeat(state_file: Path, date_label: str) -> None:
    """以原子方式更新心跳狀態（同檔系 tmp + os.replace；tmp 帶 PID 防多進程互撞）。"""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state = {}
    if state_file.exists():
        try:
            loaded = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = loaded
        except (ValueError, OSError):  # 損毀就重建，不可在送出後崩潰
            state = {}
    state["5pm_pipeline_date"] = date_label
    state.setdefault("lastChecks", {})

    tmp_file = state_file.with_name(f"{state_file.name}.{os.getpid()}.tmp")
    try:
        tmp_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_file, state_file)
    finally:
        if tmp_file.exists():
            tmp_file.unlink(missing_ok=True)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GovClaw 每日 LINE 廣播")
    parser.add_argument("--dry-run", action="store_true", help="組裝並驗證訊息，但不呼叫 LINE API、不更新狀態。")
    return parser.parse_args(argv)


def _truthy(value) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def main(argv=None) -> int:
    args = parse_args(argv)
    dry_run = args.dry_run or _truthy(os.getenv("DRY_RUN"))
    date_label = today_str()

    # fail-closed：資料不合法直接丟出，下面不會發送或標記完成。
    titles = load_news_titles()
    youtube_url = read_youtube_url()
    messages = build_flex_message(titles, date_label, youtube_url)

    if dry_run:
        print("[send_line] DRY-RUN：以下訊息「不會」實際送出，狀態也不會更新。")
        print(json.dumps(messages, ensure_ascii=False, indent=2))
        return 0

    token = get_line_token()
    broadcast_message(messages, token)  # 失敗會 raise → 不會走到下面寫狀態

    # 唯有送出成功才更新心跳。
    try:
        update_heartbeat(STATE_FILE, date_label)
        print(f"[send_line] 已標記 5pm_pipeline_date = {date_label}")
    except OSError as exc:
        print(
            f"[send_line] 嚴重：broadcast 已送出，但心跳狀態寫入失敗：{exc}\n"
            f"  請人工確認 {STATE_FILE} 是否已記為 {date_label}，以免下次重送。",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("[send_line] 已取消。", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"[send_line] 發送失敗：{exc}", file=sys.stderr)
        sys.exit(1)
