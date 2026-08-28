import asyncio
import html
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.base import StorageKey
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter
from aiogram.filters.chat_member_updated import JOIN_TRANSITION
from aiogram.filters.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
import os
import random
import logging
import aiosqlite
from db_creation import create_database
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.command import Command, CommandObject


load_dotenv()
CAPTCHA_DELAY = 60 * 30


logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUGGESTIONS_CHAT_ID = int(os.getenv("SUGGESTIONS_CHAT_ID"))
SUGGESTIONS_THREAD_ID = int(os.getenv("SUGGESTIONS_THREAD_ID"))
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class Capcha(StatesGroup):
    one = State()

class Addnotes(StatesGroup):
    one = State()
    two = State()
    three = State()

class Noteredaction(StatesGroup):
    title = State()
    text = State()
    document = State()

class Suggestions(StatesGroup):
    text = State()



async def get_admins():
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute("SELECT * FROM Admins")
        row1 = await cursor.fetchall()
        row=[]
        for i in row1:
            row.append(i[0])
    return row



async def get_notes_title():
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute("SELECT Title FROM notes")
        row1 = await cursor.fetchall()
        row = []
        for i in row1:
            row.append(i[0])
    return row


async def get_notes_titles_and_numbers():
    """Функция для получения заголовков и note_number

    Returns:
        tuple: [(title, note_number), ..]
    """
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute("SELECT Title, Note_number FROM notes")
        rows = await cursor.fetchall()
    return rows


async def get_notes_text(num):
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute("SELECT Text FROM notes WHERE Note_number =?",
                                  (num, ))
        text=(await cursor.fetchone())[0]
    return text



async def get_note_title(num):
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute("SELECT Title FROM notes WHERE Note_number =?",
                                  (num, ))
        title=(await cursor.fetchone())[0]
    return title


async def get_note_document(num):
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute("SELECT Document FROM notes WHERE Note_number =?",
                                  (num, ))
        document=(await cursor.fetchone())[0]
    return document


async def get_suggestion_data(num):
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute(
            "SELECT text, document FROM Suggestions WHERE Suggestion_number =?",
            (num, )
        )
        rows = await cursor.fetchall()
    return rows



async def get_next_suggestion():
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute(
            "SELECT Suggestion_number, Text, Document FROM Suggestions ORDER BY Suggestion_number LIMIT 1"
        )
        return await cursor.fetchone()

