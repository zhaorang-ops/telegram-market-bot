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

# Telegram Usernames collection
USERNAMES_COLLECTION_ADDRESS = os.environ.get(
    "USERNAMES_COLLECTION_ADDRESS",
    "EQCA14o1-VWhS2efqoh_9M1b_A9DtKTuoqfmkn83AbJzwnPi",
)

# Anonymous Telegram Numbers collection
# 这里请替换成你匿名号集合页 URL 里的地址；如果留空就跳过这个板块
NUMBERS_COLLECTION_ADDRESS = os.environ.get(
    "NUMBERS_COLLECTION_ADDRESS",
    "",
)

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))
TOP_N_EACH = int(os.environ.get("TOP_N_EACH", "20"))
TOP_N_NUMBERS = int(os.environ.get("TOP_N_NUMBERS", "5"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "50"))

# 用户名板块加价规则
ADD_USD = {
    4: 1000.0,
    5: 50.0,
    6: 50.0,
}

USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_]{4,32}$")
NUMBER_RE = re.compile(r"^\+?\d[\d\s]{6,}$")


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


def walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from walk(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


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


def normalize_username(name: str) -> str:
    name = str(name).strip()
    if not name.startswith("@"):
        name = "@" + name
    return name


def normalize_number(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip())


def extract_attr_length(raw: dict):
    attrs = raw.get("attributes")
    if not isinstance(attrs, list):
        return None

    for attr in attrs:
        if not isinstance(attr, dict):
            continue

        key = str(attr.get("trait_type") or attr.get("name") or attr.get("key") or "").strip().lower()
        if key != "length":
            continue

        value = attr.get("value")
        if value is None:
            continue

        m = re.search(r"\d+", str(value))
        if m:
            return int(m.group(0))

    return None


def extract_name(raw: dict, mode: str):
    # 优先取顶层 name
    name = raw.get("name")
    if isinstance(name, str) and name.strip():
        name = name.strip()
        if mode == "usernames" and USERNAME_RE.match(name):
            return normalize_username(name)
        if mode == "numbers" and NUMBER_RE.match(name):
            return normalize_number(name)

    # 再从其他字段里找
    candidates = []
    for key, value in walk(raw):
        if not isinstance(value, str):
            continue

        text = value.strip()
        if mode == "usernames" and USERNAME_RE.match(text):
            score = 0
            key_l = str(key).lower()
            if key_l == "name":
                score += 50
            if "username" in key_l:
                score += 100
            candidates.append((score, normalize_username(text)))

        if mode == "numbers" and NUMBER_RE.match(text):
            score = 0
            key_l = str(key).lower()
            if key_l == "name":
                score += 50
            if "phone" in key_l or "number" in key_l:
                score += 100
            candidates.append((score, normalize_number(text)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][1]


def nanoton_to_ton(value: float, currency: str):
    if currency.upper() == "TON" and value > 1000000:
        return value / 1_000_000_000
    return value


def extract_currency(raw: dict):
    for key, value in walk(raw):
        if str(key).lower() == "currency" and isinstance(value, str) and value.strip():
            return value.strip().upper()
    return "TON"


def extract_ton_price(raw: dict):
    currency = extract_currency(raw)

    # 先按你日志里真实出现的字段优先取
    direct_candidates = [
        raw.get("min_bid"),
        raw.get("max_bid"),
        raw.get("full_price"),
        raw.get("price"),
        raw.get("price_ton"),
        raw.get("ton_price"),
    ]

    for v in direct_candidates:
        num = to_float(v, default=0.0)
        if num > 0:
            return nanoton_to_ton(num, currency)

    # 再从嵌套字段里找
    scored = []
    for key, value in walk(raw):
        key_l = str(key).lower()
        if not any(k in key_l for k in ["min_bid", "max_bid", "price", "full_price", "ton"]):
            continue

        num = to_float(value, default=0.0)
        if num <= 0:
            continue

        score = 0
        if key_l == "min_bid":
            score += 150
        if key_l == "max_bid":
            score += 140
        if key_l == "full_price":
            score += 120
        if key_l == "price_ton":
            score += 110
        if key_l == "price":
            score += 100
        if "usd" in key_l:
            score -= 200

        scored.append((score, nanoton_to_ton(num, currency)))

    if not scored:
        return 0.0

    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1]


def extract_restricted(raw: dict):
    # 你日志里已有 is_restricted
    value = raw.get("is_restricted")
    if isinstance(value, bool):
        return value
    if value is not None:
        return str(value).strip().lower() in {"true", "1", "yes", "restricted"}

    for key, v in walk(raw):
        key_l = str(key).lower()
        if "restricted" in key_l:
            if isinstance(v, bool):
                return v
            return str(v).strip().lower() in {"true", "1", "yes", "restricted"}

        if key_l == "status" and isinstance(v, str):
            if "restricted" in v.strip().lower():
                return True

    return False


def extract_on_sale(raw: dict):
    # 官方接口默认 filter_by=onsale，这里只做兜底
    for key, v in walk(raw):
        key_l = str(key).lower()

        if key_l in {"is_on_sale", "on_sale"}:
            return bool(v)

        if key_l == "status" and isinstance(v, str):
            status = v.strip().lower()
            if status in {"onsale", "on_sale", "listed", "active"} or "sale" in status:
                return True

    # 有 listed_at 和正价格，也视为可售
    listed_at = raw.get("listed_at")
    price = extract_ton_price(raw)
    if listed_at and price > 0:
        return True

    return None


def parse_item(raw: dict, mode: str):
    name = extract_name(raw, mode)
    if not name:
        return None

    if mode == "usernames":
        attr_len = extract_attr_length(raw)
        clean = name.lstrip("@")
        length_value = attr_len if attr_len is not None else len(clean)
        if length_value not in {4, 5, 6}:
            return None
    else:
        length_value = None

    return {
        "name": name,
        "length": length_value,
        "ton_price": extract_ton_price(raw),
        "is_restricted": extract_restricted(raw),
        "is_on_sale": extract_on_sale(raw),
        "raw": raw,
    }


async def fetch_ton_usd_rate():
    # 仅用于美元换算；失败时就不显示美元加价
    override = os.environ.get("TON_USD_OVERRIDE", "").strip()
    if override:
        try:
            return float(override)
        except Exception:
            pass

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "the-open-network",
        "vs_currencies": "usd",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return float(data["the-open-network"]["usd"])
    except Exception as e:
        print("DEBUG TON USD FETCH FAILED:", repr(e))
        return 0.0


async def fetch_collection_items(collection_address: str, mode: str):
    if not collection_address:
        return []

    api_url = f"https://api.marketapp.ws/v1/nfts/collections/{collection_address}/"
    headers = {
        "Authorization": MARKETAPP_API_TOKEN,
        "Accept": "application/json",
    }

    cursor = None
    items = []
    seen = set()

    async with httpx.AsyncClient(timeout=30) as client:
        for page_no in range(1, MAX_PAGES + 1):
            params = {
                "limit": 100,
                "filter_by": "onsale",
            }
            if cursor:
                params["cursor"] = cursor

            resp = await client.get(api_url, headers=headers, params=params)
            print(f"DEBUG {mode.upper()} PAGE {page_no} STATUS:", resp.status_code)
            print(f"DEBUG {mode.upper()} URL:", str(resp.request.url))

            if resp.status_code >= 400:
                print(f"DEBUG {mode.upper()} ERROR BODY:", resp.text[:5000])
                resp.raise_for_status()

            payload = resp.json()
            raw_items = get_items_list(payload)
            print(f"DEBUG {mode.upper()} PAGE {page_no} RAW ITEMS:", len(raw_items))

            if page_no == 1 and raw_items:
                print(f"DEBUG {mode.upper()} FIRST ITEM PREVIEW:")
                print(str(raw_items[0])[:4000])

            if not raw_items:
                break

            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue

                item = parse_item(raw, mode=mode)
                if not item:
                    continue

                dedupe_key = item["name"].lower()
                old_index = next((i for i, x in enumerate(items) if x["name"].lower() == dedupe_key), None)

                if old_index is None:
                    items.append(item)
                    seen.add(dedupe_key)
                else:
                    # 同名保留价格更低的
                    old = items[old_index]
                    old_price = old["ton_price"] if old["ton_price"] > 0 else 10**18
                    new_price = item["ton_price"] if item["ton_price"] > 0 else 10**18
                    if new_price < old_price:
                        items[old_index] = item

            next_cursor = None
            if isinstance(payload, dict):
                next_cursor = payload.get("cursor") or payload.get("next_cursor")
                next_url = payload.get("next") or payload.get("next_page")
                if isinstance(next_url, str):
                    m = re.search(r"cursor=([^&]+)", next_url)
                    if m:
                        next_cursor = m.group(1)

            if not next_cursor:
                break

            cursor = next_cursor

    print(f"DEBUG {mode.upper()} TOTAL UNIQUE ITEMS:", len(items))
    return items


def build_username_groups(items):
    groups = {4: [], 5: [], 6: []}

    for item in items:
        length_value = item["length"]
        if length_value not in groups:
            continue

        if item["is_on_sale"] is False and item["ton_price"] <= 0:
            continue

        groups[length_value].append(item)

    for k in groups:
        groups[k].sort(
            key=lambda x: (
                x["ton_price"] <= 0,
                x["ton_price"] if x["ton_price"] > 0 else 10**18,
                x["name"].lower(),
            )
        )
        groups[k] = groups[k][:TOP_N_EACH]

    return groups


def build_numbers_top(items):
    filtered = []
    for item in items:
        if item["is_on_sale"] is False and item["ton_price"] <= 0:
            continue
        filtered.append(item)

    filtered.sort(
        key=lambda x: (
            x["ton_price"] <= 0,
            x["ton_price"] if x["ton_price"] > 0 else 10**18,
            x["name"],
        )
    )
    return filtered[:TOP_N_NUMBERS]


def build_message(username_groups, numbers_top, ton_usd_rate):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    lines = ["用户名价格实时更新：", ""]

    for length_value in [4, 5, 6]:
        lines.append(f"【{length_value}位 前{TOP_N_EACH}个】")
        current_items = username_groups.get(length_value, [])

        if not current_items:
            lines.append("暂无数据")
            lines.append("")
            continue

        extra = ADD_USD[length_value]

        for item in current_items:
            if ton_usd_rate > 0:
                usd_val = item["ton_price"] * ton_usd_rate + extra
                lines.append(f"{item['name']}  {item['ton_price']:.2f} TON  |  ${usd_val:.2f}")
            else:
                lines.append(f"{item['name']}  {item['ton_price']:.2f} TON")

        lines.append("")

    if numbers_top:
        lines.append(f"【匿名号 前{TOP_N_NUMBERS}个】")
        for item in numbers_top:
            restricted = " [Restricted]" if item["is_restricted"] else ""
            if ton_usd_rate > 0:
                usd_val = item["ton_price"] * ton_usd_rate
                lines.append(f"{item['name']}{restricted}  {item['ton_price']:.2f} TON  |  ${usd_val:.2f}")
            else:
                lines.append(f"{item['name']}{restricted}  {item['ton_price']:.2f} TON")
        lines.append("")

    lines.append(f"更新时间：{now_str}")
    return "\n".join(lines)


async def edit_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": CHAT_ID,
        "message_id": MESSAGE_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        data = resp.json()

    if not data.get("ok"):
        desc = str(data.get("description", ""))
        if "message is not modified" in desc.lower():
            print("Telegram message unchanged.")
            return
        raise RuntimeError(f"Telegram edit failed: {data}")


async def main():
    ton_usd_rate = await fetch_ton_usd_rate()
    print("DEBUG TON USD RATE:", ton_usd_rate)

    username_items = await fetch_collection_items(
        USERNAMES_COLLECTION_ADDRESS,
        mode="usernames",
    )
    username_groups = build_username_groups(username_items)

    numbers_top = []
    if NUMBERS_COLLECTION_ADDRESS.strip():
        number_items = await fetch_collection_items(
            NUMBERS_COLLECTION_ADDRESS.strip(),
            mode="numbers",
        )
        numbers_top = build_numbers_top(number_items)

    print("DEBUG USERNAME GROUP COUNTS:", {k: len(v) for k, v in username_groups.items()})
    print("DEBUG USERNAME SAMPLE:")
    for x in username_items[:10]:
        print(
            {
                "name": x["name"],
                "length": x["length"],
                "ton_price": x["ton_price"],
                "is_restricted": x["is_restricted"],
            }
        )

    if numbers_top:
        print("DEBUG NUMBERS TOP:")
        for x in numbers_top:
            print(
                {
                    "name": x["name"],
                    "ton_price": x["ton_price"],
                    "is_restricted": x["is_restricted"],
                }
            )

    text = build_message(username_groups, numbers_top, ton_usd_rate)
    print("DEBUG FINAL MESSAGE PREVIEW:")
    print(text[:4000])

    await edit_message(text)


if __name__ == "__main__":
    asyncio.run(main())
