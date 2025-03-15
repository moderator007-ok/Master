import os
import re
import sys
import time
import asyncio
import requests
import subprocess
import logging
from telethon import TelegramClient, events
import aiohttp
from moviepy.editor import VideoFileClip  # to extract video metadata
from telethon.tl.types import DocumentAttributeVideo  # for video attributes

# Import configuration variables from your vars module
from vars import API_ID, API_HASH, BOT_TOKEN
import core as helper  # Assumes helper.download_video() and helper.download() exist

# Import external fast_upload function from devgagantools library
try:
    from devgagantools.spylib import fast_upload
except ImportError:
    from devgagantools.spylib import upload_file as fast_upload

# Set up logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telethon")

# Initialize the Telethon client
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Helper function: convert bytes to human-readable format
def human_readable(size, decimal_places=2):
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024:
            return f"{size:.{decimal_places}f}{unit}"
        size /= 1024
    return f"{size:.{decimal_places}f}PB"


# --------------------------------------------------
# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import math
from pyrogram.errors import FloodWait
from datetime import datetime, timedelta

class Timer:
    def __init__(self, time_between=5):
        self.start_time = time.time()
        self.time_between = time_between

    def can_send(self):
        if time.time() > (self.start_time + self.time_between):
            self.start_time = time.time()
            return True
        return False

def hrb(value, digits=2, delim="", postfix=""):
    """Return a human-readable file size."""
    if value is None:
        return None
    chosen_unit = "B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        if value > 1000:
            value /= 1024
            chosen_unit = unit
        else:
            break
    return f"{value:.{digits}f}" + delim + chosen_unit + postfix

def hrt(seconds, precision=0):
    """Return a human-readable time delta as a string."""
    pieces = []
    value = timedelta(seconds=seconds)
    if value.days:
        pieces.append(f"{value.days}d")
    seconds = value.seconds
    if seconds >= 3600:
        hours = int(seconds / 3600)
        pieces.append(f"{hours}h")
        seconds -= hours * 3600
    if seconds >= 60:
        minutes = int(seconds / 60)
        pieces.append(f"{minutes}m")
        seconds -= minutes * 60
    if seconds > 0 or not pieces:
        pieces.append(f"{seconds}s")
    if not precision:
        return "".join(pieces)
    return "".join(pieces[:precision])

timer = Timer()

async def progress_bar(current, total, reply, start):
    if timer.can_send():
        now = time.time()
        diff = now - start
        if diff < 1:
            return
        else:
            perc = f"{current * 100 / total:.1f}%"
            elapsed_time = round(diff)
            speed = current / elapsed_time
            remaining_bytes = total - current
            if speed > 0:
                eta_seconds = remaining_bytes / speed
                eta = hrt(eta_seconds, precision=1)
            else:
                eta = "-"
            sp = str(hrb(speed)) + "/s"
            tot = hrb(total)
            cur = hrb(current)
            bar_length = 11
            completed_length = int(current * bar_length / total)
            remaining_length = bar_length - completed_length
            progress_str = "▰" * completed_length + "▱" * remaining_length
            
            try:
                await reply.edit(
                    f'<b>\n ╭──⌯════🆄︎ᴘʟᴏᴀᴅɪɴɢ⬆️⬆️═════⌯──╮ \n'
                    f'├⚡ {progress_str}|﹝{perc}﹞ \n'
                    f'├🚀 Speed » {sp} \n'
                    f'├📟 Processed » {cur}\n'
                    f'├🧲 Size - ETA » {tot} - {eta} \n'
                    f'├🤖 By » TechMon\n'
                    f'╰─═══ ✪ TechMon ✪ ═══─╯\n</b>'
                )
            except FloodWait as e:
                time.sleep(e.x)
# --------------------------------------------------

@bot.on(events.NewMessage(pattern=r'^/start'))
async def start_handler(event):
    msg = await event.reply(
        f"<b>Hello {event.sender.first_name} 👋\n\n"
        "I am a bot that downloads links from your <b>.TXT</b> file and uploads them to Telegram. "
        "To use me, first send /upload and follow the steps. "
        "Send /stop to abort any ongoing task.</b>"
    )
    await asyncio.sleep(5)
    await bot.delete_messages(event.chat_id, msg.id)

@bot.on(events.NewMessage(pattern=r'^/stop'))
async def stop_handler(event):
    await event.reply("**Stopped** 🚦")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r'^/upload'))
