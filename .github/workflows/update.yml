import asyncio
import os
import re
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


BOT_TOKEN = os.environ["BOT_TOKEN"].strip()

USERNAMES_CHAT_ID = os.environ["USERNAMES_CHAT_ID"].strip()
USERNAMES_MESSAGE_ID = int(os.environ.get("USERNAMES_MESSAGE_ID", "0") or "0")

NUMBERS_CHAT_ID = os.environ["NUMBERS_CHAT_ID"].strip()
NUMBERS_MESSAGE_ID = int(os.environ.get("NUMBERS_MESSAGE_ID", "0") or "0")

PROMO_CHAT_ID = (os.environ.get("PROMO_CHAT_ID", "").strip() or NUMBERS_CHAT_ID)
PROMO_MESSAGE_ID = int(os.environ.get("PROMO_MESSAGE_ID", "0") or "0")

USERNAMES_5_URL = os.environ.get("USERNAMES_5_URL", "").strip()
USERNAMES_6_URL = os.environ.get("USERNAMES_6_URL", "").strip()
USERNAMES_7_URL = os.environ.get("USERNAMES_7_URL", "").strip()

NUMBERS_URL = os.environ.get("NUMBERS_URL", "").strip()

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))

USERNAME_ADD_USD = {
    5: 50.0,
    6: 50.0,
    7: 50.0,
}

NUMBER_ADD_USD = {
    "has4": 50.0,
    "no4": 50.0,
}

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

# 提速：先用 3 / 3 / 2
USERNAME_EXTRA_COUNT = {
    5: 3,
    6: 3,
    7: 2,
}

USERNAME_QUERY_ALPHA_CHARS = "abcdefghijklmnopqrstuvwxyz"
USERNAME_QUERY_DIGIT_CHARS = ["6", "8", "9", "0", "1", "2", "3", "4", "5", "7"]

QUERY_RESULT_CACHE = {}


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

        ton_candidates = re.findall(r"(?<!\$)\b\d+(?:,\d{3})*(?:\.\d+)?\b", text)
        ton_price = 0.0
        if ton_candidates:
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


async def fetch_query_result(page, url: str, expected_length: int):
    await page.goto(url, wait_until="domcontentloaded", timeout=15000)

    selectors = [
        "table tbody tr",
        "tr",
        "text=@",
    ]

    found = False
    for sel in selectors:
        try:
            await page.wait_for_selector(sel, timeout=3000)
            found = True
            break
        except PlaywrightTimeoutError:
            pass

    if not found:
        return None

    # 给前端一点点渲染时间，但不再傻等 3 秒
    await page.wait_for_timeout(500)

    return await extract_first_row_from_page(page, expected_length)


async def fetch_best_match_by_query(page, base_url: str, length_value: int, rule_name: str, run_len, kind: str):
    if not base_url:
        return None

    cache_key = (base_url, length_value, rule_name, run_len, kind)
    if cache_key in QUERY_RESULT_CACHE:
        return QUERY_RESULT_CACHE[cache_key]

    if kind == "alpha":
        queries = [ch * run_len for ch in USERNAME_QUERY_ALPHA_CHARS]
    elif kind == "digit":
        queries = [ch * run_len for ch in USERNAME_QUERY_DIGIT_CHARS]
    elif kind == "fixed":
        queries = [rule_name]
    else:
        QUERY_RESULT_CACHE[cache_key] = None
        return None

    for q in queries:
        url = add_or_replace_query(base_url, q)
        try:
            result = await fetch_query_result(page, url, length_value)
        except Exception as e:
            print(f"DEBUG PLAYWRIGHT FAIL length={length_value} rule={rule_name} query={q} error={repr(e)}")
            result = None

        if result and rule_match(username_clean(result["name"]), rule_name, run_len, kind):
            print(f"DEBUG PLAYWRIGHT HIT length={length_value} rule={rule_name} query={q} name={result['name']}")
            QUERY_RESULT_CACHE[cache_key] = result
            return result

    QUERY_RESULT_CACHE[cache_key] = None
    return None


