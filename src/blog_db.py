import json
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def add_blog(user_id: int, text: str, image: str):
    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow("SELECT blogs FROM users WHERE user_id=$1", user_id)

    if row and row["blogs"]:
        blogs = row["blogs"]
    else:
        blogs = []

    blogs.append({
        "text": text,
        "image": image
    })

    await conn.execute(
        "UPDATE users SET blogs=$1 WHERE user_id=$2",
        blogs,
        user_id
    )

    await conn.close()


async def get_blogs(user_id: int):
    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow(
        "SELECT blogs FROM users WHERE user_id=$1",
        user_id
    )

    await conn.close()

    if row and row["blogs"]:
        return row["blogs"]

    return []