async def upload_handler(event):
    async with bot.conversation(event.chat_id) as conv:
        # --- Step 1: Ask for TXT file ---
        q1 = await conv.send_message("Send TXT file ⚡️")
        txt_msg = await conv.get_response()
        await bot.delete_messages(event.chat_id, [q1.id, txt_msg.id])
        txt_path = await bot.download_media(txt_msg)
        try:
            with open(txt_path, "r") as f:
                content = f.read()
            content = content.splitlines()
            links = [line.split("://", 1) for line in content if line.strip()]
            os.remove(txt_path)
        except Exception as e:
            err_msg = await conv.send_message("**Invalid file input.**")
            await asyncio.sleep(3)
            await bot.delete_messages(event.chat_id, err_msg.id)
            os.remove(txt_path)
            return

        # --- Step 2: Ask for password token ---
        q2 = await conv.send_message("Are there any password‑protected links in this file? If yes, send the PW token. If not, type 'no'.")
        pw_msg = await conv.get_response()
        pw_token = pw_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q2.id, pw_msg.id])

        # --- Step 3: Ask for starting link index ---
        q3 = await conv.send_message(f"**Total links found:** **{len(links)}**\n\nSend a number indicating from which link you want to start downloading (e.g. 1).")
        start_msg = await conv.get_response()
        try:
            count = int(start_msg.text.strip())
        except:
            count = 1
        await bot.delete_messages(event.chat_id, [q3.id, start_msg.id])

        # --- Step 4: Ask for batch name ---
        q4 = await conv.send_message("Now send me your batch name:")
        batch_msg = await conv.get_response()
        batch_name = batch_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q4.id, batch_msg.id])

        # --- Step 5: Ask for resolution ---
        q5 = await conv.send_message("Enter resolution (choose: 144, 240, 360, 480, 720, 1080):")
        res_msg = await conv.get_response()
        raw_res = res_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q5.id, res_msg.id])
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
        q6 = await conv.send_message("Now enter a caption for your uploaded file:")
        caption_msg = await conv.get_response()
        caption_input = caption_msg.text.strip()
        highlighter = "️ ⁪⁬⁮⁮⁮"
        caption = highlighter if caption_input == 'Robin' else caption_input
        await bot.delete_messages(event.chat_id, [q6.id, caption_msg.id])

        # --- Step 7: Ask for thumbnail image ---
        q7 = await conv.send_message("Send a thumbnail image for this batch (or type 'no' to skip and let Telegram auto‑generate one):")
        thumb_msg = await conv.get_response()
        await bot.delete_messages(event.chat_id, [q7.id, thumb_msg.id])
        if thumb_msg.media:
            thumb_path = await bot.download_media(thumb_msg)
        else:
            thumb_path = None
            if thumb_msg.text.strip().lower() != "no":
                thumb_path = None
        # Use this thumbnail for every upload in the batch
        batch_thumb = thumb_path

        status_msg = await conv.send_message("Processing your links...")

        # --- Process each link ---
        for i in range(count - 1, len(links)):
            # Reconstruct URL
            V = links[i][1].replace("file/d/", "uc?export=download&id=") \
                           .replace("www.youtube-nocookie.com/embed", "youtu.be") \
                           .replace("?modestbranding=1", "") \
                           .replace("/view?usp=sharing", "")
            url = "https://" + V

            # Special URL processing
            if "visionias" in url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'User-Agent': 'Mozilla/5.0'
                    }) as resp:
                        text = await resp.text()
                        m = re.search(r"(https://.*?playlist\.m3u8.*?)\"", text)
                        if m:
                            url = m.group(1)
            elif 'videos.classplusapp' in url:
                api_url = "https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url=" + url
                url = requests.get(api_url, headers={'x-access-token': 'TOKEN'}).json()['url']
            elif '/master.mpd' in url:
                # Extract the unique ID from the URL.
                # Assumes the URL format is: https://<domain>/<unique_id>/master.mpd
                parts = url.split("/")
                unique_id = parts[3] if len(parts) >= 5 else None
                if not unique_id:
                    unique_id = "350b02d7-2abf-4643-b88f-4ba7811feacd"  # fallback
                url = f"https://madxapi-d0cbf6ac738c.herokuapp.com/{unique_id}/master.m3u8?token={pw_token}"

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
                cmd = (
                    f'yt-dlp --external-downloader aria2c '
                    f'--external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 '
                    f'--max-download-limit=0 --max-overall-download-limit=0 '
                    f'--enable-http-pipelining=true --file-allocation=falloc" '
                    f'-o "{file_name}.mp4" "{url}"'
                )
            else:
                cmd = (
                    f'yt-dlp --external-downloader aria2c '
                    f'--external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 '
                    f'--max-download-limit=0 --max-overall-download-limit=0 '
                    f'--enable-http-pipelining=true --file-allocation=falloc" '
                    f'-f "{ytf}" "{url}" -o "{file_name}.mp4"'
                )
            try:
                cc = f'**{str(i+1).zfill(3)}**. {name1}{caption}.mkv\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                cc1 = f'**{str(i+1).zfill(3)}**. {name1}{caption}.pdf\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                if "drive" in url:
                    try:
                        ka = await helper.download(url, file_name)
                        await conv.send_message("Uploading document...")
                        # Use Telethon-based document upload function
                        await telethon_send_doc(event, ka, cc1)
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                elif ".pdf" in url:
                    try:
                        cmd_pdf = (
                            f'yt-dlp --external-downloader aria2c '
                            f'--external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 '
                            f'--max-download-limit=0 --max-overall-download-limit=0 '
                            f'--enable-http-pipelining=true --file-allocation=falloc" '
                            f'-o "{file_name}.pdf" "{url}"'
                        )
                        download_cmd = f"{cmd_pdf} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        # Use Telethon-based document upload function
                        await telethon_send_doc(event, f'{file_name}.pdf', cc1)
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                else:
                    dl_msg = await conv.send_message(
                        f"**⥥ DOWNLOADING... »**\n\n**Name »** `{file_name}`\n**Quality »** {raw_res}\n\n**URL »** `{url}`"
                    )
                    res_file = await helper.download_video(url, cmd, file_name)
                    await bot.delete_messages(event.chat_id, dl_msg.id)

                    # --- Extract video metadata using MoviePy ---
                    clip = VideoFileClip(res_file)
                    duration_sec = int(clip.duration)
                    width, height = clip.size
                    clip.close()

                    # Create a progress message and record the start time
                    progress_message = await conv.send_message("Uploading file... 0%")
                    start_time = time.time()

                    # Define a wrapper callback that calls our progress_bar function
                    async def progress_callback_wrapper(current, total):
                        await progress_bar(current, total, progress_message, start_time)

                    # Use Telethon-based video upload function with our progress callback
                    await telethon_send_video(event, res_file, cc, thumb=batch_thumb, progress_callback=progress_callback_wrapper)
                    await asyncio.sleep(1)
            except Exception as e:
                await conv.send_message(f"**Downloading Interrupted**\n{str(e)}\n**Name »** {file_name}\n**URL »** `{url}`")
                continue
        await conv.send_message("**Done Boss 😎**")
        await bot.delete_messages(event.chat_id, status_msg.id)
        
        # If a thumbnail file was provided, delete it after the batch is done.
        if batch_thumb is not None and os.path.exists(batch_thumb):
            os.remove(batch_thumb)

