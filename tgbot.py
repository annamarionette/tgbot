from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "OK"

Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

import telebot
import requests
from decimal import Decimal, getcontext
import time

# --- НАСТРОЙКИ ---
TG_TOKEN = '8330328134:AAGddNy1kYjdVZ3_JX7HUS3V6m2gJSgKNu8'
EXCHANGE_API_KEY = 'c8bbfcabe4e74531fbfaca2e'

bot = telebot.TeleBot(TG_TOKEN)
getcontext().prec = 50

# Список популярных криптовалют (можно расширить)
CRYPTO_LIST = {
    'BTC', 'ETH', 'USDT', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL',
    'TON', 'DOT', 'MATIC', 'LTC', 'SHIB', 'TRX', 'AVAX', 'LINK',
    'XLM', 'ATOM', 'XMR', 'ETC', 'BCH', 'APT', 'FIL', 'NEAR',
    'PEPE', 'ARB', 'OP', 'IMX', 'INJ', 'SUI', 'SEI', 'NOT'
}


def format_precise(d: Decimal) -> str:
    """Форматирует число без научной нотации и лишних нулей"""
    s = format(d, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def is_crypto(code: str) -> bool:
    """Проверяет, является ли валюта криптовалютой"""
    return code.upper() in CRYPTO_LIST


# --- КОНВЕРТАЦИЯ ЧЕРЕЗ EXCHANGERATE-API (ФИАТ) ---
def convert_fiat(amount: Decimal, base: str, target: str) -> dict:
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/pair/{base}/{target}"
    response = requests.get(url).json()

    if response.get('result') != 'success':
        return None

    rate = Decimal(str(response['conversion_rate']))
    result = amount * rate
    update_time = time.strftime('%H:%M UTC', time.gmtime(response['time_last_update_unix']))

    return {
        'result': result,
        'rate': rate,
        'update_time': update_time,
        'source': 'ExchangeRate-API',
        'has_24h_stats': False
    }


# --- КОНВЕРТАЦИЯ ЧЕРЕЗ CRYPTOCOMPARE (КРИПТА) ---
def convert_crypto(amount: Decimal, base: str, target: str) -> dict:
    url = f"https://min-api.cryptocompare.com/data/pricemultifull?fsyms={base}&tsyms={target}"
    response = requests.get(url).json()

    if 'RAW' not in response:
        return None

    data = response['RAW'][base][target]
    rate = Decimal(str(data['PRICE']))
    result = amount * rate

    return {
        'result': result,
        'rate': rate,
        'high_24h': Decimal(str(data['HIGH24HOUR'])),
        'low_24h': Decimal(str(data['LOW24HOUR'])),
        'change_pct': data['CHANGEPCT24HOUR'],
        'source': 'CryptoCompare',
        'has_24h_stats': True
    }


# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start(m):
    text = (
        "🏦 **Универсальный конвертер**\n\n"
        "Поддерживаю фиат (USD, RUB, EUR) и крипту (BTC, ETH, TON).\n\n"
        "Пиши: Сумма / Валюта-1 / Валюта-2\n\n"
        "Примеры:\n"
        "💵 1000 USD RUB — фиат\n"
        "💎 0.5 BTC USDT — крипта\n"
        "🔄 100 TON USD — крипта в фиат"
    )
    bot.send_message(m.chat.id, text, parse_mode='Markdown')


@bot.message_handler(content_types=['text'])
def convert(m):
    try:
        parts = m.text.upper().replace(',', '.').split()
        if len(parts) != 3:
            raise ValueError

        amount = Decimal(parts[0])
        base = parts[1]
        target = parts[2]

        # Определяем, какой API использовать
        if is_crypto(base) or is_crypto(target):
            data = convert_crypto(amount, base, target)
        else:
            data = convert_fiat(amount, base, target)

        if not data:
            bot.reply_to(m, f"❌ Не удалось найти курс {base}/{target}")
            return

        # Формируем ответ
        text = (
            f"💰 **Результат:**\n"
            f"`{format_precise(amount)} {base}` ➡️ `{format_precise(data['result'])} {target}`\n\n"
            f"📊 **Курс:** 1 {base} = `{format_precise(data['rate'])}` {target}\n"
        )

        # Добавляем статистику 24ч, если доступна
        if data['has_24h_stats']:
            pct = data['change_pct']
            emoji = "📈" if pct > 0 else "📉"
            sign = "+" if pct > 0 else ""

            text += (
                f"\n📅 **За 24 часа:**\n"
                f"⬆️ Макс: `{format_precise(data['high_24h'])}`\n"
                f"⬇️ Мин: `{format_precise(data['low_24h'])}`\n"
                f"{emoji} Изменение: `{sign}{pct:.2f}%`\n"
            )
        else:
            if 'update_time' in data:
                text += f"\n🕒 Обновлено: {data['update_time']}\n"

        text += f"\n_Источник: {data['source']}_"
        bot.reply_to(m, text, parse_mode='Markdown')

    except ValueError:
        bot.reply_to(m, "⚠️ Формат: `100 USD RUB`", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(m, f"⚠️ Ошибка: {e}")


bot.infinity_polling()
