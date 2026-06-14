import asyncio
import logging
import hashlib
import time
import aiohttp
import random
import json
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
TRACKING_ID = os.getenv("TRACKING_ID", "Telegram")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = "https://api-sg.aliexpress.com/sync"


USD_TO_DZD = 250
MAX_SHIP_FEE = 1
MIN_VOLUME = 1000
MIN_PRICE = 1
MIN_DISCOUNT = 10
POST_INTERVAL = 900          # 15 دقيقة بين كل نشر تلقائي
MANUAL_POST_INTERVAL = 3600  # ساعة بين كل منشور يدوي
MIN_GAP_BETWEEN_ANY = 300    # 5 دقائق على الأقل بين أي نشرين (تلقائي أو يدوي)

WEBSITE_URL = "https://www.facebook.com/profile.php?id=61590394005859"
SOCIAL_URL = "https://www.facebook.com/profile.php?id=61590394005859"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout
)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# =========================
# STORAGE
# =========================
DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)

PRODUCT_QUEUE = []
POSTED_IDS = set()
KEYWORD_INDEX = 0
POSTED_FILE = os.path.join(DATA_DIR, "posted.json")
KEYWORD_INDEX_FILE = os.path.join(DATA_DIR, "keyword_index.json")

SEARCH_KEYWORDS = [
    "Baseus Earbuds", "Galaxy Projector", "QCY Earbuds",
    "Redragon Mechanical Keyboard", "Bluetooth Speaker", "Sonoff Smart Switch",
    "Amazfit Smart Watch", "Portable Monitor", "Haylou Earbuds", "Phone Case",
    "DJI Drone", "UGREEN Fast Charger", "RGB Light Bar", "COLMI Smart Watch",
    "Anker Soundcore Earbuds", "Car Accessories", "Sunset Lamp", "Lenovo Earbuds",
    "Wireless Charger", "Attack Shark Mouse", "Bluetooth Keyboard",
    "Xiaomi Smartphone", "Night Light", "Gaming Headset", "Mcdodo Fast Charger",
    "Edifier Earbuds", "Security Camera", "Mini Projector", "Zeblaze Smart Watch",
    "Bluetooth Adapter", "Yeelight LED Strip", "Baseus Power Bank",
    "Smart LED Lights", "GoPro Accessories", "KOSPET Smart Watch", "RGB Mouse Pad",
    "Portable Speaker", "Bluetooth Mouse", "Vacuum Cleaner", "JOYROOM Phone Holder",
    "Crystal Lamp", "POCO Smartphone", "Bluetooth Gamepad", "Aqara Sensor",
    "Mechanical Keyboard", "SoundPEATS Earbuds", "WiFi Camera", "Desk Lamp",
    "Insta360 Camera", "Essager Fast Charger", "Moon Lamp", "Bluetooth Receiver",
    "Haylou Smart Watch", "Dash Cam", "Anker Charger", "Room Decor",
    "Bluetooth Microphone", "Neon Sign", "Gaming Mouse", "AKASO Camera",
    "BroadLink Smart Home", "Baseus Fast Charger", "Toocki Fast Charger",
    "Blackview Smart Watch", "Electric Screwdriver", "UGREEN Power Bank",
    "Bluetooth Transmitter", "Wall Decor", "Aula Keyboard", "Tuya Smart Plug",
    "Noise Cancelling Headphones", "USB C Cable", "Smart LED Strip", "Smart Home",
    "Baseus Earphones", "MagSafe Accessories", "Smart Watch", "TWS Earbuds",
    "Bluetooth Headphones", "Smartphone Accessories", "Govee RGB Lights",
    "Machenike Keyboard", "Redmi Smartphone", "TOZO Earbuds",
    "Baseus Phone Holder", "JOYROOM Fast Charger", "Fast Charger", "Power Bank",
    "Phone Holder", "Wireless Earbuds", "Smart Lamp", "RGB Lights",
    "Gaming Keyboard", "Bluetooth Devices", "LED Strip Lights", "Smart Camera",
    "Home Decor", "Portable Charger", "Smart Gadgets", "Smart Gadgets", "Baseus Power Bank",
    "Redragon Mechanical Keyboard",
    "OnePlus 15",
    "Anker Soundcore Earbuds",
    "DJI Drone",
    "Honor 400 Pro",
    "Attack Shark Mouse",
    "UGREEN Fast Charger",
    "Amazfit Smart Watch",
    "Xiaomi 15 Ultra",
    "Bluetooth Speaker",
    "Insta360 Camera",
    "POCO F7 Ultra",
    "QCY Earbuds",
    "Sonoff Smart Switch",
    "Google Pixel 9 Pro",
    "Gaming Headset",
    "RedMagic 10 Pro",
    "Edifier Headphones",
    "Tuya Security Camera",
    "Realme 16 Pro Plus",
    "Mechanical Keyboard",
    "Haylou Smart Watch",
    "OPPO Find X8 Pro",
    "Power Bank",
    "DJI Gimbal",
    "Lenovo Earbuds",
    "Vivo X200 Pro",
    "Smart Home",
    "Redmi Earbuds",
    "KOSPET Rugged Smart Watch",
    "Honor Magic 7 Pro",
    "Govee RGB Lights",
    "UGREEN Power Bank",
    "Nothing Phone 3a Pro",
    "Redragon Gaming Mouse",
    "CMF Phone 2 Pro",
    "Yeelight Desk Lamp",
    "Baseus Earbuds",
    "iQOO 13",
    "Aqara Door Sensor",
    "Edifier Bluetooth Speaker",
    "POCO X8 Pro",
    "Wireless Earbuds",
    "Google Pixel 9",
    "COLMI Smart Watch",
    "DOOGEE V Max",
    "Insta360 Accessories",
    "Xiaomi 15 Pro",
    "Tuya Smart Plug",
    "QCY Headphones",
    "Redmi Note 15 Pro Plus",
    "Zeblaze Smart Watch",
    "Blackview Shark 9",
    "Govee TV Backlight",
    "Lenovo Smart Watch",
    "Ulefone Armor 30",
    "Haylou Earbuds",
    "POCO Phone Case",
    "Amazfit Smart Band",
    "Joyroom Phone Holder",
    "Essager USB C Cable",
    "5G Smartphone",
    "12GB RAM",
    "256GB",
    "512GB",
    "Global Version",
    "NFC",
    "POCO F7",
    "Samsung Galaxy S25 Ultra",
    "OnePlus 15R",
    "Honor 400",
    "Realme 16 Pro",
    "Vivo X200",
    "OPPO Find X8",
    "Nothing Phone 3a",
    "nubia Z70 Ultra",
    "Redmi Note 15 Pro",
    "Redmi Note 15",
    "POCO M8",
    "CMF Phone 2 Pro",
    "Xiaomi 15",
    "COLMI Smart Band",
    "Yeelight LED Strip",
    "Smart Watch",
    "Bluetooth Earbuds",
    "Portable Speaker",
    "Fast Charger",
    "Phone Holder",
    "USB C Cable",
    "Wireless Charger",
    "Magnetic Power Bank",
    "Mini PC",
    "Android Tablet",
    "Gaming Mouse",
    "Gaming Keyboard",
    "Portable Monitor",
    "Mini Projector",
    "WiFi Camera",
    "Robot Vacuum",
    "Electric Scooter",
    "Dash Camera",
    "Action Camera",
]

