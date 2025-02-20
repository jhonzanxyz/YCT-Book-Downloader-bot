import os
import shutil
import asyncio
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
import img2pdf  # For PDF creation from images
import json
import re  # For extracting JSON from HTML
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, UnidentifiedImageError
from fpdf import FPDF

# Bot configurations
API_ID = "23298276"  # Your API_ID
API_HASH = "0fa5ea46f81eb24548cfc66b5d0f6107"  # Your API_HASH
BOT_TOKEN = "8098279575:AAGAMKgRgSW4b0TvbE6njoYtpntTCiONw3E"  # Your BOT_TOKEN

# Initialize the bot
app = Client("book_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Store ongoing tasks
user_tasks = {}

# ThreadPoolExecutor for parallel downloads
executor = ThreadPoolExecutor(max_workers=5)

# Step 1: Start command

# Cookie configuration using environment variables
CI_DATABASE = os.getenv("CI_DATABASE", "be31ceea64aad5111021779f7eff1dee54cc576b")
CI_SESSION = os.getenv("CI_SESSION", "92159a1e9020cd6a20a6ca76689ca215e9d5339b")


def get_cookies():
    return f"ci_database={CI_DATABASE}; ci_session={CI_SESSION}"


@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply("Welcome to the Book Downloader Bot!\nSend /download to start downloading a book.")

@app.on_message(filters.command("cookie"))
async def update_cookies(client, message: Message):
    global CI_DATABASE, CI_SESSION
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.reply("Invalid command format! Use:\n`/cookie <ci_database> <ci_session>`", parse_mode="markdown")
            return

        # Update cookies
        CI_DATABASE = args[1]
        CI_SESSION = args[2]

        await message.reply("Cookies updated successfully!")
    except Exception as e:
        await message.reply(f"An error occurred while updating cookies: {e}")
    
# Step 2: Download command
@app.on_message(filters.command("download"))
async def download_command(client, message: Message):
    user_id = message.from_user.id
    if user_id in user_tasks:
        await message.reply("You already have an ongoing task. Please wait or send /cancel to stop it.")
        return

    user_tasks[user_id] = {"status": "awaiting_book_id"}
    await message.reply("Please send the book ID to start downloading.")

# Cancel command
@app.on_message(filters.command("cancel"))
async def cancel_command(client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_tasks:
        await message.reply("You don't have any ongoing tasks.")
        return

    # Clean up and stop task
    user_folder = f"downloads/{user_id}/"
    shutil.rmtree(user_folder, ignore_errors=True)
    user_tasks.pop(user_id, None)
    await message.reply("Your task has been canceled and all temporary data has been deleted.")

# Step 3: Handle book ID
@app.on_message(filters.text)
async def handle_book_id(client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_tasks:
        return

    user_task = user_tasks[user_id]
    if user_task["status"] == "awaiting_book_id":
        book_id = message.text.strip()
        user_task["book_id"] = book_id
        user_task["status"] = "downloading"

        # Get book details from API
        status = await message.reply("Got it! Fetching book details...")
        await download_book(client, status, message, user_task)

# Step 4: Download book pages and process
def download_page(page: int, book_id: str, user_folder: str):
    page_url = f"https://yctpublication.com/getPage/{book_id}/{page}"
    output_file = f"{user_folder}{page}.jpg"
    
    # Setup headers for the request
    curl_headers = {
        "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9,hi-IN;q=0.8,hi;q=0.7",
        "cookie": get_cookies(),
        "dnt": "1",
        "priority": "u=2, i",
        "referer": f"https://yctpublication.com/readbook/{book_id}",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "image",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }

    # Download the page image using requests
    response = requests.get(page_url, headers=curl_headers)
    if response.status_code == 200:
        with open(output_file, "wb") as f:
            f.write(response.content)

# Step 5: Download book and handle
async def download_book(client, status, message: Message, user_task: dict):
    user_id = message.from_user.id
    book_id = user_task["book_id"]
    user_folder = f"downloads/{user_id}/"
    os.makedirs(user_folder, exist_ok=True)

    try:
        # Get book details from API
        response = requests.get(f"https://yctpublication.com/master/api/MasterController/bookdetails?bookid={book_id}")
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type:
                book_details = response.json()
                if book_details.get("status"):
                    book_name = book_details["data"].get("book_name", "Unknown Book").replace(" ", "_")
                    no_of_pages = int(book_details["data"].get("no_of_pages", 0))
                else:
                    raise Exception(f"API returned an error: {book_details.get('message', 'Unknown error')}")
            elif "text/html" in content_type:
                text_content = response.text
                json_match = re.search(r'({.*})', text_content)
                if json_match:
                    book_details = json.loads(json_match.group(0))
                    if book_details.get("status"):
                        book_name = book_details["data"].get("book_name", "Unknown Book").replace(" ", "_")
                        no_of_pages = int(book_details["data"].get("no_of_pages", 0))
                    else:
                        raise Exception(f"API returned an error: {book_details.get('message', 'Unknown error')}")
                else:
                    raise Exception("Failed to parse JSON from HTML response.")
            else:
                raise Exception(f"Unexpected response format: {content_type}")
        else:
            raise Exception(f"Failed to fetch book details. HTTP Status: {response.status_code}")

        if no_of_pages == 0:
            raise Exception("Invalid number of pages.")
        await status.delete()
        stage = await app.send_message(user_id, f"__**Downloading:**__\n\n📕 **Book Name:** {book_name}\n🔖 **Total Pages:** {no_of_pages}\n\n> __**Powered by Team SPY*__")

        # Proceed with image generation and PDF creation
        image_files = []

        # Use ThreadPoolExecutor for parallel downloads
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for page in range(1, no_of_pages + 1):
                future = loop.run_in_executor(executor, download_page, page, book_id, user_folder)
                futures.append(future)
            await asyncio.gather(*futures)

        await stage.edit("Creating PDFs")

        # Create PDF from images using img2pdf
        pdf_path = f"{user_folder}{book_name}.pdf"
        await create_pdf_from_images([f"{user_folder}{page}.jpg" for page in range(1, no_of_pages + 1)], pdf_path)
        await stage.edit("__**Uploading**__")
        # Send PDF to user
        await client.send_document(
            chat_id=user_id, document=pdf_path, caption=f"Here is your book: {book_name}"
        )
        await stage.delete()

    except Exception as e:
        await message.reply(f"An error occurred: {e}")
    finally:
        # Clean up
        shutil.rmtree(user_folder, ignore_errors=True)
        user_tasks.pop(user_id, None)

# Create PDF from images
async def create_pdf_from_images(image_paths, output_pdf_path):
    pdf = FPDF()
    temp_images = []

    try:
        for image_path in image_paths:
            try:
                with Image.open(image_path) as img:
                    rgb_image = img.convert("RGB")
                    temp_path = f"{image_path}.temp.jpg"
                    rgb_image.save(temp_path, "JPEG", quality=85)
                    temp_images.append(temp_path)
                    pdf.add_page()
                    pdf.image(temp_path, x=10, y=10, w=190)
            except UnidentifiedImageError:
                continue

        pdf.output(output_pdf_path)
        await compress_pdf(output_pdf_path)

    finally:
        for temp_path in temp_images:
            if os.path.exists(temp_path):
                os.remove(temp_path)

# Compress PDF
async def compress_pdf(pdf_path):
    compressed_pdf_path = pdf_path.replace(".pdf", "_compressed.pdf")
    try:
        with open(pdf_path, "rb") as pdf:
            with open(compressed_pdf_path, "wb") as compressed:
                compressed.write(pdf.read())  # Placeholder for actual compression logic
        os.replace(compressed_pdf_path, pdf_path)
    except Exception as e:
        print(f"Compression failed: {e}")

# Run the bot
app.run()
