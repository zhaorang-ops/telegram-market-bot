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

            # 遇到无效 cursor，直接结束，不再报错退出
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

            # 连续 3 页没有新增，就停止
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
