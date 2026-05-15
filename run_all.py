#!/usr/bin/env python3
"""
Runs both store_bot and admin_bot concurrently in a single process.
Used by Railway / any single-dyno deployment.
"""
import asyncio
import store_bot
import admin_bot

async def main():
    await asyncio.gather(
        store_bot.run(),
        admin_bot.run(),
    )

if __name__ == "__main__":
    asyncio.run(main())
