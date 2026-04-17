import asyncio
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MESSAGE_ID = int(os.environ["MESSAGE_ID"])
MARKETAPP_API_TOKEN = os.environ["MARKETAPP_API_TOKEN"]

COLLECTION_ADDRESS = "EQCA14o1-VWhS2efqoh_9M1b_A9DtKTuoqfmkn83AbJzwnPi"
API_URL = f"https://api.marketapp.ws/v1/nfts/collections/{COLLECTION_ADDRESS}/"

TOP_N_EACH = 20
TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))

ADD_USD = {
    4: 1000,
    5: 50,
    6: 50,
}


def pick_first(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def normalize_username(value: str) -> str:
    if not value:
        return ""
    value = str(value).strip()
    if value.startswith("@"):
        value = value[1:]
    return value


def to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def extract_items(payload):
    """
    尽量兼容不同返回结构：
    - 直接是 list
    - {"results": [...]}
    - {"items": [...]}
    - {"data": [...]}
    - {"nfts": [...]}
    """
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = (
            payload.get("results")
            or payload.get("items")
            or payload.get("data")
            or payload.get("nfts")
            or []
        )
    else:
        raw_items = []

    items = []
    seen = set()

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue

        name = normalize_username(
            pick_first(
                raw,
                ["name", "username", "nft_name", "title", "telegram_username"],
                "",
            )
        )

        if not name:
            continue

        ton_price = to_float(
            pick_first(
                raw,
                ["price", "ton_price", "sale_price", "listing_price", "price_ton"],
                0,
            )
        )

        usd_price = to_float(
            pick_first(
                raw,
                ["price_usd", "usd_price", "sale_price_usd", "listing_price_usd"],
                0,
            )
        )

        status = str(
            pick_first(raw, ["status", "sale_status", "market_status"], "")
        ).lower()

        is_on_sale = bool(
            pick_first(raw, ["is_on_sale", "on_sale"], False)
        ) or ("sale" in status)

        key = (name.lower(), ton_price, usd_price)
        if key in seen:
            continue
        seen.add(key)

        items.append(
            {
                "name": name,
                "name_len": len(name),
                "ton_price": ton_price,
                "usd_price": usd_price,
                "is_on_sale": is_on_sale,
                "raw": raw,
            }
        )

    return items


async def fetch_group(length_value: int):
    headers = {
        "Authorization": MARKETAPP_API_TOKEN,
        "Accept": "application/json",
    }

    # 这里的参数名是按你页面 URL 的筛选逻辑来写的，
    # 实际是否完全一致，请以 Swagger 里该接口的参数定义为准。
    params = {
        "filter_by": "sale",
        "sort_by": "price_asc",
        "market_filter_by": "any",
        "attrs": f"Length~{length_value}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(API_URL, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()

    items = extract_items(data)

    # 再本地兜底过滤一次，避免接口返回混杂数据
    items = [
        x for x in items
        if x["name_len"] == length_value and (x["is_on_sale"] or x["ton_price"] > 0)
    ]

    items.sort(key=lambda x: x["ton_price"])
    return items[:TOP_N_EACH]


def build_message(groups):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    lines = ["用户名价格实时更新：", ""]

    for length_value in [4, 5, 6]:
        current_items = groups.get(length_value, [])
        lines.append(f"【{length_value}位 前{TOP_N_EACH}个】")

        if not current_items:
            lines.append("暂无数据")
            lines.append("")
            continue

        extra = ADD_USD[length_value]

        for item in current_items:
            final_usd = item["usd_price"] + extra
            lines.append(
                f"@{item['name']} 当前TON价格：{item['ton_price']:.2f} | ${final_usd:.2f}"
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
        r = await client.post(api, json=payload)
        data = r.json()

    if not data.get("ok"):
        desc = str(data.get("description", ""))
        if "message is not modified" in desc.lower():
            print("Telegram message unchanged.")
            return
        raise RuntimeError(f"Telegram edit failed: {data}")


async def main():
    groups = {}
    for length_value in [4, 5, 6]:
        groups[length_value] = await fetch_group(length_value)

    text = build_message(groups)
    await edit_message(text)


if __name__ == "__main__":
    asyncio.run(main())
