from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

import telebot
from telebot import types

from database.sqlite import SessionLocal, Listing


PAGE_SIZE = 5


@dataclass
class ListingView:
    title: str
    price: str | None
    address: str | None
    link: str


def fetch_listings_page(page: int) -> Tuple[List[ListingView], int]:
    """Return listings for page (0-based) and total count."""
    offset = max(page, 0) * PAGE_SIZE
    with SessionLocal() as session:
        total = session.query(Listing).count()
        rows = (
            session.query(Listing)
            .order_by(Listing.created_at.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
            .all()
        )
        items = [
            ListingView(
                title=(r.title or "Без заголовка"),
                price=r.price,
                address=r.address,
                link=r.link,
            )
            for r in rows
        ]
        return items, total


def format_listing(item: ListingView, idx: int) -> str:
    lines = [f"{idx}. {item.title}"]
    if item.price:
        lines.append(f"Цена: {item.price}")
    if item.address:
        lines.append(f"Адрес: {item.address}")
    lines.append(f"Ссылка: {item.link}")
    return "\n".join(lines)


def run_parser_background() -> None:
    from src.main import main as run_parser
    run_parser()


def create_bot() -> telebot.TeleBot:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    bot = telebot.TeleBot(token, parse_mode="HTML")

    # Start command
    @bot.message_handler(commands=["start", "help"])
    def handle_start(message: types.Message) -> None:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton("▶️ Запустить парсер"))
        kb.add(types.KeyboardButton("🗂 Журнал"))
        kb.add(types.KeyboardButton("⚙️ Настройки"))
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=kb)

    # Text menu
    @bot.message_handler(func=lambda m: m.text in {"▶️ Запустить парсер", "🗂 Журнал", "⚙️ Настройки"})
    def handle_menu(message: types.Message) -> None:
        if message.text == "▶️ Запустить парсер":
            bot.send_message(message.chat.id, "Запускаю парсер...")
            t = threading.Thread(target=run_parser_background, daemon=True)
            t.start()
            bot.send_message(message.chat.id, "Парсер запущен. Результаты попадут в базу.")
        elif message.text == "🗂 Журнал":
            send_journal_page(bot, message.chat.id, page=0)
        else:
            bot.send_message(message.chat.id, "Настройки пока в разработке.")

    # Callback for journal pagination
    @bot.callback_query_handler(func=lambda c: c.data.startswith("journal:"))
    def handle_journal_cb(call: types.CallbackQuery) -> None:
        _, page_s = call.data.split(":", 1)
        try:
            page = int(page_s)
        except Exception:
            page = 0
        send_journal_page(bot, call.message.chat.id, page=page, edit_message=call.message)
        bot.answer_callback_query(call.id)

    return bot


def send_journal_page(bot: telebot.TeleBot, chat_id: int, page: int, edit_message: Optional[types.Message] = None) -> None:
    items, total = fetch_listings_page(page)
    if not items:
        text = "Журнал пуст."
    else:
        start = page * PAGE_SIZE + 1
        lines = [f"Последние объекты (стр. {page+1})"]
        for i, it in enumerate(items, start):
            lines.append(format_listing(it, i))
        text = "\n\n".join(lines)

    # Pagination inline keyboard
    kb = types.InlineKeyboardMarkup()
    buttons = []
    if page > 0:
        buttons.append(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"journal:{page-1}"))
    if (page + 1) * PAGE_SIZE < total:
        buttons.append(types.InlineKeyboardButton("Вперед ➡️", callback_data=f"journal:{page+1}"))
    if buttons:
        kb.row(*buttons)

    if edit_message:
        bot.edit_message_text(text, chat_id=chat_id, message_id=edit_message.message_id, reply_markup=kb, disable_web_page_preview=True)
    else:
        bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)


def main() -> None:
    bot = create_bot()
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)


if __name__ == "__main__":
    main()


