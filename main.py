import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess
import logging
import hashlib
import inspect
import math
from collections import defaultdict
from typing import Optional, List, AsyncGenerator, Union, Awaitable, DefaultDict, Tuple, BinaryIO

# Additional imports
import aiohttp
from telethon import TelegramClient, events, utils, helpers
from telethon.network import MTProtoSender
from telethon.tl.alltlobjects import LAYER
from telethon.tl.functions import InvokeWithLayerRequest
from telethon.tl.functions.auth import ExportAuthorizationRequest, ImportAuthorizationRequest
from telethon.tl.functions.upload import GetFileRequest, SaveFilePartRequest, SaveBigFilePartRequest
from telethon.tl.types import Document, InputFileLocation, InputDocumentFileLocation, InputPeerPhotoFileLocation, InputPhotoFileLocation, TypeInputFile, InputFileBig, InputFile

# Set up logging
logging.basicConfig(level=logging.INFO)
log: logging.Logger = logging.getLogger("telethon")

# ========= Telethon Fast Upload Code =========
TypeLocation = Union[
    Document,
    InputFileLocation,
    InputDocumentFileLocation,
    InputPeerPhotoFileLocation,
    InputPhotoFileLocation
]

class DownloadSender:
    def __init__(self, client: TelegramClient, sender: MTProtoSender, file: TypeLocation, offset: int, limit: int, stride: int, count: int) -> None:
        self.sender = sender
        self.client = client
        self.request = GetFileRequest(file, offset=offset, limit=limit)
        self.stride = stride
        self.remaining = count

    async def next(self) -> Optional[bytes]:
        if not self.remaining:
            return None
        result = await self.client._call(self.sender, self.request)
        self.remaining -= 1
        self.request.offset += self.stride
        return result.bytes

    def disconnect(self) -> Awaitable[None]:
        return self.sender.disconnect()

class UploadSender:
    def __init__(self, client: TelegramClient, sender: MTProtoSender, file_id: int, part_count: int, big: bool, index: int, stride: int, loop: asyncio.AbstractEventLoop) -> None:
        self.client = client
        self.sender = sender
        self.part_count = part_count
        if big:
            self.request = SaveBigFilePartRequest(file_id, index, part_count, b"")
        else:
            self.request = SaveFilePartRequest(file_id, index, b"")
        self.stride = stride
        self.previous = None
        self.loop = loop

    async def next(self, data: bytes) -> None:
        if self.previous:
            await self.previous
        self.previous = self.loop.create_task(self._next(data))

    async def _next(self, data: bytes) -> None:
        self.request.bytes = data
        log.debug(f"Sending file part {self.request.file_part}/{self.part_count} with {len(data)} bytes")
        await self.client._call(self.sender, self.request)
        self.request.file_part += self.stride

    async def disconnect(self) -> None:
        if self.previous:
            await self.previous
        return await self.sender.disconnect()

