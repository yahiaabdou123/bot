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
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = "https://api-sg.aliexpress.com/sync"

USD_TO_DZD = 260
MAX_SHIP_FEE = 7
MIN_VOLUME = 500
MIN_PRICE = 2
MIN_DISCOUNT = 10
POST_INTERVAL = 900

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

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
    "Smart Watch", "Wireless Earbuds", "Bluetooth Earbuds", "TWS Earbuds",
    "Gaming Headset", "Gaming Mouse", "Mechanical Keyboard", "RGB Keyboard",
    "Gaming Controller", "Phone Cooler", "Power Bank", "Fast Charger 65W",
    "USB C Cable", "Wireless Charger", "MagSafe Charger", "Phone Holder",
    "Magnetic Phone Holder", "Mini Projector", "Portable Projector",
    "Bluetooth Speaker", "Smart Ring", "Fitness Tracker", "Smart Home Device",
    "WiFi Camera", "Security Camera", "Dash Cam", "Car Phone Holder",
    "Car Charger", "CarPlay Adapter", "LED Strip Lights", "RGB Lights",
    "LED Matrix Display", "USB Hub", "USB C Hub", "Laptop Stand",
    "Bluetooth Mouse", "Portable SSD", "External Hard Drive", "Thermal Printer",
    "Mini Printer", "Air Duster", "Mini Vacuum Cleaner", "Portable Fan",
    "Rechargeable Flashlight", "Digital Alarm Clock", "Webcam HD",
    "Action Camera", "Drone Camera", "VR Headset", "Gamepad Mobile",
    "Streaming Microphone", "USB Microphone", "Tripod Phone", "Selfie Stick",
    "Ring Light", "Portable Monitor", "Mini PC", "Android TV Box",
    "Smart TV Stick", "Wireless Keyboard", "Wireless Mouse", "Solar Power Bank",
    "Wireless Security Camera", "Mini Bluetooth Speaker", "Noise Cancelling Earbuds",
    "Gaming Desk Accessories", "Tech Gadgets", "Cool Gadgets", "Trending Gadgets",
    "TikTok Gadgets", "Budget Tech", "Portable Electronics", "Gamer Accessories",
    "Mobile Accessories", "Smartphone Accessories", "RGB Gaming Setup",
    "USB Gadgets", "Electronic Gadgets", "Home Tech", "Car Tech Accessories",
    "Travel Gadgets", "Innovative Gadgets", "Wireless Devices",
    "Best Selling Electronics", "Viral Products", "Hot Sale Electronics",
    "AliExpress Finds", "Must Have Gadgets", "Tech Gifts", "Student Gadgets",
    "Office Gadgets", "Desk Setup Accessories", "Gaming Setup Accessories",
    "Phone Accessories", "Laptop Accessories", "Computer Accessories",
    "Electronic Accessories", "Smart Devices", "Portable Tech Devices",
    "Wireless Technology", "Mini Electronic Devices", "Smartphone",
    "Future Tech Gadgets",
]

# =========================
# LOAD / SAVE POSTED IDS
# =========================
def load_posted():
    global POSTED_IDS
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            POSTED_IDS = set(json.load(f))
    logging.info(f"Loaded {len(POSTED_IDS)} posted product IDs")

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
async def api_request(method, extra, retries=3):
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

    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(BASE_URL, data=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    return await r.json()
        except Exception as e:
            logging.warning(f"API request failed (attempt {attempt+1}/{retries}): {e}")
            await asyncio.sleep(2)
    return {}

# =========================
# AI TITLE SHORTENER
# =========================
async def shorten_title(title: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "max_tokens": 60,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"اختصر اسم هذا المنتج إلى جملة قصيرة واضحة بالفرنسية لا تتجاوز 8 كلمات مع ذكر علامة المنتج، بدون أي شرح إضافي:\n{title}"
                        }
                    ]
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                data = await r.json()
                short = data["choices"][0]["message"]["content"].strip()
                return short if short else title[:60]
    except Exception as e:
        logging.warning(f"AI title shortener failed: {e}")
        return title[:60]
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
# SHIPPING INFO
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
        return result if result else {}
    except:
        return {}

