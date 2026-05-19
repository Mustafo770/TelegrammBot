import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ───────────────────────────────────────────────
# НАСТРОЙКИ
# ───────────────────────────────────────────────
BOT_TOKEN = "8869309205:AAGx77n6mrz4jG_tMqwPbF3dlVuClnDG4kE"
GPT4ALL_URL = "http://localhost:1234/v1/chat/completions"
GPT4ALL_MODEL = "qwen2.5-coder-7b-instruct-spider-baseline"

logging.basicConfig(level=logging.INFO)

# ───────────────────────────────────────────────
# ПАМЯТЬ ЧАТА — бот помнит контекст разговора
# ───────────────────────────────────────────────
chat_history: dict[int, list] = {}
MAX_HISTORY = 10

# ───────────────────────────────────────────────
# СИСТЕМНЫЙ ПРОМПТ
# ───────────────────────────────────────────────
SYSTEM_PROMPT = """Ты — умный и дружелюбный AI-помощник туристического агентства из Душанбе, Таджикистан.
Твоё имя — Globe (с тадж. «путешествие»).
Отвечай ТОЛЬКО на русском языке. Будь живым и тёплым, как опытный друг-путешественник.

━━━ КАК ОБЩАТЬСЯ ━━━
- Приветствия (салам, salom, привет, hi, hello): тепло поздоровайся, представься и спроси куда хочет поехать
- Благодарность (спасибо, рахмат, mersi): "Пожалуйста! Рад помочь 😊"
- Прощание (пока, хайр, bye): "До свидания! Хорошего путешествия ✈️"

━━━ НАШИ ТУРЫ ━━━
🇦🇪 Дубай — от $850 | 7 ночей | авиа + отель 4★ + трансфер | вылет каждую пятницу
🇹🇷 Турция (Анталья) — от $650 | 7/10/14 ночей | All Inclusive 5★ | каждую субботу
🇪🇬 Египет (Хургада) — от $700 | 7/10 ночей | All Inclusive 5★ | чартер по запросу
🇲🇻 Мальдивы — от $2200 | 7 ночей | бунгало над водой + питание | через Дубай/Доху
🇷🇺 Россия (Москва/СПб) — от $400 | 5/7 ночей | отель 3★ | 3 раза в неделю

━━━ ЧАСТЫЕ ВОПРОСЫ ━━━
💳 Виза: помогаем оформить бесплатно, большинство стран — виза по прилёту
💰 Оплата: наличные TJS/USD, карта, рассрочка от 50% предоплаты
❌ Отмена: 14+ дней — полный возврат | 7–13 дней — 70% | менее 7 — 50%
👶 Дети: до 2 лет бесплатно | 2–12 лет скидка 30% | нужен загранпаспорт
🏥 Страховка: входит в стоимость, покрытие до $50,000
📄 Документы: загранпаспорт (срок 6+ мес.), фото, иногда справка с работы

━━━ ТЫ ЭКСПЕРТ ПО ПУТЕШЕСТВИЯМ ━━━
Отвечай на любые вопросы о:
🏙 Городах: достопримечательности, районы, транспорт, лайфхаки для туристов
🌍 Странах: климат, культура, визы, валюта, безопасность, лучшее время года
🍽 Еде: национальные блюда, рестораны, уличная еда, что обязательно попробовать
🏨 Отелях: как выбрать, звёздность, расположение, что важно при бронировании
✈️ Перелётах: стыковки, багаж, как сэкономить, лайфхаки
💵 Бюджете: примерные расходы в разных странах, советы по экономии
🎒 Сборах: что взять в дорогу, аптечка путешественника, документы
📸 Фото-местах: лучшие точки для фото в городах мира

━━━ БРОНИРОВАНИЕ ━━━
Если клиент хочет забронировать — спроси: имя, даты, количество человек, направление.
Потом скажи: "Отлично! Передам вашу заявку менеджеру, он свяжется с вами в течение 30 минут 📞"
Контакт менеджера: @nurov0005 | +992 88 807 0808 (Пн–Сб 9:00–18:00)"""