class ParallelTransferrer:
    def __init__(self, client: TelegramClient, dc_id: Optional[int] = None) -> None:
        self.client = client
        self.loop = self.client.loop
        self.dc_id = dc_id or self.client.session.dc_id
        self.auth_key = None if dc_id and self.client.session.dc_id != dc_id else self.client.session.auth_key
        self.senders = None
        self.upload_ticker = 0

    async def _cleanup(self) -> None:
        await asyncio.gather(*[sender.disconnect() for sender in self.senders])
        self.senders = None

    @staticmethod
    def _get_connection_count(file_size: int, max_count: int = 20, full_size: int = 100 * 1024 * 1024) -> int:
        if file_size > full_size:
            return max_count
        return math.ceil((file_size / full_size) * max_count)

    async def _init_download(self, connections: int, file: TypeLocation, part_count: int, part_size: int) -> None:
        minimum, remainder = divmod(part_count, connections)
        def get_part_count() -> int:
            nonlocal remainder
            if remainder > 0:
                remainder -= 1
                return minimum + 1
            return minimum
        self.senders = [
            await self._create_download_sender(file, 0, part_size, connections * part_size, get_part_count()),
            *await asyncio.gather(
                *[self._create_download_sender(file, i, part_size, connections * part_size, get_part_count())
                  for i in range(1, connections)]
            )
        ]

    async def _create_download_sender(self, file: TypeLocation, index: int, part_size: int, stride: int, part_count: int) -> DownloadSender:
        return DownloadSender(self.client, await self._create_sender(), file, index * part_size, part_size, stride, part_count)

    async def _init_upload(self, connections: int, file_id: int, part_count: int, big: bool) -> None:
        self.senders = [
            await self._create_upload_sender(file_id, part_count, big, 0, connections),
            *await asyncio.gather(
                *[self._create_upload_sender(file_id, part_count, big, i, connections)
                  for i in range(1, connections)]
            )
        ]

    async def _create_upload_sender(self, file_id: int, part_count: int, big: bool, index: int, stride: int) -> UploadSender:
        return UploadSender(self.client, await self._create_sender(), file_id, part_count, big, index, stride, loop=self.loop)

    async def _create_sender(self) -> MTProtoSender:
        dc = await self.client._get_dc(self.dc_id)
        sender = MTProtoSender(self.auth_key, loggers=self.client._log)
        await sender.connect(self.client._connection(dc.ip_address, dc.port, dc.id, loggers=self.client._log, proxy=self.client._proxy))
        if not self.auth_key:
            log.debug(f"Exporting auth to DC {self.dc_id}")
            auth = await self.client(ExportAuthorizationRequest(self.dc_id))
            self.client._init_request.query = ImportAuthorizationRequest(id=auth.id, bytes=auth.bytes)
            req = InvokeWithLayerRequest(LAYER, self.client._init_request)
            await sender.send(req)
            self.auth_key = sender.auth_key
        return sender

    async def init_upload(self, file_id: int, file_size: int, part_size_kb: Optional[float] = None, connection_count: Optional[int] = None) -> Tuple[int, int, bool]:
        connection_count = connection_count or self._get_connection_count(file_size)
        part_size = (part_size_kb or utils.get_appropriated_part_size(file_size)) * 1024
        part_count = (file_size + part_size - 1) // part_size
        is_large = file_size > 10 * 1024 * 1024
        await self._init_upload(connection_count, file_id, part_count, is_large)
        return part_size, part_count, is_large

    async def upload(self, part: bytes) -> None:
        await self.senders[self.upload_ticker].next(part)
        self.upload_ticker = (self.upload_ticker + 1) % len(self.senders)

    async def finish_upload(self) -> None:
        await self._cleanup()

    async def download(self, file: TypeLocation, file_size: int, part_size_kb: Optional[float] = None, connection_count: Optional[int] = None) -> AsyncGenerator[bytes, None]:
        connection_count = connection_count or self._get_connection_count(file_size)
        part_size = (part_size_kb or utils.get_appropriated_part_size(file_size)) * 1024
        part_count = math.ceil(file_size / part_size)
        log.debug("Starting parallel download: " f"{connection_count} {part_size} {part_count} {file!s}")
        await self._init_download(connection_count, file, part_count, part_size)
        part = 0
        while part < part_count:
            tasks = []
            for sender in self.senders:
                tasks.append(self.loop.create_task(sender.next()))
            for task in tasks:
                data = await task
                if not data:
                    break
                yield data
                part += 1
                log.debug(f"Part {part} downloaded")
        log.debug("Parallel download finished, cleaning up connections")
        await self._cleanup()

parallel_transfer_locks: DefaultDict[int, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())

def stream_file(file_to_stream: BinaryIO, chunk_size=1024):
    while True:
        data_read = file_to_stream.read(chunk_size)
        if not data_read:
            break
        yield data_read

