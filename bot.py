import asyncio
from html import unescape
import json
import os
import platform
import re
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

USERNAMES_CHAT_ID = os.environ.get("USERNAMES_CHAT_ID", "").strip()
USERNAMES_MESSAGE_ID = int(os.environ.get("USERNAMES_MESSAGE_ID", "0") or "0")

NUMBERS_CHAT_ID = os.environ.get("NUMBERS_CHAT_ID", "").strip()
NUMBERS_MESSAGE_ID = int(os.environ.get("NUMBERS_MESSAGE_ID", "0") or "0")

PROMO_CHAT_ID = (os.environ.get("PROMO_CHAT_ID", "").strip() or NUMBERS_CHAT_ID)
PROMO_MESSAGE_ID = int(os.environ.get("PROMO_MESSAGE_ID", "0") or "0")

USERNAMES_5_URL = os.environ.get("USERNAMES_5_URL", "").strip()
USERNAMES_6_URL = os.environ.get("USERNAMES_6_URL", "").strip()
USERNAMES_7_URL = os.environ.get("USERNAMES_7_URL", "").strip()

NUMBERS_URL = os.environ.get("NUMBERS_URL", "").strip()
MARKETAPP_API_TOKEN = os.environ.get("MARKETAPP_API_TOKEN", "").strip()
MARKETAPP_API_BASE = os.environ.get("MARKETAPP_API_BASE", "https://api.marketapp.ws").rstrip("/")
MARKETAPP_API_MAX_PAGES = int(os.environ.get("MARKETAPP_API_MAX_PAGES", "5") or "5")
USERNAME_API_PRICE_LIMIT_GRAM = float(os.environ.get("USERNAME_API_PRICE_LIMIT_GRAM", "5000") or "5000")
USERNAME_API_MAX_PAGES = int(os.environ.get("USERNAME_API_MAX_PAGES", "200") or "200")
MARKETAPP_API_COLLECTION_CACHE = {}
MARKETAPP_API_COLLECTION_CAPS = set()
USERNAME_DEEP_FETCH_SECONDS = int(os.environ.get("USERNAME_DEEP_FETCH_SECONDS", "540") or "540")
USERNAME_BROWSER_SCROLLS = int(os.environ.get("USERNAME_BROWSER_SCROLLS", "80") or "80")
USERNAME_QUERY_CONCURRENCY = int(os.environ.get("USERNAME_QUERY_CONCURRENCY", "6") or "6")

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))

USERNAME_ADD_USD = {
    5: 50.0,
    6: 50.0,
    7: 50.0,
}

NUMBER_ADD_USD = {
    "has4": 58.0,
    "no4": 58.0,
}
NUMBER_ITEMS_PER_GROUP = 5
NUMBERS_PAGE_ATTEMPTS = int(os.environ.get("NUMBERS_PAGE_ATTEMPTS", "5") or "5")
MARKET_BROWSER = os.environ.get("MARKET_BROWSER", "chromium").strip().lower()
RUN_MODE = os.environ.get("RUN_MODE", "full").strip().lower()
MARKET_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
CHROMIUM_ARGS = [
    "--disable-http2",
    "--disable-quic",
    "--ignore-certificate-errors",
    "--disable-blink-features=AutomationControlled",
]

PROMO_BUTTON_TEXT = "联系客服"
PROMO_BUTTON_URL = "https://t.me/daimei1"

PROMO_MESSAGE_HTML = """
<tg-emoji emoji-id="5364125616801073577">✈️</tg-emoji>买飞机号联系客服，提供会员号直登协议号，1-11年老号~
<tg-emoji emoji-id="5415758949129404605">👉</tg-emoji><a href="https://t.me/xinpf/28"> 价格表3u-60u</a><tg-emoji emoji-id="5447236223275910637">🤎</tg-emoji>机房自养飞机号
<tg-emoji emoji-id="5415758949129404605">👉</tg-emoji> <a href="https://t.me/xinpf/141">选典藏礼物</a>
<tg-emoji emoji-id="5415758949129404605">👉</tg-emoji> <a href="https://t.me/xinpf/152">选典藏多用户名实时更新</a>

<tg-emoji emoji-id="5226656353744862682">🛒</tg-emoji>租+888｜开会员买星星｜Trx兑换/笔数｜可以用下方机器人取货～
<tg-emoji emoji-id="6084545344924813749">1️⃣</tg-emoji>能量/TRX/闪兑机器人<tg-emoji emoji-id="5415758949129404605">👉</tg-emoji> @shenmi_bot
<tg-emoji emoji-id="6084472459329800521">2️⃣</tg-emoji>租888号开会员买星星<tg-emoji emoji-id="5415758949129404605">👉</tg-emoji> @zuhao8bot

官方多用户名可和礼物增加账号权重不易被封<tg-emoji emoji-id="5220166546491459639">🔥</tg-emoji>招牌11年防注销老号，注册超过11年的飞机号，超级无敌螺旋盖亚聚变核能耐操。
""".strip()

USERNAME_RULES = {
    5: [
        ("4拼", 4, "alpha"),
        ("4数", 4, "digit"),
        ("3拼", 3, "alpha"),
        ("3数", 3, "digit"),
        ("2拼", 2, "alpha"),
        ("2数", 2, "digit"),
        ("1314", None, "fixed"),
        ("520", None, "fixed"),
        ("521", None, "fixed"),
    ],
    6: [
        ("5拼", 5, "alpha"),
        ("5数", 5, "digit"),
        ("4拼", 4, "alpha"),
        ("4数", 4, "digit"),
        ("3拼", 3, "alpha"),
        ("3数", 3, "digit"),
        ("1314", None, "fixed"),
        ("520", None, "fixed"),
        ("521", None, "fixed"),
    ],
    7: [
        ("6拼", 6, "alpha"),
        ("6数", 6, "digit"),
        ("5拼", 5, "alpha"),
        ("5数", 5, "digit"),
        ("4拼", 4, "alpha"),
        ("4数", 4, "digit"),
        ("1314", None, "fixed"),
        ("520", None, "fixed"),
        ("521", None, "fixed"),
    ],
}

USERNAME_EXTRA_COUNT = {
    5: 6,
    6: 6,
    7: 6,
}

USERNAME_QUERY_ALPHA_CHARS = "abcdefghijklmnopqrstuvwxyz"
USERNAME_QUERY_DIGIT_CHARS = "0123456789"


def build_promo_reply_markup():
    return {
        "inline_keyboard": [
            [
                {
                    "text": PROMO_BUTTON_TEXT,
                    "url": PROMO_BUTTON_URL,
                }
            ]
        ]
    }


def html_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def usd_after_add(ton_price: float, ton_usd_rate: float, add_usd: float) -> float:
    return ton_price * ton_usd_rate + add_usd


def display_price_int(value: float) -> int:
    if value <= 0:
        return 0
    return int(value) + 1


def display_number_price_int(value: float) -> int:
    if value <= 0:
        return 0
    return int(value)


def username_clean(name: str) -> str:
    return name.lstrip("@").lower()


def price_or_inf(item):
    return item["ton_price"] if item["ton_price"] > 0 else 10**18


def sort_items(items):
    return sorted(
        items,
        key=lambda x: (
            x["ton_price"] <= 0,
            price_or_inf(x),
            x["name"].lower(),
        )
    )