# --- Telethon-based Uploading Functions ---

async def telethon_send_doc(event, file_path, caption, progress_callback=None):
    """
    Upload a document using Telethon's send_file.
    """
    message = await bot.send_file(
        event.chat_id,
        file=file_path,
        caption=caption,
        progress_callback=progress_callback
    )
    if os.path.exists(file_path):
        os.remove(file_path)
    return message

async def telethon_send_video(event, file_path, caption, thumb=None, progress_callback=None):
    """
    Upload a video using Telethon's send_file with streaming support.
    If no thumbnail is provided, generate one using ffmpeg.
    """
    # If no thumbnail provided, generate one from the video
    if not thumb or thumb.lower() == "no":
        thumb_path = f"{file_path}.jpg"
        subprocess.run(f'ffmpeg -i "{file_path}" -ss 00:00:12 -vframes 1 "{thumb_path}"', shell=True)
    else:
        thumb_path = thumb

    # Extract video metadata using MoviePy
    clip = VideoFileClip(file_path)
    duration_sec = int(clip.duration)
    width, height = clip.size
    clip.close()

    # Create video attributes for proper metadata display
    attributes = [DocumentAttributeVideo(duration=duration_sec, width=width, height=height, supports_streaming=True)]

    message = await bot.send_file(
        event.chat_id,
        file=file_path,
        caption=caption,
        supports_streaming=True,
        thumb=thumb_path,
        progress_callback=progress_callback,
        attributes=attributes
    )
    if os.path.exists(file_path):
        os.remove(file_path)
    # Remove generated thumbnail if it was auto‑created
    if (not thumb or thumb.lower() == "no") and os.path.exists(thumb_path):
        os.remove(thumb_path)
    return message

def main():
    print("Bot is running...")
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()
