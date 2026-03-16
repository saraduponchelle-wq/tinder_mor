from src.database import get_pool


# ===============================
# SET BLOG CHANNEL
# ===============================

async def set_blog_channel(guild_id: int, channel_id: int, server_name: str):

    pool = await get_pool()

    async with pool.acquire() as conn:

        await conn.execute("""
            INSERT INTO servers (guild_id, blog_channel_id, server_name)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id)
            DO UPDATE SET blog_channel_id = EXCLUDED.blog_channel_id
        """, guild_id, channel_id, server_name)


# ===============================
# SET ONLINE CHANNEL
# ===============================

async def set_online_channel(guild_id: int, channel_id: int, server_name: str):

    pool = await get_pool()

    async with pool.acquire() as conn:

        await conn.execute("""
            INSERT INTO servers (guild_id, online_channel_id, server_name)
            VALUES ($1,$2,$3)
            ON CONFLICT (guild_id)
            DO UPDATE SET online_channel_id = EXCLUDED.online_channel_id
        """, guild_id, channel_id, server_name)


# ===============================
# GET ALL SERVERS
# ===============================

async def get_all_servers():

    pool = await get_pool()

    async with pool.acquire() as conn:

        rows = await conn.fetch(
            "SELECT * FROM servers"
        )

        return rows