async def build_username_section(page, base_url: str, length_value: int):
    rules = USERNAME_RULES[length_value]
    extra_count = USERNAME_EXTRA_COUNT[length_value]

    selected = []
    used = set()

    for rule_name, run_len, kind in rules:
        chosen = await fetch_best_match_by_query(page, base_url, length_value, rule_name, run_len, kind)

        if chosen and chosen["name"].lower() in used:
            chosen = None

        if chosen is None:
            continue

        used.add(chosen["name"].lower())
        selected.append(chosen)

    # 补位也走复用 page
    filler_queries = ["", "6", "8", "9", "0", "a", "b", "c"]
    for q in filler_queries:
        if len(selected) >= len(rules) + extra_count:
            break

        url = add_or_replace_query(base_url, q)
        filler_key = (base_url, length_value, f"filler:{q}", None, "filler")

        if filler_key in QUERY_RESULT_CACHE:
            result = QUERY_RESULT_CACHE[filler_key]
        else:
            try:
                result = await fetch_query_result(page, url, length_value)
            except Exception:
                result = None
            QUERY_RESULT_CACHE[filler_key] = result

        if not result:
            continue
        if result["name"].lower() in used:
            continue

        used.add(result["name"].lower())
        selected.append(result)

    return selected[: len(rules) + extra_count]


async def fetch_numbers_floor(page, base_url: str):
    if not base_url:
        return {"has4": None, "no4": None}

    await page.goto(base_url, wait_until="domcontentloaded", timeout=15000)

    try:
        await page.wait_for_selector("tr", timeout=3000)
    except PlaywrightTimeoutError:
        return {"has4": None, "no4": None}

    await page.wait_for_timeout(500)

    rows = page.locator("table tbody tr")
    count = await rows.count()
    if count == 0:
        rows = page.locator("tr")
        count = await rows.count()

    has4_item = None
    no4_item = None

    for i in range(count):
        row = rows.nth(i)
        try:
            text = await row.inner_text()
        except Exception:
            continue

        if not text or "+888" not in text:
            continue

        num_match = re.search(r"\+888[\s\d]{4,20}", text)
        if not num_match:
            continue

        name = re.sub(r"\s+", " ", num_match.group(0)).strip()
        ton_candidates = re.findall(r"(?<!\$)\b\d+(?:,\d{3})*(?:\.\d+)?\b", text)
        ton_price = 0.0
        for raw in ton_candidates:
            val = to_float(raw, 0.0)
            if val > 0:
                ton_price = val
                break

        if ton_price <= 0:
            continue

        digits = re.sub(r"\D", "", name)
        tail = digits[3:] if digits.startswith("888") else digits

        item = {
            "name": name,
            "ton_price": ton_price,
            "is_restricted": "restricted" in text.lower(),
        }

        if item["is_restricted"]:
            continue

        if "4" in tail and has4_item is None:
            has4_item = item
        if "4" not in tail and no4_item is None:
            no4_item = item

        if has4_item and no4_item:
            break

    return {"has4": has4_item, "no4": no4_item}


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


async def handle_route(route):
    if route.request.resource_type in ["image", "font", "media"]:
        await route.abort()
    else:
        await route.continue_()


async def main():
    ton_usd_rate = await fetch_ton_usd_rate()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(service_workers="block")
        await context.route("**/*", handle_route)

        page5 = await context.new_page()
        page6 = await context.new_page()
        page7 = await context.new_page()
        page_num = await context.new_page()

        try:
            section_5, section_6, section_7 = await asyncio.gather(
                build_username_section(page5, USERNAMES_5_URL, 5) if USERNAMES_5_URL else asyncio.sleep(0, result=[]),
                build_username_section(page6, USERNAMES_6_URL, 6) if USERNAMES_6_URL else asyncio.sleep(0, result=[]),
                build_username_section(page7, USERNAMES_7_URL, 7) if USERNAMES_7_URL else asyncio.sleep(0, result=[]),
            )

            number_floor = await fetch_numbers_floor(page_num, NUMBERS_URL) if NUMBERS_URL else {"has4": None, "no4": None}
        finally:
            await context.close()
            await browser.close()

    usernames_text = build_usernames_message(section_5, section_6, section_7, ton_usd_rate)
    numbers_text = build_numbers_message(number_floor, ton_usd_rate) if NUMBERS_URL else None
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
