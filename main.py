# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess

import core as helper
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN
from aiohttp import ClientSession
from pyromod import listen
from subprocess import getstatusoutput

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Import fast_upload from devgagantools.spylib.
try:
    from devgagantools.spylib import fast_upload
except ImportError:
    from devgagantools.spylib import upload_file as fast_upload

bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Monkey-patch the client with a _get_dc method, if it doesn't exist.
if not hasattr(bot, "_get_dc"):
    bot._get_dc = lambda: bot.session.dc_id  # Returns the data center ID

@bot.on_message(filters.command(["start"]))
async def start(bot: Client, m: Message):
    await m.reply_text(
        f"<b>Hello {m.from_user.mention} 👋\n\n"
        "I Am A Bot For Download Links From Your **.TXT** File And Then Upload That File On Telegram "
        "So Basically If You Want To Use Me First Send Me /upload Command And Then Follow Few Steps..\n\n"
        "Use /stop to stop any ongoing task.</b>"
    )

@bot.on_message(filters.command("stop"))
async def restart_handler(_, m: Message):
    await m.reply_text("**Stopped**🚦", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on_message(filters.command(["upload"]))
async def upload(bot: Client, m: Message):
    editable = await m.reply_text('𝕤ᴇɴᴅ ᴛxᴛ ғɪʟᴇ ⚡️')
    inp: Message = await bot.listen(editable.chat.id)
    x = await inp.download()
    await inp.delete(True)

    path = f"./downloads/{m.chat.id}"
    try:
        with open(x, "r") as f:
            content = f.read()
        content = content.split("\n")
        links = [i.split("://", 1) for i in content]
        os.remove(x)
    except:
        await m.reply_text("**Invalid file input.**")
        os.remove(x)
        return

    await editable.edit("Are there any password-protected links in this file? If yes, please send the PW token. If not, type 'no'.")
    inp_pw: Message = await bot.listen(editable.chat.id)
    pw_token = inp_pw.text.strip()
    await inp_pw.delete(True)
    
    await editable.edit(
        f"**𝕋ᴏᴛᴀʟ ʟɪɴᴋ𝕤 ғᴏᴜɴᴅ ᴀʀᴇ🔗🔗** **{len(links)}**\n\n"
        "**𝕊ᴇɴᴅ 𝔽ʀᴏᴍ ᴡʜᴇʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ɪɴɪᴛɪᴀʟ ɪ𝕤** **1**"
    )
    inp0: Message = await bot.listen(editable.chat.id)
    raw_text = inp0.text
    await inp0.delete(True)

    await editable.edit("**Now Please Send Me Your Batch Name**")
    inp1: Message = await bot.listen(editable.chat.id)
    raw_text0 = inp1.text
    await inp1.delete(True)
    
    await editable.edit("**𝔼ɴᴛᴇʀ ʀᴇ𝕤ᴏʟᴜᴛɪᴏɴ📸**\n144,240,360,480,720,1080 please choose quality")
    inp2: Message = await bot.listen(editable.chat.id)
    raw_text2 = inp2.text
    await inp2.delete(True)
    try:
        if raw_text2 == "144":
            res = "256x144"
        elif raw_text2 == "240":
            res = "426x240"
        elif raw_text2 == "360":
            res = "640x360"
        elif raw_text2 == "480":
            res = "854x480"
        elif raw_text2 == "720":
            res = "1280x720"
        elif raw_text2 == "1080":
            res = "1920x1080"
        else:
            res = "UN"
    except Exception:
        res = "UN"
    
    await editable.edit("Now Enter A Caption to add caption on your uploaded file")
    inp3: Message = await bot.listen(editable.chat.id)
    raw_text3 = inp3.text
    await inp3.delete(True)
    highlighter = f"️ ⁪⁬⁮⁮⁮"
    MR = highlighter if raw_text3 == 'Robin' else raw_text3
       
    await editable.edit(
        "Now send the Thumb url/nEg » https://graph.org/file/ce1723991756e48c35aa1.jpg \nOr if don't want thumbnail send = no"
    )
    inp6 = message = await bot.listen(editable.chat.id)
    raw_text6 = inp6.text
    await inp6.delete(True)
    await editable.delete()

    thumb = inp6.text
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    count = 1 if len(links) == 1 else int(raw_text)
    try:
        for i in range(count - 1, len(links)):
            V = links[i][1].replace("file/d/", "uc?export=download&id=") \
                           .replace("www.youtube-nocookie.com/embed", "youtu.be") \
                           .replace("?modestbranding=1", "") \
                           .replace("/view?usp=sharing", "")
            url = "https://" + V

            if "visionias" in url:
                async with ClientSession() as session:
                    async with session.get(url, headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Pragma': 'no-cache',
                        'Referer': 'http://www.visionias.in/',
                        'Sec-Fetch-Dest': 'iframe',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'cross-site',
                        'Upgrade-Insecure-Requests': '1',
                        'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36',
                        'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"',
                        'sec-ch-ua-mobile': '?1',
                        'sec-ch-ua-platform': '"Android"'
                    }) as resp:
                        text = await resp.text()
                        url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)

            elif 'videos.classplusapp' in url:
                api_url = "https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url=" + url
                url = requests.get(api_url, headers={
                    'x-access-token': 'eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJpZCI6MzgzNjkyMTIsIm9yZ0lkIjoyNjA1LCJ0eXBlIjoxLCJtb2JpbGUiOiI5MTcwODI3NzQyODkiLCJuYW1lIjoiQWNlIiwiZW1haWwiOm51bGwsImlzRmlyc3RMb2dpbiI6dHJ1ZSwiZGVmYXVsdExhbmd1YWdlIjpudWxsLCJjb3VudHJ5Q29kZSI6IklOIiwiaXNJbnRlcm5hdGlvbmFsIjowLCJpYXQiOjE2NDMyODE4NzcsImV4cCI6MTY0Mzg4NjY3N30.hM33P2ai6ivdzxPPfm01LAd4JWv-vnrSxGXqvCirCSpUfhhofpeqyeHPxtstXwe0"
                }).json()['url']

            elif '/master.mpd' in url:
                if "d1d34p8vz63oiq" in url or "sec1.pw.live" in url:
                    url = f"https://anonymouspwplayer-b99f57957198.herokuapp.com/pw?url={url}?token={pw_token}"
                else:
                    id = url.split("/")[-2]
                    url = "https://d26g5bnklkwsh4.cloudfront.net/" + id + "/master.m3u8"

            name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "") \
                               .replace("+", "").replace("#", "").replace("|", "") \
                               .replace("@", "").replace("*", "").replace(".", "") \
                               .replace("https", "").replace("http", "").strip()
            name = f'{str(count).zfill(3)}) {name1[:60]}'

            if "youtu" in url:
                ytf = f"b[height<={raw_text2}][ext=mp4]/bv[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"

            if "jw-prod" in url:
                cmd = (
                    f'yt-dlp --external-downloader aria2c '
                    f'--external-downloader-args "-x 16 -s 16 -k 1M '
                    f'--timeout=120 --connect-timeout=120 '
                    f'--max-download-limit=0 --max-overall-download-limit=0 '
                    f'--enable-http-pipelining=true --file-allocation=falloc" '
                    f'-o "{name}.mp4" "{url}"'
                )
            else:
                cmd = (
                    f'yt-dlp --external-downloader aria2c '
                    f'--external-downloader-args "-x 16 -s 16 -k 1M '
                    f'--timeout=120 --connect-timeout=120 '
                    f'--max-download-limit=0 --max-overall-download-limit=0 '
                    f'--enable-http-pipelining=true --file-allocation=falloc" '
                    f'-f "{ytf}" "{url}" -o "{name}.mp4"'
                )

            try:
                cc = f'**{str(count).zfill(3)}**. {name1}{MR}.mkv\n**Batch Name »** {raw_text0}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                cc1 = f'**{str(count).zfill(3)}**. {name1}{MR}.pdf\n**Batch Name »** {raw_text0}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                if "drive" in url:
                    try:
                        ka = await helper.download(url, name)
                        copy = await bot.send_document(chat_id=m.chat.id, document=ka, caption=cc1)
                        count += 1
                        os.remove(ka)
                        await asyncio.sleep(1)
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(e.x)
                        continue
                elif ".pdf" in url:
                    try:
                        cmd = (
                            f'yt-dlp --external-downloader aria2c '
                            f'--external-downloader-args "-x 16 -s 16 -k 1M '
                            f'--timeout=120 --connect-timeout=120 '
                            f'--max-download-limit=0 --max-overall-download-limit=0 '
                            f'--enable-http-pipelining=true --file-allocation=falloc" '
                            f'-o "{name}.pdf" "{url}"'
                        )
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)
                        count += 1
                        os.remove(f'{name}.pdf')
                        await asyncio.sleep(1)
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(e.x)
                        continue
                else:
                    Show = f"**⥥ 🄳🄾🅆🄽🄻🄾🄰🄳🄸🄽🄶⬇️⬇️... »**\n\n**📝Name »** `{name}\n❄Quality » {raw_text2}`\n\n**🔗URL »** `{url}`"
                    prog = await m.reply_text(Show)
                    res_file = await helper.download_video(url, cmd, name)
                    filename = res_file
                    await prog.delete(True)
                    # Open the downloaded file and pass it to fast_upload
                    with open(filename, "rb") as file_obj:
                        uploaded_file = await fast_upload(
                            client=bot,
                            file=file_obj
                        )
                    count += 1
                    await asyncio.sleep(1)
            except Exception as e:
                await m.reply_text(
                    f"**downloading Interupted **\n{str(e)}\n**Name** » {name}\n**Link** » `{url}`"
                )
                continue
    except Exception as e:
        await m.reply_text(e)
    await m.reply_text("**𝔻ᴏɴᴇ 𝔹ᴏ𝕤𝕤😎**")

bot.run()