# =========================
# STATS
# =========================
BOT_STATS = {
    "total_posted": 0,
    "total_skipped": 0,
    "total_errors": 0,
    "start_time": time.time(),
}

# =========================
# TIMING — وقت آخر نشر منفصل لكل نوع
# =========================
LAST_AUTO_POST_TIME = 0    # آخر نشر تلقائي
LAST_MANUAL_POST_TIME = 0  # آخر نشر يدوي
LAST_ANY_POST_TIME = 0     # آخر أي نشر (لمنع التعارض)

# =========================
# LOAD / SAVE
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
# API REQUEST
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
                    BASE_URL, data=params,
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
                                "لا تتجاوز 8 كلمات مع ذكر علامة المنتج إن وجدت، "
                                "بدون أي شرح إضافي:\n" + title
                            )
                        }
                    ]
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                data = await r.json()
                short = data["choices"][0]["message"]["content"].strip().strip('"\'')
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
# جلب SKU (الخيارات مع الصور)
# =========================
async def get_sku_details(product_id: str) -> list:
    try:
        resp = await api_request(
            "aliexpress.affiliate.product.sku.detail.get",
            {
                "product_id": product_id,
                "target_currency": "USD",
                "target_language": "EN",
                "tracking_id": TRACKING_ID,
                "ship_to_country": "DZ",
            }
        )
        skus = (
            resp.get("aliexpress_affiliate_product_sku_detail_get_response", {})
            .get("result", {})
            .get("result", {})
            .get("ae_item_sku_info", {})
            .get("traffic_sku_info_list", [])
        )
        return skus if skus else []
    except Exception as e:
        logging.warning(f"SKU fetch failed: {e}")
        return []

