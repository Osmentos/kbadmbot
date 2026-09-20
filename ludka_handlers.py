import asyncio
import html
import os
from aiogram import Router, F, types
from aiogram.filters import Command
from dotenv import load_dotenv
from ludka_database import ludka_add, ludka_top

load_dotenv()
router = Router()
CHAT = int(os.getenv("SUGGESTIONS_CHAT_ID"))
THREAD = int(os.getenv("LUDKA_THREAD_ID"))
router.message.filter(F.chat.id == CHAT, F.message_thread_id == THREAD)

# слоты: 1/22/43 - три одинаковых, 64 - 777. баскет: 4,5 - попал. боулинг: 6 - страйк
# эмодзи: (игра, победные значения, текст, секунды анимации)
GAMES = {
    "🎰": ("слоты", (1, 22, 43, 64), "срывает три в ряд", 2),
    "🏀": ("баскет", (4, 5), "попадает в кольцо", 4.5),
    "🎳": ("боулинг", (6,), "выбивает страйк", 4),
}


@router.message(F.dice.emoji.in_(GAMES), ~F.forward_origin)
async def on_dice(m: types.Message):
    game, wins, txt, delay = GAMES[m.dice.emoji]
    user = m.from_user
    win = m.dice.value in wins

    place = await ludka_add(user.id, user.full_name, game, win)
    if not win:
        return

    if m.dice.value == 64:
        txt = "срывает джекпот 777"
    await asyncio.sleep(delay)  # анимация

    name = html.escape(user.full_name)
    mention = f'<a href="tg://user?id={user.id}">{name}</a>'
    await m.answer(f"{mention} {txt}! Его текущее место в топе - #{place}", parse_mode="HTML")


@router.message(Command("ludka"))
async def top(m: types.Message):
    out = ["победы/броски"]

    for info in GAMES.values():
        game = info[0]
        rows, me, place = await ludka_top(game, m.from_user.id)
        out.append(f"\n[{game}]")

        for i, (_, name, w, t) in enumerate(rows, 1):
            out.append(f"{i}. {name} - {w}/{t}")
        if not rows:
            out.append("пусто")

        # если юзера нет в топе - его строка отдельно
        if me and place > len(rows):
            _, name, w, t = me
            out.append("----")
            out.append(f"{place}. {name} - {w}/{t}")

    await m.answer("\n".join(out))