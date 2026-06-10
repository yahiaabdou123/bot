import asyncio
import logging
import hashlib
import time
import aiohttp
import random
import json
import os

from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command

# =========================
# CONFIG
# =========================


BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
TRACKING_ID = os.getenv("TRACKING_ID")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
BASE_URL = "https://api-sg.aliexpress.com/sync"

USD_TO_DZD = 260

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# =========================
# STORAGE
# =========================

PRODUCT_QUEUE = []
POSTED_FILE = "posted.json"
POSTED_IDS = set()
SEARCH_KEYWORDS = [ 
    "Smart Watch",
    "Wireless Earbuds",
    "Bluetooth Earbuds",
    "TWS Earbuds",
    "Gaming Headset",
    "Gaming Mouse",
    "Mechanical Keyboard",
    "RGB Keyboard",
    "Gaming Controller",
    "Phone Cooler",
    "Power Ban",
    "Fast Charger 65W",
    "USB C Cable",
    "Wireless Charger",
    "MagSafe Charger",
    "Phone Holder",
    "Magnetic Phone Holder",
    "Mini Projector",
    "Portable Projector",
    "Bluetooth Speaker",
    "Smart Ring",
    "Fitness Tracker",
    "Smart Home Device",
    "WiFi Camera",
    "Security Camera",
    "Dash Cam",
    "Car Phone Holder",
    "Car Charger",
    "CarPlay Adapter",
    "LED Strip Lights",
    "RGB Lights",
    "LED Matrix Display",
    "USB Hub",
    "USB C Hub",
    "Laptop Stand",
    "Bluetooth Mouse",
    "Portable SSD",
    "External Hard Drive",
    "Thermal Printer",
    "Mini Printer",
    "Air Duster",
    "Mini Vacuum Cleaner",
    "Portable Fan",
    "Rechargeable Flashlight",
    "Digital Alarm Clock",
    "Webcam HD",
    "Action Camera",
    "Drone Camera",
    "VR Headset",
    "Gamepad Mobile",
    "Streaming Microphone",
    "USB Microphone",
    "Tripod Phone",
    "Selfie Stick",
    "Ring Light",
    "Portable Monitor",
    "Mini PC",
    "Android TV Box",
    "Smart TV Stick",
    "Wireless Keyboard",
    "Wireless Mouse",
    "Solar Power Bank",
    "Wireless Security Camera",
    "Mini Bluetooth Speaker",
    "Noise Cancelling Earbuds",
    "Gaming Desk Accessories",
    "Tech Gadgets",
    "Cool Gadgets",
    "Trending Gadgets",
    "TikTok Gadgets",
    "Budget Tech",
    "Portable Electronics",
    "Gamer Accessories",
    "Mobile Accessories",
    "Smartphone Accessories",
    "RGB Gaming Setup",
    "USB Gadgets",
    "Electronic Gadgets",
    "Home Tech",
    "Car Tech Accessories",
    "Travel Gadgets",
    "Innovative Gadgets",
    "Wireless Devices",
    "Best Selling Electronics",
    "New Tech 2026",
    "Viral Products",
    "Hot Sale Electronics",
    "AliExpress Finds",
    "Must Have Gadgets",
    "Tech Gifts",
    "Student Gadgets",
    "Office Gadgets",
    "Desk Setup Accessories",
    "Gaming Setup Accessories",
    "Phone Accessories",
    "Laptop Accessories",
    "Computer Accessories",
    "Electronic Accessories",
    "Smart Devices",
    "Portable Tech Devices",
    "Wireless Technology",
    "Mini Electronic Devices",
    "Smartphone",
    "Future Tech Gadgets",
]

# =========================
# LOAD SAVED POSTS
# =========================

def load_posted():
    global POSTED_IDS
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            POSTED_IDS = set(json.load(f))

def save_posted():
    with open(POSTED_FILE, "w") as f:
        json.dump(list(POSTED_IDS), f)

# =========================
# SIGNATURE
# =========================

