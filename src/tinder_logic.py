import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")


async def get_connection():
    return await asyncpg.connect(DATABASE_URL)


async def add_like(target_id: int):

    conn = await get_connection()

    await conn.execute(
        "UPDATE profiles SET likes = COALESCE(likes,0) + 1 WHERE user_id=$1",
        target_id
    )

    await conn.close()


async def add_popularity(target_id: int):

    conn = await get_connection()

    await conn.execute(
        "UPDATE profiles SET popularity = COALESCE(popularity,0) + 1 WHERE user_id=$1",
        target_id
    )

    await conn.close()


async def add_match_stat(user1: int, user2: int):

    conn = await get_connection()

    await conn.execute(
        "UPDATE profiles SET matches_nb = COALESCE(matches_nb,0) + 1 WHERE user_id=$1",
        user1
    )

    await conn.execute(
        "UPDATE profiles SET matches_nb = COALESCE(matches_nb,0) + 1 WHERE user_id=$1",
        user2
    )

    await conn.close()


async def add_match(user_id: int, target_id: int):

    conn = await get_connection()

    row = await conn.fetchrow(
        "SELECT matches FROM profiles WHERE user_id=$1",
        user_id
    )

    matches = row["matches"] or []

    if target_id not in matches:

        matches.append(target_id)

        await conn.execute(
            "UPDATE profiles SET matches=$1 WHERE user_id=$2",
            matches,
            user_id
        )

    await conn.close()


async def is_mutual_match(user_id: int, target_id: int):

    conn = await get_connection()

    row = await conn.fetchrow(
        "SELECT matches FROM profiles WHERE user_id=$1",
        target_id
    )

    await conn.close()

    if not row:
        return False

    matches = row["matches"] or []

    return user_id in matches


async def get_full_profile(user_id: int):

    conn = await get_connection()

    row = await conn.fetchrow(
        "SELECT * FROM profiles WHERE user_id=$1",
        user_id
    )

    await conn.close()

    return dict(row)