# ───────────────────────────────────────────────
# ТУРЫ С ФОТО
# ───────────────────────────────────────────────
TOURS = {
    "dubai": {
        "name":  "🇦🇪 Дубай",
        "price": "от $850",
        "dur":   "7 ночей",
        "inc":   "Авиа + отель 4★ + трансфер",
        "dep":   "Каждую пятницу",
        "desc":  "Город будущего: Бурдж-Халифа, пустыня, шопинг в Mall of the Emirates.",
        "tip":   "💡 Лучшее время: октябрь–апрель. Летом жара до +45°C.",
        "photo": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800",
    },
    "turkey": {
        "name":  "🇹🇷 Турция (Анталья)",
        "price": "от $650",
        "dur":   "7/10/14 ночей",
        "inc":   "All Inclusive 5★ + авиа",
        "dep":   "Каждую субботу",
        "desc":  "Солнце, море, всё включено. Идеально для семейного отдыха.",
        "tip":   "💡 Лучшее время: май–октябрь. Тёплая вода с июня по сентябрь.",
        "photo": "https://images.unsplash.com/photo-1506929562872-bb421503ef21?w=800",
    },
    
    "maldives": {
        "name":  "🇲🇻 Мальдивы",
        "price": "от $2200",
        "dur":   "7 ночей",
        "inc":   "Бунгало над водой + питание",
        "dep":   "Через Дубай/Доху",
        "desc":  "Роскошный отдых. Бирюзовое море, коралловые острова.",
        "tip":   "💡 Лучшее время: декабрь–апрель (сухой сезон).",
        "photo": "https://images.unsplash.com/photo-1514282401047-d79a71a590e8?w=800",
    },
    "russia": {
        "name":  "🇷🇺 Россия (Москва/СПб)",
        "price": "от $400",
        "dur":   "5/7 ночей",
        "inc":   "Авиа + отель 3★ + трансфер",
        "dep":   "3 раза в неделю",
        "desc":  "Культура, история, Красная площадь, Эрмитаж.",
        "tip":   "💡 Белые ночи в СПб — июнь. Москва красива в любое время.",
        "photo": "https://images.unsplash.com/photo-1513326738677-b964603b136d?w=800",
    },
}

# ───────────────────────────────────────────────
# КЛАВИАТУРЫ
# ───────────────────────────────────────────────
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✈️ Наши туры",             callback_data="tours"),
         InlineKeyboardButton("❓ FAQ",                   callback_data="faq")],
        [InlineKeyboardButton("🌍 Спросить про город/страну", callback_data="ask_city")],
        [InlineKeyboardButton("📋 Забронировать тур",     callback_data="book")],
    ])

def tours_kb():
    rows = [[InlineKeyboardButton(TOURS[k]["name"], callback_data=f"tour_{k}")] for k in TOURS]
    rows.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)

def faq_kb():
    items = [
        ("💳 Визы",        "faq_visa"),
        ("💰 Оплата",      "faq_payment"),
        ("❌ Отмена тура",  "faq_cancel"),
        ("👶 Дети",        "faq_kids"),
        ("🏥 Страховка",   "faq_insurance"),
        ("📄 Документы",   "faq_docs"),
    ]
    rows = [[InlineKeyboardButton(label, callback_data=cd)] for label, cd in items]
    rows.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)

