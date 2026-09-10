import asyncio
import os
import re

from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F

from aiogram.filters import CommandStart, Command

from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
)

from spreadsheet import save_member


# =========================================================
# BOT
# =========================================================

BOT = Bot(
    token=BOT_TOKEN
)

DP = Dispatcher()


# =========================================================
# FILE QRIS
# =========================================================

QRIS_PATH = "assets/qris.jpg"


# =========================================================
# PAKET
# =========================================================

PACKAGES = {

    "TRIAL4": {

        "code": "TRIAL4",

        "name": "Trial 4 Hari",

        "price": 34000,

        "days": 4,

    },

    "1BLN": {

        "code": "1BLN",

        "name": "1 Bulan",

        "price": 149000,

        "days": 30,

    },

}


# =========================================================
# TEMPORARY PAYMENT DATA
#
# User ID ->
# data paket yang sedang dipilih
# =========================================================

pending_payments = {}


# =========================================================
# FORMAT RUPIAH
# =========================================================

def format_rupiah(value):

    return "Rp" + f"{value:,}".replace(",", ".")


# =========================================================
# USER NAME
# =========================================================

def get_user_name(user):

    if user.full_name:

        return user.full_name

    if user.username:

        return user.username

    return "User Telegram"


# =========================================================
# PARSE START PAYLOAD
#
# JOIN_TRIAL4
#
# JOIN_1BLN
#
# JOIN_TRIAL4_ref_ABC123
#
# JOIN_1BLN_ref_ABC123
# =========================================================

def parse_start_payload(payload):

    if not payload:

        return None, ""


    payload = payload.strip()


    # -----------------------------------------------------
    # TANPA REFERRAL
    # -----------------------------------------------------

    if payload.upper() == "JOIN_TRIAL4":

        return "TRIAL4", ""


    if payload.upper() == "JOIN_1BLN":

        return "1BLN", ""


    # -----------------------------------------------------
    # DENGAN REFERRAL
    # -----------------------------------------------------

    match = re.match(

        r"^JOIN_(TRIAL4|1BLN)_ref_(.+)$",

        payload,

        re.IGNORECASE

    )


    if match:

        package_code = match.group(1).upper()

        referral = match.group(2).strip()


        return package_code, referral


    return None, ""


# =========================================================
# START
# =========================================================

@DP.message(CommandStart())
async def start_handler(message: Message):

    payload = ""


    # -----------------------------------------------------
    # AMBIL PAYLOAD /START
    # -----------------------------------------------------

    if message.text:

        parts = message.text.split(
            maxsplit=1
        )


        if len(parts) > 1:

            payload = parts[1].strip()


    # -----------------------------------------------------
    # CEK PAYLOAD
    # -----------------------------------------------------

    package_code, referral = parse_start_payload(
        payload
    )


    # =====================================================
    # JIKA USER DATANG DARI LANDING PAGE
    #
    # Contoh:
    #
    # JOIN_TRIAL4
    #
    # JOIN_1BLN
    #
    # JOIN_TRIAL4_ref_ABC
    # =====================================================

    if package_code:

        await send_payment_instruction(

            message=message,

            package_code=package_code,

            referral=referral

        )

        return


    # =====================================================
    # /START NORMAL
    #
    # TAMPILKAN 2 PILIHAN PAKET
    # =====================================================

    keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="🟢 Trial 4 Hari — Rp34.000",

                    callback_data="package_TRIAL4"

                )

            ],

            [

                InlineKeyboardButton(

                    text="🟡 1 Bulan — Rp149.000",

                    callback_data="package_1BLN"

                )

            ],

        ]

    )


    await message.answer(

        "🤖 <b>XAU AI INTELLIGENCE</b>\n\n"

        "Selamat datang di sistem akses "
        "<b>XAU AI Intelligence</b>.\n\n"

        "Dapatkan analisa dan sinyal XAUUSD "
        "yang dikirim langsung ke Telegram Anda.\n\n"

        "📦 <b>PILIH PAKET AKSES</b>\n\n"

        "🟢 <b>Trial 4 Hari</b>\n"
        "💰 Rp34.000\n\n"

        "🟡 <b>1 Bulan</b>\n"
        "💰 Rp149.000\n\n"

        "Silahkan pilih paket di bawah "
        "untuk melanjutkan pembayaran.",

        reply_markup=keyboard,

        parse_mode="HTML"

    )


# =========================================================
# CALLBACK PILIH PAKET
# =========================================================

@DP.callback_query(
    F.data.startswith("package_")
)
async def package_callback(
    callback: CallbackQuery
):

    package_code = callback.data.replace(

        "package_",

        "",

        1

    ).upper()


    # -----------------------------------------------------
    # CEK PAKET
    # -----------------------------------------------------

    if package_code not in PACKAGES:

        await callback.answer(

            "Paket tidak ditemukan.",

            show_alert=True

        )

        return


    await callback.answer()


    # -----------------------------------------------------
    # KIRIM QRIS
    # -----------------------------------------------------

    await send_payment_instruction(

        message=callback.message,

        package_code=package_code,

        referral=""

    )


