import logging
import asyncio
import aiosqlite

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, PreCheckoutQuery

#DB
async def init_db():
    async with aiosqlite.connect('members.db') as db:

        #БД для пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER,
                username TEXT
            )
        ''')

        #БД для истории покупок
        await db.execute('''
            CREATE TABLE IF NOT EXISTS payments(
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER,
                charge_id TEXT UNIQUE,
                amount INTEGER,
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            )
        ''')

#DEFS
async def regist_user(telegram_id: int, username: str = None):
    async with aiosqlite.connect('members.db') as db:
        cursor = await db.execute(
            'SELECT id FROM users WHERE telegram_id = ?',
            (telegram_id,)
        )
        user = await cursor.fetchone()

        if user is None:
            await db.execute(
                'INSERT INTO users (telegram_id, username) VALUES (?, ?)',
                (telegram_id, username)
            )
            await db.commit()

async def check_charge_id(charge_id):
    async with aiosqlite.connect('members.db') as db:
        cursor = await db.execute(
            'SELECT id FROM payments WHERE charge_id = ?',
            (charge_id,)
        )
        result = await cursor.fetchone()
        return result is not None

async def save_payment(telegram_id, charge_id):
    try:
        async with aiosqlite.connect('members.db') as db:
            await db.execute(
                'INSERT INTO payments (telegram_id, charge_id) VALUES (?, ?)',
                (telegram_id, charge_id)
            )
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        return False

#BOT
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    telegram_id = message.from_user.id
    username = message.from_user.username

    await regist_user(telegram_id, username)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Оплатить', callback_data='payment')],
        [InlineKeyboardButton(text='Помощь', callback_data='help')]
    ])

    await message.answer(
        text=f'''
        Приветствую {message.from_user.first_name}!
        Чтобы продолжить оплатите 100р чтобы получить приглошение в группу
        ''',
        reply_markup=keyboard
        )

@dp.callback_query(F.data == 'help')
async def help_handler(callback: types.CallbackQuery):

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Оплатить', callback_data='payment')]])

    await callback.message.answer(
        text='''
        Это бот для добавления в закрытый тгк
        Чтобы вы получили приглошение в канал оплатите стоимость приглошения
        ''',
        reply_markup=keyboard
    )

@dp.callback_query(F.data == 'payment')
async def payment_operation(callback: types.CallbackQuery):
    provider_token = 'YOUR_PROVIDER_TOKEN'

    PRICE = LabeledPrice(label='Доступ в закрытый тгк', amount=10000)
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title='Оплата доступа',
        description='Доступ в закрытый тгк',
        payload=f'user_{callback.from_user.id}',
        provider_token=provider_token,
        currency='RUB',
        prices=[PRICE],
        start_parameter='create_invide'
    )
    await callback.answer()

@dp.pre_checkout_query()
async def on_pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)

@dp.message(F.successful_payment)
async def on_successful_payment(message: types.Message):
    payment_info = message.successful_payment
    user_id = message.from_user.id
    charge_id = payment_info.provider_payment_charge_id

    if await check_charge_id(charge_id):
        await message.answer("Этот платеж уже был обработан")
        return

    #Создаем инвайт-ссылку
    try:
        invite_link = await message.bot.create_chat_invite_link(
            chat_id=YOUR_CHAT_ID,
            member_limit=1,
            name=f"Invite for user {user_id}"
        )

        await message.answer(
            f"Оплата прошла успешно!\n"
            f"Ваша персональная ссылка для входа в канал (действует 1 раз):\n"
            f"{invite_link.invite_link}"
        )

        saved = await save_payment(user_id, charge_id)
        if not saved:
            #Логируем ошибку
            logging.error(f"Не удалось сохранить платеж {charge_id} для пользователя {user_id}")


    except Exception as e:
        # Логируем ошибку и сообщаем пользователю
        await message.answer("Произошла ошибка при выдаче доступа. Свяжитесь с поддержкой.")

async def main():
    logging.basicConfig(level=logging.INFO)
    TOKEN = 'YOUR_TOKEN'
    bot = Bot(token=TOKEN)
    await init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())