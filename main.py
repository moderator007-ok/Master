"""
Don't Remove Credit Tg - @VJ_Botz
Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
Ask Doubt on telegram @KingVJ01
"""

import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess
import html
import logging

# External modules (assumed to be available in your environment)
import core as helper
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN, BOT_TOKEN2
from aiohttp import ClientSession
from pyromod import listen
from subprocess import getstatusoutput

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.enums import ParseMode

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

###################################################
#           Uploader Bot (Primary Bot)            #
###################################################

uploader_bot = Client(
    "uploader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@uploader_bot.on_message(filters.command(["start"]))
async def start(bot: Client, m: Message):
    await m.reply_text(
        f"<b>Hello {m.from_user.mention} 👋\n\nI Am A Bot For Download Links From Your <code>.TXT</code> File And Then Upload That File On Telegram. "
        f"Basically, if you want to use me, first send me the /upload command and follow a few steps.\n\nUse /stop to stop any ongoing task.</b>"
    )

@uploader_bot.on_message(filters.command("stop"))
async def restart_handler(_, m: Message):
    await m.reply_text("**Stopped** 🚦", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

@uploader_bot.on_message(filters.command(["upload"]))
async def upload(bot: Client, m: Message):
    editable = await m.reply_text('𝕤ᴇɴᴅ ᴛxᴛ ғɪʟᴇ ⚡️')
    input_msg: Message = await bot.listen(editable.chat.id)
    x = await input_msg.download()
    await input_msg.delete(True)

    path = f"./downloads/{m.chat.id}"
    try:
        with open(x, "r") as f:
            content = f.read()
        content = content.split("\n")
        links = []
        for i in content:
            links.append(i.split("://", 1))
        os.remove(x)
    except Exception as e:
        await m.reply_text("**Invalid file input.**")
        os.remove(x)
        return

    await editable.edit(f"**𝕋ᴏᴛᴀʟ ʟɪɴᴋ𝕤 ғᴏᴜɴᴅ: {len(links)}**\n\n**𝕊ᴇɴᴅ 𝔽ʀᴏᴍ ᴡʜᴇʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ. Initial is 1.**")
    input0: Message = await bot.listen(editable.chat.id)
    raw_text = input0.text
    await input0.delete(True)

    await editable.edit("**Now Please Send Me Your Batch Name**")
    input1: Message = await bot.listen(editable.chat.id)
    raw_text0 = input1.text
    await input1.delete(True)
    
    await editable.edit("**𝔼ɴᴛᴇʀ ʀᴇ𝕤ᴏʟᴜᴛɪᴏɴ 📸**\n144,240,360,480,720,1080 please choose quality")
    input2: Message = await bot.listen(editable.chat.id)
    raw_text2 = input2.text
    await input2.delete(True)
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
    
    await editable.edit("Now Enter A Caption to add on your uploaded file")
    input3: Message = await bot.listen(editable.chat.id)
    raw_text3 = input3.text
    await input3.delete(True)
    highlighter = f"️ ⁪⁬⁮⁮⁮"
    MR = highlighter if raw_text3 == 'Robin' else raw_text3
   
    await editable.edit("Now send the Thumb url/nEg » https://graph.org/file/ce1723991756e48c35aa1.jpg \nOr if you don't want a thumbnail send = no")
    input6: Message = await bot.listen(editable.chat.id)
    raw_text6 = input6.text
    await input6.delete(True)
    await editable.delete()

    thumb = input6.text
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    count = 1 if len(links) == 1 else int(raw_text)
    try:
        for i in range(count - 1, len(links)):
            V = links[i][1].replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","")
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
                        'sec-ch-ua-platform': '"Android"',
                    }) as resp:
                        text = await resp.text()
                        url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)
            elif 'videos.classplusapp' in url:
                url = requests.get(f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url={url}', headers={'x-access-token': 'YOUR_TOKEN_HERE'}).json()['url']
            elif '/master.mpd' in url:
                id =  url.split("/")[-2]
                url =  "https://d26g5bnklkwsh4.cloudfront.net/" + id + "/master.m3u8"

            name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
            name = f'{str(count).zfill(3)}) {name1[:60]}'

            if "youtu" in url:
                ytf = f"b[height<={raw_text2}][ext=mp4]/bv[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"

            if "jw-prod" in url:
                cmd = f'yt-dlp -o "{name}.mp4" "{url}"'
            else:
                cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'

            try:  
                cc = f'**{str(count).zfill(3)}**. {name1}{MR}.mkv\n**Batch Name »** {raw_text0}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                cc1 = f'**{str(count).zfill(3)}**. {name1}{MR}.pdf\n**Batch Name »** {raw_text0}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                if "drive" in url:
                    try:
                        ka = await helper.download(url, name)
                        copy = await uploader_bot.send_document(chat_id=m.chat.id, document=ka, caption=cc1)
                        count += 1
                        os.remove(ka)
                        time.sleep(1)
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        continue
                elif ".pdf" in url:
                    try:
                        cmd = f'yt-dlp -o "{name}.pdf" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await uploader_bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)
                        count += 1
                        os.remove(f'{name}.pdf')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        continue
                else:
                    Show = f"**⥥ 🄳🄾🆆🄽🄻🄾🄰🄳🄸🄽🄶⬇️⬇️... »**\n\n**📝Name »** `{name}\n❄Quality » {raw_text2}`\n\n**🔗URL »** `{url}`"
                    prog = await m.reply_text(Show)
                    res_file = await helper.download_video(url, cmd, name)
                    filename = res_file
                    await prog.delete(True)
                    await helper.send_vid(uploader_bot, m, cc, filename, thumb, name, prog)
                    count += 1
                    time.sleep(1)
            except Exception as e:
                await m.reply_text(
                    f"**Downloading Interrupted**\n{str(e)}\n**Name** » {name}\n**Link** » `{url}`"
                )
                continue
    except Exception as e:
        await m.reply_text(e)
    await m.reply_text("**𝔻ᴏɴᴇ 𝔹ᴏ𝕤𝕤😎**")

###################################################
#           Caption Changing Bot (Secondary)      #
###################################################

caption_bot = Client(
    "caption_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN2
)

# Dictionaries for caption bot
user_files_caption = {}    # For Type 1 captions
user_files2_caption = {}   # For Type 2 captions

@caption_bot.on_message(filters.command("input") & filters.private)
async def start_input_caption(client, message):
    chat_id = message.chat.id
    user_files_caption[chat_id] = []
    await message.reply_text("✅ [CAPTION BOT] Send files (videos or PDFs) for caption change.")

@caption_bot.on_message(filters.command("input2") & filters.private)
async def start_input2_caption(client, message):
    chat_id = message.chat.id
    user_files2_caption[chat_id] = []
    await message.reply_text("✅ [CAPTION BOT] Send files for Leo ♌ Das and TIGER replacement.")

@caption_bot.on_message(filters.private & (filters.document | filters.video))
async def store_files_caption(client, message):
    chat_id = message.chat.id
    if chat_id in user_files_caption:
        user_files_caption[chat_id].append(message)
    elif chat_id in user_files2_caption:
        user_files2_caption[chat_id].append(message)

def extract_new_caption(caption: str) -> str:
    """
    Type 1 caption extraction:
    Extracts file ID (from "Lᴇᴄ ɪᴅ" or "Pᴅғ ɪᴅ"),
    title (from "Tɪᴛᴛʟᴇ"),
    and batch name (from up to 3 non-empty lines after the title, removing any underscore part).
    Returns a formatted HTML caption.
    """
    if not caption:
        return None
    lines = [line.strip() for line in caption.strip().split("\n") if line.strip()]
    file_id, title, batch_name = None, None, None
    for line in lines:
        if "Lᴇᴄ ɪᴅ" in line or "Pᴅғ ɪᴅ" in line:
            parts = line.split("»")
            if len(parts) > 1:
                file_id = parts[1].strip()
            break
    title_index = None
    for i, line in enumerate(lines):
        if "Tɪᴛᴛʟᴇ" in line:
            parts = line.split("»")
            if len(parts) > 1:
                title = parts[1].strip()
            title_index = i
            break
    if title_index is not None:
        for j in range(title_index + 1, min(title_index + 4, len(lines))):
            candidate = lines[j]
            if candidate:
                if "_" in candidate:
                    candidate = candidate.split("_")[0].strip()
                batch_name = candidate
                break
    if not file_id or not title or not batch_name:
        logger.warning("⚠️ [CAPTION BOT] Formatting issue detected!")
        logger.info(f"Extracted: file_id={file_id}, title={title}, batch_name={batch_name}")
        return None
    file_id_html = html.escape(file_id)
    title_html = html.escape(title)
    batch_name_html = html.escape(batch_name)
    return (
        f"<b>{file_id_html}.</b> {title_html}\n\n"
        f"<b>Batch Name »</b> {batch_name_html}\n\n"
        f"<b>Downloaded By :</b> TechMon ❤️‍🔥 @TechMonUPSC_2"
    )

def extract_new_caption2(caption: str) -> str:
    """
    Type 2 caption extraction:
    Replaces 'Leo ♌ Das' with 'X' and 'TIGER { Fearless Captain }' with 'TechMon ❤️‍🔥 @TechMonUPSC_2'.
    Expects the first line to contain "fileID. Title" and the second line to contain "Batch Name : ..." .
    """
    if not caption:
        return None
    lines = [line.strip() for line in caption.strip().split("\n") if line.strip()]
    file_id, title, batch_name = None, None, None
    if len(lines) >= 1:
        parts = lines[0].split(".", 1)
        if len(parts) == 2:
            file_id = parts[0].strip()
            title = parts[1].strip()
    if len(lines) >= 2:
        batch_name = lines[1].replace("Batch Name :", "").strip()
    if title:
        title = title.replace("Leo ♌ Das", "X")
    if not file_id or not title or not batch_name:
        logger.warning("⚠️ [CAPTION BOT] Formatting issue detected in type 2!")
        return None
    file_id_html = html.escape(file_id)
    title_html = html.escape(title)
    batch_name_html = html.escape(batch_name)
    return (
        f"<b>{file_id_html}.</b> {title_html}\n\n"
        f"<b>Batch Name »</b> {batch_name_html}\n\n"
        f"<b>Downloaded By :</b> TechMon ❤️‍🔥 @TechMonUPSC_2"
    )

@caption_bot.on_message(filters.command("change") & filters.private)
async def change_caption_caption(client, message):
    chat_id = message.chat.id
    if chat_id in user_files_caption and user_files_caption[chat_id]:
        for msg in user_files_caption[chat_id]:
            new_caption = extract_new_caption(msg.caption)
            if new_caption:
                if msg.document:
                    await client.send_document(chat_id, msg.document.file_id, caption=new_caption, parse_mode=ParseMode.HTML)
                elif msg.video:
                    await client.send_video(chat_id, msg.video.file_id, caption=new_caption, parse_mode=ParseMode.HTML)
        user_files_caption[chat_id] = []
    if chat_id in user_files2_caption and user_files2_caption[chat_id]:
        for msg in user_files2_caption[chat_id]:
            new_caption = extract_new_caption2(msg.caption)
            if new_caption:
                if msg.document:
                    await client.send_document(chat_id, msg.document.file_id, caption=new_caption, parse_mode=ParseMode.HTML)
                elif msg.video:
                    await client.send_video(chat_id, msg.video.file_id, caption=new_caption, parse_mode=ParseMode.HTML)
        user_files2_caption[chat_id] = []
    await message.reply_text("✅ [CAPTION BOT] All files have been sent with the new captions.")

###################################################
#         Running Both Bots Concurrently          #
###################################################

async def main():
    await asyncio.gather(uploader_bot.start(), caption_bot.start())
    print("Both bots have started.")
    await asyncio.gather(uploader_bot.idle(), caption_bot.idle())
    await asyncio.gather(uploader_bot.stop(), caption_bot.stop())

if __name__ == "__main__":
    asyncio.run(main())
