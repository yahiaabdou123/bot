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
    "Power Bank",
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
# SHORT LINK
# =========================

async def get_short_link(original_url: str) -> str:
    try:
        resp = await api_request(
            "aliexpress.affiliate.link.generate",
            {
                "promotion_link_type": "0",
                "source_values": original_url,
                "tracking_id": TRACKING_ID
            }
        )
        links = (
            resp.get("aliexpress_affiliate_link_generate_response", {})
            .get("resp_result", {})
            .get("result", {})
            .get("promotion_links", {})
            .get("promotion_link", [])
        )
        if links:
            return links[0].get("promotion_link", original_url)
        return original_url
    except:
        return original_url

# =========================
# PRODUCT DETAIL
# =========================

async def get_shipping_info(product_id: str, price: str, sku_id: str, tax_rate: str) -> dict:
    try:
        resp = await api_request(
            "aliexpress.affiliate.product.shipping.get",
            {
                "product_id": product_id,
                "sku_id": sku_id,
                "tax_rate": tax_rate,
                "tracking_id": TRACKING_ID,
                "ship_to_country": "DZ",
                "target_currency": "USD",
                "target_sale_price": price,
                "target_language": "FR"
            }
        )

        result = (
            resp.get("aliexpress_affiliate_product_shipping_get_response", {})
            .get("resp_result", {})
            .get("result", {})
        )

        if not result:
            return {}

        return result

    except:
        return {}
# =========================
# FETCH PRODUCTS
# =========================

async def fill_queue():
    global PRODUCT_QUEUE

    # تجربة كلمات مختلفة حتى يجد منتجات
    keywords_to_try = random.sample(SEARCH_KEYWORDS, min(10, len(SEARCH_KEYWORDS)))

    for keyword in keywords_to_try:
        resp = await api_request(
            "aliexpress.affiliate.hotproduct.query",
            {
                "keywords": keyword,
                "page_no": 1,
                "page_size": 20,
                "target_currency": "USD",
                "target_language": "FR",
                "tracking_id": TRACKING_ID,
                "sort": "LAST_VOLUME_DESC",
                "ship_to_country": "DZ"
            }
        )

        products = (
            resp.get("aliexpress_affiliate_hotproduct_query_response", {})
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

            try:
                price = float(p.get("target_sale_price", 0))
            except:
                continue

            volume = int(p.get("lastest_volume", 0))

            if price < 2:
                continue

            if volume < 100:
                continue

            PRODUCT_QUEUE.append(p)

        PRODUCT_QUEUE.sort(key=lambda x: int(x.get("lastest_volume", 0)), reverse=True)

        print(f"Loaded {len(PRODUCT_QUEUE)} products for keyword: {keyword}")

        if PRODUCT_QUEUE:
            break  # وجد منتجات، توقف عن المحاولة

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

    shipping = p.get("shipping_info", {})

    fee = shipping.get("shipping_fee", "0")
    min_days = shipping.get("min_delivery_days", "?")
    max_days = shipping.get("max_delivery_days", "?")
    from_country = shipping.get("ship_from_country", "?")

    if fee == "0" or fee == "0.0":
        shipping_line = "مجاني ✅"
    else:
        try:
            fee_dzd = int(float(fee) * USD_TO_DZD)
            shipping_line = f"{fee}$ | {fee_dzd:,} دج"
        except:
            shipping_line = "راجع صفحة المنتج"

    return f"""
أفضل عروض💥Aliexpress🇩🇿الأكثر مبيعا و تقييما
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 <b>{title}</b>

💵 السعر : {usd}$ | {dzd:,} دج
🚚 الشحن : {shipping_line}
📦 مدة التوصيل : {min_days} - {max_days} يوم
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
            print("No products found, retrying in 60 seconds...")
            await asyncio.sleep(60)
            continue

        product = PRODUCT_QUEUE.pop(0)

        pid = str(product.get("product_id"))
        POSTED_IDS.add(pid)
        save_posted()

        price = product.get("target_sale_price", "0")
        sku_id = str(product.get("sku_id", ""))
        tax_rate = str(product.get("tax_rate", "0.00"))
        shipping = await get_shipping_info(pid, price, sku_id, tax_rate)
        product["shipping_info"] = shipping      
              
        fee = shipping.get("shipping_fee", "0")
                try:
                    if float(fee) >= 5:
                        print(f"Skipping product {pid} - shipping fee {fee}$")
                        continue
                except:
                    pass

                product["shipping_info"] = shipping
        link = await get_short_link(product.get("promotion_link"))

        try:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=product.get("product_main_image_url"),
                caption=build_caption(product),
                reply_markup=build_button(link)
            )
        except Exception as e:
            print("ERROR SENDING:", e)

        await asyncio.sleep(900)

# =========================
# COMMANDS
# =========================

@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("✅ البوت يعمل الآن ويقوم بالنشر التلقائي.")
@dp.message(Command("test"))
async def test(m: Message):
    resp = await api_request(
        "aliexpress.affiliate.product.shipping.get",
        {
            "product_id": "1005012397551535",
            "sku_id": "12000058297248839",
            "tax_rate": "0.00",
            "tracking_id": TRACKING_ID,
            "ship_to_country": "DZ",
            "target_currency": "USD",
            "target_sale_price": "12.08",
            "target_language": "FR"
        }
    )
    print(json.dumps(resp, indent=2, ensure_ascii=False))
    await m.answer("تم إرسال نتيجة الشحن إلى الكونسول.")
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
