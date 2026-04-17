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

TOP_N = int(os.environ.get("TOP_N", "15"))
TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))

INLINE_RE = re.compile(
    r"([A-Za-z0-9_\.]{2,})\s+(?:On Sale\s+)?(\d+(?:\.\d+)?)\s+~?\$\d+(?:\.\d+)?"
)

SKIP_LINES = {
    "Marketapp", "Collection Info", "Filters", "Apply", "Loading...",
    "Telegram Usernames", "Address", "Owners", "Supply", "Royalty",
    "Floor", "Top order", "Volume 7D", "Read more", "Navigation"
}

def clean_line(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def unique_keep_order(items):
    seen = set()
    out = []
    for x in items:
        key = (x["name"].lower(), x["ton_price"])
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
            name, price = m.group(1), m.group(2)
            items.append({"name": name, "ton_price": price})

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

          function getPrice(text) {
            const m = text.match(/(?:On Sale\\s+)?(\\d+(?:\\.\\d+)?)(?:\\s+~?\\$\\d+(?:\\.\\d+)?)?/);
            return m ? m[1] : null;
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

            const price = matchedText ? getPrice(matchedText) : null;
            if (price) {
              out.push({ name, ton_price: price });
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
            "📌 Telegram Usernames 低价监控\\n\\n"
            "暂时没有解析到数据。\\n"
            f"更新时间：{now_str}"
        )

    items = items[:TOP_N]
    lines = [
        "📌 Telegram Usernames 低价监控",
        "",
        "筛选：Length 4 / 5 / 6，On Sale，按价格升序",
        ""
    ]

    for idx, item in enumerate(items, 1):
        lines.append(f"{idx}. @{item['name']} — {item['ton_price']} TON")

    lines += ["", f"更新时间：{now_str}"]
    return "\\n".join(lines)

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
