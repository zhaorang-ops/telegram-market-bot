import asyncio
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MESSAGE_ID = int(os.environ["MESSAGE_ID"])
MARKETAPP_API_TOKEN = os.environ["MARKETAPP_API_TOKEN"]

COLLECTION_ADDRESS = os.environ.get(
    "COLLECTION_ADDRESS",
    "EQCA14o1-VWhS2efqoh_9M1b_A9DtKTuoqfmkn83AbJzwnPi",
)

API_URL = f"https://api.marketapp.ws/v1/nfts/collections/{COLLECTION_ADDRESS}/"

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))
TOP_N_EACH = int(os.environ.get("TOP_N_EACH", "20"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "20"))

ADD_USD = {
    4: 1000.0,
    5: 50.0,
    6: 50.0,
}

USERNAME_RE = re.compile(r"^@?([A-Za-z0-9_]{4,32})$")


def to_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    s = s.replace(",", "")
    s = s.replace("$", "")
    s = s.replace("TON", "")
    s = s.replace("ton", "")
    s = s.replace("≈", "")
    s = s.replace("~", "")

    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return default

    try:
        return float(m.group(0))
    except Exception:
        return default


def get_items_list(payload):
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    for key in ["items", "results", "data", "nfts", "assets"]:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    for outer in ["data", "result"]:
        if isinstance(payload.get(outer), dict):
            inner = payload[outer]
            for key in ["items", "results", "nfts", "assets"]:
                value = inner.get(key)
                if isinstance(value, list):
                    return value

    return []


def walk_leaves(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_leaves(v, path + (str(k),))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_leaves(v, path + (str(i),))
    else:
        yield path, obj


def normalize_username(s: str):
    s = str(s).strip()
    if s.startswith("@"):
        s = s[1:]
    return s


def extract_username(raw: dict):
    candidates = []

    for path, value in walk_leaves(raw):
        if not isinstance(value, str):
            continue

        text = value.strip()
        m = USERNAME_RE.match(text)
        if not m:
            continue

        username = normalize_username(text)
        length = len(username)
        if length not in (4, 5, 6):
            continue

        path_text = ".".join(path).lower()

        score = 0
        if "username" in path_text:
            score += 100
        if "metadata" in path_text:
            score += 50
        if path and path[-1].lower() == "name":
            score += 30
        if "collection" in path_text:
            score -= 100
        if username.lower() == "telegramusernames":
            score -= 200

        candidates.append((score, username, path_text))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][1]


def extract_price(raw: dict, kind="ton"):
    preferred_paths = []

    if kind == "ton":
        preferred_paths = [
            ("price_ton",),
            ("ton_price",),
            ("sale", "price_ton"),
            ("order", "price_ton"),
            ("listing", "price_ton"),
            ("market", "price_ton"),
            ("sale", "price"),
            ("order", "price"),
            ("listing", "price"),
            ("market", "price"),
            ("price",),
            ("full_price",),
        ]
    else:
        preferred_paths = [
            ("price_usd",),
            ("usd_price",),
            ("sale", "price_usd"),
            ("order", "price_usd"),
            ("listing", "price_usd"),
            ("market", "price_usd"),
            ("usd",),
        ]

    for path in preferred_paths:
        cur = raw
        ok = True
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if ok:
            val = to_float(cur, default=None)
            if val is not None:
                return val

    fallback = []
    for path, value in walk_leaves(raw):
        path_text = ".".join(path).lower()
        if "price" not in path_text and kind not in path_text:
            continue

        num = to_float(value, default=None)
        if num is None:
            continue

        score = 0
        if kind == "ton":
            if "ton" in path_text:
                score += 100
            if path_text.endswith("price"):
                score += 20
        else:
            if "usd" in path_text:
                score += 100
            if path_text.endswith("price_usd"):
                score += 20

        fallback.append((score, num, path_text))

    if not fallback:
        return 0.0

    fallback.sort(key=lambda x: (-x[0], x[1]))
    return float(fallback[0][1])


def extract_on_sale(raw: dict):
    for path, value in walk_leaves(raw):
        path_text = ".".join(path).lower()

        if path_text.endswith("on_sale") or path_text.endswith("is_on_sale"):
            return bool(value)

        if path_text.endswith("status") and isinstance(value, str):
            v = value.lower()
            if "sale" in v or "active" in v or "listed" in v:
                return True

    return None