async def send_next_suggestion(chat_id: int, bot: Bot):
    row = await get_next_suggestion()
    if row is None:
        await bot.send_message(chat_id, "Все предложения обработаны!")
        return

    number, text, document = row

    if not text and not document:
        await delete_suggestion(number)
        await send_next_suggestion(chat_id, bot)
        return

    buttons = [
        [InlineKeyboardButton(text="удалить", callback_data=f"sug_del_{number}")],
        [InlineKeyboardButton(text="выложить", callback_data=f"sug_post_{number}")],
        [InlineKeyboardButton(text="выйти", callback_data="sug_quit")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # костыль , так как телеграмм отдает Telegram server says - Bad Request: can't use file of type Photo as Document
    # так как фото, присланное как фото и фото, присланное как Document - разное
    if document:
        try:
            await bot.send_document(chat_id, document, caption=text, reply_markup=keyboard)
        except TelegramBadRequest:
            await bot.send_photo(chat_id, document, caption=text, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, text, reply_markup=keyboard)


async def delete_suggestion(number):
    async with aiosqlite.connect('kb_adminbot.db') as db:
        await db.execute("DELETE FROM Suggestions WHERE Suggestion_number = ?", (number,))
        await db.commit()



#блок работы с заметками
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    admins = await get_admins()
    if message.from_user.id in admins:
        await message.answer('/suggestions - просмотр предложки,\n /notesadm - для создания заметок,\n /add_admin <tg_id> - добавление админа,\n /captcha_delay <min> - время на решение капчи')
    else:
        await message.answer(f"Привет, {message.from_user.first_name}! Добро пожаловать!")


@dp.message(Command('notesadm'))
async def add_notes(message: types.Message):
    buttons = [
        [InlineKeyboardButton(text="редактировать заметку", callback_data="note_edit")],
        [InlineKeyboardButton(text="создать заметку", callback_data="note_creation")],
        [InlineKeyboardButton(text="удалить заметку", callback_data=f"notedel")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer('выберите действие', reply_markup=keyboard)




@dp.message(Command('add_admin'))
async def add_admin(message: types.Message, command: CommandObject):
    admins = await get_admins()
    if message.from_user.id not in admins:
        return

    if not command.args:
        await message.answer('usage: /add_admin <tg_id>')
        return

    try:
        new_admin_id = int(command.args.strip())
    except ValueError:
        await message.answer("tg_id isn't number")
        return

    async with aiosqlite.connect('kb_adminbot.db') as db:
        await db.execute("INSERT OR IGNORE INTO Admins (Tg_id) VALUES (?)", (new_admin_id,))
        await db.commit()

    await message.answer(f'+, {new_admin_id} now admin')



@dp.message(Command('captcha_delay'))
async def set_captcha_delay(message: types.Message, command: CommandObject):
    global CAPTCHA_DELAY
    admins = await get_admins()
    if message.from_user.id not in admins:
        return

    if not command.args:
        await message.answer(f'usage: /captcha_delay <min>\ncurrent: {CAPTCHA_DELAY // 60} min')
        return

    try:
        minutes = float(command.args.strip())
    except ValueError:
        await message.answer('минуты должны быть числом')
        return

    if minutes <= 0 or minutes >= 300:
        await message.answer('минуты должны быть больше 0 и меньше 300')
        return

    CAPTCHA_DELAY = int(minutes * 60)
    await message.answer(f'+, теперь на капчу даётся {minutes} мин')



#создание заметки
@dp.callback_query(F.data=='note_creation')
async def command_add_notes(callback: types.CallbackQuery):
    buttons=[
        [InlineKeyboardButton(text="1 курс", callback_data="notecreation_1")],
        [InlineKeyboardButton(text="2 курс", callback_data="notecreation_2")],
        [InlineKeyboardButton(text="3 курс", callback_data="notecreation_3")],
        [InlineKeyboardButton(text="4 курс", callback_data="notecreation_4")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text('Выберите курс:', reply_markup=keyboard)
    await callback.answer()




@dp.callback_query(F.data.startswith('notecreation'))
async def command_add_notes(callback: types.CallbackQuery, state: FSMContext):
    course = callback.data.split('_')[1]
    await state.update_data(course = course)
    await callback.message.edit_text('введите заголовок')
    await state.set_state(Addnotes.one)


@dp.message(Addnotes.one)
async def add_notes_1(message: types.Message, state: FSMContext):
    title = message.text
    await state.update_data(title=title)
    await message.answer('введите текст')
    await state.set_state(Addnotes.two)


@dp.message(Addnotes.two)
async def add_notes_2(message: types.Message, state: FSMContext):
    text = message.text
    await state.update_data(text=text)
    await message.answer('документ, если нет то -')
    await state.set_state(Addnotes.three)




@dp.message(Addnotes.three)
async def add_notes_final(message: types.Message, state: FSMContext):
    data = await state.get_data()

    documentid = message.document.file_id if message.document else None

    async with aiosqlite.connect('kb_adminbot.db') as db:
        await db.execute(
            "INSERT INTO Notes (Title, Text, Document, Course) VALUES (?, ?, ?, ?)",
            (data['title'], data['text'], documentid, data['course'])
        )
        await db.commit()

    await message.answer("заметка успешно создана!")
    await state.clear()



#удаление заметки
@dp.callback_query(F.data=='notedel')
async def command_edit_notes(callback: types.CallbackQuery):
    notes = await get_notes_titles_and_numbers()
    if not notes:
        await callback.message.edit_text("Удалять пока что нечего")
        return
    
    buttons = []

    for title, note_number in notes:
        button=[InlineKeyboardButton(text=title, callback_data=f'1notedel_{note_number}')]
        buttons.append(button)
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text('выберите заметку', reply_markup=keyboard)




@dp.callback_query(F.data.startswith('1notedel'))
async def command_delete_notes(callback: types.CallbackQuery):
    notenum=callback.data.split('_')[1]
    async with aiosqlite.connect('kb_adminbot.db') as db:
        await db.execute("DELETE FROM Notes WHERE Note_number =?",
                         (notenum, ))
        await db.commit()
    await callback.message.edit_text(f'готово, заметка {notenum} удалена')



# редактирование заметки выбор заметки
@dp.callback_query(F.data=='note_edit')
async def command_edit_notes(callback: types.CallbackQuery):
    notes = await get_notes_titles_and_numbers()

    if not notes:
        await callback.message.edit_text("заметок пока нет")
        return

    buttons = []

    for title, note_number in notes:
        button=[InlineKeyboardButton(text=title, callback_data=f'notenum_{note_number}')]
        buttons.append(button)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text('выберите заметку', reply_markup=keyboard)



#редактирование заметки выбор действия
@dp.callback_query(F.data.startswith('notenum'))
async def command_edit_notes2(callback: types.CallbackQuery):
    await callback.message.delete()
    notenum=callback.data.split('_')[1]
    notetitle = await get_note_title(notenum)
    notetext = await get_notes_text(notenum)
    document = await get_note_document(notenum)
    await callback.message.answer('вид заметки:')
    if document:
        await bot.send_document(callback.message.chat.id, caption = f'\n{notetitle}\n{notetext}', document = document)
    else:
        await callback.message.answer(f'\n{notetitle}\n{notetext}')
    buttons = [
        [InlineKeyboardButton(text="заголовок", callback_data=f"notered_title_{notenum}")],
        [InlineKeyboardButton(text="текст", callback_data=f"notered_text_{notenum}")],
        [InlineKeyboardButton(text="документ", callback_data=f"notered_document_{notenum}")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer('редактировать', reply_markup=keyboard)



@dp.callback_query(F.data.startswith('notered'))
async def command_red_notes1(callback: types.CallbackQuery, state: FSMContext):
    noteaction = callback.data.split('_')[1]
    notenum = int(callback.data.split('_')[2])
    await state.update_data(notenum=notenum)
    if noteaction == 'title':
        await callback.message.edit_text('введите новый заголовок')
        await state.set_state(Noteredaction.title)
    elif noteaction == 'text':
        await callback.message.edit_text('введите новый текст')
        await state.set_state(Noteredaction.text)
    elif noteaction == 'document':
        await callback.message.edit_text('скиньте новый документ')
        await state.set_state(Noteredaction.document)



@dp.message(Noteredaction.title)
async def red_tittle(message: types.Message, state: FSMContext):
    title = message.text
    data = await state.get_data()
    notenum = data['notenum']
    async with aiosqlite.connect('kb_adminbot.db') as db:
        await db.execute("UPDATE Notes SET Title = ? WHERE Note_number = ?",
                         (title, notenum))
        await db.commit()
    await state.clear()



@dp.message(Noteredaction.text)
async def red_text(message: types.Message, state: FSMContext):
    text = message.text
    data = await state.get_data()
    notenum = data['notenum']
    async with aiosqlite.connect('kb_adminbot.db') as db:
        await db.execute("UPDATE Notes SET Text = ? WHERE Note_number = ?",
                         (text, notenum))
        await db.commit()
    await state.clear()



@dp.message(Noteredaction.document)
async def red_document(message: types.Message, state: FSMContext):
    if not message.document:
        await message.answer('нужно прислать файл (документ)')
        return
    
    documentid = message.document.file_id
    data = await state.get_data()
    notenum = data['notenum']

    async with aiosqlite.connect('kb_adminbot.db') as db:
        await db.execute("UPDATE Notes SET Document = ? WHERE Note_number = ?",
                         (documentid, notenum))
        await db.commit()

    await message.answer("документ обновлен! ")
    await state.clear()



#капча
@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def user_joined(event: types.ChatMemberUpdated, bot: Bot):
    new_user = event.new_chat_member.user
    mention = f'<a href="tg://user?id={new_user.id}">{html.escape(new_user.first_name)}</a>'

    added_by = event.from_user
    if added_by:
        admins = await get_admins()
        if added_by.id in admins:
            await bot.send_message(
                chat_id=event.chat.id,
                text=f"Привет, {mention}! Добро пожаловать в наш чат!",
                parse_mode="HTML")
            return

    key = StorageKey(bot_id=bot.id, chat_id=event.chat.id, user_id=new_user.id)
    state = FSMContext(storage=dp.storage, key=key)
    num1 = random.randint(1,10)
    num2 = random.randint(1,10)
    await bot.send_message(
        chat_id=event.chat.id,
        text=f"Привет, {mention}! Добро пожаловать в наш чат!",
        parse_mode="HTML")
    await bot.send_message(
        chat_id=event.chat.id,
        text=f"{mention}, реши капчу {num1}*{num2}, на любой ответ кроме правильного тебя забанят",
        parse_mode="HTML")
    await state.update_data(answer=str(num1*num2))
    await state.set_state(Capcha.one)
    await asyncio.sleep(CAPTCHA_DELAY)

    if await state.get_state() == Capcha.one.state:
        await bot.ban_chat_member(chat_id=event.chat.id, user_id=new_user.id)
        await state.clear()
        await bot.send_message(chat_id=event.chat.id,
                               text=f"{mention} не решил капчу вовремя и был забанен",
                               parse_mode="HTML")




@dp.message(Capcha.one)
async def capcha(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    answer = data['answer']
    if message.text == answer:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        await message.answer('красава, добро пожаловать')
        await state.clear()
    else:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=user_id)
        await state.clear()




@dp.message(Command('notes'))
async def notes(message: types.Message):
    buttons = [
        [InlineKeyboardButton(text="1 курс", callback_data="noteview_1")],
        [InlineKeyboardButton(text="2 курс", callback_data="noteview_2")],
        [InlineKeyboardButton(text="3 курс", callback_data="noteview_3")],
        [InlineKeyboardButton(text="4 курс", callback_data="noteview_4")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer('выберите курс', reply_markup=keyboard)



@dp.callback_query(F.data.startswith('noteview'))
async def command_view(callback: types.CallbackQuery, state: FSMContext):
    course = callback.data.split('_')[1]
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute("SELECT Title, Note_number FROM notes WHERE Course = ?",
                                  (course, ))
        title1 = await cursor.fetchall()
        title = []
        number = []
        for i in title1:
            title.append(i[0])
            number.append(i[1])
    buttons = []
    for i in range(len(title)):
        button = [InlineKeyboardButton(text=title[i], callback_data=f'1noteview_{number[i]}')]
        buttons.append(button)
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text('выберите заметку', reply_markup=keyboard)



@dp.callback_query(F.data.startswith('1noteview'))
async def command_view1(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    number = callback.data.split('_')[1]
    async with aiosqlite.connect('kb_adminbot.db') as db:
        cursor = await db.execute("SELECT Title, Text, Document FROM notes WHERE Note_number = ?",
                                  (number, ))
        data = await cursor.fetchall()
        title = data[0][0]
        text = data[0][1]
        document = data[0][2]
    if document:
        await bot.send_document(callback.message.chat.id, document, caption=f'{title}\n\n{text}')
    else:
        await bot.send_message(callback.message.chat.id, f'{title}\n\n{text}')


@dp.message(Command('suggest'))
async def add_suggestion(message: types.Message, state: FSMContext):
    await message.answer('Напишите пост/идею для обьявлений в чате, сообщение будет проверено админами')
    await state.set_state(Suggestions.text)




@dp.message(Suggestions.text)
async def suggestions(message: types.Message, state: FSMContext):
    if message.document:
        documentid = message.document.file_id
    elif message.photo:
        documentid = message.photo[-1].file_id
    else:
        documentid = None

    text = message.text or message.caption

    if not text and not documentid:
        await message.answer('не получилось прочитать сообщение, пришли текстом или файлом/фото с подписью')
        return

    async with aiosqlite.connect('kb_adminbot.db') as db:
        await db.execute(
            "INSERT INTO Suggestions (Text, Document) VALUES (?, ?)",
            (text, documentid)
        )
        await db.commit()
    await state.clear()
    await message.answer('предложение отправлено на модерацию, спасибо!')



@dp.message(Command('suggestions'))
async def check_suggestions(message: types.Message):
    admins = await get_admins()
    if message.from_user.id in admins:
        await send_next_suggestion(message.chat.id, message.bot)

@dp.callback_query(F.data.startswith('sug_del_'))
async def sug_del(callback: types.CallbackQuery):
    number = int(callback.data.split('_')[2])
    await callback.message.delete()
    await delete_suggestion(number)
    await send_next_suggestion(callback.message.chat.id, callback.bot)



@dp.callback_query(F.data.startswith('sug_post_'))
async def sug_post(callback: types.CallbackQuery):
    number = int(callback.data.split('_')[2])
    await callback.message.delete()
    row = await get_next_suggestion()
    if row and row[0] == number:
        _, text, document = row
        if document:
            try:
                await bot.send_document(chat_id=SUGGESTIONS_CHAT_ID, document=document, caption=text, message_thread_id=SUGGESTIONS_THREAD_ID)
            except TelegramBadRequest:
                await bot.send_photo(chat_id=SUGGESTIONS_CHAT_ID, photo=document, caption=text, message_thread_id=SUGGESTIONS_THREAD_ID)
        else:
            await bot.send_message(chat_id=SUGGESTIONS_CHAT_ID, text=text, message_thread_id=SUGGESTIONS_THREAD_ID)
        await delete_suggestion(number)

    await send_next_suggestion(callback.message.chat.id, callback.bot)



@dp.callback_query(F.data == 'sug_quit')
async def sug_quit(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer('Вы вышли из режима просмотра предложки')



async def main():
    await create_database()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())