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
MAX_PAGES = int(os.environ.get("MAX_PAGES", "10"))

ADD_USD = {
    4: 1000.0,
    5: 50.0,
    6: 50.0,
}


def clean_username(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith("@"):
        s = s[1:]
    return s


def deep_get(obj, path):
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def first_value(obj, paths):
    for path in paths:
        value = deep_get(obj, path)
        if value is not None:
            return value
    return None


def to_float(value, default=0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    s = s.replace(",", "")
    s = s.replace("TON", "").replace("ton", "")
    s = s.replace("$", "").replace("≈", "").replace("~", "").strip()

    match = re.search(r"-?\d+(?:\.\d+)?", s)
    if not match:
        return default

    try:
        return float(match.group(0))
    except Exception:
        return default


def get_raw_items(payload):
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    candidates = [
        payload.get("results"),
        payload.get("items"),
        payload.get("data"),
        payload.get("nfts"),
        payload.get("assets"),
        deep_get(payload, ["data", "results"]),
        deep_get(payload, ["data", "items"]),
        deep_get(payload, ["collection", "items"]),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate

    return []


def parse_item(raw: dict):
    name = clean_username(
        first_value(
            raw,
            [
                ["username"],
                ["telegram_username"],
                ["name"],
                ["title"],
                ["nft", "name"],
                ["meta", "name"],
                ["asset", "name"],
            ],
        )
    )
    if not name:
        return None

    ton_price = to_float(
        first_value(
            raw,
            [
                ["price_ton"],
                ["ton_price"],
                ["price"],
                ["sale_price"],
                ["listing_price"],
                ["order", "price_ton"],
                ["order", "price"],
                ["listing", "price_ton"],
                ["listing", "price"],
                ["market", "price_ton"],
                ["market", "price"],
            ],
        ),
        default=0.0,
    )

    usd_price = to_float(
        first_value(
            raw,
            [
                ["price_usd"],
                ["usd_price"],
                ["sale_price_usd"],
                ["listing_price_usd"],
                ["order", "price_usd"],
                ["listing", "price_usd"],
                ["market", "price_usd"],
            ],
        ),
        default=0.0,
    )

    on_sale_flag = first_value(
        raw,
        [
            ["on_sale"],
            ["is_on_sale"],
            ["listing", "active"],
            ["order", "active"],
            ["market", "on_sale"],
        ],
    )

    status_text = str(
        first_value(
            raw,
            [
                ["status"],
                ["sale_status"],
                ["listing", "status"],
                ["order", "status"],
                ["market", "status"],
            ],
        )
        or ""
    ).lower()

    is_on_sale = bool(on_sale_flag) or ("sale" in status_text) or ("active" in status_text)

    return {
        "name": name,
        "name_len": len(name),
        "ton_price": ton_price,
        "usd_price": usd_price,
        "is_on_sale": is_on_sale,
        "raw": raw,
    }


async def fetch_all_collection_items():
    headers = {
        "Authorization": MARKETAPP_API_TOKEN,
        "Accept": "application/json",
    }

    url = API_URL
    all_items = []
    seen = set()

    async with httpx.AsyncClient(timeout=30) as client:
        for page_no in range(1, MAX_PAGES + 1):
            resp = await client.get(url, headers=headers)

            print(f"DEBUG PAGE {page_no} STATUS:", resp.status_code)
            print("DEBUG URL:", str(resp.request.url))

            # 失败时把返回体打出来，方便你在 GitHub Actions 日志里看
            if resp.status_code >= 400:
                print("DEBUG ERROR BODY:", resp.text[:5000])
                resp.raise_for_status()

            payload = resp.json()
            raw_items = get_raw_items(payload)
            print(f"DEBUG PAGE {page_no} RAW ITEMS:", len(raw_items))

            if not raw_items:
                print("DEBUG BODY PREVIEW:", str(payload)[:3000])

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

            next_url = None
            if isinstance(payload, dict):
                next_url = (
                    payload.get("next")
                    or payload.get("next_page")
                    or payload.get("next_page_url")
                )

            if not next_url:
                break

            url = next_url

    print("DEBUG TOTAL UNIQUE ITEMS:", len(all_items))
    return all_items


def build_groups(items):
    groups = {4: [], 5: [], 6: []}

    for item in items:
        if item["name_len"] not in groups:
            continue

        # 只保留 on sale；如果接口没有明确 on_sale 字段，则用有价格的项兜底
        if not item["is_on_sale"] and item["ton_price"] <= 0:
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
    items = await fetch_all_collection_items()
    groups = build_groups(items)
    text = build_message(groups)
    print("DEBUG FINAL MESSAGE PREVIEW:")
    print(text[:4000])
    await edit_message(text)


if __name__ == "__main__":
    asyncio.run(main())
