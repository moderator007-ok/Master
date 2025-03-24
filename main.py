#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
                           MASTER BOT
===========================================================================
Author             : Moderator007
Latest Commit Hash : a70a8a8
Description        : This bot downloads links from a .TXT file and uploads
                     them to Telegram with metadata extraction (via ffprobe),
                     FFmpeg‑generated thumbnails (using copy merging, no re‑encode),
                     and real‑time progress updates.
===========================================================================
"""

import os
import re
import sys
import time
import asyncio
import requests
import subprocess
import logging
import shutil
from telethon import TelegramClient, events
import aiohttp
from telethon.tl.types import DocumentAttributeVideo  # For video attributes

# ---------------------------------------------------------------------------
# Import configuration variables from vars module
# ---------------------------------------------------------------------------
from vars import API_ID, API_HASH, BOT_TOKEN

# ---------------------------------------------------------------------------
# Import custom helper functions for downloading operations
# ---------------------------------------------------------------------------
import core as helper  # Assumes helper.download_video() and helper.download() exist

# ---------------------------------------------------------------------------
# Import external fast_upload function from devgagantools library
# Attempt to import fast_upload; if not found, fallback to upload_file as fast_upload
# ---------------------------------------------------------------------------
try:
    from devgagantools.spylib import fast_upload
except ImportError:
    from devgagantools.spylib import upload_file as fast_upload

# ---------------------------------------------------------------------------
# Set up logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telethon")

# ---------------------------------------------------------------------------
# Initialize the Telethon client
# ---------------------------------------------------------------------------
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# =============================================================================
#                           HELPER FUNCTIONS
# =============================================================================
def human_readable(size, decimal_places=2):
    """Convert bytes to a human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.{decimal_places}f}{unit}"
        size /= 1024
    return f"{size:.{decimal_places}f}PB"

def format_eta(seconds):
    """Format seconds as HH:MM:SS."""
    return time.strftime("%H:%M:%S", time.gmtime(seconds))

def generate_thumbnail(video_file, thumbnail_path, time_offset="00:00:01.000"):
    """
    Generate a thumbnail image from a video file using FFmpeg.
    This call uses copy mode (no re‑encoding) as the file is already merged.
    """
    ffmpeg_executable = "ffmpeg"  # Adjust path if necessary
    command = [
        ffmpeg_executable,
        "-threads", "0",  # Use all available cores
        "-i", video_file,
        "-ss", time_offset,
        "-vframes", "1",
        thumbnail_path,
        "-y"
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return thumbnail_path
    except subprocess.CalledProcessError as e:
        log.error(f"Thumbnail generation failed: {e}")
        return None

def get_video_metadata(file_path):
    """
    Quickly extract video metadata (duration, width, height) using ffprobe.
    This avoids using heavier Python libraries like MoviePy.
    """
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        output = result.stdout.strip().splitlines()
        if len(output) >= 3:
            width = int(float(output[0]))
            height = int(float(output[1]))
            duration = int(float(output[2]))
            return duration, width, height
    except Exception as e:
        log.error(f"Metadata extraction failed: {e}")
    return 0, 0, 0

# =============================================================================
#                           TELEGRAM BOT HANDLERS
# =============================================================================

@bot.on(events.NewMessage(pattern=r'^/start'))
async def start_handler(event):
    """Handle /start command."""
    welcome_message = (
        f"<b>Hello {event.sender.first_name} 👋</b>\n\n"
        "I am a bot that downloads links from your <b>.TXT</b> file and uploads them to Telegram.\n"
        "To use me, send /upload and follow the steps.\n"
        "Send /stop to abort any ongoing task."
    )
    msg = await event.reply(welcome_message)
    await asyncio.sleep(5)
    await bot.delete_messages(event.chat_id, msg.id)

@bot.on(events.NewMessage(pattern=r'^/stop'))
async def stop_handler(event):
    """Handle /stop command by restarting the script."""
    await event.reply("**Stopped** 🚦")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r'^/upload'))
