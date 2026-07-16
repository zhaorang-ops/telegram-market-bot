import argparse
import asyncio
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env.local"
OFFSET_FILE = ROOT / ".local_username_offset"


def load_local_env():
    if not ENV_FILE.exists():
        raise RuntimeError("Missing .env.local; copy .env.local.example and fill in the local settings")

    for raw_line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    os.environ["RUN_MODE"] = "usernames"


load_local_env()

import bot  # noqa: E402


UPDATE_LOCK = asyncio.Lock()
COMMAND = os.environ.get("LOCAL_USERNAME_COMMAND", "/update_usernames").strip().lower()
COMMAND_CHAT_ID = os.environ.get("LOCAL_COMMAND_CHAT_ID", "").strip() or bot.USERNAMES_CHAT_ID


async def update_usernames():
    if UPDATE_LOCK.locked():
        print("LOCAL USERNAMES update already running")
        return False
    async with UPDATE_LOCK:
        print("LOCAL USERNAMES update started")
        await bot.update_usernames_only()
        await send_completion_message()
        print("LOCAL USERNAMES update completed")
        return True


async def send_completion_message():
    data = await bot.telegram_api(
        "sendMessage",
        {
            "chat_id": COMMAND_CHAT_ID,
            "text": f"用户名更新完成\n可用指令：{COMMAND}",
        },
    )
    if not data.get("ok"):
        raise RuntimeError("Telegram completion message failed")


def read_offset():
    try:
        return int(OFFSET_FILE.read_text(encoding="ascii").strip())
    except (FileNotFoundError, ValueError):
        return None


def write_offset(offset):
    OFFSET_FILE.write_text(str(offset), encoding="ascii")


def is_update_command(message):
    text = str(message.get("text", "")).strip()
    if not text:
        return False
    command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
    chat_id = str(message.get("chat", {}).get("id", ""))
    return command == COMMAND and chat_id == COMMAND_CHAT_ID


async def initialize_offset():
    offset = read_offset()
    if offset is not None:
        return offset
    data = await bot.telegram_api("getUpdates", {"offset": -1, "limit": 1, "timeout": 0})
    updates = data.get("result", []) if data.get("ok") else []
    offset = updates[-1]["update_id"] + 1 if updates else 0
    write_offset(offset)
    return offset


async def listen_for_commands():
    if not COMMAND_CHAT_ID:
        raise RuntimeError("LOCAL_COMMAND_CHAT_ID is required for Telegram command control")

    await bot.verify_telegram_bot()
    offset = await initialize_offset()
    print(f"LOCAL USERNAMES listener ready command={COMMAND}")

    while True:
        try:
            data = await bot.telegram_api(
                "getUpdates",
                {"offset": offset, "timeout": 20, "allowed_updates": ["message"]},
            )
            if not data.get("ok"):
                raise RuntimeError("Telegram getUpdates returned an error")

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                write_offset(offset)
                message = update.get("message", {})
                if not is_update_command(message):
                    continue
                try:
                    await update_usernames()
                except Exception as exc:
                    print(f"LOCAL USERNAMES command failed: {type(exc).__name__}: {exc}")
        except Exception as exc:
            print(f"LOCAL USERNAMES listener retry: {type(exc).__name__}: {exc}")
            await asyncio.sleep(10)


async def async_main(mode):
    if mode == "once":
        await update_usernames()
    else:
        await listen_for_commands()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("once", "listen"), default="once")
    args = parser.parse_args()
    asyncio.run(async_main(args.mode))


if __name__ == "__main__":
    main()
