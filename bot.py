import asyncio
from aiogram import Bot, Dispatcher, types, F
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
from aiogram.filters.command import Command


load_dotenv()


logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
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






#блок работы с заметками
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    admins = await get_admins()
    if message.from_user.id in admins:
        buttons = [
            [InlineKeyboardButton(text="редактировать заметку", callback_data="note_edit")],
            [InlineKeyboardButton(text="создать заметку", callback_data="note_creation")],
            [InlineKeyboardButton(text="удалить заметку", callback_data=f"notedel")]
            ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer('выберите действие', reply_markup=keyboard)
    else:
        await message.answer(f"Привет, {message.from_user.first_name}! Добро пожаловать!")




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
        callback.message.edit_text("Удалять пока что нечего")
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
    key = StorageKey(bot_id=bot.id, chat_id=event.chat.id, user_id=new_user.id)
    state = FSMContext(storage=dp.storage, key=key)
    num1 = random.randint(1,10)
    num2 = random.randint(1,10)
    await bot.send_message(
        chat_id=event.chat.id,
        text=f"Привет, {event.new_chat_member.user.first_name}! Добро пожаловать в наш чат!")
    await bot.send_message(
        chat_id=event.chat.id,
        text=f"реши капчу {num1}*{num2}, на любой ответ кроме правильного тебя забанят")
    await state.update_data(answer=str(num1*num2))
    await state.set_state(Capcha.one)
    await asyncio.sleep(60)

    if await state.get_state() == Capcha.one.state:
        await bot.ban_chat_member(chat_id=event.chat.id, user_id=new_user.id)
        await state.clear()
        await bot.send_message(chat_id=event.chat.id,
                               text=f"{new_user.first_name} не решил капчу вовремя и был забанен")




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








async def main():
    await create_database()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())