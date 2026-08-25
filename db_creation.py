import asyncio
import os
import aiosqlite

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb_adminbot.db")


async def create_database(db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:


        await db.execute("""
                    CREATE TABLE IF NOT EXISTS Admins (
                        Tg_id INTEGER PRIMARY KEY
                    );
                """)


        await db.execute("""
                    CREATE TABLE IF NOT EXISTS Notes (
                        Note_number INTEGER PRIMARY KEY,
                        Title TEXT,
                        Text TEXT,
                        Document TEXT,
                        Course TEXT
                    );
                """)


        await db.commit()




if __name__ == "__main__":
    asyncio.run(create_database())