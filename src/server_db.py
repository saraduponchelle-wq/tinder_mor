import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")


# ===============================
# SET BLOG CHANNEL
# ===============================

async def set_blog_channel(guild_id: int, channel_id: int, server_name: str):

    conn = await asyncpg.connect(DATABASE_URL)

    await conn.execute("""
        INSERT INTO servers (guild_id, blog_channel_id, server_name)
        VALUES ($1,$2,$3)
        ON CONFLICT (guild_id)
        DO UPDATE SET blog_channel_id = EXCLUDED.blog_channel_id
    """, guild_id, channel_id, server_name)

    await conn.close()


# ===============================
# SET ONLINE CHANNEL
# ===============================

async def set_online_channel(guild_id: int, channel_id: int, server_name: str):

    conn = await asyncpg.connect(DATABASE_URL)

    await conn.execute("""
        INSERT INTO servers (guild_id, online_channel_id, server_name)
        VALUES ($1,$2,$3)
        ON CONFLICT (guild_id)
        DO UPDATE SET online_channel_id = EXCLUDED.online_channel_id
    """, guild_id, channel_id, server_name)

    await conn.close()


# ===============================
# GET ALL SERVERS
# ===============================

async def get_all_servers():

    conn = await asyncpg.connect(DATABASE_URL)

    rows = await conn.fetch(
        "SELECT * FROM servers"
    )

    await conn.close()

    return rows