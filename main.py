import os
import re
import sys
import time
import asyncio
import requests
import subprocess
import logging
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo  # for video attributes
from moviepy.editor import VideoFileClip  # to extract video metadata
from telethon.errors import FloodWait

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


def human_readable(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.{decimal_places}f}{unit}"
        size /= 1024
    return f"{size:.{decimal_places}f}PB"


def generate_thumbnail(video_file, thumb_output="generated_thumb.jpg", time_stamp="00:00:01"):
    cmd = ["ffmpeg", "-y", "-i", video_file, "-ss", time_stamp, "-vframes", "1", thumb_output]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0 and os.path.exists(thumb_output):
        return thumb_output
    return None


def get_video_metadata(video_file):
    clip = VideoFileClip(video_file)
    duration = int(clip.duration)
    width, height = clip.size
    clip.close()
    return duration, width, height


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
        # Step 1: Ask for TXT file
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
        except Exception:
            err_msg = await conv.send_message("**Invalid file input.**")
            await asyncio.sleep(3)
            await bot.delete_messages(event.chat_id, err_msg.id)
            os.remove(txt_path)
            return

        # Step 2: Ask for PW token
        q2 = await conv.send_message(
            "Are there any password-protected links in this file? If yes, send the PW token. If not, type 'no'."
        )
        pw_msg = await conv.get_response()
        pw_token = pw_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q2.id, pw_msg.id])

        # Step 3: Ask for starting link index
        q3 = await conv.send_message(
            f"**Total links found:** **{len(links)}**\n\nSend a number indicating from which link you want to start downloading (e.g. 1)."
        )
        start_msg = await conv.get_response()
        try:
            start_index = int(start_msg.text.strip())
        except:
            start_index = 1
        await bot.delete_messages(event.chat_id, [q3.id, start_msg.id])

        # Step 4: Ask for batch name
        q4 = await conv.send_message("Now send me your batch name:")
        batch_msg = await conv.get_response()
        batch_name = batch_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q4.id, batch_msg.id])

        # Step 5: Ask for resolution
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

        # Step 6: Ask for caption
        q6 = await conv.send_message("Now enter a caption for your uploaded file:")
        caption_msg = await conv.get_response()
        caption_input = caption_msg.text.strip()
        highlighter = "️ ⁪⁬⁮⁮⁮"
        caption = highlighter if caption_input == 'Robin' else caption_input
        await bot.delete_messages(event.chat_id, [q6.id, caption_msg.id])

        # Step 7: Ask for thumbnail image
        q7 = await conv.send_message("Send a thumbnail image for this batch (or type 'no' to skip and let Telegram auto‑generate one):")
        thumb_msg = await conv.get_response()
        await bot.delete_messages(event.chat_id, [q7.id, thumb_msg.id])
        if thumb_msg.media:
            batch_thumb = await bot.download_media(thumb_msg)
        else:
            batch_thumb = None

        status_msg = await conv.send_message("Processing your links...")

        # Process each link
        counter = start_index
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
                    async with session.get(url, headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'User-Agent': 'Mozilla/5.0'
                    }) as resp:
                        text = await resp.text()
                        m_obj = re.search(r"(https://.*?playlist\.m3u8.*?)\"", text)
                        if m_obj:
                            url = m_obj.group(1)
            elif 'videos.classplusapp' in url:
                api_url = "https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url=" + url
                url = requests.get(api_url, headers={'x-access-token': 'TOKEN'}).json()['url']
            elif '/master.mpd' in url:
                if "d1d34p8vz63oiq.cloudfront.net" in url:
                    parts = url.split("/")
                    extracted_id = parts[3] if len(parts) > 3 else None
                    if extracted_id:
                        url = f"https://madxapi-d0cbf6ac738c.herokuapp.com/{extracted_id}/master.m3u8?token={pw_token}"
                    else:
                        id_part = url.split("/")[-2]
                        url = "https://d26g5bnklkwsh4.cloudfront.net/" + id_part + "/master.m3u8"
                elif "sec1.pw.live" in url:
                    id_part = url.split("/")[-2]
                    url = f"https://madxapi-d0cbf6ac738c.herokuapp.com/{id_part}/master.m3u8?token={pw_token}"
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
                cc = f'**[📽️] Vid_ID:** {str(i+1).zfill(3)}. {name1}{caption}.mkv\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                cc1 = f'**[📁] Pdf_ID:** {str(i+1).zfill(3)}. {name1}{caption}.pdf\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                if "drive" in url:
                    try:
                        ka = await helper.download(url, file_name)
                        await conv.send_message("Uploading document...")
                        await bot.send_file(event.chat_id, file=ka, caption=cc1)
                        counter += 1
                        os.remove(ka)
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                elif ".pdf" in url:
                    try:
                        cmd_pdf = f'yt-dlp -o "{file_name}.pdf" "{url}"'
                        download_cmd = f"{cmd_pdf} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        await bot.send_file(event.chat_id, file=f'{file_name}.pdf', caption=cc1)
                        counter += 1
                        os.remove(f'{file_name}.pdf')
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                else:
                    Show = f"**⥥ DOWNLOADING... »**\n\n**Name »** `{file_name}`\n**Quality »** {raw_res}\n\n**URL »** `{url}`"
                    prog = await conv.send_message(Show)
                    res_file = await helper.download_video(url, cmd, file_name)
                    await bot.delete_messages(event.chat_id, prog.id)
                    
                    # Extract video metadata using MoviePy
                    duration, width, height = get_video_metadata(res_file)
                    
                    # Generate thumbnail if none provided
                    if batch_thumb is None:
                        batch_thumb = generate_thumbnail(res_file)
                    
                    # UPLOAD WITH PROGRESS (update every ~5%)
                    progress_msg = await conv.send_message("Uploading file... 0%")
                    last_percent = 0
                    last_time = time.time()
                    last_bytes = 0

                    async def progress_callback(current, total):
                        nonlocal last_percent, last_time, last_bytes
                        percent = (current / total) * 100
                        if (percent - last_percent >= 5) or (current == total):
                            now = time.time()
                            dt = now - last_time
                            speed = (current - last_bytes) / dt if dt > 0 else 0
                            speed_str = human_readable(speed) + "/s"
                            text = f"Uploading: {percent:.2f}% ({human_readable(current)}/{human_readable(total)}) at {speed_str}"
                            try:
                                await bot.edit_message(event.chat_id, progress_msg.id, text)
                            except Exception as ex:
                                log.error(f"Progress update failed: {ex}")
                            last_percent = percent
                            last_time = now
                            last_bytes = current

                    with open(res_file, "rb") as file_obj:
                        uploaded_file = await fast_upload(bot, file_obj, progress_callback=progress_callback)
                    await bot.delete_messages(event.chat_id, progress_msg.id)

                    # Set the filename so Telegram recognizes it as MP4
                    uploaded_file.name = f"{file_name}.mp4"

                    # Create video attributes for correct metadata display
                    attributes = [DocumentAttributeVideo(duration=duration, width=width, height=height, supports_streaming=True)]

                    await bot.send_file(
                        event.chat_id,
                        file=uploaded_file,
                        caption=cc,
                        supports_streaming=True,
                        attributes=attributes,
                        thumb=batch_thumb
                    )
                    counter += 1
                    await asyncio.sleep(1)
            except Exception as e:
                await conv.send_message(
                    f"**Downloading Interrupted**\n{str(e)}\n**Name »** {file_name}\n**URL »** `{url}`"
                )
                continue
    except Exception as e:
        await conv.send_message(str(e))
    await conv.send_message("**Done Boss 😎**")
    await bot.delete_messages(event.chat_id, status_msg.id)


def main():
    print("Bot is running...")
    bot.run_until_disconnected()


if __name__ == '__main__':
    main()