# =========================================================
# KIRIM QRIS + INSTRUKSI PEMBAYARAN
# =========================================================

async def send_payment_instruction(

    message: Message,

    package_code: str,

    referral: str = ""

):

    # -----------------------------------------------------
    # AMBIL PAKET
    # -----------------------------------------------------

    package = PACKAGES.get(
        package_code
    )


    if not package:

        await message.answer(

            "❌ Paket tidak ditemukan."

        )

        return


    user = message.from_user


    # -----------------------------------------------------
    # SIMPAN PAYMENT STATE
    # -----------------------------------------------------

    pending_payments[user.id] = {

        "package_code": package["code"],

        "package": package["name"],

        "harga": package["price"],

        "days": package["days"],

        "referral": referral,

        "telegram_id": user.id,

        "username": user.username or "",

        "nama": get_user_name(user),

    }


    # -----------------------------------------------------
    # CEK FILE QRIS
    # -----------------------------------------------------

    if not os.path.exists(QRIS_PATH):

        await message.answer(

            "❌ <b>QRIS tidak ditemukan.</b>\n\n"

            "Pastikan file berikut tersedia:\n"

            f"<code>{QRIS_PATH}</code>",

            parse_mode="HTML"

        )

        return


    # -----------------------------------------------------
    # CAPTION QRIS
    # -----------------------------------------------------

    caption = (

        "💳 <b>PEMBAYARAN XAU AI INTELLIGENCE</b>\n\n"

        f"📦 <b>Paket:</b> {package['name']}\n"

        f"💰 <b>Harga:</b> "
        f"{format_rupiah(package['price'])}\n"

        f"⏳ <b>Masa akses:</b> "
        f"{package['days']} hari\n\n"

        "📲 <b>Silahkan lakukan pembayaran "
        "sesuai nominal paket.</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "📸 <b>SETELAH TRANSFER</b>\n\n"

        "Silahkan <b>screenshoot bukti Transfer</b> "
        "dan kirim lagi ke sini.\n\n"

        "Setelah bukti transfer diterima, "
        "data Anda akan dikirim ke admin "
        "untuk proses verifikasi.\n\n"

        "⚠️ Pastikan screenshot bukti transfer "
        "terlihat jelas."
    )


    # -----------------------------------------------------
    # KIRIM QRIS
    # -----------------------------------------------------

    photo = FSInputFile(
        QRIS_PATH
    )


    await message.answer_photo(

        photo=photo,

        caption=caption,

        parse_mode="HTML"

    )


# =========================================================
# USER KIRIM FOTO BUKTI TRANSFER
# =========================================================

@DP.message(F.photo)
async def proof_photo_handler(
    message: Message
):

    user = message.from_user


    # -----------------------------------------------------
    # CEK PAYMENT STATE
    # -----------------------------------------------------

    payment = pending_payments.get(
        user.id
    )


    if not payment:

        await message.answer(

            "⚠️ <b>Belum ada paket yang dipilih.</b>\n\n"

            "Silahkan tekan /start terlebih dahulu "
            "dan pilih paket yang ingin Anda beli.",

            parse_mode="HTML"

        )

        return


    # -----------------------------------------------------
    # FOTO RESOLUSI TERBESAR
    # -----------------------------------------------------

    photo = message.photo[-1]


    # -----------------------------------------------------
    # USER DATA
    # -----------------------------------------------------

    telegram_id = user.id

    username = user.username or "-"

    nama = get_user_name(user)


    # -----------------------------------------------------
    # PACKAGE DATA
    # -----------------------------------------------------

    package_name = payment["package"]

    harga = payment["harga"]

    referral = payment.get(
        "referral",
        ""
    )


    # -----------------------------------------------------
    # TANGGAL
    # -----------------------------------------------------

    now = datetime.now()


    register_date = now.strftime(
        "%d-%m-%Y"
    )


    expired_date = (

        now +

        timedelta(
            days=payment["days"]
        )

    ).strftime(
        "%d-%m-%Y"
    )


    # =====================================================
    # DATA MEMBER
    # =====================================================

    member_data = {

        "telegram_id": telegram_id,

        "username": username,

        "nama": nama,

        "paket": package_name,

        "harga": harga,

        "register": register_date,

        "expired": expired_date,

        "status": "PENDING",

        "referral": referral,

    }


    print("")
    print("========================================")
    print("BUKTI TRANSFER DITERIMA")
    print("========================================")

    print(
        member_data
    )


    # =====================================================
    # SIMPAN KE GOOGLE SHEETS
    # =====================================================

    sheet_success = False


    try:

        sheet_success = await asyncio.to_thread(

            save_member,

            member_data

        )


    except Exception as e:

        print(
            "Google Sheet Error:",
            e
        )


        sheet_success = False


    # =====================================================
    # REFERRAL TEXT
    # =====================================================

    referral_text = (

        referral

        if referral

        else "-"

    )


    # =====================================================
    # ADMIN CAPTION
    # =====================================================

    admin_caption = (

        "🚨 <b>BUKTI TRANSFER BARU</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "👤 <b>DATA USER</b>\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"Nama: <b>{nama}</b>\n"

        f"Username: "
        f"<b>@{username if username != '-' else '-'}</b>\n"

        f"Telegram ID: "
        f"<code>{telegram_id}</code>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "📦 <b>PAKET</b>\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"Paket: <b>{package_name}</b>\n"

        f"Harga: <b>{format_rupiah(harga)}</b>\n"

        f"Referral: <code>{referral_text}</code>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "📅 <b>REGISTRASI</b>\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"Register: {register_date}\n"

        f"Expired: {expired_date}\n"

        "Status: <b>PENDING</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "📊 <b>GOOGLE SHEETS</b>\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"Status: "
        f"<b>{'SUCCESS' if sheet_success else 'ERROR'}</b>\n\n"

        "⚠️ Silahkan periksa bukti transfer "
        "sebelum mengaktifkan akses user."
    )


    # =====================================================
    # KIRIM KE ADMIN
    # =====================================================

    admin_sent = False


    for admin_id in ADMIN_IDS:

        try:

            await BOT.send_photo(

                chat_id=admin_id,

                photo=photo.file_id,

                caption=admin_caption,

                parse_mode="HTML"

            )


            admin_sent = True


            print(
                f"[ADMIN] Bukti transfer "
                f"dikirim ke {admin_id}"
            )


        except Exception as e:

            print(
                f"[ADMIN ERROR] "
                f"{admin_id}: {e}"
            )


    # =====================================================
    # BALAS KE USER
    # =====================================================

    if admin_sent:

        await message.answer(

            "✅ <b>BUKTI TRANSFER BERHASIL DITERIMA</b>\n\n"

            f"📦 Paket: <b>{package_name}</b>\n"

            f"💰 Nominal: "
            f"<b>{format_rupiah(harga)}</b>\n\n"

            "Bukti pembayaran sudah dikirim "
            "ke admin untuk proses verifikasi.\n\n"

            "⏳ Mohon tunggu proses aktivasi "
            "akses Anda.",

            parse_mode="HTML"

        )


    else:

        await message.answer(

            "⚠️ Bukti transfer sudah diterima, "
            "tetapi sistem gagal mengirimkannya "
            "ke admin.\n\n"

            "Silahkan hubungi admin."

        )


    # -----------------------------------------------------
    # HAPUS PAYMENT STATE
    #
    # Setelah bukti dikirim, user harus memilih paket
    # lagi untuk transaksi berikutnya.
    # -----------------------------------------------------

    pending_payments.pop(
        user.id,
        None
    )


