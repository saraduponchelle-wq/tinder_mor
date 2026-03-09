import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")


async def add_blog(user_id: int, text: str, image: str | None):
    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow("SELECT blogs FROM profiles WHERE user_id=$1", user_id)

    blogs = row["blogs"] if row and row["blogs"] else []

    if not image:
        image = "nothing"

    blogs.append({"text": text, "image": image})

    await conn.execute("UPDATE profiles SET blogs=$1 WHERE user_id=$2", blogs, user_id)
    await conn.close()


async def get_blogs(user_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT blogs FROM profiles WHERE user_id=$1", user_id)
    await conn.close()
    return row["blogs"] if row and row["blogs"] else []