def generate_sign(params):
    s = APP_SECRET
    for k, v in sorted(params.items()):
        s += f"{k}{v}"
    s += APP_SECRET
    return hashlib.md5(s.encode()).hexdigest().upper()

# =========================
# API REQUEST
# =========================

async def api_request(method, extra):
    params = {
        "app_key": APP_KEY,
        "method": method,
        "timestamp": str(int(time.time() * 1000)),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
    }

    params.update(extra)
    params["sign"] = generate_sign(params)

    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL, data=params) as r:
            return await r.json()

# =========================
# FETCH PRODUCTS
# =========================

async def fill_queue():
    global PRODUCT_QUEUE

    keyword = random.choice(SEARCH_KEYWORDS)
    page = random.randint(1, 30)

    resp = await api_request(
        "aliexpress.affiliate.product.query",
        {
            "keywords": keyword,
            "page_no": page,
            "page_size": 1,
            "target_currency": "USD",
            "target_language": "FR",
            "tracking_id": TRACKING_ID,
            "sort": "LAST_VOLUME_DESC"
            "country": "DZ" 
        }
    )

    products = (
        resp.get("aliexpress_affiliate_product_query_response", {})
        .get("resp_result", {})
        .get("result", {})
        .get("products", {})
        .get("product", [])
    )

    PRODUCT_QUEUE = []

    for p in products:
        pid = str(p.get("product_id"))

        if pid in POSTED_IDS:
            continue

        # فلترة المنتجات الضعيفة
        try:
            price = float(p.get("target_sale_price", 0))
        except:
            continue

        volume = int(p.get("lastest_volume", 0))

        if price < 2:   # تجاهل المنتجات الرخيصة جداً
            continue

        if volume < 10:
            continue

        PRODUCT_QUEUE.append(p)

    print(f"Loaded {len(PRODUCT_QUEUE)} products for keyword: {keyword}")

# =========================
# FORMAT MESSAGE
# =========================

def build_caption(p):
    title = p.get("product_title", "No Title")[:120]

    try:
        usd = float(p.get("target_sale_price", 0))
    except:
        usd = 0

    dzd = int(usd * USD_TO_DZD)

    return f"""    
أفضل عروض💥Aliexpress🇩🇿الأكثر مبيعا و تقييما
━━━━━━━━━━━━━━━━━━━━━━━━━━ 
🔥 <b>{title}</b>

💵 السعر : {usd}$ | {dzd:,} دج
🔖 الخصم : {p.get('discount','N/A')}
🚀 عدد المبيعات : {p.get('lastest_volume','0')}
━━━━━━━━━━━━━━━━━━━━━━━━━━
              ⏬ اضغط على زر الشراء أسفل ⏬
"""

def build_button(link):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 شراء الآن", url=link)]
        ]
    )

# =========================
# POST LOOP
# =========================

async def post_loop():
    while True:

        if not PRODUCT_QUEUE:
            await fill_queue()

        if not PRODUCT_QUEUE:
            await asyncio.sleep(30)
            continue

        product = PRODUCT_QUEUE.pop(0)

        pid = str(product.get("product_id"))
        POSTED_IDS.add(pid)
        save_posted()

        try:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=product.get("product_main_image_url"),
                caption=build_caption(product),
                reply_markup=build_button(product.get("promotion_link"))
            )
        except Exception as e:
            print("ERROR SENDING:", e)

        await asyncio.sleep(900)  # 15 دقيقة

# =========================
# COMMANDS
# =========================

@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("✅ البوت يعمل الآن ويقوم بالنشر التلقائي.")

@dp.message(Command("test"))
async def test(m: Message):
    resp = await api_request(
        "aliexpress.affiliate.product.query",
        {
            "keywords": "headphones",
            "page_no": 1,
            "page_size": 5,
            "tracking_id": TRACKING_ID
        }
    )
    print(resp)
    await m.answer("تم إرسال النتيجة إلى الكونسول.")

# =========================
# MAIN
# =========================

async def main():
    print("BOT STARTED")

    load_posted()

    asyncio.create_task(post_loop())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
