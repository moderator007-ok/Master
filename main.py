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

# Import your configuration variables
from vars import API_ID, API_HASH, BOT_TOKEN

# Import your helper functions (e.g. for video downloads)
import core as helper

# Import the external fast_upload function from devgagantools library.
try:
    from devgagantools.spylib import fast_upload
except ImportError:
    from devgagantools.spylib import upload_file as fast_upload

# Set up logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telethon")

# Initialize the Telethon client
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# /start command
@bot.on(events.NewMessage(pattern=r'^/start'))
async def start_handler(event):
    await event.reply(
        f"<b>Hello {event.sender.first_name} 👋\n\n"
        "I am a bot that downloads links from your <b>.TXT</b> file and uploads them to Telegram. "
        "To use me, first send /upload and follow the steps. "
        "Send /stop to abort any ongoing task.</b>"
    )

# /stop command – this restarts the process
@bot.on(events.NewMessage(pattern=r'^/stop'))
async def stop_handler(event):
    await event.reply("**Stopped** 🚦")
    os.execl(sys.executable, sys.executable, *sys.argv)

# /upload command – interactive conversation using Telethon's conversation helper
@bot.on(events.NewMessage(pattern=r'^/upload'))
async def upload_handler(event):
    async with bot.conversation(event.chat_id) as conv:
        # Ask for the TXT file containing the links
        await conv.send_message("Send TXT file ⚡️")
        txt_msg = await conv.get_response()
        txt_path = await bot.download_media(txt_msg)
        try:
            with open(txt_path, "r") as f:
                content = f.read()
            # Split file into lines and then by "://"
            content = content.splitlines()
            links = [line.split("://", 1) for line in content if line.strip()]
            os.remove(txt_path)
        except Exception as e:
            await conv.send_message("**Invalid file input.**")
            os.remove(txt_path)
            return

        # Ask for password token if any
        await conv.send_message("Are there any password-protected links in this file? If yes, send the PW token. If not, type 'no'.")
        pw_msg = await conv.get_response()
        pw_token = pw_msg.text.strip()
        
        # Ask for starting link index
        await conv.send_message(f"**Total links found:** **{len(links)}**\n\nSend a number indicating from which link you want to start downloading (e.g. 1).")
        start_msg = await conv.get_response()
        try:
            count = int(start_msg.text.strip())
        except:
            count = 1

        # Ask for batch name
        await conv.send_message("Now send me your batch name:")
        batch_msg = await conv.get_response()
        batch_name = batch_msg.text.strip()
        
        # Ask for resolution
        await conv.send_message("Enter resolution (choose: 144, 240, 360, 480, 720, 1080):")
        res_msg = await conv.get_response()
        raw_res = res_msg.text.strip()
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
        
        # Ask for caption
        await conv.send_message("Now enter a caption for your uploaded file:")
        caption_msg = await conv.get_response()
        caption_input = caption_msg.text.strip()
        # For example, use a special highlighter if caption is exactly 'Robin'
        highlighter = "️ ⁪⁬⁮⁮⁮"
        caption = highlighter if caption_input == 'Robin' else caption_input
        
        # Ask for thumbnail URL (optional)
        await conv.send_message("Send the thumbnail URL (e.g. https://graph.org/file/ce1723991756e48c35aa1.jpg) or type 'no' for no thumbnail.")
        thumb_msg = await conv.get_response()
        thumb_input = thumb_msg.text.strip()
        await conv.send_message("Processing your links...")
        
        thumb = thumb_input
        if thumb.startswith("http://") or thumb.startswith("https://"):
            # Download thumbnail using a system call to wget (or implement your own downloader)
            subprocess.getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
            thumb = "thumb.jpg"
        else:
            thumb = "no"

        # Process each link starting from the given count (1-indexed)
        for i in range(count - 1, len(links)):
            # Reconstruct URL from the parts (this assumes the link split by "://")
            V = links[i][1].replace("file/d/", "uc?export=download&id=") \
                           .replace("www.youtube-nocookie.com/embed", "youtu.be") \
                           .replace("?modestbranding=1", "") \
                           .replace("/view?usp=sharing", "")
            url = "https://" + V

            # Special URL processing for certain hosts
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

            # Choose format strings based on whether the URL is from YouTube
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
                # Build captions for different file types
                cc = f'**{str(i+1).zfill(3)}**. {name1}{caption}.mkv\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                cc1 = f'**{str(i+1).zfill(3)}**. {name1}{caption}.pdf\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                if "drive" in url:
                    try:
                        # For drive links, use your helper.download() function
                        ka = await helper.download(url, file_name)
                        await conv.send_message("Uploading document...")
                        await bot.send_file(event.chat_id, file=ka, caption=cc1)
                        os.remove(ka)
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
                        await bot.send_file(event.chat_id, file=f'{file_name}.pdf', caption=cc1)
                        os.remove(f'{file_name}.pdf')
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                else:
                    await conv.send_message(f"**⥥ DOWNLOADING... »**\n\n**Name »** `{file_name}`\n**Quality »** {raw_res}\n\n**URL »** `{url}`")
                    # Download the video using your helper.download_video (which calls yt-dlp)
                    res_file = await helper.download_video(url, cmd, file_name)
                    # Use Telethon’s normal file upload: open file and call fast_upload from devgagantools
                    with open(res_file, "rb") as file_obj:
                        await conv.send_message("Uploading file...")
                        uploaded_file = await fast_upload(bot, file_obj)
                    await asyncio.sleep(1)
            except Exception as e:
                await conv.send_message(f"**Downloading Interrupted**\n{str(e)}\n**Name »** {file_name}\n**URL »** `{url}`")
                continue
        await conv.send_message("**Done Boss 😎**")

def main():
    print("Bot is running...")
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()