# =========================
# تحليل SKU
# =========================
def parse_skus(skus: list) -> list:
    results = []
    seen_images = set()
    for sku in skus:
        try:
            sale_price = float(sku.get("sale_price_with_tax", 0))
            original_price = float(sku.get("price_with_tax", sale_price))
            discount = sku.get("discount_rate", "")
            image = sku.get("sku_image_link", "")
            link = sku.get("link", "")

            props_raw = sku.get("sku_properties", "[]")
            try:
                props = json.loads(props_raw)
                prop_name = list(props[0].keys())[0] if props else "خيار"
                prop_value = list(props[0].values())[0] if props else str(sku.get("color", ""))
            except:
                prop_name = "خيار"
                prop_value = str(sku.get("color", ""))

            if image and image in seen_images:
                continue
            if image:
                seen_images.add(image)

            results.append({
                "prop_name": prop_name,
                "prop_value": prop_value,
                "sale_price": sale_price,
                "original_price": original_price,
                "discount": discount,
                "image": image,
                "link": link,
            })
        except:
            continue

    results.sort(key=lambda x: x["sale_price"])
    return results

# =========================
# FORMAT MESSAGE — النشر التلقائي
# =========================
def format_stars(rating_str: str) -> str:
    try:
        if "%" in rating_str:
            score = float(rating_str.replace("%", "")) / 20
        else:
            score = float(rating_str)
        full = int(score)
        half = 1 if (score - full) >= 0.4 else 0
        empty = 5 - full - half
        return "★" * full + ("★" if half else "") + "☆" * empty
    except Exception:
        return rating_str

async def build_caption(p: dict, shipping: dict) -> str:
    """تنسيق النشر التلقائي"""
    title = await shorten_title(p.get("product_title", "No Title"))

    try:
        usd = float(p.get("target_sale_price", 0))
    except (ValueError, TypeError):
        usd = 0.0
    dzd = int(usd * USD_TO_DZD)

    try:
        original_usd = float(p.get("target_original_price", usd))
        if original_usd > usd:
            original_dzd = int(original_usd * USD_TO_DZD)
            original_line = f"<s>{original_usd:.2f}$ | {original_dzd:,} دج</s>"
        else:
            original_line = ""
    except (ValueError, TypeError):
        original_line = ""

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

    rating_raw = p.get("evaluate_rate", "")
    if rating_raw:
        stars = format_stars(str(rating_raw))
        rating_line = f"⭐ التقييم : {stars} ({rating_raw})"
    else:
        rating_line = ""

    lines = [
        "🇩🇿 منتج يستحق الشراء 🔥📢📢📢🔥",
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
        "AFFIXON-express | لافار تاع AliExpress 💯",
    ]

    return "\n".join(lines)