def has_same_run(s: str, run_len: int, kind: str) -> bool:
    if len(s) < run_len:
        return False

    for i in range(len(s) - run_len + 1):
        chunk = s[i:i + run_len]
        if len(set(chunk)) != 1:
            continue
        ch = chunk[0]
        if kind == "alpha" and ch.isalpha():
            return True
        if kind == "digit" and ch.isdigit():
            return True
    return False


def matches_fixed_keyword(s: str, keyword: str) -> bool:
    return keyword in s


def rule_match(clean: str, rule_name: str, run_len, kind: str) -> bool:
    if kind == "alpha":
        return has_same_run(clean, run_len, "alpha")
    if kind == "digit":
        return has_same_run(clean, run_len, "digit")
    if kind == "fixed":
        return matches_fixed_keyword(clean, rule_name)
    return False


def pick_closest_by_price(candidates, target_price):
    if not candidates:
        return None
    if target_price is None or target_price <= 0:
        return sort_items(candidates)[0]

    return min(
        candidates,
        key=lambda x: (
            abs(price_or_inf(x) - target_price),
            price_or_inf(x),
            x["name"].lower(),
        ),
    )


def to_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    s = s.replace(",", "")
    s = s.replace("$", "")
    s = s.replace("USDT", "")
    s = s.replace("usdt", "")
    s = s.replace("USD", "")
    s = s.replace("usd", "")
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


