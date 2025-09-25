from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple
import json

import telebot
from telebot import types

from database.sqlite import SessionLocal, Listing
from dotenv import load_dotenv


PAGE_SIZE = 5


# Global variables to track parser status
parser_is_running: bool = False
parser_thread: Optional[threading.Thread] = None


@dataclass
class ListingView:
    id: int
    title: str
    price: str | None
    address: str | None
    link: str
    images: list[str] | None = None


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
                id=r.id,
                title=(r.title or "Без заголовка"),
                price=r.price,
                address=r.address,
                link=r.link,
                images=json.loads(r.images) if r.images else None,
            )
            for r in rows
        ]
        return items, total

def fetch_listings_by_query(query: str, page: int) -> Tuple[List[ListingView], int]:
    offset = max(page, 0) * PAGE_SIZE
    with SessionLocal() as session:
        search_pattern = f"%{query}%"
        total = session.query(Listing).filter(
            (Listing.title.ilike(search_pattern)) | (Listing.address.ilike(search_pattern))
        ).count()
        rows = (
            session.query(Listing)
            .filter((Listing.title.ilike(search_pattern)) | (Listing.address.ilike(search_pattern)))
            .order_by(Listing.created_at.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
            .all()
        )
        items = [
            ListingView(
                id=r.id,
                title=(r.title or "Без заголовка"),
                price=r.price,
                address=r.address,
                link=r.link,
                images=json.loads(r.images) if r.images else None,
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

def run_parser_background(bot: telebot.TeleBot, chat_id: int) -> None:
    """Run parser and notify the user about the result."""
    global parser_is_running
    global parser_thread
    try:
        parser_is_running = True
        from src.main import main as run_parser
        new_items_count = run_parser()
        with SessionLocal() as session:
            total_count = session.query(Listing).count()
        
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))
        bot.send_message(
            chat_id,
            f"\u2705 <b>Парсер завершен успешно!</b>\n\nНовых объектов: {new_items_count}\nВсего в базе: {total_count}",
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception as e:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))
        bot.send_message(chat_id, f"\u2757 <b>Ошибка парсера:</b> {e}", reply_markup=kb)
    finally:
        parser_is_running = False
        parser_thread = None

def get_db_statistics() -> str:
    with SessionLocal() as session:
        total_listings = session.query(Listing).count()
        first_listing = session.query(Listing).order_by(Listing.created_at.asc()).first()
        last_listing = session.query(Listing).order_by(Listing.created_at.desc()).first()

        stats_text = f"\U0001F4CA <b>Статистика базы данных:</b>\n"
        stats_text += f"Общее количество объявлений: {total_listings}\n"
        if first_listing:
            stats_text += f"Самое старое объявление: {first_listing.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        if last_listing:
            stats_text += f"Самое новое объявление: {last_listing.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return stats_text

def send_main_menu(bot: telebot.TeleBot, chat_id: int, message_id: Optional[int] = None) -> None:
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("\u25B6\uFE0F Запустить парсер", callback_data="start_parser"))
    kb.row(types.InlineKeyboardButton("\U0001F5C2 Журнал", callback_data="journal:0"))
    kb.row(types.InlineKeyboardButton("\U0001F4CA Статистика БД", callback_data="db_stats"))
    kb.row(types.InlineKeyboardButton("\U0001F50D Поиск объектов", callback_data="search_prompt"))
    kb.row(types.InlineKeyboardButton("\u2139\uFE0F Статус парсера", callback_data="parser_status"))
    kb.row(types.InlineKeyboardButton("\u2699\uFE0F Настройки", callback_data="settings"))
    text = "\U0001F44B <b>Добро пожаловать!</b>\n\nЯ бот для парсинга объявлений с Avito.\nВыберите одно из следующих действий:"
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="HTML")
        except telebot.apihelper.ApiTelegramException as e:
            if 'message is not modified' in e.description:
                pass # Ignore if message is not modified
            elif 'there is no text in the message to edit' in e.description:
                bot.delete_message(chat_id, message_id)
                bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
            else:
                raise
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