# =========================
# FORMAT MESSAGE — النشر اليدوي (تنسيق مختلف تماماً)
# =========================
async def build_manual_caption(p: dict, shipping: dict) -> str:
    """تنسيق النشر اليدوي — مختلف كلياً عن التلقائي"""
    title = await shorten_title(p.get("product_title", "No Title"))

    try:
        usd = float(p.get("target_sale_price", 0))
    except:
        usd = 0.0
    dzd = int(usd * USD_TO_DZD)

    try:
        original_usd = float(p.get("target_original_price", usd))
        if original_usd > usd:
            original_dzd = int(original_usd * USD_TO_DZD)
            original_line = f"<s>{original_usd:.2f}$ | {original_dzd:,} دج</s>"
            saving = original_usd - usd
            saving_dzd = int(saving * USD_TO_DZD)
            saving_line = f"💰 وفّر : <b>{saving:.2f}$ | {saving_dzd:,} دج</b>"
        else:
            original_line = ""
            saving_line = ""
    except:
        original_line = ""
        saving_line = ""

    fee = str(shipping.get("shipping_fee", "0"))
    min_days = shipping.get("min_delivery_days", "?")
    max_days = shipping.get("max_delivery_days", "?")
    delivery_line = f"📅 يصل خلال : {min_days}-{max_days} يوم" if min_days != "?" else ""

    try:
        fee_float = float(fee)
        if fee_float == 0:
            shipping_line = "مجاني ✅"
        else:
            fee_dzd = int(fee_float * USD_TO_DZD)
            shipping_line = f"{fee_float:.2f}$ | {fee_dzd:,} دج"
    except:
        shipping_line = "راجع صفحة المنتج"

    rating_raw = p.get("evaluate_rate", "")
    if rating_raw:
        stars = format_stars(str(rating_raw))
        rating_line = f"⭐ {stars} ({rating_raw})"
    else:
        rating_line = ""

    discount = p.get("discount", "")
    volume = p.get("lastest_volume", "0")

    lines = [
        "🛍 <b>منتج مختار بعناية</b> 👇",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"✨ <b>{title}</b>",
        "",
    ]
    if original_line:
        lines.append(f"🏷 السعر الأصلي : {original_line}")
    lines.append(f"💵 السعر الآن : <b>{usd:.2f}$ | {dzd:,} دج</b>")
    lines.append(f"📦 الشحن : {shipping_line}")
    if delivery_line:
        lines.append(delivery_line)
    if rating_line:
        lines.append(f"⭐ التقييم : {rating_line}")
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "💡 منتج أنصح به شخصياً 🤝",
        "AFFIXON-express | لافار تاع AliExpress 💯",
    ]

    return "\n".join(lines)

def build_button(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 شراء الآن على Aliexpress", url=link)],
            [
                InlineKeyboardButton(text="🌐 الموقع الإلكتروني", url=WEBSITE_URL),
                InlineKeyboardButton(text="📱 صفحة التواصل", url=SOCIAL_URL)
            ]
        ]
    )

# =========================
# إرسال الخيارات كـ Album
# =========================
async def send_sku_album(chat_id: int, skus: list, title: str):
    if not skus:
        return

    skus_with_images = [s for s in skus if s.get("image")]
    if not skus_with_images:
        return

    skus_with_images = skus_with_images[:10]
    prop_name = skus_with_images[0].get("prop_name", "خيار")

    media_group = []
    for i, sku in enumerate(skus_with_images):
        price = sku["sale_price"]
        dzd = int(price * USD_TO_DZD)
        discount = sku.get("discount", "")
        val = sku.get("prop_value", str(i + 1))

        cheapest_mark = " ✅ الأرخص" if i == 0 else ""
        caption = f"🎨 {prop_name} <b>{val}</b> — {price:.2f}$ | {dzd:,} دج"
        if discount:
            caption += f" 🏷{discount}%"
        caption += cheapest_mark

        if i == 0:
            caption += f"\n\n<b>كل الخيارات:</b>\n"
            for j, s in enumerate(skus_with_images):
                p = s["sale_price"]
                d = int(p * USD_TO_DZD)
                v = s.get("prop_value", str(j + 1))
                disc = s.get("discount", "")
                mark = " ✅" if j == 0 else ""
                caption += f"{j+1}. {prop_name} {v} — {p:.2f}$ | {d:,} دج"
                if disc:
                    caption += f" 🏷{disc}%"
                caption += mark + "\n"
            caption = caption[:1024]

        media_group.append(
            InputMediaPhoto(
                media=sku["image"],
                caption=caption,
                parse_mode=ParseMode.HTML if i == 0 else None
            )
        )

    try:
        await bot.send_media_group(chat_id=chat_id, media=media_group)
    except Exception as e:
        logging.warning(f"Album send failed: {e}")

