import asyncio
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx


def normalize_collection_address(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    if "/collection/" in value:
        value = value.split("/collection/", 1)[1]
        value = value.split("?", 1)[0]
        value = value.split("/", 1)[0]

    return value.strip()


BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MESSAGE_ID = int(os.environ["MESSAGE_ID"])
MARKETAPP_API_TOKEN = os.environ["MARKETAPP_API_TOKEN"]

USERNAMES_COLLECTION_ADDRESS = normalize_collection_address(
    os.environ.get(
        "USERNAMES_COLLECTION_ADDRESS",
        "EQCA14o1-VWhS2efqoh_9M1b_A9DtKTuoqfmkn83AbJzwnPi",
    )
)

NUMBERS_COLLECTION_ADDRESS = normalize_collection_address(
    os.environ.get("NUMBERS_COLLECTION_ADDRESS", "")
)

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))
TOP_N_EACH = int(os.environ.get("TOP_N_EACH", "20"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "120"))

USERNAME_ADD_USD = {
    5: 50.0,
    6: 50.0,
}

NUMBER_ADD_USD = {
    "has4": 100.0,
    "no4": 100.0,
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
    text = re.sub(r"\s+", "", str(name).strip())
    text = re.sub(r"[^\d+]", "", text)

    if text.startswith("+"):
        digits = text[1:]
    else:
        digits = text

    if digits.startswith("888"):
        tail = digits[3:]
        if len(tail) == 4:
            return f"+888 {tail[0]} {tail[1:]}"
        if len(tail) == 8:
            return f"+888 {tail[:4]} {tail[4:]}"
        return f"+{digits}"

    return str(name).strip()


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
    name = raw.get("name")
    if isinstance(name, str) and name.strip():
        name = name.strip()
        if mode == "usernames" and USERNAME_RE.match(name):
            return normalize_username(name)
        if mode == "numbers" and NUMBER_RE.match(name):
            return normalize_number(name)

    candidates = []
    for key, value in walk(raw):
        if not isinstance(value, str):
            continue

        text = value.strip()
        key_l = str(key).lower()

        if mode == "usernames" and USERNAME_RE.match(text):
            score = 0
            if key_l == "name":
                score += 50
            if "username" in key_l:
                score += 100
            if "telegram" in key_l:
                score += 30
            candidates.append((score, normalize_username(text)))

        if mode == "numbers" and NUMBER_RE.match(text):
            score = 0
            if key_l == "name":
                score += 50
            if "phone" in key_l or "number" in key_l:
                score += 100
            candidates.append((score, normalize_number(text)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][1]


def extract_currency(raw: dict):
    if isinstance(raw.get("currency"), str) and raw.get("currency").strip():
        return raw["currency"].strip().upper()

    for key, value in walk(raw):
        if str(key).lower() == "currency" and isinstance(value, str) and value.strip():
            return value.strip().upper()

    return "TON"


def nanoton_to_ton(value: float, currency: str):
    if currency.upper() == "TON" and value > 1_000_000:
        return value / 1_000_000_000
    return value


def extract_ton_price(raw: dict):
    currency = extract_currency(raw)

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
    for key, v in walk(raw):
        key_l = str(key).lower()

        if key_l in {"is_on_sale", "on_sale"}:
            return bool(v)

        if key_l == "status" and isinstance(v, str):
            status = v.strip().lower()
            if status in {"onsale", "on_sale", "listed", "active"} or "sale" in status:
                return True

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
        if length_value not in {5, 6}:
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
    no_new_pages = 0

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

            if resp.status_code == 400:
                body_text = resp.text[:5000]
                print(f"DEBUG {mode.upper()} ERROR BODY:", body_text)
                if "Invalid cursor format" in body_text:
                    print(f"DEBUG {mode.upper()} STOP: invalid cursor reached")
                    break
                resp.raise_for_status()

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
                print(f"DEBUG {mode.upper()} STOP: empty page")
                break

            before_count = len(items)

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
                else:
                    old = items[old_index]
                    old_price = old["ton_price"] if old["ton_price"] > 0 else 10**18
                    new_price = item["ton_price"] if item["ton_price"] > 0 else 10**18
                    if new_price < old_price:
                        items[old_index] = item

            after_count = len(items)
            added_count = after_count - before_count
            print(f"DEBUG {mode.upper()} PAGE {page_no} NEW UNIQUE:", added_count)

            if added_count == 0:
                no_new_pages += 1
            else:
                no_new_pages = 0

            if no_new_pages >= 3:
                print(f"DEBUG {mode.upper()} STOP: 3 pages with no new unique items")
                break

            next_cursor = None
            if isinstance(payload, dict):
                next_cursor = payload.get("cursor") or payload.get("next_cursor")
                next_url = payload.get("next") or payload.get("next_page")
                if isinstance(next_url, str):
                    m = re.search(r"cursor=([^&]+)", next_url)
                    if m:
                        next_cursor = m.group(1)

            if not next_cursor:
                print(f"DEBUG {mode.upper()} STOP: no next cursor")
                break

            cursor = next_cursor

    print(f"DEBUG {mode.upper()} TOTAL UNIQUE ITEMS:", len(items))
    return items


def username_clean(name: str) -> str:
    return name.lstrip("@").lower()


def match_5_patterns(s: str):
    return {
        "aa***": len(s) == 5 and s[0] == s[1],
        "aaa**": len(s) == 5 and s[0] == s[1] == s[2],
        "aaaa*": len(s) == 5 and s[0] == s[1] == s[2] == s[3],
        "*aaaa": len(s) == 5 and s[1] == s[2] == s[3] == s[4],
        "**aaa": len(s) == 5 and s[2] == s[3] == s[4],
        "***aa": len(s) == 5 and s[3] == s[4],
    }


def match_6_patterns(s: str):
    return {
        "aa****": len(s) == 6 and s[0] == s[1],
        "aaa***": len(s) == 6 and s[0] == s[1] == s[2],
        "aaaa**": len(s) == 6 and s[0] == s[1] == s[2] == s[3],
        "**aaaa": len(s) == 6 and s[2] == s[3] == s[4] == s[5],
        "***aaa": len(s) == 6 and s[3] == s[4] == s[5],
        "****aa": len(s) == 6 and s[4] == s[5],
    }


def pattern_matchers(length_value: int):
    if length_value == 5:
        return [
            ("aa***", lambda s: match_5_patterns(s)["aa***"]),
            ("aaa**", lambda s: match_5_patterns(s)["aaa**"]),
            ("aaaa*", lambda s: match_5_patterns(s)["aaaa*"]),
            ("*aaaa", lambda s: match_5_patterns(s)["*aaaa"]),
            ("**aaa", lambda s: match_5_patterns(s)["**aaa"]),
            ("***aa", lambda s: match_5_patterns(s)["***aa"]),
        ]
    if length_value == 6:
        return [
            ("aa****", lambda s: match_6_patterns(s)["aa****"]),
            ("aaa***", lambda s: match_6_patterns(s)["aaa***"]),
            ("aaaa**", lambda s: match_6_patterns(s)["aaaa**"]),
            ("**aaaa", lambda s: match_6_patterns(s)["**aaaa"]),
            ("***aaa", lambda s: match_6_patterns(s)["***aaa"]),
            ("****aa", lambda s: match_6_patterns(s)["****aa"]),
        ]
    return []


def build_username_section(items, length_value: int):
    pool = [
        x for x in items
        if x["length"] == length_value and not (x["is_on_sale"] is False and x["ton_price"] <= 0)
    ]

    pool.sort(
        key=lambda x: (
            x["ton_price"] <= 0,
            x["ton_price"] if x["ton_price"] > 0 else 10**18,
            x["name"].lower(),
        )
    )

    matchers = pattern_matchers(length_value)

    def is_special(item):
        s = username_clean(item["name"])
        return any(fn(s) for _, fn in matchers)

    used = set()

    normal_candidates = [x for x in pool if not is_special(x)]
    first_14 = []

    for x in normal_candidates:
        k = x["name"].lower()
        if k in used:
            continue
        used.add(k)
        first_14.append(x)
        if len(first_14) == 14:
            break

    if len(first_14) < 14:
        for x in pool:
            k = x["name"].lower()
            if k in used:
                continue
            used.add(k)
            first_14.append(x)
            if len(first_14) == 14:
                break

    last_6 = []
    for _, fn in matchers:
        chosen = None
        for x in pool:
            k = x["name"].lower()
            if k in used:
                continue
            if fn(username_clean(x["name"])):
                chosen = x
                break

        if chosen:
            used.add(chosen["name"].lower())
            last_6.append(chosen)
        else:
            filler = None
            for x in pool:
                k = x["name"].lower()
                if k in used:
                    continue
                filler = x
                break
            if filler:
                used.add(filler["name"].lower())
                last_6.append(filler)

    return first_14 + last_6


def number_digits(name: str) -> str:
    return re.sub(r"\D", "", name or "")


def number_tail(name: str) -> str:
    digits = number_digits(name)
    if digits.startswith("888"):
        return digits[3:]
    return digits


def floor_pick(items, predicate):
    matched = [x for x in items if predicate(x)]
    if not matched:
        return None

    matched.sort(
        key=lambda x: (
            x["ton_price"] <= 0,
            x["ton_price"] if x["ton_price"] > 0 else 10**18,
            x["name"],
        )
    )
    return matched[0]


def build_number_floor(items):
    valid = [x for x in items if x["ton_price"] > 0 and not x["is_restricted"]]

    def has4(x):
        tail = number_tail(x["name"])
        return "4" in tail

    def no4(x):
        tail = number_tail(x["name"])
        return "4" not in tail

    return {
        "has4": floor_pick(valid, has4),
        "no4": floor_pick(valid, no4),
    }


def usd_after_add(ton_price: float, ton_usd_rate: float, add_usd: float) -> float:
    return ton_price * ton_usd_rate + add_usd


def build_message(section_5, section_6, number_floor, ton_usd_rate):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    lines = ["用户名价格实时更新：", ""]

    lines.append("【5位用户名】")
    if not section_5:
        lines.append("暂无数据")
    else:
        for item in section_5:
            usd_val = usd_after_add(item["ton_price"], ton_usd_rate, USERNAME_ADD_USD[5])
            lines.append(f"{item['name']}  ${usd_val:.2f}")
    lines.append("")

    lines.append("【6位用户名】")
    if not section_6:
        lines.append("暂无数据")
    else:
        for item in section_6:
            usd_val = usd_after_add(item["ton_price"], ton_usd_rate, USERNAME_ADD_USD[6])
            lines.append(f"{item['name']}  ${usd_val:.2f}")
    lines.append("")

    if number_floor:
        lines.append("【888】地板价")

        item = number_floor.get("has4")
        if item:
            usd_val = usd_after_add(item["ton_price"], ton_usd_rate, NUMBER_ADD_USD["has4"])
            lines.append(f"【有4】 {item['name']} - ${usd_val:.2f}")
        else:
            lines.append("【有4】 暂无数据")

        item = number_floor.get("no4")
        if item:
            usd_val = usd_after_add(item["ton_price"], ton_usd_rate, NUMBER_ADD_USD["no4"])
            lines.append(f"【无4】 {item['name']} - ${usd_val:.2f}")
        else:
            lines.append("【无4】 暂无数据")

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

    section_5 = build_username_section(username_items, 5)
    section_6 = build_username_section(username_items, 6)

    number_floor = {}
    if NUMBERS_COLLECTION_ADDRESS:
        number_items = await fetch_collection_items(
            NUMBERS_COLLECTION_ADDRESS,
            mode="numbers",
        )
        number_floor = build_number_floor(number_items)

    print("DEBUG SECTION 5 COUNT:", len(section_5))
    print("DEBUG SECTION 6 COUNT:", len(section_6))
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

    if number_floor:
        print("DEBUG NUMBER FLOOR:")
        for k, v in number_floor.items():
            if v:
                print(k, {"name": v["name"], "ton_price": v["ton_price"]})
            else:
                print(k, None)

    text = build_message(section_5, section_6, number_floor, ton_usd_rate)
    print("DEBUG FINAL MESSAGE PREVIEW:")
    print(text[:4000])

    await edit_message(text)


if __name__ == "__main__":
    asyncio.run(main())
