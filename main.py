import os  # 1
import re  # 2
import sys  # 3
import json  # 4
import time  # 5
import asyncio  # 6
import requests  # 7
import subprocess  # 8

import core as helper  # 9
from utils import progress_bar  # 10
from vars import API_ID, API_HASH, BOT_TOKEN  # 11
from aiohttp import ClientSession  # 12
from pyromod import listen  # 13
from subprocess import getstatusoutput  # 14

from pyrogram import Client, filters  # 15
from pyrogram.types import Message  # 16
from pyrogram.errors import FloodWait  # 17
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid  # 18
from pyrogram.types.messages_and_media import message  # 19
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup  # 20

bot = Client(  # 21
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@bot.on_message(filters.command(["start"]))  # 22
async def start(bot: Client, m: Message):
    await m.reply_text(f"<b>Hello {m.from_user.mention} 👋\n\n I Am A Bot For Download Links From Your **.TXT** File And Then Upload That File On Telegram So Basically If You Want To Use Me First Send Me A Txt File.</b>")

@bot.on_message(filters.command("stop"))  # 23
async def restart_handler(_, m):
    await m.reply_text("**Stopped**🚦", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on_message(filters.command(["upload"]))  # 24
async def upload(bot: Client, m: Message):
    editable = await m.reply_text('𝕤ᴇɴᴅ ᴛxᴛ ғɪʟᴇ ⚡️')  # 25
    input: Message = await bot.listen(editable.chat.id)  # 26
    x = await input.download()  # 27
    await input.delete(True)  # 28

    path = f"./downloads/{m.chat.id}"  # 29

    try:
        with open(x, "r") as f:  # 30
            content = f.read()
        content = content.split("\n")  # 31
        links = []  # 32
        for i in content:  # 33
            links.append(i.split("://", 1))  # 34
        os.remove(x)  # 35
    except:
        await m.reply_text("**Invalid file input.**")  # 36
        os.remove(x)  # 37
        return

    await editable.edit(f"**𝕋ᴏᴛᴀʟ ʟɪɴᴋ𝕤 ғᴏᴜɴᴅ ᴀʀᴇ🔗🔗** **{len(links)}**\n\n**𝕊ᴇɴᴅ 𝔽ʀᴏᴍ ᴡʜᴇʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ**")  # 38
    input0: Message = await bot.listen(editable.chat.id)  # 39
    raw_text = input0.text.strip()  # 40
    await input0.delete(True)  # 41

    await editable.edit("**Now Please Send Me Your Batch Name**")  # 42
    input1: Message = await bot.listen(editable.chat.id)  # 43
    raw_text0 = input1.text.strip()  # 44
    await input1.delete(True)  # 45

    await editable.edit("**𝔼ɴᴛᴇʀ ʀᴇ𝕤ᴏʟᴜᴛɪᴏɴ📸**\n144,240,360,480,720,1080 please choose quality")  # 46
    input2: Message = await bot.listen(editable.chat.id)  # 47
    raw_text2 = input2.text.strip()  # 48
    await input2.delete(True)  # 49

    res_map = {"144": "256x144", "240": "426x240", "360": "640x360", "480": "854x480", "720": "1280x720", "1080": "1920x1080"}  # 50
    res = res_map.get(raw_text2, "UN")  # 51

    await editable.edit("Now Enter A Caption to add caption on your uploaded file")  # 52
    input3: Message = await bot.listen(editable.chat.id)  # 53
    raw_text3 = input3.text.strip()  # 54
    await input3.delete(True)  # 55

    highlighter = f"‍️"  # 56
    MR = highlighter if raw_text3 == 'Robin' else raw_text3  # 57

    await editable.edit("Now send the Thumb url/nEg » https://graph.org/file/ce1723991756e48c35aa1.jpg \n Or if don't want thumbnail send = no")  # 58
    input6 = message = await bot.listen(editable.chat.id)  # 59
    raw_text6 = input6.text.strip()  # 60
    await input6.delete(True)  # 61
    await editable.delete()  # 62

    thumb = raw_text6  # 63
    if thumb.startswith("http://") or thumb.startswith("https://"):  # 64
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")  # 65
        thumb = "thumb.jpg"  # 66
    else:
        thumb = "no"  # 67

    try:
        count = int(raw_text)  # 68
    except ValueError:
        await m.reply_text("Invalid count value provided.")  # 69
        return

    # Download and processing logic continues...
    
    await m.reply_text("**Magic Brewed😎**")  # 100

bot.run()  # 101