# =========================
# FETCH PRODUCTS
# =========================
async def fill_queue():
    global PRODUCT_QUEUE

    keywords_to_try = random.sample(SEARCH_KEYWORDS, min(15, len(SEARCH_KEYWORDS)))

    for keyword in keywords_to_try:
        try:
            resp = await api_request(
                "aliexpress.affiliate.hotproduct.query",
                {
                    "keywords": keyword,
                    "page_no": 1,
                    "page_size": 1,
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

            filtered = []
            for p in products:
                pid = str(p.get("product_id"))

                if pid in POSTED_IDS:
                    continue

                try:
                    price = float(p.get("target_sale_price", 0))
                except:
                    continue
                if price < MIN_PRICE:
                    continue

                try:
                    volume = int(p.get("lastest_volume", 0))
                except:
                    continue
                if volume < MIN_VOLUME:
                    continue

                try:
                    discount = int(str(p.get("discount", "0%")).replace("%", ""))
                except:
                    discount = 0
                if discount < MIN_DISCOUNT:
                    continue

                filtered.append(p)

            filtered.sort(key=lambda x: int(x.get("lastest_volume", 0)), reverse=True)
            logging.info(f"Loaded {len(filtered)} products for keyword: {keyword}")

            if filtered:
                PRODUCT_QUEUE = filtered
                break

        except Exception as e:
            logging.error(f"Error fetching products for '{keyword}': {e}")
            continue

# =========================
# FORMAT MESSAGE
# =========================
async def build_caption(p, shipping: dict) -> str:
    # اسم مختصر بالذكاء الاصطناعي
    title = await shorten_title(p.get("product_title", "No Title"))

    try:
        usd = float(p.get("target_sale_price", 0))
    except:
        usd = 0
    dzd = int(usd * USD_TO_DZD)

    # السعر الأصلي
    try:
        original_usd = float(p.get("target_original_price", usd))
        original_dzd = int(original_usd * USD_TO_DZD)
        original_line = f"<s>{original_usd}$ | {original_dzd:,} دج</s>"
    except:
        original_line = ""

    # الشحن
    fee = shipping.get("shipping_fee", "0")
    min_days = shipping.get("min_delivery_days", "?")
    max_days = shipping.get("max_delivery_days", "?")

    if fee == "0" or fee == "0.0":
        shipping_line = "مجاني ✅"
    else:
        try:
            fee_dzd = int(float(fee) * USD_TO_DZD)
            shipping_line = f"{fee}$ | {fee_dzd:,} دج"
        except:
            shipping_line = "راجع صفحة المنتج"

    # التقييم
    rating = p.get("evaluate_rate", "")
    rating_line = f"⭐ التقييم : {rating}" if rating else ""

    return f"""
🇩🇿 أفضل عروض Aliexpress 💥
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 <b>{title}</b>

{original_line}
💵 السعر : <b>{usd}$ | {dzd:,} دج</b>
🔖 الخصم : <b>{p.get('discount', 'N/A')}</b>
🚚 الشحن : {shipping_line}
🚀 المبيعات : {p.get('lastest_volume', '0')}+
{rating_line}
━━━━━━━━━━━━━━━━━━━━━━━━━━
⏬ اضغط على زر الشراء أسفله ⏬
"""

def build_button(link):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 شراء الآن على AliExpress", url=link)]
        ]
    )

# =========================
# POST LOOP
# =========================
async def post_loop():
    while True:
        try:
            if not PRODUCT_QUEUE:
                await fill_queue()

            if not PRODUCT_QUEUE:
                logging.warning("No products found, retrying in 60 seconds...")
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

            fee = shipping.get("shipping_fee", "0")
            try:
                if float(fee) >= MAX_SHIP_FEE:
                    logging.info(f"Skipping {pid} - high shipping: {fee}$")
                    continue
            except:
                pass

            link = await get_short_link(product.get("promotion_link", ""))
            caption = await build_caption(product, shipping)

            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=product.get("product_main_image_url"),
                caption=caption,
                reply_markup=build_button(link)
            )
            logging.info(f"Posted product {pid} | volume: {product.get('lastest_volume')} | fee: {fee}$")

        except Exception as e:
            logging.error(f"Error in post_loop: {e}")

        await asyncio.sleep(POST_INTERVAL)

# =========================
# COMMANDS
# =========================
@dp.message(Command("start"))
async def start(m: Message):
    await m.answer(
        "✅ <b>البوت يعمل الآن</b>\n\n"
        "📢 يقوم بنشر أفضل منتجات AliExpress كل 15 دقيقة\n"
        "🇩🇿 مخصص للسوق الجزائري\n\n"
        "الأوامر المتاحة:\n"
        "/status — حالة البوت\n"
        "/queue — عدد المنتجات في الانتظار"
    )

@dp.message(Command("status"))
async def status(m: Message):
    await m.answer(
        f"📊 <b>حالة البوت</b>\n\n"
        f"📦 المنتجات في الانتظار: {len(PRODUCT_QUEUE)}\n"
        f"✅ المنتجات المنشورة: {len(POSTED_IDS)}\n"
        f"⏱ الفترة بين المنشورات: {POST_INTERVAL // 60} دقيقة"
    )

@dp.message(Command("queue"))
async def queue_info(m: Message):
    if not PRODUCT_QUEUE:
        await m.answer("📭 قائمة الانتظار فارغة، سيتم جلب منتجات جديدة قريباً.")
    else:
        lines = [f"📦 <b>المنتجات في الانتظار: {len(PRODUCT_QUEUE)}</b>\n"]
        for i, p in enumerate(PRODUCT_QUEUE[:5], 1):
            lines.append(f"{i}. {p.get('product_title', '')[:60]}...")
        await m.answer("\n".join(lines))

# =========================
# MAIN
# =========================
async def main():
    logging.info("BOT STARTED")
    load_posted()
    asyncio.create_task(post_loop())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
