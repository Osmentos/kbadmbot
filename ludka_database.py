import aiosqlite
from db_creation import DB_PATH


async def ludka_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS Ludka (Tg_id INTEGER, Name TEXT, Game TEXT, Throws INTEGER, Wins INTEGER, PRIMARY KEY (Tg_id, Game))")
        await db.commit()


async def place(db, uid, game):
    # место = сколько людей лучше + 1 (больше побед, при равенстве меньше бросков)
    cur = await db.execute(
        "SELECT COUNT(*) + 1 FROM Ludka a, Ludka b WHERE a.Game=? AND b.Game=a.Game AND b.Tg_id=? "
        "AND (a.Wins > b.Wins OR (a.Wins = b.Wins AND a.Throws < b.Throws))", (game, uid))
    return (await cur.fetchone())[0]


async def ludka_add(uid, name, game, win):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO Ludka VALUES (?, ?, ?, 1, ?) ON CONFLICT(Tg_id, Game) "
            "DO UPDATE SET Name=excluded.Name, Throws=Throws+1, Wins=Wins+excluded.Wins",
            (uid, name, game, int(win)))
        await db.commit()
        return await place(db, uid, game)


async def ludka_top(game, uid, n=5):
    """returns: (топ n, строка юзера или None, место юзера)"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT Tg_id, Name, Wins, Throws FROM Ludka WHERE Game=? ORDER BY Wins DESC, Throws LIMIT ?", (game, n))
        rows = await cur.fetchall()
        cur = await db.execute("SELECT Tg_id, Name, Wins, Throws FROM Ludka WHERE Game=? AND Tg_id=?", (game, uid))
        me = await cur.fetchone()
        return rows, me, (await place(db, uid, game) if me else 0)
