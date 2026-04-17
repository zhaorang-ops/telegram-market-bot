import asyncio
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from playwright.async_api import async_playwright

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MESSAGE_ID = int(os.environ["MESSAGE_ID"])

URL = os.environ.get(
    "MARKET_URL",
    "https://marketapp.ws/collection/EQCA14o1-VWhS2efqoh_9M1b_A9DtKTuoqfmkn83AbJzwnPi/?tab=nfts&view=list&query=&sort_by=price_asc&filter_by=sale&market_filter_by=any&min_price=&max_price=&attrs=Length%7E4&attrs=Length%7E6&attrs=Length%7E5"
)

TOP_N_EACH = 20
TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))

# 解析：用户名 + TON价格 + 美元价格
INLINE_RE = re.compile(
    r"([A-Za-z0-9_\.]{2,})\s+(?:On Sale\s+)?(\d+(?:\.\d+)?)\s+~?\$(\d+(?:\.\d+)?)"
)

SKIP_LINES = {
    "Marketapp", "Collection Info", "Filters", "Apply", "Loading...",
    "Telegram Usernames", "Address", "Owners", "Supply", "Royalty",
    "Floor", "Top order", "Volume 7D", "Read more", "Navigation"
}

ADD_USD = {
    4: 1000,
    5: 50,
    6: 50,
}


def clean_line(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def unique_keep_order(items):
    seen = set()
    out = []
    for x in items:
        key = (x["name"].lower(), round(x["ton_price"], 8), round(x["usd_price"], 2))
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def parse_body_text(text: str):
    lines = [clean_line(x) for x in text.splitlines()]
    lines = [x for x in lines if x and x not in SKIP_LINES]

    items = []
    for line in lines:
        m = INLINE_RE.search(line)
        if m:
            items.append({
                "name": m.group(1),
                "ton_price": float(m.group(2)),
                "usd_price": float(m.group(3)),
            })

    return unique_keep_order(items)


async def extract_items_from_page(page):
    await page.goto(URL, wait_until="networkidle", timeout=90000)
    await page.wait_for_timeout(4000)

    dom_items = await page.evaluate(
        """
        () => {
          const clean = (s) => (s || "").replace(/\\s+/g, " ").trim();
          const out = [];
          const seen = new Set();

          function getPrices(text) {
            const m = text.match(/(?:On Sale\\s+)?(\\d+(?:\\.\\d+)?)\\s+~?\\$(\\d+(?:\\.\\d+)?)/);
            if (!m) return null;
            return {
              ton_price: parseFloat(m[1]),
              usd_price: parseFloat(m[2]),
            };
          }

          const anchors = [...document.querySelectorAll('a')];
          for (const a of anchors) {
            const name = clean(a.textContent);
            if (!/^[A-Za-z0-9_.]{2,}$/.test(name)) continue;
            if (seen.has(name.toLowerCase())) continue;

            let el = a;
            let matchedText = "";
            for (let i = 0; i < 8 && el; i++, el = el.parentElement) {
              const txt = clean(el.innerText);
              if (!txt || !txt.includes(name)) continue;
              if (/\\d+(?:\\.\\d+)?\\s+~?\\$\\d+(?:\\.\\d+)?/.test(txt) || /On Sale/.test(txt)) {
                matchedText = txt;
                break;
              }
            }

            const prices = matchedText ? getPrices(matchedText) : null;
            if (prices) {
              out.push({
                name,
                ton_price: prices.ton_price,
                usd_price: prices.usd_price
              });
              seen.add(name.toLowerCase());
            }
          }
          return out;
        }
        """
    )

    dom_items = unique_keep_order(dom_items)
    if dom_items:
        return dom_items

    body_text = await page.locator("body").inner_text()
    return parse_body_text(body_text)


def build_message(items):
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    if not items:
        return (
            "用户名价格实时更新：\n\n"
            "暂时没有解析到数据。\n"
            f"更新时间：{now_str}"
        )

    groups = {4: [], 5: [], 6: []}

    for item in items:
        name_len = len(item["name"])
        if name_len in groups:
            groups[name_len].append(item)

    for name_len in groups:
        groups[name_len].sort(key=lambda x: x["ton_price"])

    lines = ["用户名价格实时更新：", ""]

    for name_len in [4, 5, 6]:
        lines.append(f"【{name_len}位 前{TOP_N_EACH}个】")
        current_items = groups[name_len][:TOP_N_EACH]

        if not current_items:
            lines.append("暂无数据")
            lines.append("")
            continue

        extra = ADD_USD[name_len]
        for item in current_items:
            final_usd = item["usd_price"] + extra
            lines.append(f"@{item['name']}  ${final_usd:.2f}")

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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        items = await extract_items_from_page(page)
        text = build_message(items)
        await edit_message(text)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