# =========================================================
# USER MENGIRIM FILE/DOKUMEN
# =========================================================

@DP.message(F.document)
async def proof_document_handler(
    message: Message
):

    user = message.from_user


    payment = pending_payments.get(
        user.id
    )


    if not payment:

        await message.answer(

            "⚠️ Silahkan tekan /start "
            "dan pilih paket terlebih dahulu."

        )

        return


    await message.answer(

        "📸 Silahkan kirim "
        "<b>screenshoot/foto bukti transfer</b> "
        "langsung ke chat ini.",

        parse_mode="HTML"

    )


# =========================================================
# USER MENGIRIM TEXT
# =========================================================

@DP.message(F.text)
async def text_handler(
    message: Message
):

    user = message.from_user


    # -----------------------------------------------------
    # Jika sedang menunggu bukti transfer
    # -----------------------------------------------------

    payment = pending_payments.get(
        user.id
    )


    if payment:

        await message.answer(

            "📸 <b>Bukti transfer belum diterima.</b>\n\n"

            "Silahkan kirim "
            "<b>screenshoot bukti Transfer</b> "
            "di chat ini.\n\n"

            f"📦 Paket: "
            f"<b>{payment['package']}</b>\n"

            f"💰 Nominal: "
            f"<b>{format_rupiah(payment['harga'])}</b>",

            parse_mode="HTML"

        )

        return


    # -----------------------------------------------------
    # User belum memilih paket
    # -----------------------------------------------------

    keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="🟢 Trial 4 Hari — Rp34.000",

                    callback_data="package_TRIAL4"

                )

            ],

            [

                InlineKeyboardButton(

                    text="🟡 1 Bulan — Rp149.000",

                    callback_data="package_1BLN"

                )

            ]

        ]

    )


    await message.answer(

        "Silahkan pilih paket terlebih dahulu:",

        reply_markup=keyboard

    )


# =========================================================
# COMMAND /ID
# =========================================================

@DP.message(Command("id"))
async def get_id(
    message: Message
):

    await message.answer(

        "🆔 <b>Telegram ID Anda:</b>\n\n"

        f"<code>{message.from_user.id}</code>",

        parse_mode="HTML"

    )


# =========================================================
# START BOT
# =========================================================

async def main():

    print("")
    print("========================================")
    print("🤖 XAU AI ASSISTANT BOT")
    print("========================================")
    print("BOT RUNNING")
    print("QRIS:", QRIS_PATH)
    print("PACKAGES:")
    print(" - Trial 4 Hari : Rp34.000")
    print(" - 1 Bulan      : Rp149.000")
    print("========================================")
    print("")


    await DP.start_polling(
        BOT
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "Bot stopped."
        )