async def upload_handler(event):
    """
    Handle /upload command:
      - Receive a TXT file with URLs.
      - Optionally receive a password token, starting index, batch name,
        resolution, caption, and thumbnail.
      - For HLS URLs, download all TS fragments concurrently using yt‑dlp with -N 128,
        storing fragments in a temporary folder.
      - Once the download is complete, merge the fragments into an MP4 using ffmpeg (copy mode).
      - For non‑HLS URLs, use yt‑dlp’s standard merging.
      - Extract metadata via ffprobe.
      - Generate a thumbnail with ffmpeg.
      - Upload the final file.
    """
    async with bot.conversation(event.chat_id) as conv:
        # STEP 1: Get TXT file
        q1 = await conv.send_message("Send TXT file ⚡️")
        txt_msg = await conv.get_response()
        await bot.delete_messages(event.chat_id, [q1.id, txt_msg.id])
        txt_path = await bot.download_media(txt_msg)
        try:
            with open(txt_path, "r") as f:
                content = f.read()
            lines = content.splitlines()
            links = [line.split("://", 1) for line in lines if line.strip()]
            os.remove(txt_path)
        except Exception as e:
            err_msg = await conv.send_message("**Invalid file input.**")
            await asyncio.sleep(3)
            await bot.delete_messages(event.chat_id, err_msg.id)
            os.remove(txt_path)
            return

        # STEP 2: Get password token (if any)
        q2 = await conv.send_message(
            "Are there any password-protected links in this file? "
            "If yes, send the PW token. If not, type 'no'."
        )
        pw_msg = await conv.get_response()
        pw_token = pw_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q2.id, pw_msg.id])

        # STEP 3: Get starting index
        q3 = await conv.send_message(
            f"**Total links found:** **{len(links)}**\n\n"
            "Send a number indicating from which link you want to start downloading (e.g. 1)."
        )
        start_msg = await conv.get_response()
        try:
            start_index = int(start_msg.text.strip())
        except Exception:
            start_index = 1
        await bot.delete_messages(event.chat_id, [q3.id, start_msg.id])

        # STEP 4: Get batch name
        q4 = await conv.send_message("Now send me your batch name:")
        batch_msg = await conv.get_response()
        batch_name = batch_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q4.id, batch_msg.id])

        # STEP 5: Get resolution
        q5 = await conv.send_message("Enter resolution (choose: 144, 240, 360, 480, 720, 1080):")
        res_msg = await conv.get_response()
        raw_res = res_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q5.id, res_msg.id])
        resolution_map = {
            "144": "256x144",
            "240": "426x240",
            "360": "640x360",
            "480": "854x480",
            "720": "1280x720",
            "1080": "1920x1080"
        }
        res = resolution_map.get(raw_res, "UN")

        # STEP 6: Get caption
        q6 = await conv.send_message("Now enter a caption for your uploaded file:")
        caption_msg = await conv.get_response()
        caption_input = caption_msg.text.strip()
        highlighter = "️ ⁪⁬⁮⁮⁮"
        caption = highlighter if caption_input == 'Robin' else caption_input
        await bot.delete_messages(event.chat_id, [q6.id, caption_msg.id])

        # STEP 7: Get thumbnail (optional)
        q7 = await conv.send_message(
            "Send a thumbnail image for this batch (or type 'no' to skip and let Telegram auto‑generate one):"
        )
        thumb_msg = await conv.get_response()
        await bot.delete_messages(event.chat_id, [q7.id, thumb_msg.id])
        thumb_path = await bot.download_media(thumb_msg) if thumb_msg.media else None
        batch_thumb = thumb_path

        # Notify processing start
        status_msg = await conv.send_message("Processing your links...")

        # =============================================================================
        # PROCESS EACH LINK
        # =============================================================================
        for i in range(start_index - 1, len(links)):
            # Reconstruct URL
            link_protocol, link_body = links[i]
            V = link_body.replace("file/d/", "uc?export=download&id=") \
                         .replace("www.youtube-nocookie.com/embed", "youtu.be") \
                         .replace("?modestbranding=1", "") \
                         .replace("/view?usp=sharing", "")
            url = "https://" + V

            # Special URL processing
            is_hls = False
            if "visionias" in url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers={
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                                      'image/avif,image/webp,image/apng,*/*;q=0.8',
                            'User-Agent': 'Mozilla/5.0'
                        }
                    ) as resp:
                        text = await resp.text()
                        m = re.search(r"(https://.*?playlist\.m3u8.*?)\"", text)
                        if m:
                            url = m.group(1)
            elif 'videos.classplusapp' in url:
                api_url = "https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url=" + url
                response = requests.get(api_url, headers={'x-access-token': 'TOKEN'})
                try:
                    url = response.json()['url']
                except Exception as e:
                    log.error(f"Error processing Classplusapp URL: {e}")
            elif '/master.mpd' in url:
                url = f"https://anonymouspwplayer-b99f57957198.herokuapp.com/pw?url={url}?token={pw_token}"
                is_hls = True

            # Construct a safe file name
            name1 = links[i][0]
            name1 = name1.replace("\t", "").replace(":", "").replace("/", "") \
                         .replace("+", "").replace("#", "").replace("|", "") \
                         .replace("@", "").replace("*", "").replace(".", "") \
                         .replace("https", "").replace("http", "").strip()
            file_name = f'{str(i+1).zfill(3)}) {name1[:60]}'

            # Determine yt-dlp format template
            if "youtu" in url:
                ytf = f"b[height<={raw_res}][ext=mp4]/bv[height<={raw_res}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={raw_res}]/bv[height<={raw_res}]+ba/b/bv+ba"

            # Build yt-dlp command:
            # For HLS downloads, enforce a two-step process:
            # 1. Download all TS fragments concurrently using -N 128 into a temporary folder.
            # 2. After download completion, merge them using ffmpeg (copy mode).
            if is_hls:
                temp_dir = os.path.join("temp", file_name.replace(" ", "_"))
                os.makedirs(temp_dir, exist_ok=True)
                # Download TS fragments into the temp folder.
                # The output template uses the fragment index.
                if "jw-prod" in url:
                    cmd = f'yt-dlp -N 128 -o "{temp_dir}/%(fragment_index)03d.ts" "{url}"'
                else:
                    cmd = f'yt-dlp -N 128 -f "{ytf}" -o "{temp_dir}/%(fragment_index)03d.ts" "{url}"'
                # Download all fragments (this call should wait until all fragments are downloaded)
                await helper.download_video(url, cmd, file_name)
                # Create a file list for ffmpeg concat demuxer.
                ts_files = sorted([os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith(".ts")])
                filelist_path = os.path.join(temp_dir, "filelist.txt")
                with open(filelist_path, "w") as fl:
                    for ts in ts_files:
                        fl.write(f"file '{os.path.abspath(ts)}'\n")
                # Merge fragments into one MP4 file using ffmpeg (copy mode).
                merged_file = f"{file_name}.mp4"
                merge_cmd = [
                    "ffmpeg", "-f", "concat", "-safe", "0", "-i", filelist_path,
                    "-c", "copy", merged_file, "-y"
                ]
                subprocess.run(merge_cmd, check=True)
                res_file = merged_file
                # Optionally clean up the temporary directory:
                # shutil.rmtree(temp_dir)
            else:
                # For non-HLS URLs, use yt-dlp's standard merging.
                if "jw-prod" in url:
                    cmd = (
                        f'yt-dlp -N 128 --merge-output-format mp4 '
                        f'-o "{file_name}.mp4" "{url}"'
                    )
                else:
                    cmd = (
                        f'yt-dlp -N 128 --merge-output-format mp4 '
                        f'-f "{ytf}" "{url}" -o "{file_name}.mp4"'
                    )
                res_file = await helper.download_video(url, cmd, file_name)

            # Post-download processing:
            # Extract metadata via ffprobe.
            duration, width, height = get_video_metadata(res_file)
            
            # Generate thumbnail if not provided.
            if batch_thumb is None:
                thumb_file = f"{file_name}_thumb.jpg"
                generated_thumb = generate_thumbnail(res_file, thumb_file)
                current_thumb = generated_thumb
            else:
                current_thumb = batch_thumb

            # Upload the file with progress callback.
            progress_msg = await conv.send_message("Uploading file... 0%")
            last_percent = 0
            last_time = time.time()
            last_bytes = 0

            async def progress_callback(current, total):
                nonlocal last_percent, last_time, last_bytes
                percent = (current / total) * 100
                if percent - last_percent >= 5 or current == total:
                    now = time.time()
                    dt = now - last_time
                    speed = (current - last_bytes) / dt if dt > 0 else 0
                    speed_str = human_readable(speed) + "/s"
                    bar_length = 20
                    filled_length = int(bar_length * current // total)
                    progress_bar = "█" * filled_length + "░" * (bar_length - filled_length)
                    perc_str = f"{percent:.2f}%"
                    cur_str = human_readable(current)
                    tot_str = human_readable(total)
                    eta = format_eta((total - current) / speed) if speed > 0 else "Calculating..."
                    text = (
                        f"<b>\n"
                        f" ╭──⌯════🆄︎ᴘʟᴏᴀᴅɪɴɢ⬆️⬆️═════⌯──╮ \n"
                        f"├⚡ {progress_bar}|﹝{perc_str}﹞ \n"
                        f"├🚀 Speed » {speed_str} \n"
                        f"├📟 Processed » {cur_str}\n"
                        f"├🧲 Size - ETA » {tot_str} - {eta} \n"
                        f"├🤖 By » TechMon\n"
                        f"╰─═══ ✪ TechMon ✪ ═══─╯\n"
                        f"</b>"
                    )
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

            # Set video attributes and send the file.
            uploaded_file.name = f"{file_name}.mp4"
            attributes = [DocumentAttributeVideo(duration, w=width, h=height, supports_streaming=True)]
            await bot.send_file(
                event.chat_id,
                file=uploaded_file,
                caption=f"**{file_name}**\n{caption}\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX",
                supports_streaming=True,
                attributes=attributes,
                thumb=current_thumb
            )
            await asyncio.sleep(1)

        # End processing
        await conv.send_message("**Done Boss 😎**")
        await bot.delete_messages(event.chat_id, status_msg.id)

        # Clean up thumbnail if provided/generated
        if batch_thumb is not None and os.path.exists(batch_thumb):
            os.remove(batch_thumb)

# =============================================================================
#                           MAIN ENTRY POINT
# =============================================================================
def main():
    print("Bot is running... (Commit a70a8a8)")
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()