async def _internal_transfer_to_telegram(client: TelegramClient, response: BinaryIO, progress_callback: callable) -> Tuple[TypeInputFile, int]:
    file_id = helpers.generate_random_long()
    file_size = os.path.getsize(response.name)
    hash_md5 = hashlib.md5()
    uploader = ParallelTransferrer(client)
    part_size, part_count, is_large = await uploader.init_upload(file_id, file_size)
    buffer = bytearray()
    for data in stream_file(response):
        if progress_callback:
            r = progress_callback(response.tell(), file_size)
            if inspect.isawaitable(r):
                await r
        if not is_large:
            hash_md5.update(data)
        if len(buffer) == 0 and len(data) == part_size:
            await uploader.upload(data)
            continue
        new_len = len(buffer) + len(data)
        if new_len >= part_size:
            cutoff = part_size - len(buffer)
            buffer.extend(data[:cutoff])
            await uploader.upload(bytes(buffer))
            buffer.clear()
            buffer.extend(data[cutoff:])
        else:
            buffer.extend(data)
    if len(buffer) > 0:
        await uploader.upload(bytes(buffer))
    await uploader.finish_upload()
    if is_large:
        return InputFileBig(file_id, part_count, "upload"), file_size
    else:
        return InputFile(file_id, part_count, "upload", hash_md5.hexdigest()), file_size

async def upload_file(client: TelegramClient, file: BinaryIO, progress_callback: callable = None) -> TypeInputFile:
    res = (await _internal_transfer_to_telegram(client, file, progress_callback))[0]
    return res

# Create a fast_upload alias for later use
fast_upload = upload_file
# ========= End of Fast Upload Code =========

# ========= Telethon Bot Setup =========
# Replace these with your own credentials
API_ID = YOUR_API_ID         # e.g., 1234567
API_HASH = "YOUR_API_HASH"   # e.g., "abcdef123456..."
BOT_TOKEN = "YOUR_BOT_TOKEN" # e.g., "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ========= Helper (Assumed Existing Functions) =========
# It is assumed you have a 'helper' module that defines download() and download_video() functions.
# If not, replace these calls with your own download implementations.
import core as helper
# ======================================================

# ========= Command Handlers =========
@bot.on(events.NewMessage(pattern=r'^/start'))
async def start_handler(event):
    await event.reply(
        f"<b>Hello {event.sender.first_name} 👋\n\n"
        "I am a bot that downloads links from your <b>.TXT</b> file and uploads them to Telegram. "
        "To use me, first send /upload and follow the steps. "
        "Send /stop to abort any ongoing task.</b>"
    )

@bot.on(events.NewMessage(pattern=r'^/stop'))
async def stop_handler(event):
    await event.reply("**Stopped** 🚦")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r'^/upload'))
