import os
import re
import sys
import time
import asyncio
import requests
import subprocess
import logging
import aiohttp
from pyrogram import Client, filters
from pyromod import listen  # Provides an easy "conversation" interface
from subprocess import getstatusoutput

# Attempt to import ConnectionTcpFull for a faster TCP connection.
try:
    from pyrogram.connection import ConnectionTcpFull
    custom_connection = ConnectionTcpFull
except ImportError:
    logging.warning("ConnectionTcpFull not found; falling back to default connection.")
    custom_connection = None

# Import configuration variables from your vars module
from vars import API_ID, API_HASH, BOT_TOKEN
import core as helper  # Assumes helper.download_video() and helper.download() exist

# Set up logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pyrogram")

# Build client keyword arguments; include custom connection if available.
client_kwargs = {
    "api_id": API_ID,
    "api_hash": API_HASH,
    "bot_token": BOT_TOKEN,
}
if custom_connection is not None:
    client_kwargs["connection"] = custom_connection

bot = Client("bot", **client_kwargs)


@bot.on_message(filters.command(["start"]))
async def start_handler(bot: Client, m):
    await m.reply_text(
        f"<b>Hello {m.from_user.mention} 👋\n\n"
        "I Am A Bot For Download Links From Your <b>.TXT</b> File And Then Upload That File On Telegram. "
        "So if you want to use me, first send me /upload command and then follow few steps.\n\n"
        "Use /stop to stop any ongoing task.</b>"
    )


@bot.on_message(filters.command("stop"))
async def stop_handler(bot: Client, m):
    await m.reply_text("**Stopped** 🚦")
    # Restart the script (or exit)
    os.execl(sys.executable, sys.executable, *sys.argv)


