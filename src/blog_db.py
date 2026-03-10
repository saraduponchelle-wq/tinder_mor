import json
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")


async def add_blog(user_id: int, text: str, image: str | None):
    conn = await asyncpg.connect(DATABASE_URL)

    row = await conn.fetchrow("SELECT blogs FROM profiles WHERE user_id=$1", user_id)

    if row and row["blogs"]:
        blogs = row["blogs"]
        if isinstance(blogs, str):
            blogs = json.loads(blogs)
    else:
        blogs = []

    if not image:
        image = "nothing"

    blogs.append({"text": text, "image": image})

    # Convertir a JSON antes de guardar
    blogs_json = json.dumps(blogs)

    await conn.execute("UPDATE profiles SET blogs=$1 WHERE user_id=$2", blogs_json, user_id)
    await conn.close()


async def get_blogs(user_id: int):
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT blogs FROM profiles WHERE user_id=$1", user_id)
    await conn.close()

    if not row or not row["blogs"]:
        return []

    blogs = row["blogs"]
    if isinstance(blogs, str):
        blogs = json.loads(blogs)

    return blogs