async def upload_handler(event):
    # Use Telethon's conversation helper for interactive steps
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("Send TXT file ⚡️")
        txt_msg = await conv.get_response()
        txt_path = await bot.download_media(txt_msg)
        try:
            with open(txt_path, "r") as f:
                content = f.read()
            content = content.splitlines()
            links = [line.split("://", 1) for line in content if line.strip()]
            os.remove(txt_path)
        except Exception as e:
            await conv.send_message("**Invalid file input.**")
            os.remove(txt_path)
            return

        await conv.send_message("Are there any password-protected links in this file? If yes, send the PW token. If not, type 'no'.")
        pw_msg = await conv.get_response()
        pw_token = pw_msg.text.strip()
        
        await conv.send_message(f"**Total links found:** **{len(links)}**\n\nSend a number indicating from which link you want to start downloading (e.g. 1).")
        start_msg = await conv.get_response()
        raw_text = start_msg.text.strip()

        await conv.send_message("Now send me your batch name:")
        batch_msg = await conv.get_response()
        batch_name = batch_msg.text.strip()
        
        await conv.send_message("Enter resolution (choose: 144, 240, 360, 480, 720, 1080):")
        res_msg = await conv.get_response()
        raw_text2 = res_msg.text.strip()
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
        
        await conv.send_message("Now enter a caption for your uploaded file:")
        caption_msg = await conv.get_response()
        caption_input = caption_msg.text.strip()
        highlighter = "️ ⁪⁬⁮⁮⁮"
        caption = highlighter if caption_input == 'Robin' else caption_input
        
        await conv.send_message("Send the thumbnail URL (e.g. https://graph.org/file/ce1723991756e48c35aa1.jpg) or type 'no' for no thumbnail.")
        thumb_msg = await conv.get_response()
        thumb_input = thumb_msg.text.strip()
        await conv.send_message("Processing your links...")
        
        thumb = thumb_input
        if thumb.startswith("http://") or thumb.startswith("https://"):
            subprocess.getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
            thumb = "thumb.jpg"
        else:
            thumb = "no"
        
        try:
            count = 1 if len(links) == 1 else int(raw_text)
        except:
            count = 1

        # Process each link
        for i in range(count - 1, len(links)):
            V = links[i][1].replace("file/d/", "uc?export=download&id=") \
                           .replace("www.youtube-nocookie.com/embed", "youtu.be") \
                           .replace("?modestbranding=1", "") \
                           .replace("/view?usp=sharing", "")
            url = "https://" + V

            # Special URL processing
            if "visionias" in url:
                async with aiohttp.ClientSession() as session:
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
                        m = re.search(r"(https://.*?playlist.m3u8.*?)\"", text)
                        if m:
                            url = m.group(1)
            elif 'videos.classplusapp' in url:
                api_url = "https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url=" + url
                url = requests.get(api_url, headers={
                    'x-access-token': 'TOKEN'  # Replace TOKEN if needed
                }).json()['url']
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
            file_name = f'{str(count).zfill(3)}) {name1[:60]}'
            if "youtu" in url:
                ytf = f"b[height<={raw_text2}][ext=mp4]/bv[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"
            if "jw-prod" in url:
                cmd = f'yt-dlp --external-downloader aria2c --external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 --max-download-limit=0 --max-overall-download-limit=0 --enable-http-pipelining=true --file-allocation=falloc" -o "{file_name}.mp4" "{url}"'
            else:
                cmd = f'yt-dlp --external-downloader aria2c --external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 --max-download-limit=0 --max-overall-download-limit=0 --enable-http-pipelining=true --file-allocation=falloc" -f "{ytf}" "{url}" -o "{file_name}.mp4"'
            try:
                cc = f'**{str(count).zfill(3)}**. {name1}{caption}.mkv\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                cc1 = f'**{str(count).zfill(3)}**. {name1}{caption}.pdf\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                if "drive" in url:
                    try:
                        ka = await helper.download(url, file_name)
                        await bot.send_file(event.chat_id, file=ka, caption=cc1)
                        count += 1
                        os.remove(ka)
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                elif ".pdf" in url:
                    try:
                        cmd = f'yt-dlp --external-downloader aria2c --external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 --max-download-limit=0 --max-overall-download-limit=0 --enable-http-pipelining=true --file-allocation=falloc" -o "{file_name}.pdf" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        await bot.send_file(event.chat_id, file=f'{file_name}.pdf', caption=cc1)
                        count += 1
                        os.remove(f'{file_name}.pdf')
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                else:
                    show_msg = f"**⥥ DOWNLOADING... »**\n\n**📝Name »** `{file_name}`\n**❄Quality »** {raw_text2}\n\n**🔗URL »** `{url}`"
                    status_msg = await conv.send_message(show_msg)
                    res_file = await helper.download_video(url, cmd, file_name)
                    filename = res_file
                    await status_msg.delete()
                    with open(filename, "rb") as file_obj:
                        uploaded_file = await fast_upload(bot, file_obj)
                    count += 1
                    await asyncio.sleep(1)
            except Exception as e:
                await conv.send_message(f"**Downloading Interrupted**\n{str(e)}\n**Name »** {file_name}\n**Link »** `{url}`")
                continue
        await conv.send_message("**Done Boss 😎**")

# ========= Run the Bot =========
def main():
    print("Bot is running...")
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()
