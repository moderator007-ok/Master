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
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ========= Telethon Fast Upload Code (Embedded) =========
# This code is taken from the Telethon parallel file transfer implementation.
# It provides a fast_upload function that expects a Telethon client.
# (A minimal monkey-patch is provided below for compatibility.)
import asyncio
import hashlib
import inspect
import logging
import math
from collections import defaultdict
from typing import Optional, List, AsyncGenerator, Union, Awaitable, DefaultDict, Tuple, BinaryIO

from telethon import utils, helpers, TelegramClient
from telethon.network import MTProtoSender
from telethon.tl.alltlobjects import LAYER
from telethon.tl.functions import InvokeWithLayerRequest
from telethon.tl.functions.auth import ExportAuthorizationRequest, ImportAuthorizationRequest
from telethon.tl.functions.upload import GetFileRequest, SaveFilePartRequest, SaveBigFilePartRequest
from telethon.tl.types import Document, InputFileLocation, InputDocumentFileLocation, InputPeerPhotoFileLocation, InputPhotoFileLocation, TypeInputFile, InputFileBig, InputFile

log: logging.Logger = logging.getLogger("telethon")

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

# Create a fast_upload alias so that your later code need not change.
fast_upload = upload_file
# ========= End of Telethon Fast Upload Code =========

# ========= Minimal Monkey-Patch for Telethon Compatibility =========
# Since your bot uses Pyrogram’s Client (not Telethon’s), we add a basic stub for _get_dc.
# Note that a complete implementation would require more methods.
if not hasattr(Client, "_get_dc"):
    Client._get_dc = lambda self, dc_id=None: self.session.dc_id
# =============================================================

# ========= Bot Code =========
bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@bot.on_message(filters.command(["start"]))
async def start(bot: Client, m: Message):
    await m.reply_text(
        f"<b>Hello {m.from_user.mention} 👋\n\n"
        "I am a bot that downloads links from your **.TXT** file and uploads them to Telegram. "
        "To use me, first send /upload and follow the steps. "
        "Send /stop to abort any ongoing task.</b>"
    )

@bot.on_message(filters.command("stop"))
async def stop_handler(_, m: Message):
    await m.reply_text("**Stopped** 🚦", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on_message(filters.command(["upload"]))
async def upload(bot: Client, m: Message):
    editable = await m.reply_text('Send TXT file ⚡️')
    inp: Message = await bot.listen(editable.chat.id)
    txt_path = await inp.download()
    await inp.delete(True)
    path = f"./downloads/{m.chat.id}"
    try:
        with open(txt_path, "r") as f:
            content = f.read()
        content = content.split("\n")
        links = [line.split("://", 1) for line in content if line.strip()]
        os.remove(txt_path)
    except Exception as e:
        await m.reply_text("**Invalid file input.**")
        os.remove(txt_path)
        return

    await editable.edit("Are there any password-protected links in this file? If yes, send the PW token. If not, type 'no'.")
    inp_pw: Message = await bot.listen(editable.chat.id)
    pw_token = inp_pw.text.strip()
    await inp_pw.delete(True)
    
    await editable.edit(
        f"**Total links found:** **{len(links)}**\n\n"
        "Send a number indicating from which link you want to start downloading (e.g. 1)."
    )
    inp0: Message = await bot.listen(editable.chat.id)
    raw_text = inp0.text
    await inp0.delete(True)

    await editable.edit("Now send me your batch name:")
    inp1: Message = await bot.listen(editable.chat.id)
    batch_name = inp1.text
    await inp1.delete(True)
    
    await editable.edit("Enter resolution (choose: 144, 240, 360, 480, 720, 1080):")
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
    
    await editable.edit("Now enter a caption for your uploaded file:")
    inp3: Message = await bot.listen(editable.chat.id)
    caption_input = inp3.text
    await inp3.delete(True)
    highlighter = "️ ⁪⁬⁮⁮⁮"
    caption = highlighter if caption_input == 'Robin' else caption_input
       
    await editable.edit(
        "Send the thumbnail URL (e.g. https://graph.org/file/ce1723991756e48c35aa1.jpg) "
        "or type 'no' for no thumbnail."
    )
    inp6: Message = await bot.listen(editable.chat.id)
    thumb_input = inp6.text
    await inp6.delete(True)
    await editable.delete()

    thumb = thumb_input
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
                    'x-access-token': TOKEN
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
                cmd = (
                    f'yt-dlp --external-downloader aria2c '
                    f'--external-downloader-args "-x 16 -s 16 -k 1M '
                    f'--timeout=120 --connect-timeout=120 '
                    f'--max-download-limit=0 --max-overall-download-limit=0 '
                    f'--enable-http-pipelining=true --file-allocation=falloc" '
                    f'-o "{file_name}.mp4" "{url}"'
                )
            else:
                cmd = (
                    f'yt-dlp --external-downloader aria2c '
                    f'--external-downloader-args "-x 16 -s 16 -k 1M '
                    f'--timeout=120 --connect-timeout=120 '
                    f'--max-download-limit=0 --max-overall-download-limit=0 '
                    f'--enable-http-pipelining=true --file-allocation=falloc" '
                    f'-f "{ytf}" "{url}" -o "{file_name}.mp4"'
                )
            try:
                cc = f'**{str(count).zfill(3)}**. {name1}{caption}.mkv\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                cc1 = f'**{str(count).zfill(3)}**. {name1}{caption}.pdf\n**Batch Name »** {batch_name}\n**Downloaded By :** TechMon ❤️‍🔥 @TechMonX'
                if "drive" in url:
                    try:
                        ka = await helper.download(url, file_name)
                        await bot.send_document(chat_id=m.chat.id, document=ka, caption=cc1)
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
                            f'-o "{file_name}.pdf" "{url}"'
                        )
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        await bot.send_document(chat_id=m.chat.id, document=f'{file_name}.pdf', caption=cc1)
                        count += 1
                        os.remove(f'{file_name}.pdf')
                        await asyncio.sleep(1)
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        await asyncio.sleep(e.x)
                        continue
                else:
                    show_msg = (
                        f"**⥥ DOWNLOADING... »**\n\n"
                        f"**📝Name »** `{file_name}`\n"
                        f"**❄Quality »** {raw_text2}\n\n"
                        f"**🔗URL »** `{url}`"
                    )
                    prog = await m.reply_text(show_msg)
                    res_file = await helper.download_video(url, cmd, file_name)
                    filename = res_file
                    await prog.delete(True)
                    # Open the downloaded file and pass it along with the client to the upload function.
                    with open(filename, "rb") as file_obj:
                        uploaded_file = await fast_upload(bot, file_obj)
                    count += 1
                    await asyncio.sleep(1)
            except Exception as e:
                await m.reply_text(
                    f"**Downloading Interrupted**\n{str(e)}\n**Name »** {file_name}\n**Link »** `{url}`"
                )
                continue
    except Exception as e:
        await m.reply_text(str(e))
    await m.reply_text("**Done Boss 😎**")

bot.run()