def create_bot() -> telebot.TeleBot:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    bot = telebot.TeleBot(token, parse_mode="HTML")

    # Start command
    @bot.message_handler(commands=["start", "help"])
    def handle_start(message: types.Message) -> None:
        send_main_menu(bot, message.chat.id)

    def search_query_step(message: types.Message) -> None:
        query = message.text
        if not query:
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))
            bot.send_message(message.chat.id, "Запрос не может быть пустым.", reply_markup=kb)
            return
        send_search_results_page(bot, message.chat.id, query, page=0)

    @bot.callback_query_handler(func=lambda c: c.data == "start_parser")
    def handle_start_parser_cb(call: types.CallbackQuery) -> None:
        global parser_is_running
        global parser_thread

        bot.answer_callback_query(call.id)
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))
        if parser_is_running and parser_thread and parser_thread.is_alive():
            bot.send_message(call.message.chat.id, "Парсер уже запущен.", reply_markup=kb)
        else:
            bot.send_message(call.message.chat.id, "Запускаю парсер...", reply_markup=kb)
            parser_thread = threading.Thread(
                target=run_parser_background,
                args=(bot, call.message.chat.id),
                daemon=True
            )
            parser_thread.start()

    @bot.callback_query_handler(func=lambda c: c.data == "db_stats")
    def handle_db_stats_cb(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        stats = get_db_statistics()
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))
        bot.send_message(call.message.chat.id, stats, parse_mode="HTML", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "search_prompt")
    def handle_search_prompt_cb(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))
        bot.send_message(call.message.chat.id, "Введите запрос для поиска:", reply_markup=kb)
        bot.register_next_step_handler(call.message, search_query_step)

    @bot.callback_query_handler(func=lambda c: c.data == "parser_status")
    def handle_parser_status_cb(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        status_text = "Парсер активен." if parser_is_running and parser_thread and parser_thread.is_alive() else "Парсер неактивен."
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))
        bot.send_message(call.message.chat.id, status_text, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "settings")
    def handle_settings_cb(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Настройки пока в разработке.")

    @bot.callback_query_handler(func=lambda c: c.data == "main_menu")
    def handle_main_menu_cb(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        send_main_menu(bot, call.message.chat.id, call.message.message_id)

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

    # Callback for search pagination
    @bot.callback_query_handler(func=lambda c: c.data.startswith("search:"))
    def handle_search_cb(call: types.CallbackQuery) -> None:
        _, query, page_s = call.data.split(":", 2)
        try:
            page = int(page_s)
        except Exception:
            page = 0
        send_search_results_page(bot, call.message.chat.id, query, page=page, edit_message=call.message)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("details:"))
    def handle_details_cb(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id) # Answer immediately
        _, listing_id_str, page_str = call.data.split(":", 2) # Parse page from callback_data
        try:
            listing_id = int(listing_id_str)
            journal_page = int(page_str) # Store journal page
        except ValueError:
            bot.send_message(call.message.chat.id, "Неверный ID объявления или номер страницы.")
            return
        with SessionLocal() as session:
            listing = session.query(Listing).filter_by(id=listing_id).first()
            if listing:
                images = json.loads(listing.images) if listing.images else []
                image_url = images[0] if images else None

                detail_text = f"<b>{listing.title or 'Без заголовка'}</b>\n"
                if listing.price:
                    detail_text += f"Цена: {listing.price}\n"
                if listing.address:
                    detail_text += f"Адрес: {listing.address}\n"
                if listing.bail:
                    detail_text += f"Залог: {listing.bail}\n"
                if listing.tax:
                    detail_text += f"Комиссия: {listing.tax}\n"
                if listing.services:
                    detail_text += f"ЖКУ: {listing.services}\n"
                if listing.desc:
                    detail_text += f"\nОписание:\n{listing.desc}\n"

                # Create inline keyboard for the link button and "К списку" button
                kb_details = types.InlineKeyboardMarkup()
                kb_details.add(types.InlineKeyboardButton("Ссылка", url=listing.link))
                kb_details.row(
                    types.InlineKeyboardButton("К списку", callback_data=f"back_to_journal:{journal_page}"),
                    types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu")
                )

                if image_url:
                    bot.send_photo(call.message.chat.id, image_url, caption=detail_text, parse_mode="HTML", reply_markup=kb_details)
                else:
                    bot.send_message(call.message.chat.id, detail_text, parse_mode="HTML", reply_markup=kb_details)
            else:
                bot.send_message(call.message.chat.id, "Детали объявления не найдены.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("back_to_journal:"))
    def handle_back_to_journal_cb(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        _, page_str = call.data.split(":", 1)
        try:
            page = int(page_str)
        except ValueError:
            page = 0 # Default to first page if invalid
        # We can't edit a message with a photo into a text-only message.
        # So, we delete the old message and send a new one.
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: # Ignore if deletion fails
            pass
        send_journal_page(bot, call.message.chat.id, page=page)

    return bot

def send_journal_page(bot: telebot.TeleBot, chat_id: int, page: int, edit_message: Optional[types.Message] = None) -> None:
    text = "" # Initialize text
    kb = types.InlineKeyboardMarkup()

    items, total = fetch_listings_page(page)
    if not items:
        text = "Журнал пуст."
    else:
        start_range = page * PAGE_SIZE + 1
        end_range = min((page + 1) * PAGE_SIZE, total)
        
        lines = [f"Показано {start_range}-{end_range} из {total} объявлений."]
        
        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        lines.append(f"Страница {page+1} из {total_pages}.")
        lines.append("Выберете объект для просмотра:") # New line
        
        text = "\n".join(lines)

        # Create a list of inline keyboard buttons for listings
        listing_buttons = []
        for i, it in enumerate(items, start_range):
            button_text = f"{i}. {it.title}"
            if it.price:
                button_text += f" - {it.price}"
            listing_buttons.append(types.InlineKeyboardButton(button_text, callback_data=f"details:{it.id}:{page}")) # Brief description for button

        # Add listing buttons as separate rows (now before pagination)
        for btn in listing_buttons:
            kb.row(btn)

        buttons = []
        if page > 0:
            buttons.append(types.InlineKeyboardButton("\u2B05\uFE0F Назад", callback_data=f"journal:{page-1}"))
        if (page + 1) * PAGE_SIZE < total:
            buttons.append(types.InlineKeyboardButton("Далее \u27A1\uFE0F", callback_data=f"journal:{page+1}"))
        if buttons:
            kb.row(*buttons) # Add pagination buttons as a row

    kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))

    if edit_message:
        bot.edit_message_text(text, chat_id=chat_id, message_id=edit_message.message_id, reply_markup=kb, disable_web_page_preview=True)
    else:
        bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)

