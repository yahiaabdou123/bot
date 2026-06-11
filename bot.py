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
MIN_VOLUME = 1000
MIN_PRICE = 2
MIN_DISCOUNT = 10
POST_INTERVAL = 900       # 15 دقيقة بين كل منشور

WEBSITE_URL = "https://your-site.com"
SOCIAL_URL = "https://t.me/yourchannel"
POST_COUNTER = 0

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
# STORAGE — مسارات ثابتة على Railway Volume
# =========================
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)

PRODUCT_QUEUE = []
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)
POSTED_FILE = os.path.join(DATA_DIR, "posted.json")
KEYWORD_INDEX_FILE = os.path.join(DATA_DIR, "keyword_index.json")

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
# STATS TRACKING
# =========================
BOT_STATS = {
    "total_posted": 0,
    "total_skipped": 0,
    "total_errors": 0,
    "start_time": time.time(),
}

# =========================
# LOAD / SAVE HELPERS
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

def load_keyword_index():
    global KEYWORD_INDEX
    if os.path.exists(KEYWORD_INDEX_FILE):
        with open(KEYWORD_INDEX_FILE, "r") as f:
            data = json.load(f)
            KEYWORD_INDEX = data.get("index", 0) % len(SEARCH_KEYWORDS)
    logging.info(f"Starting from keyword index {KEYWORD_INDEX}: {SEARCH_KEYWORDS[KEYWORD_INDEX]}")

def save_keyword_index():
    with open(KEYWORD_INDEX_FILE, "w") as f:
        json.dump({"index": KEYWORD_INDEX}, f)

def next_keyword() -> str:
    """يرجع الكلمة التالية في الدورة ويقدّم الفهرس."""
    global KEYWORD_INDEX
    keyword = SEARCH_KEYWORDS[KEYWORD_INDEX]
    KEYWORD_INDEX = (KEYWORD_INDEX + 1) % len(SEARCH_KEYWORDS)
    save_keyword_index()
    return keyword

# =========================
# SIGNATURE
# =========================
def generate_sign(params: dict) -> str:
    s = APP_SECRET
    for k, v in sorted(params.items()):
        s += f"{k}{v}"
    s += APP_SECRET
    return hashlib.md5(s.encode()).hexdigest().upper()

# =========================
# API REQUEST (مع إعادة المحاولة والانتظار التدريجي)
# =========================
async def api_request(method: str, extra: dict, retries: int = 3) -> dict:
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
                async with session.post(
                    BASE_URL,
                    data=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as r:
                    return await r.json()
        except Exception as e:
            wait = 2 ** attempt
            logging.warning(f"API request failed (attempt {attempt+1}/{retries}): {e}. Retrying in {wait}s…")
            await asyncio.sleep(wait)
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
                    "Authorization": f"Bearer {GROQ_API_KEY}"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "max_tokens": 60,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "اختصر اسم هذا المنتج إلى جملة قصيرة واضحة بالفرنسية "
                                "لا تتجاوز 8 كلمات مع ذكر علامة المنتج، "
                                "بدون أي شرح إضافي:\n" + title
                            )
                        }
                    ]
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                data = await r.json()
                short = data["choices"][0]["message"]["content"].strip()
                short = short.strip('"\'')
                return short if short else title[:60]
    except Exception as e:
        logging.warning(f"AI title shortener failed: {e}")
        return title[:60]

# =========================
# SHORT LINK
# =========================
async def get_short_link(original_url: str) -> str:
    if not original_url:
        return original_url
    try:
        resp = await api_request(
            "aliexpress.affiliate.link.generate",
            {
                "promotion_link_type": "0",
                "source_values": original_url,
                "tracking_id": TRACKING_ID,
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
    except Exception as e:
        logging.warning(f"Short link failed: {e}")
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
                "target_language": "FR",
            }
        )
        result = (
            resp.get("aliexpress_affiliate_product_shipping_get_response", {})
            .get("resp_result", {})
            .get("result", {})
        )
        return result if result else {}
    except Exception as e:
        logging.warning(f"Shipping info failed: {e}")
        return {}

