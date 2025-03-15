import os
import re
import sys
import time
import asyncio
import requests
import subprocess
import logging
import aiohttp
from moviepy.editor import VideoFileClip  # for extracting video metadata
from pyrogram import Client, filters
from pyromod import listen  # provides an easy "conversation" interface

# Import configuration variables from your vars module
from vars import API_ID, API_HASH, BOT_TOKEN
import core as helper  # Assumes helper.download_video() and helper.download() exist

# Set up logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pyrogram")

# Initialize the Pyrogram client
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Helper: convert bytes to human-readable format
def human_readable(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.{decimal_places}f}{unit}"
        size /= 1024
    return f"{size:.{decimal_places}f}PB"

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    msg = await message.reply(
        f"<b>Hello {message.from_user.first_name} 👋\n\n"
        "I am a bot that downloads links from your <b>.TXT</b> file and uploads them to Telegram. "
        "To use me, first send /upload and follow the steps. "
        "Send /stop to abort any ongoing task.</b>"
    )
    await asyncio.sleep(5)
    await client.delete_messages(message.chat.id, msg.message_id)

@app.on_message(filters.command("stop"))
async def stop_handler(client, message):
    await message.reply("**Stopped** 🚦")
    # Restart the script (or exit)
    os.execl(sys.executable, sys.executable, *sys.argv)

@app.on_message(filters.command("upload"))
async def upload_handler(client, message):
    chat_id = message.chat.id

    # --- Step 1: Ask for TXT file ---
    q1 = await message.reply("Send TXT file ⚡️")
    txt_msg = await client.listen(chat_id)
    await client.delete_messages(chat_id, [q1.message_id, txt_msg.message_id])
    txt_path = await txt_msg.download()
    try:
        with open(txt_path, "r") as f:
            content = f.read()
        content = content.splitlines()
        links = [line.split("://", 1) for line in content if line.strip()]
        os.remove(txt_path)
    except Exception as e:
        err_msg = await message.reply("**Invalid file input.**")
        await asyncio.sleep(3)
        await client.delete_messages(chat_id, err_msg.message_id)
        os.remove(txt_path)
        return

    # --- Step 2: Ask for password token ---
    q2 = await message.reply(
        "Are there any password-protected links in this file? If yes, send the PW token. If not, type 'no'."
    )
    pw_msg = await client.listen(chat_id)
    pw_token = pw_msg.text.strip()
    await client.delete_messages(chat_id, [q2.message_id, pw_msg.message_id])

    # --- Step 3: Ask for starting link index ---
    q3 = await message.reply(
        f"**Total links found:** **{len(links)}**\n\nSend a number indicating from which link you want to start downloading (e.g. 1)."
    )
    start_msg = await client.listen(chat_id)
    try:
        count = int(start_msg.text.strip())
    except:
        count = 1
    await client.delete_messages(chat_id, [q3.message_id, start_msg.message_id])

    # --- Step 4: Ask for batch name ---
    q4 = await message.reply("Now send me your batch name:")
    batch_msg = await client.listen(chat_id)
    batch_name = batch_msg.text.strip()
    await client.delete_messages(chat_id, [q4.message_id, batch_msg.message_id])

    # --- Step 5: Ask for resolution ---
    q5 = await message.reply("Enter resolution (choose: 144, 240, 360, 480, 720, 1080):")
    res_msg = await client.listen(chat_id)
    raw_res = res_msg.text.strip()
    await client.delete_messages(chat_id, [q5.message_id, res_msg.message_id])
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
    q6 = await message.reply("Now enter a caption for your uploaded file:")
    caption_msg = await client.listen(chat_id)
    caption_input = caption_msg.text.strip()
    highlighter = "️ ⁪⁬⁮⁮⁮"
    caption = highlighter if caption_input == 'Robin' else caption_input
    await client.delete_messages(chat_id, [q6.message_id, caption_msg.message_id])

    # --- Skip Thumbnail Step ---
    status_msg = await message.reply("Processing your links...")

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
                    await message.reply("Uploading document...")
                    await client.send_document(chat_id, document=ka, caption=cc1)
                    os.remove(ka)
                    await asyncio.sleep(1)
                except Exception as e:
                    await message.reply(str(e))
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
                    await client.send_document(chat_id, document=f'{file_name}.pdf', caption=cc1)
                    os.remove(f'{file_name}.pdf')
                    await asyncio.sleep(1)
                except Exception as e:
                    await message.reply(str(e))
                    await asyncio.sleep(5)
                    continue
            else:
                dl_msg = await message.reply(
                    f"**⥥ DOWNLOADING... »**\n\n**Name »** `{file_name}`\n**Quality »** {raw_res}\n\n**URL »** `{url}`"
                )
                res_file = await helper.download_video(url, cmd, file_name)
                await client.delete_messages(chat_id, dl_msg.message_id)

                # --- Extract video metadata using MoviePy ---
                clip = VideoFileClip(res_file)
                duration = int(clip.duration)
                width, height = clip.size
                clip.close()

                total_size = os.path.getsize(res_file)
                last_percent = 0
                last_time = time.time()
                last_bytes = 0

                progress_msg = await message.reply("Uploading file... 0%")

                async def progress_callback(current, total):
                    nonlocal last_percent, last_time, last_bytes
                    percent = (current / total) * 100
                    if percent - last_percent >= 5 or current == total:
                        now = time.time()
                        dt = now - last_time
                        speed = (current - last_bytes) / dt if dt > 0 else 0
                        speed_str = human_readable(speed) + "/s"
                        text = f"Uploading: {percent:.2f}% ({human_readable(current)}/{human_readable(total)}) at {speed_str}"
                        try:
                            await client.edit_message_text(chat_id, progress_msg.message_id, text)
                        except Exception as ex:
                            log.error(f"Progress update failed: {ex}")
                        last_percent = percent
                        last_time = now
                        last_bytes = current

                # --- Upload video using send_video with progress callback ---
                await client.send_video(
                    chat_id,
                    video=res_file,
                    caption=cc,
                    duration=duration,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    progress=progress_callback
                )
                await client.delete_messages(chat_id, progress_msg.message_id)
                os.remove(res_file)
                await asyncio.sleep(1)
        except Exception as e:
            await message.reply(
                f"**Downloading Interrupted**\n{str(e)}\n**Name »** {file_name}\n**URL »** `{url}`"
            )
            continue
    await message.reply("**Done Boss 😎**")
    await client.delete_messages(chat_id, status_msg.message_id)

def main():
    print("Bot is running...")
    app.run()

if __name__ == '__main__':
    main()
