import asyncio
import os
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
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


def parse_message_id(value: str):
    value = (value or "").strip()
    if value.isdigit() and int(value) > 0:
        return int(value)
    return None


def parse_marketapp_url(url: str):
    url = (url or "").strip()
    if not url:
        return {"collection_address": "", "length": None}

    collection_address = normalize_collection_address(url)

    length_value = None
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        attrs = qs.get("attrs", [])
        for attr in attrs:
            m = re.search(r"Length~(\d+)", attr)
            if m:
                length_value = int(m.group(1))
                break
    except Exception:
        pass

    return {
        "collection_address": collection_address,
        "length": length_value,
    }


def marketapp_api_params_from_url(url: str):
    url = (url or "").strip()
    if not url:
        return {}

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    out = {}

    single_keys = [
        "query",
        "sort_by",
        "filter_by",
        "min_price",
        "max_price",
    ]
    for key in single_keys:
        values = qs.get(key, [])
        if values and values[0] != "":
            out[key] = values[0]

    attrs = qs.get("attrs", [])
    if attrs:
        out["attrs"] = attrs

    return out


BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
MARKETAPP_API_TOKEN = os.environ["MARKETAPP_API_TOKEN"].strip()

USERNAMES_CHAT_ID = os.environ["USERNAMES_CHAT_ID"].strip()
USERNAMES_MESSAGE_ID = parse_message_id(os.environ.get("USERNAMES_MESSAGE_ID", "0"))

NUMBERS_CHAT_ID = os.environ["NUMBERS_CHAT_ID"].strip()
NUMBERS_MESSAGE_ID = parse_message_id(os.environ.get("NUMBERS_MESSAGE_ID", "0"))

PROMO_CHAT_ID = (os.environ.get("PROMO_CHAT_ID", "").strip() or NUMBERS_CHAT_ID)
PROMO_MESSAGE_ID = parse_message_id(os.environ.get("PROMO_MESSAGE_ID", "0"))

USERNAMES_5_URL = os.environ.get("USERNAMES_5_URL", "").strip()
USERNAMES_6_URL = os.environ.get("USERNAMES_6_URL", "").strip()
USERNAMES_7_URL = os.environ.get("USERNAMES_7_URL", "").strip()

USERNAMES_5_INFO = parse_marketapp_url(USERNAMES_5_URL)
USERNAMES_6_INFO = parse_marketapp_url(USERNAMES_6_URL)
USERNAMES_7_INFO = parse_marketapp_url(USERNAMES_7_URL)

USERNAMES_5_API_PARAMS = marketapp_api_params_from_url(USERNAMES_5_URL)
USERNAMES_6_API_PARAMS = marketapp_api_params_from_url(USERNAMES_6_URL)
USERNAMES_7_API_PARAMS = marketapp_api_params_from_url(USERNAMES_7_URL)

USERNAMES_COLLECTION_ADDRESS = (
    USERNAMES_5_INFO["collection_address"]
    or USERNAMES_6_INFO["collection_address"]
    or USERNAMES_7_INFO["collection_address"]
    or "EQCA14o1-VWhS2efqoh_9M1b_A9DtKTuoqfmkn83AbJzwnPi"
)

NUMBERS_COLLECTION_ADDRESS = normalize_collection_address(
    os.environ.get("NUMBERS_COLLECTION_ADDRESS", "")
)

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "70"))
MAX_QUERY_PAGES = int(os.environ.get("MAX_QUERY_PAGES", "1"))

USERNAME_ADD_USD = {
    5: 50.0,
    6: 50.0,
    7: 50.0,
}

NUMBER_ADD_USD = {
    "has4": 50.0,
    "no4": 50.0,
}

USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_]{4,32}$")
NUMBER_RE = re.compile(r"^\+?\d[\d\s]{6,}$")
USERNAME_QUERY_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

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

USERNAME_PATTERN_CONFIG = {
    5: {
        "patterns": [
            "aaaa*",
            "aaa*a",
            "aa*aa",
            "a*aaa",
            "*aaaa",
            "aaa**",
            "aa**a",
            "a**aa",
            "aaa",
            "aa***",
            "a***a",
            "***aa",
            "a****",
            "****a",
        ],
        "extra_count": 6,
    },
    6: {
        "patterns": [
            "aaaaa*",
            "aaaa*a",
            "aaa*aa",
            "aa*aaa",
            "a*aaaa",
            "*aaaaa",
            "aaaa",
            "aaa**a",
            "aa**aa",
            "a**aaa",
            "aaaa",
            "aaa***",
            "aa***a",
            "a***aa",
            "***aaa",
            "aa****",
            "a****a",
            "****aa",
        ],
        "extra_count": 2,
    },
    7: {
        "patterns": [
            "aaaaaa*",
            "aaaaa*a",
            "aaaa*aa",
            "aaa*aaa",
            "aa*aaaa",
            "a*aaaaa",
            "aaaaa",
            "aaaa**a",
            "aaa**aa",
            "aa**aaa",
            "a**aaaa",
        ],
        "extra_count": 0,
    },
}


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
        if length_value not in {5, 6, 7}:
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
    except Exception:
        return 0.0


