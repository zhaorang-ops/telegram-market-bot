async def fetch_group(length_value: int):
    headers = {
        "Authorization": MARKETAPP_API_TOKEN,
        "Accept": "application/json",
    }

    params = {
        "filter_by": "sale",
        "sort_by": "price_asc",
        "market_filter_by": "any",
        "attrs": f"Length~{length_value}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(API_URL, headers=headers, params=params)

        print("DEBUG URL:", r.request.url)
        print("DEBUG STATUS:", r.status_code)
        print("DEBUG RESPONSE:", r.text[:3000])

        r.raise_for_status()
        data = r.json()

    items = extract_items(data)
    items = [x for x in items if x["name_len"] == length_value]
    items.sort(key=lambda x: x["ton_price"])
    return items[:TOP_N_EACH]