# =========================
# FETCH PRODUCT (للنشر التلقائي)
# =========================
async def fetch_one_product() -> dict | None:
    for _ in range(min(10, len(SEARCH_KEYWORDS))):
        keyword = next_keyword()
        logging.info(f"Searching with keyword: '{keyword}'")
        try:
            resp = await api_request(
                "aliexpress.affiliate.product.query",
                {
                    "keywords": keyword,
                    "page_no": random.randint(1, 3),
                    "page_size": 20,
                    "target_currency": "USD",
                    "target_language": "FR",
                    "tracking_id": TRACKING_ID,
                    "sort": "LAST_VOLUME_DESC",
                    "ship_to_country": "DZ",
                    "min_sale_price": MIN_PRICE,
                    "fields": (
                        "product_id,product_title,target_sale_price,target_original_price,"
                        "discount,evaluate_rate,lastest_volume,product_main_image_url,"
                        "promotion_link,product_detail_url,sku_id,tax_rate"
                    ),
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
                except (ValueError, TypeError):
                    continue
                if price < MIN_PRICE:
                    continue
                try:
                    volume = int(p.get("lastest_volume", 0))
                except (ValueError, TypeError):
                    volume = 0
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
# MANUAL QUEUE — قائمة الانتظار اليدوية
# =========================
MANUAL_QUEUE_FILE = os.path.join(DATA_DIR, "manual_queue.json")
MANUAL_QUEUE: list = []

def load_manual_queue():
    global MANUAL_QUEUE
    if os.path.exists(MANUAL_QUEUE_FILE):
        with open(MANUAL_QUEUE_FILE, "r") as f:
            MANUAL_QUEUE = json.load(f)
    logging.info(f"Loaded {len(MANUAL_QUEUE)} manual queue items")

def save_manual_queue():
    with open(MANUAL_QUEUE_FILE, "w") as f:
        json.dump(MANUAL_QUEUE, f)

# =========================
# جلب تفاصيل منتج من رابط
# =========================
async def expand_url(url: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                return str(r.url)
    except:
        return url

def extract_product_id(url: str) -> str | None:
    import re
    patterns = [
        r"/item/(\d+)\.html",
        r"/i/(\d+)\.html",
        r"productId=(\d+)",
        r"/(\d{10,})(?:\.html)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def get_product_details(product_id: str) -> dict:
    resp = await api_request(
        "aliexpress.affiliate.productdetail.get",
        {
            "product_ids": product_id,
            "target_currency": "USD",
            "target_language": "EN",
            "tracking_id": TRACKING_ID,
            "ship_to_country": "DZ",
        }
    )
    result = (
        resp.get("aliexpress_affiliate_productdetail_get_response", {})
        .get("resp_result", {})
        .get("result", {})
        .get("products", {})
        .get("product", [])
    )
    return result[0] if result else {}

# =========================
# نشر منتج يدوي من رابط
# =========================
async def post_manual_product(url: str) -> bool:
    global LAST_MANUAL_POST_TIME, LAST_ANY_POST_TIME
    try:
        if "a.aliexpress.com" in url:
            url = await expand_url(url)

        product_id = extract_product_id(url)
        if not product_id:
            logging.warning(f"Could not extract product ID from: {url}")
            return False

        product = await get_product_details(product_id)
        if not product:
            logging.warning(f"No product details for ID: {product_id}")
            return False

        pid = str(product.get("product_id", product_id))
        price = str(product.get("target_sale_price", "0"))
        sku_id = str(product.get("sku_id", ""))
        tax_rate = str(product.get("tax_rate", "0.00"))

        shipping, skus_raw = await asyncio.gather(
            get_shipping_info(pid, price, sku_id, tax_rate),
            get_sku_details(pid),
        )

        link = await get_short_link(product.get("promotion_link", "") or url)
        caption = await build_manual_caption(product, shipping)
        skus = parse_skus(skus_raw)

        if len(skus) > 1:
            title = product.get("product_title", "")
            await send_sku_album(CHANNEL_ID, skus, title)
            await asyncio.sleep(1)

        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=product.get("product_main_image_url"),
            caption=caption,
            reply_markup=build_button(link),
        )

        now = time.time()
        POSTED_IDS.add(pid)
        save_posted()
        BOT_STATS["total_posted"] += 1
        LAST_MANUAL_POST_TIME = now
        LAST_ANY_POST_TIME = now

        logging.info(f"✅ Manual posted {pid}")
        return True

    except Exception as e:
        logging.error(f"Error posting manual product: {e}", exc_info=True)
        return False

# =========================
# MANUAL QUEUE LOOP — لا يتعارض مع التلقائي
# =========================
async def manual_queue_loop():
    """
    ينشر من القائمة اليدوية كل ساعة،
    مع ضمان فجوة 5 دقائق على الأقل بين أي نشرين.
    """
    while True:
        await asyncio.sleep(60)  # تحقق كل دقيقة
        try:
            if not MANUAL_QUEUE:
                continue

            now = time.time()

            # شرط 1: مضت ساعة على الأقل منذ آخر نشر يدوي
            time_since_manual = now - LAST_MANUAL_POST_TIME
            if LAST_MANUAL_POST_TIME > 0 and time_since_manual < MANUAL_POST_INTERVAL:
                remaining_min = int((MANUAL_POST_INTERVAL - time_since_manual) / 60)
                logging.info(f"Manual queue: {remaining_min} min until next manual post")
                continue

            # شرط 2: فجوة 5 دقائق بين أي نشرين (تجنب التعارض مع التلقائي)
            time_since_any = now - LAST_ANY_POST_TIME
            if LAST_ANY_POST_TIME > 0 and time_since_any < MIN_GAP_BETWEEN_ANY:
                remaining_sec = int(MIN_GAP_BETWEEN_ANY - time_since_any)
                logging.info(f"Manual queue: waiting {remaining_sec}s gap after last post")
                continue

            # خذ أول رابط من القائمة
            url = MANUAL_QUEUE.pop(0)
            save_manual_queue()
            logging.info(f"Manual queue posting: {url} | {len(MANUAL_QUEUE)} remaining")

            success = await post_manual_product(url)
            if not success:
                logging.warning(f"Failed to post manual product, skipping: {url}")

        except Exception as e:
            logging.error(f"Error in manual_queue_loop: {e}", exc_info=True)

# =========================
# POST LOOP (التلقائي) — لا يتعارض مع اليدوي
# =========================
async def post_loop():
    """
    ينشر تلقائياً كل 15 دقيقة،
    مع ضمان فجوة 5 دقائق بعد أي نشر يدوي.
    """
    global LAST_AUTO_POST_TIME, LAST_ANY_POST_TIME

    while True:
        try:
            now = time.time()

            # شرط 1: مضت 15 دقيقة منذ آخر نشر تلقائي
            time_since_auto = now - LAST_AUTO_POST_TIME
            if LAST_AUTO_POST_TIME > 0 and time_since_auto < POST_INTERVAL:
                wait = POST_INTERVAL - time_since_auto
                await asyncio.sleep(wait)
                continue

            # شرط 2: فجوة 5 دقائق بين أي نشرين (يحترم النشر اليدوي)
            time_since_any = now - LAST_ANY_POST_TIME
            if LAST_ANY_POST_TIME > 0 and time_since_any < MIN_GAP_BETWEEN_ANY:
                wait = MIN_GAP_BETWEEN_ANY - time_since_any
                logging.info(f"Auto post waiting {int(wait)}s gap after manual post")
                await asyncio.sleep(wait)
                continue

            product = await fetch_one_product()

            if not product:
                logging.warning("No product found this cycle. Waiting 60s…")
                await asyncio.sleep(60)
                continue

            pid = str(product.get("product_id", ""))
            if pid in POSTED_IDS:
                logging.info(f"Product {pid} already posted, skipping.")
                await asyncio.sleep(60)
                continue

            price = str(product.get("target_sale_price", "0"))
            sku_id = str(product.get("sku_id", ""))
            tax_rate = str(product.get("tax_rate", "0.00"))

            shipping, skus_raw = await asyncio.gather(
                get_shipping_info(pid, price, sku_id, tax_rate),
                get_sku_details(pid),
            )

            fee_raw = shipping.get("shipping_fee", "0")
            try:
                if float(fee_raw) >= MAX_SHIP_FEE:
                    logging.info(f"Skipping {pid} — high shipping: {fee_raw}$")
                    BOT_STATS["total_skipped"] += 1
                    await asyncio.sleep(60)
                    continue
            except (ValueError, TypeError):
                pass

            link = await get_short_link(product.get("promotion_link", ""))
            caption = await build_caption(product, shipping)
            skus = parse_skus(skus_raw)

            if len(skus) > 1:
                title = product.get("product_title", "")
                await send_sku_album(CHANNEL_ID, skus, title)
                await asyncio.sleep(1)

            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=product.get("product_main_image_url"),
                caption=caption,
                reply_markup=build_button(link),
            )

            now = time.time()
            POSTED_IDS.add(pid)
            save_posted()
            BOT_STATS["total_posted"] += 1
            LAST_AUTO_POST_TIME = now
            LAST_ANY_POST_TIME = now

            logging.info(
                f"✅ Auto posted {pid} | volume: {product.get('lastest_volume')} "
                f"| fee: {fee_raw}$ | skus: {len(skus)} | keyword index: {KEYWORD_INDEX}"
            )

        except Exception as e:
            BOT_STATS["total_errors"] += 1
            logging.error(f"Error in post_loop: {e}", exc_info=True)
            await asyncio.sleep(60)

        await asyncio.sleep(POST_INTERVAL)

# =========================
# COMMANDS
# =========================
@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer(
        "✅ <b>البوت يعمل الآن</b>\n\n"
        "📢 ينشر تلقائياً كل 15 دقيقة\n"
        "🛍 ينشر المنتجات اليدوية كل ساعة\n"
        "⚡ فجوة 5 دقائق بين أي نشرين لتجنب التعارض\n"
        "🇩🇿 مخصص للسوق الجزائري\n\n"
        "<b>الأوامر:</b>\n"
        "/status — حالة البوت\n"
        "/keyword — الكلمة المفتاحية\n"
        "/stats — الإحصائيات\n"
        "/queue — عرض قائمة الانتظار اليدوية\n"
        "/clear — مسح قائمة الانتظار\n\n"
        "<b>لإضافة منتجات يدوياً:</b>\n"
        "أرسل الروابط مباشرة (كل رابط في سطر)\n"
        "سيُنشر كل منتج بصيغة مختلفة عن التلقائي 🎨"
    )

@dp.message(Command("status"))
async def cmd_status(m: Message):
    uptime_sec = int(time.time() - BOT_STATS["start_time"])
    hours, rem = divmod(uptime_sec, 3600)
    minutes = rem // 60

    now = time.time()

    since_auto = int((now - LAST_AUTO_POST_TIME) / 60) if LAST_AUTO_POST_TIME else 0
    next_auto = max(0, int((POST_INTERVAL - (now - LAST_AUTO_POST_TIME)) / 60)) if LAST_AUTO_POST_TIME else 0

    since_manual = int((now - LAST_MANUAL_POST_TIME) / 60) if LAST_MANUAL_POST_TIME else 0
    next_manual = max(0, int((MANUAL_POST_INTERVAL - (now - LAST_MANUAL_POST_TIME)) / 60)) if LAST_MANUAL_POST_TIME else 0

    gap_remaining = max(0, int(MIN_GAP_BETWEEN_ANY - (now - LAST_ANY_POST_TIME))) if LAST_ANY_POST_TIME else 0

    await m.answer(
        f"📊 <b>حالة البوت</b>\n\n"
        f"✅ المنتجات المنشورة: {len(POSTED_IDS)}\n"
        f"🕐 وقت التشغيل: {hours}h {minutes}m\n"
        f"📋 قائمة الانتظار: {len(MANUAL_QUEUE)} منتج\n\n"
        f"<b>النشر التلقائي:</b>\n"
        f"⏰ آخر نشر تلقائي: منذ {since_auto} دقيقة\n"
        f"⏳ التلقائي القادم: بعد {next_auto} دقيقة\n\n"
        f"<b>النشر اليدوي:</b>\n"
        f"⏰ آخر نشر يدوي: منذ {since_manual} دقيقة\n"
        f"⏳ اليدوي القادم: بعد {next_manual} دقيقة\n\n"
        f"{'⚡ فجوة حماية متبقية: ' + str(gap_remaining) + ' ثانية' if gap_remaining > 0 else '✅ جاهز للنشر'}"
    )

@dp.message(Command("queue"))
async def cmd_queue(m: Message):
    if not MANUAL_QUEUE:
        await m.answer("📭 قائمة الانتظار فارغة.")
        return
    lines = [f"📋 <b>قائمة الانتظار ({len(MANUAL_QUEUE)} منتج):</b>\n"]
    for i, url in enumerate(MANUAL_QUEUE[:10], 1):
        short = url[:50] + "..." if len(url) > 50 else url
        lines.append(f"{i}. {short}")
    if len(MANUAL_QUEUE) > 10:
        lines.append(f"\n... و {len(MANUAL_QUEUE) - 10} منتج آخر")

    now = time.time()
    next_manual = max(0, int((MANUAL_POST_INTERVAL - (now - LAST_MANUAL_POST_TIME)) / 60)) if LAST_MANUAL_POST_TIME else 0
    lines.append(f"\n⏳ المنشور اليدوي القادم: بعد {next_manual} دقيقة")

    await m.answer("\n".join(lines))

@dp.message(Command("clear"))
async def cmd_clear(m: Message):
    count = len(MANUAL_QUEUE)
    MANUAL_QUEUE.clear()
    save_manual_queue()
    await m.answer(f"🗑 تم مسح {count} منتج من قائمة الانتظار.")

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

# =========================
# استقبال الروابط اليدوية
# =========================
import re as _re

@dp.message()
async def handle_links(m: Message):
    text = m.text or ""
    urls = _re.findall(r'https?://\S*aliexpress\S*', text)

    if not urls:
        return

    added = 0
    duplicates = 0
    for url in urls:
        if url not in MANUAL_QUEUE:
            MANUAL_QUEUE.append(url)
            added += 1
        else:
            duplicates += 1

    save_manual_queue()

    now = time.time()
    next_manual_min = max(0, int((MANUAL_POST_INTERVAL - (now - LAST_MANUAL_POST_TIME)) / 60)) if LAST_MANUAL_POST_TIME else 0
    gap_remaining = max(0, int(MIN_GAP_BETWEEN_ANY - (now - LAST_ANY_POST_TIME))) if LAST_ANY_POST_TIME else 0

    msg = f"✅ تمت إضافة <b>{added}</b> رابط لقائمة الانتظار\n"
    if duplicates:
        msg += f"⚠️ {duplicates} رابط موجود مسبقاً\n"
    msg += f"📋 إجمالي القائمة: <b>{len(MANUAL_QUEUE)}</b> منتج\n"

    if gap_remaining > 0:
        msg += f"⚡ فجوة حماية: {gap_remaining} ثانية\n"

    if next_manual_min > 0:
        msg += f"⏳ المنشور القادم بعد: <b>{next_manual_min} دقيقة</b>"
    else:
        msg += "🚀 سيُنشر قريباً (بعد انتهاء الفجوة إن وجدت)!"

    await m.answer(msg)

# =========================
# MAIN
# =========================
async def main():
    logging.info("BOT STARTED")
    load_posted()
    load_keyword_index()
    load_manual_queue()
    asyncio.create_task(post_loop())
    asyncio.create_task(manual_queue_loop())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