async def safe_get(client, url, headers, params, retries=2, fail_soft=False):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, headers=headers, params=params)
            return resp
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
            last_error = e
            print(f"DEBUG HTTP RETRY {attempt}/{retries} params={params} error={repr(e)}")
            if attempt < retries:
                await asyncio.sleep(attempt)

    if fail_soft:
        print(f"DEBUG HTTP FAIL_SOFT params={params} error={repr(last_error)}")
        return None

    raise last_error


def merge_lowest_price_item(items_map, item):
    key = item["name"].lower()
    old = items_map.get(key)
    if old is None:
        items_map[key] = item
        return

    old_price = old["ton_price"] if old["ton_price"] > 0 else 10**18
    new_price = item["ton_price"] if item["ton_price"] > 0 else 10**18
    if new_price < old_price:
        items_map[key] = item


async def fetch_collection_items(collection_address: str, mode: str, extra_params=None, fail_soft=False, page_limit=None):
    if not collection_address:
        return []

    api_url = f"https://api.marketapp.ws/v1/nfts/collections/{collection_address}/"
    headers = {
        "Authorization": MARKETAPP_API_TOKEN,
        "Accept": "application/json",
    }

    cursor = None
    items_map = {}
    no_new_pages = 0
    extra_params = dict(extra_params or {})

    timeout = httpx.Timeout(connect=15.0, read=30.0, write=20.0, pool=30.0)
    total_pages = page_limit or MAX_PAGES

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for page_no in range(1, total_pages + 1):
            params = {
                "limit": 100,
                "filter_by": extra_params.get("filter_by", "onsale"),
            }

            for key, value in extra_params.items():
                if key in {"limit", "cursor", "filter_by"}:
                    continue
                if value is None:
                    continue
                if isinstance(value, str) and value == "":
                    continue
                params[key] = value

            if cursor:
                params["cursor"] = cursor

            resp = await safe_get(
                client,
                api_url,
                headers=headers,
                params=params,
                retries=2,
                fail_soft=fail_soft,
            )

            if resp is None:
                return []

            if resp.status_code == 400:
                body_text = resp.text[:2000]
                if "Invalid cursor format" in body_text:
                    print(f"DEBUG {mode.upper()} STOP invalid cursor at page {page_no}")
                    break
                if fail_soft:
                    print(f"DEBUG {mode.upper()} FAIL_SOFT 400 page {page_no}: {body_text[:200]}")
                    return []
                resp.raise_for_status()

            if resp.status_code >= 400:
                if fail_soft:
                    print(f"DEBUG {mode.upper()} FAIL_SOFT {resp.status_code} page {page_no}: {resp.text[:200]}")
                    return []
                resp.raise_for_status()

            payload = resp.json()
            raw_items = get_items_list(payload)

            if not raw_items:
                print(f"DEBUG {mode.upper()} STOP empty page {page_no}")
                break

            before_count = len(items_map)

            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue

                item = parse_item(raw, mode=mode)
                if not item:
                    continue

                merge_lowest_price_item(items_map, item)

            after_count = len(items_map)
            added_count = after_count - before_count
            print(f"DEBUG {mode.upper()} PAGE {page_no}: raw={len(raw_items)} new_unique={added_count} total={after_count} params={extra_params}")

            if added_count == 0:
                no_new_pages += 1
            else:
                no_new_pages = 0

            if no_new_pages >= 3:
                print(f"DEBUG {mode.upper()} STOP 3 pages no new unique")
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
                print(f"DEBUG {mode.upper()} STOP no next cursor")
                break

            cursor = next_cursor

    return list(items_map.values())


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


def max_a_run(pattern: str) -> int:
    best = 0
    cur = 0
    for ch in pattern:
        if ch == "a":
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def pattern_total_a(pattern: str) -> int:
    return pattern.count("a")


def pattern_query_lengths(pattern: str):
    lengths = {max_a_run(pattern), pattern_total_a(pattern)}
    return sorted(x for x in lengths if x >= 2)


def match_pattern(clean: str, pattern: str) -> bool:
    if len(pattern) == len(clean):
        groups = {}
        for i, ch in enumerate(pattern):
            if ch == "*":
                continue
            groups.setdefault(ch, []).append(i)

        for positions in groups.values():
            first_char = clean[positions[0]]
            for pos in positions[1:]:
                if clean[pos] != first_char:
                    return False
        return True

    if pattern and set(pattern) == {"a"} and len(pattern) <= len(clean):
        run_len = len(pattern)
        for i in range(len(clean) - run_len + 1):
            chunk = clean[i:i + run_len]
            if len(set(chunk)) == 1:
                return True
        return False

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