def back_kb(to="menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=to)]])

# ───────────────────────────────────────────────
# GPT4ALL / LM STUDIO — запрос с памятью разговора
# ───────────────────────────────────────────────
async def ask_ai(user_id: int, user_text: str) -> str:
    if user_id not in chat_history:
        chat_history[user_id] = []

    chat_history[user_id].append({"role": "user", "content": user_text})
    # Обрезаем если история слишком длинная
    if len(chat_history[user_id]) > MAX_HISTORY * 2:
        chat_history[user_id] = chat_history[user_id][-MAX_HISTORY * 2:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history[user_id]

    try:
        response = requests.post(
            GPT4ALL_URL,
            json={
                "model": GPT4ALL_MODEL,
                "messages": messages,
                "max_tokens": 600,
            },
            timeout=120
        )
        answer = response.json()["choices"][0]["message"]["content"]
        chat_history[user_id].append({"role": "assistant", "content": answer})
        return answer
    except Exception as e:
        return (
            f"⚠️ Не могу подключиться к AI модели.\n\n"
            f"Проверьте, что в LM Studio запущен Local Server (кнопка Status горит зеленым) на порту 1234.\n"
            f"Ошибка: {e}"
        )

# ───────────────────────────────────────────────
# ОТПРАВКА ФОТО
# ───────────────────────────────────────────────
async def send_photo(message, photo: str, caption: str, kb):
    if photo.startswith("http"):
        await message.reply_photo(photo=photo, caption=caption, reply_markup=kb)
    else:
        with open(photo, "rb") as f:
            await message.reply_photo(photo=f, caption=caption, reply_markup=kb)

# ───────────────────────────────────────────────
# КОМАНДЫ
# ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name or "друг"
    chat_history[user_id] = []  # сброс истории при старте

    await update.message.reply_text(
        f"Салом, {name}! 👋\n\n"
        "Я — Globe, ваш AI-помощник по путешествиям 🌍\n\n"
        "Могу помочь с:\n"
        "✈️ Подбором и бронированием тура\n"
        "🏙 Информацией о городах и странах\n"
        "🍽 Ресторанами и национальной кухней\n"
        "🗺 Достопримечательностями\n"
        "💡 Travel-советами и лайфхаками\n\n"
        "Пишите любой вопрос или выбирайте из меню 👇",
        reply_markup=main_kb()
    )

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_history[update.effective_user.id] = []
    await update.message.reply_text(
        "🔄 История чата очищена!\n\nЧем могу помочь?",
        reply_markup=main_kb()
    )

# ───────────────────────────────────────────────
# КНОПКИ
# ───────────────────────────────────────────────
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id

    if d == "menu":
        await q.message.delete()
        await q.message.reply_text("Главное меню 👇", reply_markup=main_kb())

    elif d == "tours":
        await q.message.delete()
        await q.message.reply_text("✈️ Выберите направление:", reply_markup=tours_kb())

    elif d.startswith("tour_"):
        key = d[5:]
        t = TOURS[key]
        caption = (
            f"{t['name']}\n\n"
            f"💰 Цена: {t['price']}\n"
            f"📅 Длительность: {t['dur']}\n"
            f"✅ Включено: {t['inc']}\n"
            f"🛫 Вылеты: {t['dep']}\n\n"
            f"📝 {t['desc']}\n\n"
            f"{t['tip']}\n\n"
            f"Есть вопросы? Напишите прямо в чат 💬"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Забронировать этот тур", callback_data="book")],
            [InlineKeyboardButton("⬅️ Все туры", callback_data="tours")],
        ])
        await q.message.delete()
        await send_photo(q.message, t["photo"], caption, kb)

    elif d == "faq":
        await q.message.delete()
        await q.message.reply_text("❓ Выберите тему:", reply_markup=faq_kb())

    elif d == "faq_visa":
        answer = await ask_ai(uid, "Расскажи подробно про визы для наших туров")
        await q.message.delete()
        await q.message.reply_text(f"💳 Визы\n\n{answer}", reply_markup=back_kb("faq"))
        
    elif d == "faq_payment":
        answer = await ask_ai(uid, "Расскажи подробно про способы оплаты туров")
        await q.message.delete()
        await q.message.reply_text(f"💰 Оплата\n\n{answer}", reply_markup=back_kb("faq"))

    elif d == "faq_cancel":
        answer = await ask_ai(uid, "Расскажи про условия отмены тура и возврата денег")
        await q.message.delete()
        await q.message.reply_text(f"❌ Отмена тура\n\n{answer}", reply_markup=back_kb("faq"))

    elif d == "faq_kids":
        answer = await ask_ai(uid, "Расскажи про туры с детьми, скидки и условия для детей")
        await q.message.delete()
        await q.message.reply_text(f"👶 Дети\n\n{answer}", reply_markup=back_kb("faq"))

    elif d == "faq_insurance":
        answer = await ask_ai(uid, "Расскажи подробно про страховку которая входит в тур")
        await q.message.delete()
        await q.message.reply_text(f"🏥 Страховка\n\n{answer}", reply_markup=back_kb("faq"))

    elif d == "faq_docs":
        answer = await ask_ai(uid, "Какие документы нужны для оформления тура?")
        await q.message.delete()
        await q.message.reply_text(f"📄 Документы\n\n{answer}", reply_markup=back_kb("faq"))

    elif d == "ask_city":
        await q.message.delete()
        await q.message.reply_text(
            "🌍 Напишите название города или страны!\n\n"
            "Расскажу всё что знаю:\n"
            "• Достопримечательности\n"
            "• Лучшие рестораны и кухня\n"
            "• Когда лучше ехать\n"
            "• Примерный бюджет\n"
            "• Лайфхаки путешественника\n\n"
            "Например: _Стамбул_, _Бали_, _Париж_, _Токио_, _Барселона_... ✍️",
            parse_mode="Markdown",
            reply_markup=back_kb()
        )

    elif d == "book":
        await q.message.delete()
        await q.message.reply_text(
            "📋 Бронирование тура\n\n"
            "Для бронирования свяжитесь с нашим менеджером — он подберёт лучший вариант и оформит всё быстро!\n\n"
            "📞 Телефон: +992 88 807 0808\n"
            "💬 Telegram: @nurov0005\n"
            "✉️ Email: info@youragency.tj\n\n"
            "🕐 Работаем: Пн–Сб, 9:00–18:00\n\n"
            "Или напишите прямо здесь — я приму заявку! 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Написать в Telegram", url="https://t.me/nurov0005")],
                [InlineKeyboardButton("📱 Написать в WhatsApp", url="https://wa.me/992888070808")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="menu")],
            ])
        )

# ───────────────────────────────────────────────
# ТЕКСТОВЫЕ СООБЩЕНИЯ — всё через AI
# ───────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    await update.message.chat.send_action("typing")

    answer = await ask_ai(user_id, user_text)

    await update.message.reply_text(answer, reply_markup=main_kb())

# ───────────────────────────────────────────────
# ЗАПУСК
# ───────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_cmd))  # сбросить историю
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Globe-бот запущен!")
    print("📍 LM Studio сервер должен работать на localhost:1234")
    app.run_polling()