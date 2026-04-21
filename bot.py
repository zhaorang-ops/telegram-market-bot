import asyncio
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from playwright.async_api import async_playwright


BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
NUMBERS_CHAT_ID = os.environ["NUMBERS_CHAT_ID"].strip()
NUMBERS_MESSAGE_ID = int(os.environ.get("NUMBERS_MESSAGE_ID", "0") or "0")
NUMBERS_URL = os.environ.get("NUMBERS_URL", "").strip()
TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))

NUMBER_ADD_USD = {
    "has4": 50.0,
    "no4": 50.0,
}

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


def display_price_int(value: float) -> int:
    if value <= 0:
        return 0
    return int(value) + 1


def deep_walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from deep_walk(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from deep_walk(item)


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


def has_usd_marker(text: str) -> bool:
    if not text:
        return False
    s = str(text)
    return bool(re.search(r"(?:\$|\bUSD\b|\bUSDT\b)", s, re.I))


def has_ton_marker(text: str) -> bool:
    if not text:
        return False
    s = str(text)
    return bool(re.search(r"\bTON\b", s, re.I))


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


def build_price_debug_text(item: dict, ton_usd_rate: float, add_usd: float) -> str:
    base_usd = item.get("usd_price", 0.0)
    ton_price = item.get("ton_price", 0.0)

    if base_usd > 0:
        final_usd = build_display_usd(item, ton_usd_rate, add_usd)
        return f"原始USDT/USD: {base_usd:g} -> +{int(add_usd)} = ${display_price_int(final_usd)}"

    if ton_price > 0 and ton_usd_rate > 0:
        final_usd = build_display_usd(item, ton_usd_rate, add_usd)
        return f"原始TON: {ton_price:g} -> ×{ton_usd_rate:.6f} + {int(add_usd)} = ${display_price_int(final_usd)}"

    if ton_price > 0:
        return f"原始TON: {ton_price:g} -> 汇率获取失败"

    return "暂无有效价格"


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


async def fetch_numbers_floor(browser, base_url: str, ton_usd_rate: float):
    if not base_url:
        return {"has4": None, "no4": None}

    context = await browser.new_context()
    page = await context.new_page()
    responses = []

    def on_response(response):
        responses.append(response)

    page.on("response", on_response)

    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        json_candidates = []
        for response in responses[-30:]:
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

        def has4(x):
            digits = re.sub(r"\D", "", x["name"])
            tail = digits[3:] if digits.startswith("888") else digits
            return "4" in tail

        def no4(x):
            digits = re.sub(r"\D", "", x["name"])
            tail = digits[3:] if digits.startswith("888") else digits
            return "4" not in tail

        if json_candidates:
            valid = [x for x in json_candidates if has_any_price(x) and not x["is_restricted"]]
            has4_item = next((x for x in valid if has4(x)), None)
            no4_item = next((x for x in valid if no4(x)), None)
            if has4_item or no4_item:
                return {"has4": has4_item, "no4": no4_item}

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
            usd_price = extract_usd_from_text(text)
            ton_price = 0.0

            price_match = re.search(r"▽\s*([\d,]+(?:\.\d+)?)", text)
            if price_match and not (usd_price > 0 and not has_ton_marker(text)):
                ton_price = to_float(price_match.group(1), 0.0)

            if ton_price <= 0 and usd_price <= 0 and has_ton_marker(text):
                text_wo_name = text.replace(name, " ")
                ton_candidates = re.findall(r"(?<!\$)\b\d+(?:,\d{3})*(?:\.\d+)?\b", text_wo_name)
                for raw in ton_candidates:
                    val = to_float(raw, 0.0)
                    if val > 0:
                        ton_price = val
                        break

            item = {
                "name": name,
                "ton_price": ton_price,
                "usd_price": usd_price,
                "is_restricted": "restricted" in text.lower(),
            }

            if item["is_restricted"] or not has_any_price(item):
                continue

            digits = re.sub(r"\D", "", name)
            tail = digits[3:] if digits.startswith("888") else digits

            if "4" in tail and has4_item is None:
                has4_item = item
            if "4" not in tail and no4_item is None:
                no4_item = item

            if has4_item and no4_item:
                break

        return {"has4": has4_item, "no4": no4_item}
    finally:
        await context.close()


def build_numbers_message(number_floor, ton_usd_rate):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    lines = ["📱【官方888号】地板价（匿名号测试版 v2）"]

    item = number_floor.get("has4")
    if item:
        usd_val = build_display_usd(item, ton_usd_rate, NUMBER_ADD_USD["has4"])
        if usd_val > 0:
            lines.append(f"【含4正常】 {item['name']} - ${display_price_int(usd_val)}")
            lines.append(f"    {build_price_debug_text(item, ton_usd_rate, NUMBER_ADD_USD['has4'])}")
        else:
            lines.append(f"【含4正常】 {item['name']} - 暂无有效价格")
    else:
        lines.append("【含4正常】 暂无数据")

    item = number_floor.get("no4")
    if item:
        usd_val = build_display_usd(item, ton_usd_rate, NUMBER_ADD_USD["no4"])
        if usd_val > 0:
            lines.append(f"【无4正常】 {item['name']} - ${display_price_int(usd_val)}")
            lines.append(f"    {build_price_debug_text(item, ton_usd_rate, NUMBER_ADD_USD['no4'])}")
        else:
            lines.append(f"【无4正常】 {item['name']} - 暂无有效价格")
    else:
        lines.append("【无4正常】 暂无数据")

    lines.append("")
    lines.append("规则：USDT/USD 直接 +50；TON 按汇率换算后 +50")
    lines.append(f"当前 TON 汇率：{ton_usd_rate:.6f} USD" if ton_usd_rate > 0 else "当前 TON 汇率：获取失败")
    lines.append(f"更新时间：{now_str}")
    return "\n".join(lines)


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


async def send_new_message(chat_id: str, text: str, label: str):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    data = await telegram_api("sendMessage", payload)
    if not data.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed for {label}: {data}")

    result = data.get("result", {})
    new_message_id = result.get("message_id")
    print(f"DEBUG NEW MESSAGE ID [{label}]:", new_message_id)
    return new_message_id


async def edit_existing_message(chat_id: str, message_id, text: str, label: str):
    if not message_id:
        return False

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "disable_web_page_preview": True,
    }
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


async def upsert_message(chat_id: str, message_id, text: str, label: str):
    edited = await edit_existing_message(chat_id, message_id, text, label)
    if edited:
        return

    new_message_id = await send_new_message(chat_id, text, label)
    print(f"IMPORTANT: Update {label} secret to:", new_message_id)


async def main():
    ton_usd_rate = await fetch_ton_usd_rate()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            number_floor = await fetch_numbers_floor(browser, NUMBERS_URL, ton_usd_rate) if NUMBERS_URL else {"has4": None, "no4": None}
        finally:
            await browser.close()

    numbers_text = build_numbers_message(number_floor, ton_usd_rate)
    print(numbers_text)

    await verify_telegram_bot()
    await upsert_message(
        NUMBERS_CHAT_ID,
        NUMBERS_MESSAGE_ID,
        numbers_text,
        "NUMBERS_MESSAGE_ID_TEST_V2",
    )


if __name__ == "__main__":
    asyncio.run(main())