@bot.on_message(filters.command(["upload"]))
async def upload_handler(bot: Client, m):
    chat_id = m.chat.id

    # --- Step 1: Ask for TXT file ---
    editable = await m.reply_text('𝕤ᴇɴᴅ ᴛxᴛ ғɪʟᴇ ⚡️')
    input_msg = await bot.listen(editable.chat.id)
    txt_path = await input_msg.download()
    await input_msg.delete(True)

    try:
        with open(txt_path, "r") as f:
            content = f.read()
        content = content.splitlines()
        links = [line.split("://", 1) for line in content if line.strip()]
        os.remove(txt_path)
    except Exception:
        await m.reply_text("**Invalid file input.**")
        os.remove(txt_path)
        return

    # --- Step 2: Ask for PW token ---
    q2 = await m.reply_text(
        "Are there any password-protected links in this file? If yes, send the PW token. If not, type 'no'."
    )
    pw_msg = await bot.listen(editable.chat.id)
    pw_token = pw_msg.text.strip()
    await bot.delete_messages(chat_id, [q2.id, pw_msg.id])

    # --- Step 3: Ask for starting link index ---
    q3 = await m.reply_text(
        f"**Total links found:** **{len(links)}**\n\nSend a number indicating from which link you want to start downloading (e.g. 1)."
    )
    start_msg = await bot.listen(editable.chat.id)
    try:
        start_index = int(start_msg.text.strip())
    except Exception:
        start_index = 1
    await bot.delete_messages(chat_id, [q3.id, start_msg.id])

    # --- Step 4: Ask for batch name ---
    q4 = await m.reply_text("Now send me your batch name:")
    batch_msg = await bot.listen(editable.chat.id)
    batch_name = batch_msg.text.strip()
    await bot.delete_messages(chat_id, [q4.id, batch_msg.id])

    # --- Step 5: Ask for resolution ---
    q5 = await m.reply_text("Enter resolution (choose: 144, 240, 360, 480, 720, 1080):")
    res_msg = await bot.listen(editable.chat.id)
    raw_res = res_msg.text.strip()
    await bot.delete_messages(chat_id, [q5.id, res_msg.id])
    if raw_res == "144":
        res = "256x144"
    elif raw_res == "240":
        res = "426x240"
    elif raw_res == "360":
        res = "640x360"
    elif raw_res == "480":
        res = "854x480"
    elif raw_res == "720":
        res = "1280x720"
    elif raw_res == "1080":
        res = "1920x1080"
    else:
        res = "UN"

    # --- Step 6: Ask for caption ---
    q6 = await m.reply_text("Now enter a caption for your uploaded file:")
    caption_msg = await bot.listen(editable.chat.id)
    caption_input = caption_msg.text.strip()
    highlighter = "️ ⁪⁬⁮⁮⁮"
    caption = highlighter if caption_input == 'Robin' else caption_input
    await bot.delete_messages(chat_id, [q6.id, caption_msg.id])

    # --- Step 7: Ask for thumbnail URL ---
    await m.reply_text("Now send the Thumb URL\nEg: https://graph.org/file/ce1723991756e48c35aa1.jpg\nOr if you don't want a thumbnail, send = no")
    input6 = await bot.listen(editable.chat.id)
    thumb_input = input6.text.strip()
    await input6.delete(True)
    await editable.delete()

    thumb = thumb_input
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = None

    # --- Processing Links ---
    # Set the counter based on starting index
    counter = start_index

    status_msg = await m.reply_text("Processing your links...")

    try:
        for i in range(start_index - 1, len(links)):
            # Reconstruct URL
            V = links[i][1].replace("file/d/", "uc?export=download&id=") \
                           .replace("www.youtube-nocookie.com/embed", "youtu.be") \
                           .replace("?modestbranding=1", "") \
                           .replace("/view?usp=sharing", "")
            url = "https://" + V

            # Special URL processing
            if "visionias" in url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers={
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                            'User-Agent': 'Mozilla/5.0'
                        }
                    ) as resp:
                        text = await resp.text()
                        m_obj = re.search(r"(https://.*?playlist\.m3u8.*?)\"", text)
                        if m_obj:
                            url = m_obj.group(1)
            elif 'videos.classplusapp' in url:
                api_url = f"https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url={url}"
                url = requests.get(api_url, headers={'x-access-token': 'TOKEN'}).json()['url']
            elif '/master.mpd' in url:
                if "d1d34p8vz63oiq" in url or "sec1.pw.live" in url:
                    url = f"https://anonymouspwplayer-b99f57957198.herokuapp.com/pw?url={url}?token={pw_token}"
                else:
                    id_part = url.split("/")[-2]
                    url = "https://d26g5bnklkwsh4.cloudfront.net/" + id_part + "/master.m3u8"

            name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "") \
                               .replace("+", "").replace("#", "").replace("|", "") \
                               .replace("@", "").replace("*", "").replace(".", "") \
                               .replace("https", "").replace("http", "").strip()
            file_name = f'{str(i+1).zfill(3)}) {name1[:60]}'
            if "youtu" in url:
                ytf = f"b[height<={raw_res}][ext=mp4]/bv[height<={raw_res}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={raw_res}]/bv[height<={raw_res}]+ba/b/bv+ba"

            if "jw-prod" in url:
                cmd = f'yt-dlp -o "{file_name}.mp4" "{url}"'
            else:
                cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{file_name}.mp4"'

            try:  
                cc = f'**[📽️] Vid_ID:** {str(i+1).zfill(3)}. {name1}{caption}.mkv\n**Batch Name »** {raw_text0}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                cc1 = f'**[📁] Pdf_ID:** {str(i+1).zfill(3)}. {name1}{caption}.pdf\n**Batch Name »** {raw_text0}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                if "drive" in url:
                    try:
                        ka = await helper.download(url, file_name)
                        await m.reply_text("Uploading document...")
                        await bot.send_document(chat_id=m.chat.id, document=ka, caption=cc1)
                        counter += 1
                        os.remove(ka)
                        await asyncio.sleep(1)
                    except Exception as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(5)
                        continue
                elif ".pdf" in url:
                    try:
                        cmd_pdf = f'yt-dlp -o "{file_name}.pdf" "{url}"'
                        download_cmd = f"{cmd_pdf} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        await bot.send_document(chat_id=m.chat.id, document=f'{file_name}.pdf', caption=cc1)
                        counter += 1
                        os.remove(f'{file_name}.pdf')
                        await asyncio.sleep(1)
                    except Exception as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(5)
                        continue
                else:
                    Show = f"**⥥ DOWNLOADING... »**\n\n**Name »** `{file_name}`\n**Quality »** {raw_res}\n\n**URL »** `{url}`"
                    prog = await m.reply_text(Show)
                    res_file = await helper.download_video(url, cmd, file_name)
                    await bot.delete_messages(m.chat.id, prog.id)
                    # Use helper.send_vid (your working upload method)
                    await helper.send_vid(bot, m, cc, res_file, thumb, file_name, prog)
                    counter += 1
                    await asyncio.sleep(1)
            except Exception as e:
                await m.reply_text(
                    f"**Downloading Interrupted**\n{str(e)}\n**Name »** {file_name}\n**URL »** `{url}`"
                )
                continue
    except Exception as e:
        await m.reply_text(str(e))
    await m.reply_text("**Done Boss 😎**")
    await bot.delete_messages(m.chat.id, status_msg.id)

def main():
    print("Bot is running...")
    bot.run()

if __name__ == '__main__':
    main()
