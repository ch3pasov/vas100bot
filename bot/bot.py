import hashlib
import random
import string
import os
import html
import re
import json
import time

from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, InlineQueryHandler, CallbackContext, MessageHandler, filters

logfile = open("./data/updates.log", 'a', encoding='utf-8')

hex2ones = {"0":0,"1":1,"2":1,"3":2,"4":1,"5":2,"6":2,"7":3,"8":1,"9":2,"a":2,"b":3,"c":2,"d":3,"e":3,"f":4}

def vas100(seed, random_seed):
    if random_seed:
        seed = str(random.randint(-2**63, 2**63-1))

    hash = hashlib.sha256()
    hash.update(seed.encode())

    digest = hash.hexdigest()[0:25]

    b1 = sum([hex2ones[hex] for hex in digest])
    b0 = 100 - b1

    e = b1 - 2 * b0
    x = 2 ** e
    won = re.match(r"^\d+(\.0{0,60}[^0]{0,2})?", str(x) if x >= 1 else f'{x:.50f}').group(0)
    if float(won) == 0:
        won = f'{x:.2e}'
    randomness = "рандомный (пустой) " if random_seed else ""

    return e, seed, digest[0:13], f'Симулятор игры Василия, вернется <b>x{won}</b> ставки, {randomness}сид:\n\n<code>{html.escape(seed)}</code>\n\n' + \
        f'Первые <b>100 бит SHA-256</b> {digest}\n' + \
        f'{b1} x "1", {b0} x "0", <b>2 в степени {e}</b> = {b1} - 2 * {b0}'


async def inline_query(update, ctx):
    seed = update.inline_query.query
    random_seed = seed == ""
    randomness = "рандомный (пустой) " if random_seed else ""

    x, seed, hash, out = vas100(seed, random_seed)
    logline = json.dumps((update.to_dict(), x, seed, hash, out, time.time()), ensure_ascii=False) + "\n"
    logfile.write(logline)
    logfile.flush()

    await update.inline_query.answer([
        InlineQueryResultArticle(
            id=''.join(random.choices(string.ascii_letters + string.digits, k=16)),
            title=f'Сыграть с Василием, {randomness}сид',
            description=("" if random_seed else f'"{seed}"'),
            input_message_content=InputTextMessageContent(out, parse_mode='HTML')
        )
    ], cache_time=0)


async def text_message_handler(update, ctx: CallbackContext):
    seed = update.message.text

    x, seed, hash, out = vas100(seed, seed == "/random")
    logline = json.dumps((update.to_dict(), x, seed, hash, out, time.time()), ensure_ascii=False) + "\n"
    logfile.write(logline)
    logfile.flush()

    await ctx.bot.send_message(chat_id=update.effective_chat.id, text=out, parse_mode='HTML')


if __name__ == "__main__":
    application = Application.builder().token(os.getenv('API_KEY')).build()
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(MessageHandler(filters.TEXT, text_message_handler))
    application.run_polling()