def send_search_results_page(bot: telebot.TeleBot, chat_id: int, query: str, page: int, edit_message: Optional[types.Message] = None) -> None:
    items, total = fetch_listings_by_query(query, page)
    kb = types.InlineKeyboardMarkup()
    if not items:
        text = f"По запросу \'{query}\' ничего не найдено."
    else:
        start = page * PAGE_SIZE + 1
        lines = [f"Результаты поиска по запросу \'{query}\' (стр. {page+1})"]
        for i, it in enumerate(items, start):
            lines.append(format_listing(it, i))
        text = "\n".join(lines)

        # Pagination inline keyboard
        buttons = []
        if page > 0:
            buttons.append(types.InlineKeyboardButton("\u2B05\uFE0F Назад", callback_data=f"search:{query}:{page-1}"))
        if (page + 1) * PAGE_SIZE < total:
            buttons.append(types.InlineKeyboardButton("Вперед \u27A1\uFE0F", callback_data=f"search:{query}:{page+1}"))
        if buttons:
            kb.row(*buttons)

    kb.row(types.InlineKeyboardButton("\U0001F3E0 Меню", callback_data="main_menu"))

    if edit_message:
        bot.edit_message_text(text, chat_id=chat_id, message_id=edit_message.message_id, reply_markup=kb, disable_web_page_preview=True)
    else:
        bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)

def main() -> None:
    load_dotenv()
    bot = create_bot()
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)


if __name__ == "__main__":
    main()