def parse_item(raw: dict):
    username = extract_username(raw)
    if not username:
        return None

    ton_price = extract_price(raw, kind="ton")
    usd_price = extract_price(raw, kind="usd")
    on_sale = extract_on_sale(raw)

    return {
        "name": username,
        "name_len": len(username),
        "ton_price": ton_price,
        "usd_price": usd_price,
        "is_on_sale": on_sale,
        "raw": raw,
    }


async def fetch_all_items():
    headers = {
        "Authorization": MARKETAPP_API_TOKEN,
        "Accept": "application/json",
    }

    cursor = None
    all_items = []
    seen = set()

    async with httpx.AsyncClient(timeout=30) as client:
        for page_no in range(1, MAX_PAGES + 1):
            params = {
                "limit": 100,
            }
            if cursor:
                params["cursor"] = cursor

            resp = await client.get(API_URL, headers=headers, params=params)

            print(f"DEBUG PAGE {page_no} STATUS:", resp.status_code)
            print("DEBUG URL:", str(resp.request.url))

            if resp.status_code >= 400:
                print("DEBUG ERROR BODY:", resp.text[:5000])
                resp.raise_for_status()

            payload = resp.json()
            raw_items = get_items_list(payload)
            print(f"DEBUG PAGE {page_no} RAW ITEMS:", len(raw_items))

            if page_no == 1 and raw_items:
                print("DEBUG FIRST ITEM PREVIEW:")
                print(str(raw_items[0])[:4000])

            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue

                item = parse_item(raw)
                if not item:
                    continue

                key = (
                    item["name"].lower(),
                    round(item["ton_price"], 8),
                    round(item["usd_price"], 2),
                )
                if key in seen:
                    continue
                seen.add(key)
                all_items.append(item)

            next_cursor = None
            if isinstance(payload, dict):
                next_cursor = payload.get("cursor") or payload.get("next_cursor")
                next_url = payload.get("next") or payload.get("next_page")
                if next_url and isinstance(next_url, str) and "cursor=" in next_url:
                    m = re.search(r"cursor=([^&]+)", next_url)
                    if m:
                        next_cursor = m.group(1)

            if not next_cursor or not raw_items:
                break

            cursor = next_cursor

    print("DEBUG TOTAL UNIQUE ITEMS:", len(all_items))
    return all_items


def build_groups(items):
    groups = {4: [], 5: [], 6: []}

    for item in items:
        if item["name_len"] not in groups:
            continue

        # 这个接口本身就是 collection NFTs on sale；
        # 这里再做一次兜底过滤：有 on_sale=true 或有价格就算有效
        if item["is_on_sale"] is False and item["ton_price"] <= 0:
            continue

        groups[item["name_len"]].append(item)

    for length_value in groups:
        groups[length_value].sort(
            key=lambda x: (
                x["ton_price"] <= 0,
                x["ton_price"],
                x["name"].lower(),
            )
        )
        groups[length_value] = groups[length_value][:TOP_N_EACH]

    return groups


def build_message(groups):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    lines = ["用户名价格实时更新：", ""]

    for length_value in [4, 5, 6]:
        lines.append(f"【{length_value}位 前{TOP_N_EACH}个】")
        current_items = groups.get(length_value, [])

        if not current_items:
            lines.append("暂无数据")
            lines.append("")
            continue

        extra_usd = ADD_USD[length_value]

        for item in current_items:
            adjusted_usd = item["usd_price"] + extra_usd
            lines.append(
                f"@{item['name']}  {item['ton_price']:.2f} TON  |  ${adjusted_usd:.2f}"
            )

        lines.append("")

    lines.append(f"更新时间：{now_str}")
    return "\n".join(lines)


async def edit_message(text: str):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": CHAT_ID,
        "message_id": MESSAGE_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(api, json=payload)
        data = resp.json()

    if not data.get("ok"):
        desc = str(data.get("description", ""))
        if "message is not modified" in desc.lower():
            print("Telegram message unchanged.")
            return
        raise RuntimeError(f"Telegram edit failed: {data}")


async def main():
    items = await fetch_all_items()
    groups = build_groups(items)

    print("DEBUG GROUP COUNTS:", {k: len(v) for k, v in groups.items()})

    text = build_message(groups)
    print("DEBUG FINAL MESSAGE PREVIEW:")
    print(text[:4000])

    await edit_message(text)


if __name__ == "__main__":
    asyncio.run(main())
