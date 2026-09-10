import asyncio
import json
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
    ADMIN_ID,
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
# PAYMENT STATE
# =========================================================
#
# Status pembayaran disimpan ke file JSON.
#
# KEUNTUNGAN:
# - Tidak hilang saat bot restart
# - User tetap dikenali setelah memilih paket
# - Bukti transfer tidak membuat user kembali ke /start
#
# =========================================================

PAYMENT_STATE_FILE = "payment_state.json"


def load_payment_state():
    """
    Membaca data transaksi dari file JSON.
    """

    if not os.path.exists(PAYMENT_STATE_FILE):
        return {}

    try:
        with open(
            PAYMENT_STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            if isinstance(data, dict):
                return data

    except Exception as e:

        print(
            "Payment state load error:",
            e
        )

    return {}


def save_payment_state():
    """
    Menyimpan payment state secara aman.
    """

    temp_file = PAYMENT_STATE_FILE + ".tmp"

    try:

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                pending_payments,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temp_file,
            PAYMENT_STATE_FILE
        )

    except Exception as e:

        print(
            "Payment state save error:",
            e
        )


# =========================================================
# PAYMENT STATE DI LOAD SAAT BOT START
# =========================================================

pending_payments = load_payment_state()

print(
    f"[PAYMENT STATE] "
    f"{len(pending_payments)} transaksi dimuat."
)


# =========================================================
# LOCK
# =========================================================

payment_lock = asyncio.Lock()


# =========================================================
# ADMIN
# =========================================================
#
# config.py menggunakan ADMIN_ID.
#
# Bisa berupa:
#
# ADMIN_ID = 123456789
#
# atau:
#
# ADMIN_ID = [123456789, 987654321]
#
# =========================================================

if isinstance(ADMIN_ID, (list, tuple, set)):

    ADMIN_IDS = list(ADMIN_ID)