def extract_usd_from_text(text: str) -> float:
    if not text:
        return 0.0

    patterns = [
        r"~?\$\s*([\d,]+(?:\.\d+)?)",
        r"([\d,]+(?:\.\d+)?)\s*(?:USDT|usdt|USD|usd)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        try:
            return float(m.group(1).replace(",", ""))
        except Exception:
            continue
    return 0.0


def deep_walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from deep_walk(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from deep_walk(item)


def looks_like_username(value: str, expected_length: int) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not re.fullmatch(r"@?[A-Za-z0-9_]{4,32}", text):
        return False
    return len(text.lstrip("@")) == expected_length


def normalize_username(value: str) -> str:
    text = value.strip()
    if not text.startswith("@"):
        text = "@" + text
    return text


PRICE_KEYS_PRIORITY = {
    "min_bid": 100,
    "max_bid": 95,
    "full_price": 92,
    "price": 90,
    "price_ton": 89,
    "ton_price": 88,
    "floor_price": 86,
    "amount": 84,
}


def has_usd_marker(text: str) -> bool:
    if not text:
        return False
    s = str(text)
    return bool(re.search(r"(?:\$|USD|USDT)", s, re.I))


def has_ton_marker(text: str) -> bool:
    if not text:
        return False
    s = str(text)
    return bool(re.search(r"TON", s, re.I))


def normalize_ton_amount(num: float) -> float:
    if num > 1_000_000:
        return num / 1_000_000_000
    return num


def infer_object_currency(raw: dict):
    hint_keys = {
        "currency",
        "quote_currency",
        "quotecurrency",
        "unit",
        "price_unit",
        "asset",
        "asset_type",
        "quote_asset",
        "quote_token",
        "payment_token",
        "token",
        "coin",
        "denom",
        "symbol",
    }

    for key, value in deep_walk(raw):
        key_l = str(key).lower().replace("-", "_")
        if key_l not in hint_keys and not any(h in key_l for h in ["currency", "unit", "token", "asset"]):
            continue

        val_s = str(value).strip().lower()
        if "usdt" in val_s or val_s == "usd" or val_s.endswith("usd"):
            return "usd"
        if val_s == "ton" or "the open network" in val_s:
            return "ton"

    return None


def infer_currency_from_key_value(key, value, default_currency=None):
    key_l = str(key).lower()
    value_s = str(value)

    if "usdt" in key_l or "usd" in key_l or has_usd_marker(value_s):
        return "usd"

    if "ton" in key_l or has_ton_marker(value_s):
        return "ton"

    return default_currency


def extract_prices_from_dict(raw: dict):
    ton_candidates = []
    usd_candidates = []
    default_currency = infer_object_currency(raw)

    def add_candidate(key, value, base_score):
        num = to_float(value, 0.0)
        if num <= 0:
            return

        currency = infer_currency_from_key_value(key, value, default_currency)
        key_l = str(key).lower()

        if currency == "usd":
            usd_candidates.append((base_score, num))
            return

        if currency == "ton":
            ton_candidates.append((base_score, normalize_ton_amount(num)))
            return

        if key_l in {"min_bid", "price_ton", "ton_price"}:
            ton_candidates.append((base_score, normalize_ton_amount(num)))

    for key in [
        "min_bid",
        "max_bid",
        "full_price",
        "price",
        "price_ton",
        "ton_price",
        "floor_price",
        "amount",
    ]:
        if key in raw:
            add_candidate(key, raw.get(key), PRICE_KEYS_PRIORITY.get(key, 50))

    for key, value in deep_walk(raw):
        key_l = str(key).lower()
        if not any(x in key_l for x in ["price", "bid", "ton", "usd", "usdt", "amount"]):
            continue
        add_candidate(key, value, PRICE_KEYS_PRIORITY.get(key_l, 40))

    ton_price = 0.0
    usd_price = 0.0

    if ton_candidates:
        ton_candidates.sort(key=lambda x: (-x[0], x[1]))
        ton_price = ton_candidates[0][1]

    if usd_candidates:
        usd_candidates.sort(key=lambda x: (-x[0], x[1]))
        usd_price = usd_candidates[0][1]

    return ton_price, usd_price


def has_any_price(item: dict) -> bool:
    return item.get("usd_price", 0.0) > 0 or item.get("ton_price", 0.0) > 0


def build_display_usd(item: dict, ton_usd_rate: float, add_usd: float) -> float:
    base_usd = item.get("usd_price", 0.0)
    if base_usd > 0:
        return base_usd + add_usd

    ton_price = item.get("ton_price", 0.0)
    if ton_price > 0 and ton_usd_rate > 0:
        return ton_price * ton_usd_rate + add_usd

    return 0.0


def collection_address_from_url(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"/collection/([^/?#]+)", url)
    return m.group(1) if m else ""


def normalize_marketapp_gram_price(price: float) -> float:
    if price > 1_000_000_000:
        return price / 1_000_000_000
    if price > 100_000:
        return price / 1_000
    return price


def prices_from_marketapp_api_item(item: dict):
    price = to_float(item.get("min_bid"), 0.0)
    if price <= 0:
        price = to_float(item.get("max_bid"), 0.0)
    if price <= 0:
        return 0.0, 0.0

    currency = str(item.get("currency") or "").upper()
    if currency == "USDT":
        return 0.0, price
    if currency == "GRAM":
        return normalize_marketapp_gram_price(price), 0.0
    return price, 0.0


def gram_price_from_marketapp_api_item(item: dict) -> float:
    price = to_float(item.get("min_bid"), 0.0)
    if price <= 0:
        price = to_float(item.get("max_bid"), 0.0)
    if price <= 0:
        return 0.0

    currency = str(item.get("currency") or "").upper()
    if currency != "GRAM":
        return 0.0
    return normalize_marketapp_gram_price(price)


def username_candidate_from_api_item(item: dict, expected_length: int):
    name = normalize_username(str(item.get("name") or ""))
    if not looks_like_username(name, expected_length):
        return None

    ton_price, usd_price = prices_from_marketapp_api_item(item)
    if ton_price <= 0 and usd_price <= 0:
        return None

    return {
        "name": name,
        "length": expected_length,
        "ton_price": ton_price,
        "usd_price": usd_price,
        "is_on_sale": True,
        "is_restricted": bool(item.get("is_restricted")),
        "raw": item,
    }


def number_candidate_from_api_item(item: dict):
    name = normalize_888_number(str(item.get("name") or ""))
    if not looks_like_888_number(name):
        return None

    ton_price, usd_price = prices_from_marketapp_api_item(item)
    if ton_price <= 0 and usd_price <= 0:
        return None

    return {
        "name": name,
        "ton_price": ton_price,
        "usd_price": usd_price,
        "is_restricted": bool(item.get("is_restricted")),
        "raw": item,
    }


def parse_candidates_from_json_payload(payload, expected_length: int):
    candidates = {}

    def add_candidate(name: str, ton_price: float, usd_price: float, raw_obj):
        if not looks_like_username(name, expected_length):
            return
        if ton_price <= 0 and usd_price <= 0:
            return

        restricted = False
        for k, v in deep_walk(raw_obj):
            key_l = str(k).lower()
            if "restricted" in key_l:
                restricted = str(v).strip().lower() in {"true", "1", "yes", "restricted"}
                break
            if key_l == "status" and isinstance(v, str) and "restricted" in v.lower():
                restricted = True
                break

        item = {
            "name": normalize_username(name),
            "length": expected_length,
            "ton_price": ton_price,
            "usd_price": usd_price,
            "is_on_sale": True,
            "is_restricted": restricted,
            "raw": raw_obj,
        }
        key = item["name"].lower()
        old = candidates.get(key)
        if old is None or candidate_sort_key(item, 1.0) < candidate_sort_key(old, 1.0):
            candidates[key] = item

    roots = payload if isinstance(payload, list) else [payload]
    for root in roots:
        if not isinstance(root, dict):
            continue

        maybe_objects = [root]
        for _, v in deep_walk(root):
            if isinstance(v, dict):
                maybe_objects.append(v)

        for obj in maybe_objects:
            names = []
            for _, v in obj.items():
                if isinstance(v, str) and looks_like_username(v, expected_length):
                    names.append(v)
            if not names:
                for _, v in deep_walk(obj):
                    if isinstance(v, str) and looks_like_username(v, expected_length):
                        names.append(v)

            if not names:
                continue

            ton_price, usd_price = prices_from_marketapp_api_item(obj)
            if ton_price <= 0 and usd_price <= 0:
                ton_price, usd_price = extract_prices_from_dict(obj)

            for name in names:
                add_candidate(name, ton_price, usd_price, obj)

    return sorted(candidates.values(), key=lambda x: candidate_sort_key(x, 1.0))


def candidate_sort_key(item: dict, ton_usd_rate: float):
    display_usd = build_display_usd(item, ton_usd_rate, 0.0)
    if display_usd > 0:
        return (0, display_usd, item["name"])

    usd_price = item.get("usd_price", 0.0)
    if usd_price > 0:
        return (1, usd_price, item["name"])

    ton_price = item.get("ton_price", 0.0)
    if ton_price > 0:
        return (2, ton_price, item["name"])

    return (9, 10**18, item["name"])


def looks_like_888_number(value: str) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    digits = re.sub(r"\D", "", text)
    return digits.startswith("888") and len(digits) >= 7


def normalize_888_number(value: str) -> str:
    digits = re.sub(r"\D", "", str(value))
    if not digits.startswith("888"):
        return str(value).strip()

    tail = digits[3:]
    if len(tail) == 4:
        return f"+888 {tail[0]} {tail[1:]}"
    if len(tail) == 8:
        return f"+888 {tail[:4]} {tail[4:]}"
    return f"+{digits}"


def empty_number_floor():
    return {"has4": [], "no4": []}


def number_tail_digits(name: str) -> str:
    digits = re.sub(r"\D", "", name)
    return digits[3:] if digits.startswith("888") else digits


def number_has4(item: dict) -> bool:
    return "4" in number_tail_digits(item["name"])


def group_number_candidates(candidates):
    valid = [
        item
        for item in candidates
        if has_any_price(item) and not item.get("is_restricted")
    ]

    groups = empty_number_floor()
    seen = {"has4": set(), "no4": set()}

    for item in valid:
        key = "has4" if number_has4(item) else "no4"
        name_key = item["name"].lower()
        if name_key in seen[key]:
            continue
        if len(groups[key]) >= NUMBER_ITEMS_PER_GROUP:
            continue

        seen[key].add(name_key)
        groups[key].append(item)

        if (
            len(groups["has4"]) >= NUMBER_ITEMS_PER_GROUP
            and len(groups["no4"]) >= NUMBER_ITEMS_PER_GROUP
        ):
            break

    return groups


def parse_number_candidate_from_text(text: str):
    if not text or "+888" not in text:
        return None

    num_match = re.search(r"\+888[\s\d]{4,20}", text)
    if not num_match:
        return None

    name = re.sub(r"\s+", " ", num_match.group(0)).strip()
    item = {
        "name": name,
        "ton_price": 0.0,
        "usd_price": extract_usd_from_text(text),
        "is_restricted": "restricted" in text.lower(),
    }

    lines = [
        re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()
        for line in text.splitlines()
    ]
    lines = [line for line in lines if line]

    try:
        start_index = lines.index("On Sale") + 1
    except ValueError:
        start_index = 0

    price_lines = []
    for line in lines[start_index:]:
        if re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", line):
            break
        if line.startswith("Listed:"):
            break
        if re.fullmatch(r"\d+d(?:\s+\d+h)?|\d+h|\d+m", line):
            break
        if re.fullmatch(r"~?\$?[\d,]+(?:\.\d+)?(?:\s+GRAM)?", line):
            price_lines.append(line)
        if len(price_lines) >= 2:
            break

    if price_lines:
        first_price = price_lines[0]
        second_price = price_lines[1] if len(price_lines) > 1 else ""

        if "$" in first_price:
            item["usd_price"] = to_float(first_price, 0.0)
            item["ton_price"] = 0.0
        elif "GRAM" in first_price:
            item["ton_price"] = to_float(first_price, 0.0)
            item["usd_price"] = 0.0
        elif "GRAM" in second_price:
            item["usd_price"] = to_float(first_price, 0.0)
            item["ton_price"] = 0.0
        elif item["usd_price"] <= 0:
            item["ton_price"] = to_float(first_price, 0.0)

    return item


def parse_number_candidates_from_page_text(text: str):
    if not text:
        return []

    matches = list(re.finditer(r"\+888[\s\d]{4,20}", text))
    candidates = []

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        item = parse_number_candidate_from_text(text[match.start():end])
        if item:
            candidates.append(item)

    return candidates


def parse_number_candidates_from_json_payload(payload, ton_usd_rate: float):
    candidates = {}

    def add_candidate(name: str, ton_price: float, usd_price: float, raw_obj):
        if not name:
            return
        if ton_price <= 0 and usd_price <= 0:
            return

        restricted = False
        for k, v in deep_walk(raw_obj):
            key_l = str(k).lower()
            if "restricted" in key_l:
                restricted = str(v).strip().lower() in {"true", "1", "yes", "restricted"}
                break
            if key_l == "status" and isinstance(v, str) and "restricted" in v.lower():
                restricted = True
                break

        key = name.lower()
        old = candidates.get(key)
        item = {
            "name": name,
            "ton_price": ton_price,
            "usd_price": usd_price,
            "is_restricted": restricted,
            "raw": raw_obj,
        }

        if old is None:
            candidates[key] = item
            return

        if candidate_sort_key(item, ton_usd_rate) < candidate_sort_key(old, ton_usd_rate):
            candidates[key] = item

    roots = payload if isinstance(payload, list) else [payload]

    for root in roots:
        if not isinstance(root, dict):
            continue

        maybe_objects = [root]
        for _, v in deep_walk(root):
            if isinstance(v, dict):
                maybe_objects.append(v)

        for obj in maybe_objects:
            names = []

            for _, v in obj.items():
                if isinstance(v, str) and looks_like_888_number(v):
                    names.append(normalize_888_number(v))

            if not names:
                for _, v in deep_walk(obj):
                    if isinstance(v, str) and looks_like_888_number(v):
                        names.append(normalize_888_number(v))

            if not names:
                continue

            ton_price, usd_price = extract_prices_from_dict(obj)
            for name in names:
                add_candidate(name, ton_price, usd_price, obj)

    return sorted(candidates.values(), key=lambda x: candidate_sort_key(x, ton_usd_rate))


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
    except Exception:
        return 0.0


async def fetch_marketapp_api_collection_items(
    collection_address: str,
    label: str,
    max_pages=None,
    stop_after_gram_price=None,
):
    if not MARKETAPP_API_TOKEN or not collection_address:
        return None

    items = []
    cursor = None
    page_limit = max_pages or MARKETAPP_API_MAX_PAGES
    cache_key = (collection_address, page_limit, stop_after_gram_price)
    if cache_key in MARKETAPP_API_COLLECTION_CACHE:
        cached_items = MARKETAPP_API_COLLECTION_CACHE[cache_key]
        print(f"DEBUG API COLLECTION CACHE label={label} total={len(cached_items)}")
        return cached_items

    headers = {
        "Authorization": MARKETAPP_API_TOKEN,
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            current_limit = 100
            for page_num in range(1, page_limit + 1):
                params = {
                    "filter_by": "onsale",
                    "limit": current_limit,
                }
                if cursor:
                    params["cursor"] = cursor

                resp = await client.get(
                    f"{MARKETAPP_API_BASE}/v1/nfts/collections/{collection_address}/",
                    params=params,
                    headers=headers,
                )
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 400 and items:
                        recovered = None
                        for retry_limit in [50, 25, 10, 1]:
                            retry_params = dict(params)
                            retry_params["limit"] = retry_limit
                            try:
                                retry_resp = await client.get(
                                    f"{MARKETAPP_API_BASE}/v1/nfts/collections/{collection_address}/",
                                    params=retry_params,
                                    headers=headers,
                                )
                                retry_resp.raise_for_status()
                                recovered = retry_resp
                                current_limit = retry_limit
                                print(
                                    "DEBUG API COLLECTION RECOVER "
                                    f"label={label} page={page_num} limit={retry_limit} total={len(items)}"
                                )
                                break
                            except Exception:
                                continue

                        if recovered is not None:
                            resp = recovered
                        else:
                            print(
                                "DEBUG API COLLECTION CAP "
                                f"label={label} page={page_num} status=400 total={len(items)}"
                            )
                            MARKETAPP_API_COLLECTION_CAPS.add(cache_key)
                            break
                    else:
                        raise

                if resp.status_code == 400 and items:
                    print(
                        "DEBUG API COLLECTION STOP "
                        f"label={label} page={page_num} status=400 total={len(items)}"
                    )
                    break
                payload = resp.json()

                page_items = payload.get("items") or []
                items.extend(page_items)
                cursor = payload.get("cursor")
                gram_prices = [
                    gram_price_from_marketapp_api_item(item)
                    for item in page_items
                ]
                gram_prices = [price for price in gram_prices if price > 0]
                page_min_gram = min(gram_prices, default=0.0)

                print(
                    "DEBUG API COLLECTION "
                    f"label={label} page={page_num} limit={current_limit} items={len(page_items)} total={len(items)} "
                    f"has_cursor={bool(cursor)} min_gram={page_min_gram:.2f}"
                )

                if not cursor or not page_items:
                    break
                if (
                    stop_after_gram_price is not None
                    and page_min_gram > stop_after_gram_price
                ):
                    break
    except Exception as e:
        print(f"DEBUG API COLLECTION FAIL label={label} error={type(e).__name__}: {e}")
        return None

    MARKETAPP_API_COLLECTION_CACHE[cache_key] = items
    return items


async def fetch_marketapp_browser_username_items(browser, base_url: str, length_value: int, seconds_budget: int):
    if not base_url or seconds_budget <= 0:
        return []

    deadline = asyncio.get_running_loop().time() + seconds_budget
    context = await browser.new_context(
        ignore_https_errors=True,
        locale="en-US",
        user_agent=MARKET_USER_AGENT,
    )
    page = await context.new_page()
    candidates = {}
    response_count = 0

    async def collect_response(response):
        nonlocal response_count
        try:
            ctype = (response.headers.get("content-type") or "").lower()
            if "application/json" not in ctype:
                return
            body = await response.text()
            if not body or body[0] not in "{[":
                return
            payload = json.loads(body)
            response_count += 1
            for item in parse_candidates_from_json_payload(payload, length_value):
                gram_price = item.get("ton_price", 0.0)
                if item.get("is_restricted"):
                    continue
                if gram_price > USERNAME_API_PRICE_LIMIT_GRAM:
                    continue
                key = item["name"].lower()
                old = candidates.get(key)
                if old is None or candidate_sort_key(item, 1.0) < candidate_sort_key(old, 1.0):
                    candidates[key] = item
        except Exception:
            return

    page.on("response", lambda response: asyncio.create_task(collect_response(response)))

    try:
        urls = [base_url]
        if "marketapp.org" in base_url:
            urls.append(base_url.replace("marketapp.org", "marketapp.ws"))
        elif "marketapp.ws" in base_url:
            urls.append(base_url.replace("marketapp.ws", "marketapp.org"))

        loaded = False
        for url in urls:
            if asyncio.get_running_loop().time() >= deadline:
                break
            try:
                await page.goto(url, wait_until="commit", timeout=30000)
                loaded = True
                break
            except Exception as e:
                print(f"DEBUG BROWSER USERNAMES GOTO length={length_value} error={type(e).__name__}: {e}")
                await page.wait_for_timeout(2500)
                if candidates:
                    loaded = True
                    break

        if loaded:
            await page.wait_for_timeout(3000)

            stable_rounds = 0
            last_count = 0
            for scroll_num in range(1, USERNAME_BROWSER_SCROLLS + 1):
                if asyncio.get_running_loop().time() >= deadline:
                    break

                await page.mouse.wheel(0, 5000)
                await page.wait_for_timeout(1200)

                count = len(candidates)
                if count == last_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_count = count

                if stable_rounds >= 8:
                    break

            await page.wait_for_timeout(1500)
    except Exception as e:
        print(f"DEBUG BROWSER USERNAMES FAIL length={length_value} error={type(e).__name__}: {e}")
    finally:
        await context.close()

    result = sorted(candidates.values(), key=lambda x: candidate_sort_key(x, 1.0))
    print(
        "DEBUG BROWSER USERNAMES "
        f"length={length_value} responses={response_count} candidates={len(result)}"
    )
    return result


def select_username_items(api_items, browser_items, length_value: int):
    rules = USERNAME_RULES[length_value]
    extra_count = USERNAME_EXTRA_COUNT[length_value]

    candidates_by_name = {}
    for raw in api_items or []:
        item = username_candidate_from_api_item(raw, length_value)
        gram_price = gram_price_from_marketapp_api_item(raw)
        if (
            item
            and not item.get("is_restricted")
            and (gram_price <= 0 or gram_price <= USERNAME_API_PRICE_LIMIT_GRAM)
        ):
            candidates_by_name[item["name"].lower()] = item

    for item in browser_items or []:
        if item.get("is_restricted"):
            continue
        gram_price = item.get("ton_price", 0.0)
        if gram_price > USERNAME_API_PRICE_LIMIT_GRAM:
            continue
        key = item["name"].lower()
        old = candidates_by_name.get(key)
        if old is None or candidate_sort_key(item, 1.0) < candidate_sort_key(old, 1.0):
            candidates_by_name[key] = item

    api_candidates = list(candidates_by_name.values())
    selected = []
    used = set()

    for rule_name, run_len, kind in rules:
        matches = [
            item
            for item in api_candidates
            if item["name"].lower() not in used
            and rule_match(username_clean(item["name"]), rule_name, run_len, kind)
        ]
        chosen = min(matches, key=lambda x: candidate_sort_key(x, 1.0), default=None)
        if chosen is None:
            continue

        chosen["matched_rule"] = rule_name
        used.add(chosen["name"].lower())
        selected.append(chosen)

    if extra_count > 0:
        extras = [
            item
            for item in sorted(api_candidates, key=lambda x: candidate_sort_key(x, 1.0))
            if item["name"].lower() not in used
        ]
        for item in extras:
            if len(selected) >= len(rules) + extra_count:
                break
            item["matched_rule"] = "extra"
            used.add(item["name"].lower())
            selected.append(item)

    return selected[: len(rules) + extra_count], len(api_candidates)


def valid_username_candidate(item: dict) -> bool:
    if not item:
        return False
    if item.get("is_restricted"):
        return False
    gram_price = item.get("ton_price", 0.0)
    return gram_price <= 0 or gram_price <= USERNAME_API_PRICE_LIMIT_GRAM


def merge_username_candidates(target: dict, items):
    for item in items or []:
        if not valid_username_candidate(item):
            continue
        key = item["name"].lower()
        old = target.get(key)
        if old is None or candidate_sort_key(item, 1.0) < candidate_sort_key(old, 1.0):
            target[key] = item


def api_username_candidates(api_items, length_value: int):
    candidates = {}
    for raw in api_items or []:
        item = username_candidate_from_api_item(raw, length_value)
        merge_username_candidates(candidates, [item])
    return candidates


def pick_rule_matches(candidates: dict, rules, selected=None, used=None, only_rules=None):
    selected = selected or []
    used = used or set()
    matched = set()
    allowed_rules = set(only_rules) if only_rules is not None else None

    for rule_name, run_len, kind in rules:
        if allowed_rules is not None and rule_name not in allowed_rules:
            continue

        matches = [
            item
            for item in candidates.values()
            if item["name"].lower() not in used
            and rule_match(username_clean(item["name"]), rule_name, run_len, kind)
        ]
        chosen = min(matches, key=lambda x: candidate_sort_key(x, 1.0), default=None)
        if chosen is None:
            continue

        chosen["matched_rule"] = rule_name
        used.add(chosen["name"].lower())
        selected.append(chosen)
        matched.add(rule_name)

    return selected, used, matched


def add_extra_username_items(candidates: dict, selected, used, target_count: int):
    for item in sorted(candidates.values(), key=lambda x: candidate_sort_key(x, 1.0)):
        if len(selected) >= target_count:
            break
        key = item["name"].lower()
        if key in used:
            continue
        item["matched_rule"] = "extra"
        used.add(key)
        selected.append(item)
    return selected


def query_values_for_rule(rule_name: str, run_len, kind: str):
    if kind == "alpha":
        return [ch * run_len for ch in USERNAME_QUERY_ALPHA_CHARS]
    if kind == "digit":
        return [ch * run_len for ch in USERNAME_QUERY_DIGIT_CHARS]
    if kind == "fixed":
        return [rule_name]
    return []


def add_or_replace_query(base_url: str, query_value: str) -> str:
    if not base_url:
        return ""

    if "query=" in base_url:
        return re.sub(r"query=[^&]*", f"query={quote(query_value)}", base_url)

    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}query={quote(query_value)}"


async def extract_first_row_from_page(page, expected_length: int):
    row_locator = page.locator("table tbody tr")
    count = await row_locator.count()
    if count == 0:
        row_locator = page.locator("tr")
        count = await row_locator.count()

    for i in range(count):
        row = row_locator.nth(i)
        try:
            text = await row.inner_text()
        except Exception:
            continue

        if not text or "@" not in text:
            continue

        name_match = re.search(r"@[A-Za-z0-9_]{4,32}", text)
        if not name_match:
            continue

        name = name_match.group(0)
        if len(name.lstrip("@")) != expected_length:
            continue

        price_match = re.search(r"▽\s*([\d,]+(?:\.\d+)?)", text)
        ton_price = 0.0
        if price_match:
            ton_price = to_float(price_match.group(1), 0.0)

        if ton_price <= 0:
            text_wo_name = text.replace(name, " ")
            ton_candidates = re.findall(r"(?<!\$)\b\d+(?:,\d{3})*(?:\.\d+)?\b", text_wo_name)
            for raw in ton_candidates:
                val = to_float(raw, 0.0)
                if val > 0:
                    ton_price = val
                    break

        if ton_price <= 0:
            continue

        return {
            "name": name,
            "length": expected_length,
            "ton_price": ton_price,
            "is_on_sale": True,
            "is_restricted": False,
            "raw_text": text,
        }

    return None


async def extract_username_candidates_from_page(page, expected_length: int):
    candidates = {}
    row_locator = page.locator("table tbody tr")
    count = await row_locator.count()
    if count == 0:
        row_locator = page.locator("tr")
        count = await row_locator.count()

    for i in range(count):
        row = row_locator.nth(i)
        try:
            text = await row.inner_text()
        except Exception:
            continue

        item = parse_username_candidate_from_text(text, expected_length)
        merge_username_candidates(candidates, [item])

    try:
        body_text = await page.locator("body").inner_text(timeout=10000)
        merge_username_candidates(
            candidates,
            parse_username_candidates_from_page_text(body_text, expected_length),
        )
    except Exception:
        pass

    return sorted(candidates.values(), key=lambda x: candidate_sort_key(x, 1.0))


def parse_username_candidates_from_page_text(text: str, expected_length: int):
    if not text:
        return []

    matches = list(re.finditer(r"@[A-Za-z0-9_]{4,32}", text))
    candidates = []

    for i, match in enumerate(matches):
        name = match.group(0)
        if len(name.lstrip("@")) != expected_length:
            continue

        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        for marker in ["Advanced solution", "NAVIGATION", "COMMUNITY", "Based on TON"]:
            marker_index = text.find(marker, match.start(), end)
            if marker_index != -1:
                end = marker_index
        item = parse_username_candidate_from_text(text[match.start():end], expected_length)
        if item:
            candidates.append(item)

    return candidates


def parse_username_candidate_from_text(text: str, expected_length: int):
    if not text or "@" not in text:
        return None
    if "on sale" not in text.lower():
        return None

    name_match = re.search(r"@[A-Za-z0-9_]{4,32}", text)
    if not name_match:
        return None

    name = name_match.group(0)
    if len(name.lstrip("@")) != expected_length:
        return None

    usd_price = extract_usd_from_text(text)
    ton_price = 0.0

    if usd_price <= 0:
        gram_match = re.search(r"([\d,]+(?:\.\d+)?)\s*GRAM", text, re.I)
        if gram_match:
            ton_price = to_float(gram_match.group(1), 0.0)

    if usd_price <= 0 and ton_price <= 0:
        price_match = re.search(r"鈻絓s*([\d,]+(?:\.\d+)?)", text)
        if price_match:
            ton_price = to_float(price_match.group(1), 0.0)

    if usd_price <= 0 and ton_price <= 0:
        text_wo_name = text.replace(name, " ")
        ton_candidates = re.findall(r"(?<!\$)\b\d+(?:,\d{3})*(?:\.\d+)?\b", text_wo_name)
        for raw in ton_candidates:
            val = to_float(raw, 0.0)
            if val > 0:
                ton_price = val
                break

    if usd_price <= 0 and ton_price <= 0:
        return None

    return {
        "name": name,
        "length": expected_length,
        "ton_price": ton_price,
        "usd_price": usd_price,
        "is_on_sale": True,
        "is_restricted": "restricted" in text.lower(),
        "raw_text": text,
    }


async def fetch_query_candidates(browser, url: str, expected_length: int):
    query_match = re.search(r"[?&]query=([^&]*)", url)
    query_value = query_match.group(1) if query_match else ""
    urls = [url]
    if "marketapp.org" in url:
        urls.append(url.replace("marketapp.org", "marketapp.ws"))
    elif "marketapp.ws" in url:
        urls.append(url.replace("marketapp.ws", "marketapp.org"))

    candidates = {}
    last_error = None

    for attempt in range(1, 3):
        context = await browser.new_context(
            ignore_https_errors=True,
            locale="en-US",
            user_agent=MARKET_USER_AGENT,
        )
        page = await context.new_page()
        responses = []
        attempt_had_error = False

        def on_response(response):
            responses.append(response)

        page.on("response", on_response)

        try:
            loaded = False
            for target_url in urls:
                try:
                    await page.goto(target_url, wait_until="commit", timeout=10000)
                    loaded = True
                    break
                except Exception as e:
                    attempt_had_error = True
                    last_error = e
                    await page.wait_for_timeout(600)
                    if responses:
                        loaded = True
                        break
                if loaded:
                    break

            await page.wait_for_timeout(1200 if loaded else 600)

            for response in responses[-80:]:
                try:
                    ctype = (response.headers.get("content-type") or "").lower()
                    body = await response.text()
                    if not body:
                        continue

                    if "application/json" in ctype and body[0] in "{[":
                        payload = json.loads(body)
                        merge_username_candidates(
                            candidates,
                            parse_candidates_from_json_payload(payload, expected_length),
                        )
                    elif "text/html" in ctype and "@" in body:
                        text = unescape(re.sub(r"<[^>]+>", "\n", body))
                        merge_username_candidates(
                            candidates,
                            parse_username_candidates_from_page_text(text, expected_length),
                        )
                except Exception:
                    continue

            try:
                await page.wait_for_selector("tr", timeout=2000)
            except PlaywrightTimeoutError:
                pass

            try:
                dom_candidates = await extract_username_candidates_from_page(page, expected_length)
            except Exception as e:
                print(
                    "DEBUG QUERY DOM SKIP "
                    f"length={expected_length} query={query_value} attempt={attempt} error={type(e).__name__}"
                )
                dom_candidates = []

            merge_username_candidates(candidates, dom_candidates)
        finally:
            await context.close()

        if candidates:
            result = sorted(candidates.values(), key=lambda x: candidate_sort_key(x, 1.0))
            print(
                "DEBUG QUERY OK "
                f"length={expected_length} query={query_value} attempt={attempt} candidates={len(result)}"
            )
            return result

        if attempt < 2 and attempt_had_error:
            await asyncio.sleep(0.4)
        else:
            break

    if last_error is not None:
        print(
            "DEBUG QUERY EMPTY "
            f"length={expected_length} query={query_value} error={type(last_error).__name__}"
        )
    return []


async def fetch_query_result(browser, url: str, expected_length: int):
    candidates = await fetch_query_candidates(browser, url, expected_length)
    return candidates[0] if candidates else None


async def fetch_best_match_by_query(browser, base_url: str, length_value: int, rule_name: str, run_len, kind: str):
    if not base_url:
        return None

    if kind == "alpha":
        queries = [ch * run_len for ch in USERNAME_QUERY_ALPHA_CHARS]
    elif kind == "digit":
        queries = [ch * run_len for ch in USERNAME_QUERY_DIGIT_CHARS]
    elif kind == "fixed":
        queries = [rule_name]
    else:
        return None

    for q in queries:
        url = add_or_replace_query(base_url, q)
        try:
            result = await fetch_query_result(browser, url, length_value)
        except Exception as e:
            print(f"DEBUG QUERY FAIL length={length_value} rule={rule_name} query={q} error={repr(e)}")
            result = None

        if result and rule_match(username_clean(result["name"]), rule_name, run_len, kind):
            result["matched_rule"] = rule_name
            print(f"DEBUG QUERY HIT length={length_value} rule={rule_name} query={q} name={result['name']}")
            return result

    return None


async def fetch_all_username_items():
    return []


async def build_username_section(browser, base_url: str, length_value: int):
    rules = USERNAME_RULES[length_value]
    extra_count = USERNAME_EXTRA_COUNT[length_value]

    selected = []
    used = set()
    last_price = None

    if MARKETAPP_API_TOKEN:
        collection_address = collection_address_from_url(base_url)
        page_limit = USERNAME_API_MAX_PAGES
        cache_key = (collection_address, page_limit, USERNAME_API_PRICE_LIMIT_GRAM)
        api_items = await fetch_marketapp_api_collection_items(
            collection_address,
            f"usernames-{length_value}",
            max_pages=page_limit,
            stop_after_gram_price=USERNAME_API_PRICE_LIMIT_GRAM,
        )
        if api_items is None:
            print(f"ERROR API USERNAMES length={length_value} unavailable; use browser supplement")
            api_items = []

        api_candidates = api_username_candidates(api_items, length_value)

        query_pool = {}
        query_jobs = []
        for rule_name, run_len, kind in rules:
            for q in query_values_for_rule(rule_name, run_len, kind):
                query_jobs.append((rule_name, q, add_or_replace_query(base_url, q)))

        sem = asyncio.Semaphore(USERNAME_QUERY_CONCURRENCY)

        async def fetch_query_job(job):
            rule_name, q, url = job
            async with sem:
                try:
                    return await fetch_query_candidates(browser, url, length_value)
                except Exception as e:
                    print(
                        "DEBUG QUERY POOL FAIL "
                        f"length={length_value} rule={rule_name} query={q} error={type(e).__name__}: {e}"
                    )
                    return []

        for query_items in await asyncio.gather(*(fetch_query_job(job) for job in query_jobs)):
            merge_username_candidates(query_pool, query_items)

        selected, used, api_matched = pick_rule_matches(api_candidates, rules)
        missing_rules = [
            rule
            for rule in rules
            if rule[0] not in api_matched
        ]
        selected, used, query_matched = pick_rule_matches(
            query_pool,
            rules,
            selected=selected,
            used=used,
            only_rules={rule[0] for rule in missing_rules},
        )

        all_candidates = dict(query_pool)
        merge_username_candidates(all_candidates, api_candidates.values())
        selected = add_extra_username_items(
            all_candidates,
            selected,
            used,
            len(rules) + extra_count,
        )

        print(
            "DEBUG USERNAMES "
            f"length={length_value} api_items={len(api_items)} api_candidates={len(api_candidates)} "
            f"query_requests={len(query_jobs)} query_pool={len(query_pool)} query_rules={len(query_matched)} "
            f"api_rules={len(api_matched)} missing_rules_after_api={len(missing_rules)} "
            f"final_selected={len(selected)} "
            f"price_limit_gram={USERNAME_API_PRICE_LIMIT_GRAM:.0f} "
            f"official_api_cursor_cap={cache_key in MARKETAPP_API_COLLECTION_CAPS}"
        )
        return selected[: len(rules) + extra_count]

    for rule_name, run_len, kind in rules:
        chosen = await fetch_best_match_by_query(browser, base_url, length_value, rule_name, run_len, kind)

        if chosen and chosen["name"].lower() in used:
            chosen = None

        if chosen is None:
            continue

        used.add(chosen["name"].lower())
        selected.append(chosen)

        if chosen["ton_price"] > 0:
            last_price = chosen["ton_price"]

    if extra_count > 0 and base_url:
        filler_queries = [
            "", "a", "e", "i", "o", "u",
            "1", "6", "8", "9", "0",
            "aa", "11", "66", "88",
        ]
        for q in filler_queries:
            if len(selected) >= len(rules) + extra_count:
                break

            url = add_or_replace_query(base_url, q)
            try:
                result = await fetch_query_result(browser, url, length_value)
            except Exception:
                result = None

            if not result:
                continue
            if result["name"].lower() in used:
                continue

            result["matched_rule"] = "extra"
            used.add(result["name"].lower())
            selected.append(result)

    return selected[: len(rules) + extra_count]


async def fetch_numbers_floor(browser, base_url: str, ton_usd_rate: float):
    if not base_url:
        return empty_number_floor()

    api_items = await fetch_marketapp_api_collection_items(
        collection_address_from_url(base_url),
        "numbers",
    )
    if api_items is not None:
        api_candidates = []
        for raw in api_items:
            item = number_candidate_from_api_item(raw)
            if item:
                api_candidates.append(item)

        api_groups = group_number_candidates(
            sorted(api_candidates, key=lambda x: candidate_sort_key(x, ton_usd_rate))
        )
        print(
            "DEBUG API NUMBERS "
            f"candidates={len(api_candidates)} has4={len(api_groups['has4'])} no4={len(api_groups['no4'])}"
        )
        return api_groups

    final_groups = empty_number_floor()

    for attempt in range(1, NUMBERS_PAGE_ATTEMPTS + 1):
        context = await browser.new_context(
            ignore_https_errors=True,
            locale="en-US",
            user_agent=MARKET_USER_AGENT,
        )
        page = await context.new_page()

        responses = []

        def on_response(response):
            responses.append(response)

        page.on("response", on_response)

        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"DEBUG NUMBERS attempt={attempt} goto_error={repr(e)}")

        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass

        await page.wait_for_timeout(3000)

        json_candidates = []
        for response in responses[-50:]:
            try:
                ctype = (response.headers.get("content-type") or "").lower()
                if "application/json" not in ctype:
                    continue

                body = await response.text()
                if not body or body[0] not in "[{":
                    continue

                payload = json.loads(body)
                json_candidates.extend(parse_number_candidates_from_json_payload(payload, ton_usd_rate))
            except Exception:
                continue

        json_groups = group_number_candidates(json_candidates)
        if json_groups["has4"] or json_groups["no4"]:
            print(
                "DEBUG NUMBERS "
                f"attempt={attempt} source=json json_candidates={len(json_candidates)} "
                f"has4={len(json_groups['has4'])} no4={len(json_groups['no4'])}"
            )
            await context.close()
            return json_groups

        body_text = ""
        try:
            body_text = await page.locator("body").inner_text(timeout=10000)
        except Exception as e:
            print(f"DEBUG NUMBERS attempt={attempt} body_error={repr(e)}")

        text_candidates = parse_number_candidates_from_page_text(body_text)
        text_groups = group_number_candidates(text_candidates)
        print(
            "DEBUG NUMBERS "
            f"attempt={attempt} url={page.url} body_len={len(body_text)} "
            f"plus888={body_text.count('+888')} text_candidates={len(text_candidates)} "
            f"has4={len(text_groups['has4'])} no4={len(text_groups['no4'])}"
        )

        await context.close()

        if text_groups["has4"] or text_groups["no4"]:
            return text_groups

        final_groups = text_groups

    print(
        "DEBUG NUMBERS final "
        f"has4={len(final_groups['has4'])} no4={len(final_groups['no4'])}"
    )
    return final_groups

def username_add_by_rule(item):
    length_value = item.get("length")
    matched_rule = item.get("matched_rule", "")

    if length_value == 5 and matched_rule == "4拼":
        return 100.0
    if length_value == 6 and matched_rule == "5拼":
        return 100.0
    if length_value == 7 and matched_rule == "6拼":
        return 70.0

    return USERNAME_ADD_USD.get(length_value, 50.0)


def build_usernames_message(section_5, section_6, section_7, ton_usd_rate):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    lines = []

    lines.append("【5位用户名】")
    if not section_5:
        lines.append("暂无数据")
    else:
        for item in section_5:
            add_usd = username_add_by_rule(item)
            usd_val = build_display_usd(item, ton_usd_rate, add_usd)
            lines.append(f"{item['name']}  ${display_price_int(usd_val)}")

    lines.append("")
    lines.append("【6位用户名】")
    if not section_6:
        lines.append("暂无数据")
    else:
        for item in section_6:
            add_usd = username_add_by_rule(item)
            usd_val = build_display_usd(item, ton_usd_rate, add_usd)
            lines.append(f"{item['name']}  ${display_price_int(usd_val)}")

    lines.append("")
    lines.append("【7位用户名】")
    if not section_7:
        lines.append("暂无数据")
    else:
        for item in section_7:
            add_usd = username_add_by_rule(item)
            usd_val = build_display_usd(item, ton_usd_rate, add_usd)
            lines.append(f"{item['name']}  ${display_price_int(usd_val)}")

    lines.append("")
    lines.append(f"更多用户名咨询客服，更新时间：{now_str}")

    body = html_escape("\n".join(lines))
    return f"多用户名价格实时更新（点开展开）\n<blockquote expandable>{body}</blockquote>"


def build_numbers_message(number_floor, ton_usd_rate):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    lines = ["📱【官方888号】地板价"]

    has4_items = number_floor.get("has4") or []
    if isinstance(has4_items, dict):
        has4_items = [has4_items]

    lines.append("【📱+888号码中带4】")
    if has4_items:
        for item in has4_items[:NUMBER_ITEMS_PER_GROUP]:
            usd_val = build_display_usd(item, ton_usd_rate, NUMBER_ADD_USD["has4"])
            if usd_val > 0:
                lines.append(f"{item['name']} - ${display_number_price_int(usd_val)}")
            else:
                lines.append(f"{item['name']} - 暂无有效价格")
    else:
        lines.append("暂无数据")

    no4_items = number_floor.get("no4") or []
    if isinstance(no4_items, dict):
        no4_items = [no4_items]

    lines.append("")
    lines.append("【📱+888号码中不带4】")
    if no4_items:
        for item in no4_items[:NUMBER_ITEMS_PER_GROUP]:
            usd_val = build_display_usd(item, ton_usd_rate, NUMBER_ADD_USD["no4"])
            if usd_val > 0:
                lines.append(f"{item['name']} - ${display_number_price_int(usd_val)}")
            else:
                lines.append(f"{item['name']} - 暂无有效价格")
    else:
        lines.append("暂无数据")

    lines.append("")
    lines.append("📱 自有500+号码库存")
    lines.append("🔐 Telegram官方匿名号码完全隐私")
    lines.append("⏰ 24小时自助接码即租即用")
    lines.append("🤖 自助下单：@zuhao8bot")
    lines.append("")
    lines.append(f"更新时间：{now_str}")
    return "\n".join(lines)


def build_promo_message_html():
    return PROMO_MESSAGE_HTML


async def telegram_api(method: str, payload=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    async with httpx.AsyncClient(timeout=30) as client:
        if payload is None:
            resp = await client.get(url)
        else:
            resp = await client.post(url, json=payload)

    try:
        return resp.json()
    except Exception:
        raise RuntimeError(f"Telegram {method} failed: HTTP {resp.status_code}, body={resp.text[:500]}")


async def verify_telegram_bot():
    data = await telegram_api("getMe")
    if not data.get("ok"):
        raise RuntimeError(f"Telegram getMe failed: {data}")


async def send_new_message(chat_id: str, text: str, label: str, parse_mode=None, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    data = await telegram_api("sendMessage", payload)
    if not data.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed for {label}: {data}")

    result = data.get("result", {})
    new_message_id = result.get("message_id")
    print(f"DEBUG NEW MESSAGE ID [{label}]:", new_message_id)
    return new_message_id


async def edit_existing_message(chat_id: str, message_id, text: str, label: str, parse_mode=None, reply_markup=None):
    if not message_id:
        return False

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    data = await telegram_api("editMessageText", payload)

    if data.get("ok"):
        return True

    desc = str(data.get("description", "")).lower()
    error_code = data.get("error_code")

    if "message is not modified" in desc:
        return True

    if error_code in {400, 404}:
        print(f"ERROR TELEGRAM EDIT label={label} code={error_code} description={desc}")
        return False

    raise RuntimeError(f"Telegram edit failed for {label}: {data}")


async def upsert_message(chat_id: str, message_id, text: str, label: str, parse_mode=None, reply_markup=None):
    edited = await edit_existing_message(
        chat_id,
        message_id,
        text,
        label,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )
    if edited:
        return

    new_message_id = await send_new_message(
        chat_id,
        text,
        label,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )
    print(f"IMPORTANT: Update {label} secret to:", new_message_id)


async def update_required_message(chat_id: str, message_id, text: str, label: str, parse_mode=None):
    try:
        edited = await edit_existing_message(
            chat_id,
            message_id,
            text,
            label,
            parse_mode=parse_mode,
        )
    except Exception as e:
        message = f"{label} edit failed: {type(e).__name__}: {e}"
        print(f"ERROR: {message}")
        return message

    if edited:
        return None

    message = f"{label} edit failed; update the {label} secret to the existing Telegram message id"
    print(f"ERROR: {message}")
    return message


async def launch_market_browser(playwright):
    if MARKET_BROWSER == "firefox":
        return await playwright.firefox.launch(headless=True)
    return await playwright.chromium.launch(headless=True, args=CHROMIUM_ARGS)


async def update_usernames_only():
    if not all((BOT_TOKEN, USERNAMES_CHAT_ID, USERNAMES_MESSAGE_ID)):
        raise RuntimeError("Local username Telegram settings are incomplete")
    if not all((USERNAMES_5_URL, USERNAMES_6_URL, USERNAMES_7_URL)):
        raise RuntimeError("Local username Marketapp URLs are incomplete")

    ton_usd_rate = await fetch_ton_usd_rate()
    async with async_playwright() as p:
        browser = await launch_market_browser(p)
        try:
            section_5 = await build_username_section(browser, USERNAMES_5_URL, 5)
            section_6 = await build_username_section(browser, USERNAMES_6_URL, 6)
            section_7 = await build_username_section(browser, USERNAMES_7_URL, 7)
        finally:
            await browser.close()

    usernames_text = build_usernames_message(section_5, section_6, section_7, ton_usd_rate)
    await verify_telegram_bot()
    update_error = await update_required_message(
        USERNAMES_CHAT_ID,
        USERNAMES_MESSAGE_ID,
        usernames_text,
        "USERNAMES_MESSAGE_ID",
        parse_mode="HTML",
    )
    if update_error:
        raise RuntimeError(update_error)


async def update_online_only():
    ton_usd_rate = await fetch_ton_usd_rate()
    print(
        "DEBUG RUNTIME "
        f"sha={os.environ.get('GITHUB_SHA', 'local')} "
        f"runner={os.environ.get('RUNNER_OS', platform.system())} "
        f"python={platform.python_version()} "
        f"browser={MARKET_BROWSER} "
        f"numbers_attempts={NUMBERS_PAGE_ATTEMPTS}"
    )

    number_floor = {"has4": None, "no4": None}
    if NUMBERS_URL:
        async with async_playwright() as p:
            browser = await launch_market_browser(p)
            try:
                number_floor = await fetch_numbers_floor(browser, NUMBERS_URL, ton_usd_rate)
            finally:
                await browser.close()

    has_number_data = bool(number_floor.get("has4") or number_floor.get("no4"))
    numbers_text = (
        build_numbers_message(number_floor, ton_usd_rate)
        if NUMBERS_URL and has_number_data
        else None
    )
    numbers_update_error = None
    if NUMBERS_URL and not has_number_data:
        numbers_update_error = "Number sources returned no data; retained the existing Telegram message"
        print(f"ERROR: {numbers_update_error}")
    promo_text = build_promo_message_html()
    promo_reply_markup = build_promo_reply_markup()

    await verify_telegram_bot()

    if numbers_text:
        await upsert_message(
            NUMBERS_CHAT_ID,
            NUMBERS_MESSAGE_ID,
            numbers_text,
            "NUMBERS_MESSAGE_ID",
        )

    await upsert_message(
        PROMO_CHAT_ID,
        PROMO_MESSAGE_ID,
        promo_text,
        "PROMO_MESSAGE_ID",
        parse_mode="HTML",
        reply_markup=promo_reply_markup,
    )

    if numbers_update_error:
        raise RuntimeError(numbers_update_error)


async def main():
    if RUN_MODE == "online":
        await update_online_only()
        return
    if RUN_MODE == "usernames":
        await update_usernames_only()
        return

    await update_usernames_only()
    await update_online_only()


if __name__ == "__main__":
    asyncio.run(main())
