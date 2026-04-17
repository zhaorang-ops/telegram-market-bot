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
MAX_PAGES = int(os.environ.get("MAX_PAGES", "50"))

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
        outer_val = payload.get(outer)
        if isinstance(outer_val, dict):
            for key in ["items", "results", "nfts", "assets"]:
                value = outer_val.get(key)
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
        if "telegram" in path_text:
            score += 60
        if "metadata" in path_text:
            score += 40
        if path and path[-1].lower() == "name":
            score += 20

        # 避免误取集合名
        if "collection" in path_text:
            score -= 100
        if username.lower() in {"telegramusernames", "fragment", "marketapp"}:
            score -= 200

        candidates.append((score, username, path_text))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][1]


def extract_ton_price(raw: dict):
    # 优先尝试常见字段
    preferred_paths = [
        ("full_price",),
        ("price",),
        ("price_ton",),
        ("ton_price",),
        ("sale", "full_price"),
        ("sale", "price"),
        ("sale", "price_ton"),
        ("order", "full_price"),
        ("order", "price"),
        ("order", "price_ton"),
        ("listing", "full_price"),
        ("listing", "price"),
        ("listing", "price_ton"),
        ("market", "full_price"),
        ("market", "price"),
        ("market", "price_ton"),
        ("nft_sale", "full_price"),
        ("nft_sale", "price"),
        ("nft_sale", "price_ton"),
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
            if val is not None and val > 0:
                return val

    # 回退：扫描所有叶子节点，优先找带 ton / price / full_price 的数值
    candidates = []
    for path, value in walk_leaves(raw):
        path_text = ".".join(path).lower()

        if not any(k in path_text for k in ["price", "ton", "full_price", "sale"]):
            continue

        num = to_float(value, default=None)
        if num is None or num <= 0:
            continue

        score = 0
        if "full_price" in path_text:
            score += 120
        if "price_ton" in path_text:
            score += 110
        if path_text.endswith("price"):
            score += 80
        if "ton" in path_text:
            score += 60
        if "sale" in path_text or "listing" in path_text or "order" in path_text:
            score += 40
        if "usd" in path_text:
            score -= 120

        candidates.append((score, num, path_text))

    if not candidates:
        return 0.0

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return float(candidates[0][1])


def extract_usd_price(raw: dict):
    preferred_paths = [
        ("price_usd",),
        ("usd_price",),
        ("sale", "price_usd"),
        ("order", "price_usd"),
        ("listing", "price_usd"),
        ("market", "price_usd"),
        ("nft_sale", "price_usd"),
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
            if val is not None and val > 0:
                return val

    candidates = []
    for path, value in walk_leaves(raw):
        path_text = ".".join(path).lower()
        if "usd" not in path_text:
            continue

        num = to_float(value, default=None)
        if num is None or num <= 0:
            continue

        score = 0
        if "price_usd" in path_text:
            score += 120
        if path_text.endswith("usd"):
            score += 60

        candidates.append((score, num, path_text))

    if not candidates:
        return 0.0

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return float(candidates[0][1])


def extract_banned(raw: dict):
    # 官方文档没公开 banned 字段名，这里做兼容识别
    for path, value in walk_leaves(raw):
        path_text = ".".join(path).lower()

        if "banned" in path_text or "ban" in path_text:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes", "banned"}

        if "status" in path_text and isinstance(value, str):
            status = value.strip().lower()
            if "banned" in status or "ban" == status:
                return True

    return False


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

    ton_price = extract_ton_price(raw)
    usd_price = extract_usd_price(raw)
    is_banned = extract_banned(raw)
    on_sale = extract_on_sale(raw)

    return {
        "name": username,
        "name_len": len(username),
        "ton_price": ton_price,
        "usd_price": usd_price,
        "is_banned": is_banned,
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
                "filter_by": "onsale",
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

                key = item["name"].lower()
                old = next((x for x in all_items if x["name"].lower() == key), None)

                # 同名只保留价格更合理的一条
                if old is None:
                    all_items.append(item)
                    seen.add(key)
                else:
                    old_price = old["ton_price"] if old["ton_price"] > 0 else 10**18
                    new_price = item["ton_price"] if item["ton_price"] > 0 else 10**18
                    if new_price < old_price:
                        all_items.remove(old)
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

        # 这个接口默认就是 onsale；这里再用价格做兜底
        if item["is_on_sale"] is False and item["ton_price"] <= 0:
            continue

        groups[item["name_len"]].append(item)

    for length_value in groups:
        groups[length_value].sort(
            key=lambda x: (
                x["ton_price"] <= 0,
                x["ton_price"] if x["ton_price"] > 0 else 10**18,
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
            if item["usd_price"] > 0:
                adjusted_usd = item["usd_price"] + extra_usd
            else:
                adjusted_usd = extra_usd

            banned_tag = " [BANNED]" if item["is_banned"] else ""
            lines.append(
                f"@{item['name']}{banned_tag}  {item['ton_price']:.2f} TON  |  ${adjusted_usd:.2f}"
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
    print("DEBUG SAMPLE WITH PRICE:")
    for x in items[:10]:
        print(
            {
                "name": x["name"],
                "len": x["name_len"],
                "ton_price": x["ton_price"],
                "usd_price": x["usd_price"],
                "is_banned": x["is_banned"],
            }
        )

    text = build_message(groups)
    print("DEBUG FINAL MESSAGE PREVIEW:")
    print(text[:4000])

    await edit_message(text)


if __name__ == "__main__":
    asyncio.run(main())
