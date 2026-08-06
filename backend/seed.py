"""Seed script - creates collections and initial users in MongoDB Atlas."""

import asyncio
import os
import certifi
import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "sim_monitor")


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed():
    print(f"[SEED] Connecting to: {DB_NAME} ...")
    client = AsyncIOMotorClient(MONGO_URL, tlsCAFile=certifi.where())
    db = client[DB_NAME]

    # -- Create collections --
    existing = await db.list_collection_names()
    for col in ["users", "sessions", "monitor_state"]:
        if col not in existing:
            await db.create_collection(col)
            print(f"  [+] Created collection: {col}")
        else:
            print(f"  [.] Collection exists:  {col}")

    # -- Create indexes --
    await db["users"].create_index("username", unique=True)
    await db["sessions"].create_index("session_code", unique=True)
    await db["monitor_state"].create_index("session_id", unique=True)
    print("  [+] Indexes ensured")

    # -- Seed users --
    users = db["users"]

    # Clear existing users (fresh seed)
    await users.delete_many({})
    print("  [.] Cleared existing users")

    instructor = {
        "username": "instructor",
        "password_hash": hash_pw("instructor123"),
        "role": "instructor",
        "created_at": datetime.utcnow(),
    }
    student = {
        "username": "student",
        "password_hash": hash_pw("student123"),
        "role": "student",
        "created_at": datetime.utcnow(),
    }

    await users.insert_many([instructor, student])
    print("  [+] Seeded users:")
    print("      | Username     | Password      | Role       |")
    print("      |--------------|---------------|------------|")
    print("      | instructor   | instructor123 | instructor |")
    print("      | student      | student123    | student    |")

    # -- Clear old sessions/state --
    await db["sessions"].delete_many({})
    await db["monitor_state"].delete_many({})
    print("  [+] Cleared old sessions and monitor states")

    # -- Verify --
    count = await users.count_documents({})
    print(f"\n[SEED] Done - {count} users in '{DB_NAME}' database")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