async def fetch_best_match_for_pattern(length_value: int, pattern: str, base_params: dict):
    query_lengths = pattern_query_lengths(pattern)
    if not query_lengths:
        return None

    params_base = dict(base_params or {})
    params_base["filter_by"] = "onsale"

    attrs = list(params_base.get("attrs", []))
    need_attr = f"Length~{length_value}"
    if need_attr not in attrs:
        attrs.append(need_attr)
    params_base["attrs"] = attrs

    candidates = {}

    for ql in query_lengths:
        for ch in USERNAME_QUERY_CHARS:
            params = dict(params_base)
            params["query"] = ch * ql

            items = await fetch_collection_items(
                USERNAMES_COLLECTION_ADDRESS,
                mode="usernames",
                extra_params=params,
                fail_soft=True,
                page_limit=MAX_QUERY_PAGES,
            )

            for item in items:
                if item["length"] != length_value:
                    continue
                if match_pattern(username_clean(item["name"]), pattern):
                    merge_lowest_price_item(candidates, item)

            if len(candidates) >= 2:
                return sort_items(list(candidates.values()))[0]

    if not candidates:
        return None

    return sort_items(list(candidates.values()))[0]


async def build_username_section(all_items, length_value: int, api_params: dict):
    config = USERNAME_PATTERN_CONFIG[length_value]
    patterns = config["patterns"]
    extra_count = config["extra_count"]

    full_pool = sort_items([
        x for x in all_items
        if x["length"] == length_value
        and not (x["is_on_sale"] is False and x["ton_price"] <= 0)
    ])

    used = set()
    selected = []
    last_price = None

    for pattern in patterns:
        local_matches = [
            x for x in full_pool
            if x["name"].lower() not in used
            and match_pattern(username_clean(x["name"]), pattern)
        ]

        if local_matches:
            chosen = local_matches[0]
        else:
            chosen = await fetch_best_match_for_pattern(length_value, pattern, api_params)

            if chosen and chosen["name"].lower() in used:
                chosen = None

            if chosen is None:
                remaining = [x for x in full_pool if x["name"].lower() not in used]
                chosen = pick_closest_by_price(remaining, last_price)

        if not chosen:
            break

        used.add(chosen["name"].lower())
        selected.append(chosen)

        if chosen["ton_price"] > 0:
            last_price = chosen["ton_price"]

    if extra_count > 0:
        remaining = [x for x in full_pool if x["name"].lower() not in used]
        for x in remaining[:extra_count]:
            used.add(x["name"].lower())
            selected.append(x)

    return selected


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


def html_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_usernames_message(section_5, section_6, section_7, ton_usd_rate):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    lines = []

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
    lines.append("【7位用户名】")
    if not section_7:
        lines.append("暂无数据")
    else:
        for item in section_7:
            usd_val = usd_after_add(item["ton_price"], ton_usd_rate, USERNAME_ADD_USD[7])
            lines.append(f"{item['name']}  ${usd_val:.2f}")

    lines.append("")
    lines.append(f"更多用户名咨询客服，更新时间：{now_str}")

    body = html_escape("\n".join(lines))
    return f"多用户名价格实时更新（点开展开）\n<blockquote expandable>{body}</blockquote>"


def build_numbers_message(number_floor, ton_usd_rate):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    lines = ["📱【官方888号】地板价"]

    item = number_floor.get("has4")
    if item:
        usd_val = usd_after_add(item["ton_price"], ton_usd_rate, NUMBER_ADD_USD["has4"])
        lines.append(f"【含4正常】 {item['name']} - ${usd_val:.2f}")
    else:
        lines.append("【含4正常】 暂无数据")

    item = number_floor.get("no4")
    if item:
        usd_val = usd_after_add(item["ton_price"], ton_usd_rate, NUMBER_ADD_USD["no4"])
        lines.append(f"【无4正常】 {item['name']} - ${usd_val:.2f}")
    else:
        lines.append("【无4正常】 暂无数据")

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


async def fetch_all_username_items():
    items = await fetch_collection_items(
        USERNAMES_COLLECTION_ADDRESS,
        mode="usernames",
        extra_params={},
        fail_soft=False,
    )
    print(f"DEBUG FULL USERNAMES TOTAL={len(items)}")
    return items


async def main():
    ton_usd_rate = await fetch_ton_usd_rate()

    all_username_items = await fetch_all_username_items()

    section_5 = await build_username_section(all_username_items, 5, USERNAMES_5_API_PARAMS)
    section_6 = await build_username_section(all_username_items, 6, USERNAMES_6_API_PARAMS)
    section_7 = await build_username_section(all_username_items, 7, USERNAMES_7_API_PARAMS)

    number_floor = {}
    if NUMBERS_COLLECTION_ADDRESS:
        number_items = await fetch_collection_items(
            NUMBERS_COLLECTION_ADDRESS,
            mode="numbers",
            extra_params={},
            fail_soft=False,
        )
        number_floor = build_number_floor(number_items)

    usernames_text = build_usernames_message(section_5, section_6, section_7, ton_usd_rate)
    numbers_text = build_numbers_message(number_floor, ton_usd_rate) if NUMBERS_COLLECTION_ADDRESS else None
    promo_text = build_promo_message_html()
    promo_reply_markup = build_promo_reply_markup()

    await verify_telegram_bot()

    await upsert_message(
        USERNAMES_CHAT_ID,
        USERNAMES_MESSAGE_ID,
        usernames_text,
        "USERNAMES_MESSAGE_ID",
        parse_mode="HTML",
    )

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


if __name__ == "__main__":
    asyncio.run(main())