else:

    ADMIN_IDS = [ADMIN_ID]


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
# =========================================================
#
# JOIN_TRIAL4
# JOIN_1BLN
#
# JOIN_TRIAL4_ref_ABC123
# JOIN_1BLN_ref_ABC123
#
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
    # =====================================================

    if package_code:

        await send_payment_instruction(
            message=message,
            package_code=package_code,
            referral=referral
        )

        return

    # =====================================================
    # CEK APAKAH USER MASIH MEMILIKI TRANSAKSI
    # =====================================================

    user_id = str(message.from_user.id)

    payment = pending_payments.get(user_id)

    if payment:

        status = payment.get(
            "status",
            "WAITING_PROOF"
        )

        # -------------------------------------------------
        # Bukti sudah dikirim
        # -------------------------------------------------

        if status == "PROOF_SENT":

            await message.answer(

                "⏳ <b>PEMBAYARAN ANDA SEDANG DIPROSES</b>\n\n"

                f"📦 Paket: <b>{payment['package']}</b>\n"
                f"💰 Nominal: <b>{format_rupiah(payment['harga'])}</b>\n\n"

                "Bukti transfer sudah diterima dan "
                "dikirim ke admin.\n\n"

                "Mohon tunggu proses verifikasi.\n"
                "Anda <b>tidak perlu mengirim /start lagi.</b>",

                parse_mode="HTML"
            )

            return

        # -------------------------------------------------
        # Masih menunggu bukti
        # -------------------------------------------------

        if status == "WAITING_PROOF":

            await message.answer(

                "📸 <b>TRANSAKSI ANDA MASIH AKTIF</b>\n\n"

                f"📦 Paket: <b>{payment['package']}</b>\n"
                f"💰 Nominal: <b>{format_rupiah(payment['harga'])}</b>\n\n"

                "Silahkan kirim screenshot bukti transfer "
                "di chat ini.\n\n"

                "Anda tidak perlu memilih paket lagi.",

                parse_mode="HTML"
            )

            return

    # =====================================================
    # /START NORMAL
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

    user_id = str(user.id)

    # -----------------------------------------------------
    # CEK TRANSAKSI LAMA
    # -----------------------------------------------------

    async with payment_lock:

        old_payment = pending_payments.get(
            user_id
        )

        # Jika sudah ada transaksi aktif
        if old_payment:

            old_status = old_payment.get(
                "status",
                "WAITING_PROOF"
            )

            # Jangan membuat transaksi baru
            # jika bukti sudah dikirim.

            if old_status == "PROOF_SENT":

                await message.answer(

                    "⏳ <b>TRANSAKSI ANDA MASIH DIPROSES</b>\n\n"

                    f"📦 Paket: <b>{old_payment['package']}</b>\n"
                    f"💰 Nominal: <b>{format_rupiah(old_payment['harga'])}</b>\n\n"

                    "Bukti transfer sudah dikirim ke admin.\n"
                    "Mohon tunggu proses verifikasi.\n\n"

                    "Anda tidak perlu melakukan /start ulang.",

                    parse_mode="HTML"
                )

                return

        # -------------------------------------------------
        # SIMPAN PAYMENT STATE
        # -------------------------------------------------

        pending_payments[user_id] = {

            "package_code": package["code"],

            "package": package["name"],

            "harga": package["price"],

            "days": package["days"],

            "referral": referral,

            "telegram_id": user.id,

            "username": user.username or "",

            "nama": get_user_name(user),

            "status": "WAITING_PROOF",

            "created_at": datetime.now().isoformat(),

        }

        # -------------------------------------------------
        # LANGSUNG SIMPAN KE FILE
        # -------------------------------------------------

        save_payment_state()

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

    user_id = str(user.id)

    # -----------------------------------------------------
    # CEK PAYMENT STATE
    # -----------------------------------------------------

    payment = pending_payments.get(
        user_id
    )

    if not payment:

        # -------------------------------------------------
        # FALLBACK:
        # Jangan hanya menyuruh /start.
        # Berikan tombol paket.
        # -------------------------------------------------

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

            "⚠️ <b>Transaksi tidak ditemukan.</b>\n\n"

            "Silahkan pilih paket di bawah "
            "untuk membuat transaksi baru.",

            reply_markup=keyboard,

            parse_mode="HTML"

        )

        return

    # -----------------------------------------------------
    # JIKA BUKTI SUDAH PERNAH DIKIRIM
    # -----------------------------------------------------

    if payment.get("status") == "PROOF_SENT":

        await message.answer(

            "⏳ <b>BUKTI TRANSFER SUDAH DITERIMA</b>\n\n"

            f"📦 Paket: <b>{payment['package']}</b>\n"
            f"💰 Nominal: <b>{format_rupiah(payment['harga'])}</b>\n\n"

            "Bukti Anda sudah dikirim ke admin "
            "dan sedang menunggu verifikasi.\n\n"

            "Mohon tunggu. "
            "Anda tidak perlu mengirim bukti ulang.",

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
    # JIKA ADMIN BERHASIL MENERIMA
    # =====================================================

    if admin_sent:

        # -------------------------------------------------
        # PENTING:
        # JANGAN HAPUS pending_payments
        #
        # Ubah status menjadi PROOF_SENT.
        # -------------------------------------------------

        async with payment_lock:

            if user_id in pending_payments:

                pending_payments[user_id][
                    "status"
                ] = "PROOF_SENT"

                pending_payments[user_id][
                    "proof_sent_at"
                ] = datetime.now().isoformat()

                pending_payments[user_id][
                    "sheet_success"
                ] = sheet_success

                save_payment_state()

        # -------------------------------------------------
        # BALAS KE USER
        # -------------------------------------------------

        await message.answer(

            "✅ <b>BUKTI TRANSFER BERHASIL DITERIMA</b>\n\n"

            f"📦 Paket: <b>{package_name}</b>\n"

            f"💰 Nominal: "
            f"<b>{format_rupiah(harga)}</b>\n\n"

            "Bukti pembayaran sudah dikirim "
            "ke admin untuk proses verifikasi.\n\n"

            "⏳ Mohon tunggu proses aktivasi "
            "akses Anda.\n\n"

            "✅ <b>Anda tidak perlu menekan /start lagi.</b>",

            parse_mode="HTML"

        )

    # =====================================================
    # ADMIN GAGAL MENERIMA
    # =====================================================

    else:

        # -------------------------------------------------
        # Jangan ubah menjadi PROOF_SENT.
        # Tetap WAITING_PROOF agar bisa dikirim ulang.
        # -------------------------------------------------

        async with payment_lock:

            if user_id in pending_payments:

                pending_payments[user_id][
                    "status"
                ] = "WAITING_PROOF"

                save_payment_state()

        await message.answer(

            "⚠️ <b>BUKTI TRANSFER SUDAH DITERIMA</b>\n\n"

            "Namun sistem gagal mengirim bukti "
            "ke admin.\n\n"

            "Silahkan coba kirim bukti transfer "
            "sekali lagi.\n\n"

            "Anda <b>tidak perlu /start ulang</b>.",

            parse_mode="HTML"

        )


# =========================================================
# USER MENGIRIM FILE/DOKUMEN
# =========================================================

@DP.message(F.document)
async def proof_document_handler(
    message: Message
):

    user = message.from_user

    user_id = str(user.id)

    payment = pending_payments.get(
        user_id
    )

    # -----------------------------------------------------
    # Kalau transaksi tidak ditemukan
    # -----------------------------------------------------

    if not payment:

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

            "⚠️ Transaksi tidak ditemukan.\n\n"
            "Silahkan pilih paket terlebih dahulu.",

            reply_markup=keyboard

        )

        return

    # -----------------------------------------------------
    # JIKA SUDAH TERKIRIM
    # -----------------------------------------------------

    if payment.get("status") == "PROOF_SENT":

        await message.answer(

            "⏳ <b>BUKTI TRANSFER SUDAH DITERIMA</b>\n\n"

            "Bukti sebelumnya sudah dikirim "
            "ke admin untuk verifikasi.\n\n"

            "Mohon tunggu proses aktivasi.",

            parse_mode="HTML"

        )

        return

    # -----------------------------------------------------
    # DOCUMENT BUKAN FOTO
    # -----------------------------------------------------

    await message.answer(

        "📸 Silahkan kirim "
        "<b>screenshoot/foto bukti transfer</b> "
        "langsung ke chat ini.\n\n"

        "Jangan kirim sebagai file/document.",

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

    user_id = str(user.id)

    # -----------------------------------------------------
    # CEK TRANSAKSI
    # -----------------------------------------------------

    payment = pending_payments.get(
        user_id
    )

    if payment:

        status = payment.get(
            "status",
            "WAITING_PROOF"
        )

        # -------------------------------------------------
        # BUKTI SUDAH TERKIRIM
        # -------------------------------------------------

        if status == "PROOF_SENT":

            await message.answer(

                "⏳ <b>TRANSAKSI ANDA SEDANG DIPROSES</b>\n\n"

                f"📦 Paket: <b>{payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

                "Bukti transfer sudah diterima "
                "dan dikirim ke admin.\n\n"

                "Mohon tunggu proses verifikasi.\n\n"

                "Anda tidak perlu menekan /start lagi.",

                parse_mode="HTML"

            )

            return

        # -------------------------------------------------
        # MASIH MENUNGGU BUKTI
        # -------------------------------------------------

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

    # =====================================================
    # USER BELUM MEMILIKI TRANSAKSI
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

    print("PAYMENT STATE:", PAYMENT_STATE_FILE)

    print("TRANSAKSI AKTIF:", len(pending_payments))

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