# =========================
# FETCH PRODUCT — عشوائي (للمنشورات الأولى)
# =========================
async def fetch_product_query():
    for _ in range(10):
        keyword = random.choice(SEARCH_KEYWORDS)
        try:
            resp = await api_request(
                "aliexpress.affiliate.product.query",
                {
                    "keywords": keyword,
                    "page_no": random.randint(1, 5),
                    "page_size": 50,
                    "target_currency": "USD",
                    "target_language": "FR",
                    "tracking_id": TRACKING_ID,
                    "ship_to_country": "DZ",
                }
            )

            products = (
                resp.get("aliexpress_affiliate_product_query_response", {})
                .get("resp_result", {})
                .get("result", {})
                .get("products", {})
                .get("product", [])
            )

            filtered = []
            for p in products:
                pid = str(p.get("product_id", ""))
                if not pid or pid in POSTED_IDS:
                    continue
                try:
                    price = float(p.get("target_sale_price", 0))
                    volume = int(p.get("lastest_volume", 0))
                    discount = int(str(p.get("discount", "0")).replace("%", ""))
                except Exception:
                    continue
                if price < MIN_PRICE or volume < MIN_VOLUME or discount < MIN_DISCOUNT:
                    continue
                if not p.get("product_main_image_url"):
                    continue
                filtered.append(p)

            if filtered:
                # ✅ إصلاح: اختيار المنتج الأعلى مبيعاً بدل العشوائي
                return max(filtered, key=lambda x: int(x.get("lastest_volume", 0)))

        except Exception as e:
            logging.error(e)

    return None

# =========================
# FETCH ONE PRODUCT — كلمة مفتاحية واحدة لكل دورة
# =========================
async def fetch_one_product() -> dict | None:
    """
    يستخدم الكلمة التالية في الدورة، يجلب المنتجات، يفلترها،
    ويرجع المنتج الأعلى مبيعاً.
    يجرب 10 كلمات متتالية إذا لم يجد نتائج.
    """
    for _ in range(min(10, len(SEARCH_KEYWORDS))):
        keyword = next_keyword()
        logging.info(f"Searching with keyword: '{keyword}'")
        try:
            resp = await api_request(
                "aliexpress.affiliate.hotproduct.query",
                {
                    "keywords": keyword,
                    "page_no": random.randint(1, 3),
                    "page_size": 20,
                    "target_currency": "USD",
                    "target_language": "FR",
                    "tracking_id": TRACKING_ID,
                    "sort": "LAST_VOLUME_DESC",
                    "ship_to_country": "DZ",
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
                pid = str(p.get("product_id", ""))
                if not pid or pid in POSTED_IDS:
                    continue
                try:
                    price = float(p.get("target_sale_price", 0))
                except (ValueError, TypeError):
                    continue
                if price < MIN_PRICE:
                    continue
                try:
                    volume = int(p.get("lastest_volume", 0))
                except (ValueError, TypeError):
                    continue
                if volume < MIN_VOLUME:
                    continue
                try:
                    discount = int(str(p.get("discount", "0%")).replace("%", ""))
                except (ValueError, TypeError):
                    discount = 0
                if discount < MIN_DISCOUNT:
                    continue
                if not p.get("product_main_image_url"):
                    continue
                filtered.append(p)

            if not filtered:
                logging.info(f"Keyword '{keyword}': no valid products, trying next…")
                continue

            # ✅ إصلاح: اختيار المنتج الأعلى مبيعاً بدل العشوائي
            best = max(filtered, key=lambda x: int(x.get("lastest_volume", 0)))
            logging.info(
                f"Keyword '{keyword}': picked product {best.get('product_id')} "
                f"| volume: {best.get('lastest_volume')}"
            )
            return best

        except Exception as e:
            logging.error(f"Error fetching products for '{keyword}': {e}")
            continue

    logging.warning("No valid product found after trying 10 keywords.")
    return None

# =========================
# FORMAT MESSAGE
# =========================
def format_stars(rating_str: str) -> str:
    """تحويل التقييم مثل '96%' أو '4.8' إلى نجوم."""
    try:
        if "%" in rating_str:
            pct = float(rating_str.replace("%", ""))
            score = pct / 20
        else:
            score = float(rating_str)
        full = int(score)
        half = 1 if (score - full) >= 0.4 else 0
        empty = 5 - full - half
        return "★" * full + ("★" if half else "") + "☆" * empty
    except Exception:
        return rating_str

async def build_caption(p: dict, shipping: dict) -> str:
    title = await shorten_title(p.get("product_title", "No Title"))

    try:
        usd = float(p.get("target_sale_price", 0))
    except (ValueError, TypeError):
        usd = 0.0
    dzd = int(usd * USD_TO_DZD)

    # السعر الأصلي
    try:
        original_usd = float(p.get("target_original_price", usd))
        if original_usd > usd:
            original_dzd = int(original_usd * USD_TO_DZD)
            original_line = f"<s>{original_usd:.2f}$ | {original_dzd:,} دج</s>"
        else:
            original_line = ""
    except (ValueError, TypeError):
        original_line = ""

    # الشحن
    fee = str(shipping.get("shipping_fee", "0"))
    min_days = shipping.get("min_delivery_days", "?")
    max_days = shipping.get("max_delivery_days", "?")
    delivery_line = f"⏱ التوصيل : {min_days}-{max_days} يوم" if min_days != "?" else ""

    try:
        fee_float = float(fee)
    except (ValueError, TypeError):
        fee_float = None

    if fee_float is None:
        shipping_line = "راجع صفحة المنتج"
    elif fee_float == 0:
        shipping_line = "مجاني ✅"
    else:
        fee_dzd = int(fee_float * USD_TO_DZD)
        shipping_line = f"{fee_float:.2f}$ | {fee_dzd:,} دج"

    # التقييم
    rating_raw = p.get("evaluate_rate", "")
    if rating_raw:
        stars = format_stars(str(rating_raw))
        rating_line = f"⭐ التقييم : {stars} ({rating_raw})"
    else:
        rating_line = ""

    discount = p.get("discount", "N/A")

    lines = [
        "🇩🇿 أفضل عروض Aliexpress 💥",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🔥 <b>{title}</b>",
        "",
    ]
    if original_line:
        lines.append(original_line)
    lines += [
        f"💵 السعر : <b>{usd:.2f}$ | {dzd:,} دج</b>",
        f"🚚 الشحن : {shipping_line}",
    ]
    if delivery_line:
        lines.append(delivery_line)
    lines.append(f"🚀 المبيعات : {p.get('lastest_volume', '0')}+")
    if rating_line:
        lines.append(rating_line)
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "⏬ اضغط على زر الشراء أسفل ⏬",
    ]

    return "\n".join(lines)

def build_button(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 شراء الآن", url=link)],
            [
                InlineKeyboardButton(text="🌐 الموقع الإلكتروني", url=WEBSITE_URL),
                InlineKeyboardButton(text="📱 صفحات التواصل", url=SOCIAL_URL)
            ]
        ]
    )

# =========================
# POST LOOP
# =========================
async def post_loop():
    while True:
        try:
            global POST_COUNTER

            if POST_COUNTER < 5:
                product = await fetch_product_query()
            else:
                product = await fetch_one_product()

            if not product:
                logging.warning("No product found this cycle. Waiting 60s…")
                await asyncio.sleep(60)
                continue

            pid = str(product.get("product_id", ""))

            if pid in POSTED_IDS:
                logging.info(f"Product {pid} already posted, skipping.")
                continue

            price = str(product.get("target_sale_price", "0"))
            sku_id = str(product.get("sku_id", ""))
            tax_rate = str(product.get("tax_rate", "0.00"))

            shipping = await get_shipping_info(pid, price, sku_id, tax_rate)

            fee_raw = shipping.get("shipping_fee", "0")
            try:
                if float(fee_raw) >= MAX_SHIP_FEE:
                    logging.info(f"Skipping {pid} — high shipping: {fee_raw}$")
                    BOT_STATS["total_skipped"] += 1
                    continue
            except (ValueError, TypeError):
                pass

            link = await get_short_link(product.get("promotion_link", ""))
            caption = await build_caption(product, shipping)

            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=product.get("product_main_image_url"),
                caption=caption,
                reply_markup=build_button(link),
            )

            POSTED_IDS.add(pid)
            save_posted()
            BOT_STATS["total_posted"] += 1

            POST_COUNTER += 1
            if POST_COUNTER >= 6:
                POST_COUNTER = 0

            logging.info(
                f"✅ Posted {pid} | volume: {product.get('lastest_volume')} "
                f"| fee: {fee_raw}$ | keyword index now: {KEYWORD_INDEX}"
            )

        except Exception as e:
            BOT_STATS["total_errors"] += 1
            logging.error(f"Error in post_loop: {e}", exc_info=True)

        await asyncio.sleep(POST_INTERVAL)

# =========================
# COMMANDS
# =========================
@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer(
        "✅ <b>البوت يعمل الآن</b>\n\n"
        "📢 يقوم بنشر أفضل منتجات AliExpress كل 15 دقيقة\n"
        "🇩🇿 مخصص للسوق الجزائري\n\n"
        "<b>الأوامر المتاحة:</b>\n"
        "/status — حالة البوت\n"
        "/queue — عدد المنتجات في الانتظار\n"
        "/keyword — الكلمة المفتاحية الحالية\n"
        "/stats — إحصائيات المنشورات"
    )

@dp.message(Command("status"))
async def cmd_status(m: Message):
    uptime_sec = int(time.time() - BOT_STATS["start_time"])
    hours, rem = divmod(uptime_sec, 3600)
    minutes = rem // 60
    await m.answer(
        f"📊 <b>حالة البوت</b>\n\n"
        f"📦 المنتجات في الانتظار: {len(PRODUCT_QUEUE)}\n"
        f"✅ المنتجات المنشورة: {len(POSTED_IDS)}\n"
        f"⏱ الفترة بين المنشورات: {POST_INTERVAL // 60} دقيقة\n"
        f"🕐 وقت التشغيل: {hours}h {minutes}m"
    )

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    await m.answer(
        f"📈 <b>إحصائيات الجلسة</b>\n\n"
        f"✅ منشور: {BOT_STATS['total_posted']}\n"
        f"⏭ تخطي: {BOT_STATS['total_skipped']}\n"
        f"❌ أخطاء: {BOT_STATS['total_errors']}\n"
        f"🔑 عدد الكلمات المفتاحية: {len(SEARCH_KEYWORDS)}\n"
        f"📌 الكلمة التالية: <b>{SEARCH_KEYWORDS[KEYWORD_INDEX]}</b>"
    )

@dp.message(Command("keyword"))
async def cmd_keyword(m: Message):
    current = SEARCH_KEYWORDS[KEYWORD_INDEX]
    next_kw = SEARCH_KEYWORDS[(KEYWORD_INDEX + 1) % len(SEARCH_KEYWORDS)]
    await m.answer(
        f"🔍 <b>الكلمة الحالية:</b> {current}\n"
        f"➡️ <b>التالية:</b> {next_kw}\n"
        f"📌 <b>الرقم:</b> {KEYWORD_INDEX + 1} / {len(SEARCH_KEYWORDS)}"
    )

@dp.message(Command("queue"))
async def cmd_queue(m: Message):
    if not PRODUCT_QUEUE:
        await m.answer("📭 قائمة الانتظار فارغة، سيتم جلب منتجات جديدة قريباً.")
    else:
        lines = [f"📦 <b>المنتجات في الانتظار: {len(PRODUCT_QUEUE)}</b>\n"]
        for i, p in enumerate(PRODUCT_QUEUE[:5], 1):
            lines.append(f"{i}. {p.get('product_title', '')[:55]}…")
        await m.answer("\n".join(lines))

# =========================
# MAIN
# =========================
async def main():
    logging.info("BOT STARTED")
    load_posted()
    load_keyword_index()
    asyncio.create_task(post_loop())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
