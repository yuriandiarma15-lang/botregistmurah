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

from config import BOT_TOKEN, ADMIN_ID
from spreadsheet import save_member


# =========================================================
# BOT
# =========================================================

BOT = Bot(token=BOT_TOKEN)
DP = Dispatcher()


# =========================================================
# FILE QRIS
# =========================================================

QRIS_PATH = "assets/qris.jpg"


# =========================================================
# PAYMENT STATE
# =========================================================
#
# Semua transaksi sementara disimpan di JSON.
#
# PENTING:
# Data transaksi BELUM masuk Google Sheets
# sampai admin menekan tombol TERIMA.
#
# =========================================================

PAYMENT_STATE_FILE = "payment_state.json"


def load_payment_state():

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
            "[PAYMENT STATE LOAD ERROR]",
            e
        )

    return {}


pending_payments = load_payment_state()


def save_payment_state():

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
            "[PAYMENT STATE SAVE ERROR]",
            e
        )


# =========================================================
# ADMIN
# =========================================================

if isinstance(
    ADMIN_ID,
    (list, tuple, set)
):

    ADMIN_IDS = list(ADMIN_ID)

else:

    ADMIN_IDS = [ADMIN_ID]


# =========================================================
# PAKET
# =========================================================

PACKAGE_MAP = {

    "4 hari": {
        "label": "4 hari",
        "price": 34000,
        "days": 4
    },

    "1BLN": {
        "label": "1 Bulan",
        "price": 149000,
        "days": 30
    }

}


# =========================================================
# CALLBACK CODE -> PACKAGE MAP
# =========================================================

CALLBACK_PACKAGE_MAP = {

    "TRIAL4": "4 hari",

    "1BLN": "1BLN",

}


# =========================================================
# FORMAT RUPIAH
# =========================================================

def format_rupiah(value):

    return "Rp" + f"{value:,}".replace(
        ",",
        "."
    )


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
# START PAYLOAD
# =========================================================

def parse_start_payload(payload):

    if not payload:
        return None, ""

    payload = payload.strip()

    if payload.upper() == "JOIN_TRIAL4":

        return "TRIAL4", ""

    if payload.upper() == "JOIN_1BLN":

        return "1BLN", ""

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
# KEYBOARD PAKET
# =========================================================

def package_keyboard():

    return InlineKeyboardMarkup(

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


# =========================================================
# START
# =========================================================

@DP.message(CommandStart())
async def start_handler(message: Message):

    payload = ""

    if message.text:

        parts = message.text.split(
            maxsplit=1
        )

        if len(parts) > 1:

            payload = parts[1].strip()

    package_code, referral = parse_start_payload(
        payload
    )

    # -----------------------------------------------------
    # USER DARI LANDING PAGE
    # -----------------------------------------------------

    if package_code:

        await send_payment_instruction(

            message=message,

            user=message.from_user,

            package_code=package_code,

            referral=referral

        )

        return

    # -----------------------------------------------------
    # CEK TRANSAKSI
    # -----------------------------------------------------

    user_id = str(
        message.from_user.id
    )

    payment = pending_payments.get(
        user_id
    )

    if payment:

        status = payment.get(
            "status",
            "WAITING_PROOF"
        )

        # -------------------------------------------------
        # APPROVED
        # -------------------------------------------------

        if status == "APPROVED":

            await message.answer(

                "🎉 <b>PEMBAYARAN ANDA SUDAH DISETUJUI</b>\n\n"

                f"📦 Paket: "
                f"<b>{payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

                "✅ <b>Status: ACTIVE</b>\n\n"

                "🤖 Bot AI Anda sudah siap digunakan.\n\n"

                "👉 <a href=\"https://t.me/AIGOLDASSISTANT_BOT\">"
                "START @AIGOLDASSISTANT_BOT"
                "</a>",

                parse_mode="HTML",

                disable_web_page_preview=True

            )

            return

        # -------------------------------------------------
        # PROOF SENT
        # -------------------------------------------------

        if status == "PROOF_SENT":

            await message.answer(

                "⏳ <b>TRANSAKSI ANDA SEDANG DIPROSES</b>\n\n"

                f"📦 Paket: "
                f"<b>{payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

                "Bukti transfer sudah diterima dan "
                "sudah dikirim ke admin untuk verifikasi.\n\n"

                "Mohon tunggu proses aktivasi.\n\n"

                "✅ Anda tidak perlu menekan /start lagi.",

                parse_mode="HTML"

            )

            return

        # -------------------------------------------------
        # REJECTED
        # -------------------------------------------------

        if status == "REJECTED":

            await message.answer(

                "❌ <b>BUKTI PEMBAYARAN DITOLAK</b>\n\n"

                f"📦 Paket: "
                f"<b>{payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

                "Silahkan hubungi admin untuk informasi "
                "lebih lanjut.",

                parse_mode="HTML"

            )

            return

        # -------------------------------------------------
        # WAITING PROOF
        # -------------------------------------------------

        if status == "WAITING_PROOF":

            await message.answer(

                "📸 <b>TRANSAKSI ANDA MASIH AKTIF</b>\n\n"

                f"📦 Paket: "
                f"<b>{payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

                "Silahkan kirim screenshot bukti transfer "
                "di chat ini.\n\n"

                "Anda tidak perlu memilih paket lagi.",

                parse_mode="HTML"

            )

            return

    # -----------------------------------------------------
    # START NORMAL
    # -----------------------------------------------------

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

        reply_markup=package_keyboard(),

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

    package_key = CALLBACK_PACKAGE_MAP.get(
        package_code
    )

    if not package_key:

        await callback.answer(
            "Paket tidak ditemukan.",
            show_alert=True
        )

        return

    package = PACKAGE_MAP.get(
        package_key
    )

    if not package:

        await callback.answer(
            "Data paket tidak ditemukan.",
            show_alert=True
        )

        return

    await callback.answer()

    user = callback.from_user

    await send_payment_instruction(

        message=callback.message,

        user=user,

        package_code=package_code,

        referral=""

    )


# =========================================================
# KIRIM QRIS + SIMPAN TRANSAKSI
# =========================================================

async def send_payment_instruction(
    message: Message,
    user,
    package_code: str,
    referral: str = ""
):

    package_key = CALLBACK_PACKAGE_MAP.get(
        package_code
    )

    if not package_key:

        await message.answer(
            "❌ Paket tidak ditemukan."
        )

        return

    package = PACKAGE_MAP.get(
        package_key
    )

    if not package:

        await message.answer(
            "❌ Data paket tidak ditemukan."
        )

        return

    user_id = str(
        user.id
    )

    # -----------------------------------------------------
    # CEK TRANSAKSI LAMA
    # -----------------------------------------------------

    old_payment = pending_payments.get(
        user_id
    )

    if old_payment:

        old_status = old_payment.get(
            "status",
            "WAITING_PROOF"
        )

        if old_status == "PROOF_SENT":

            await message.answer(

                "⏳ <b>TRANSAKSI ANDA MASIH DIPROSES</b>\n\n"

                f"📦 Paket: "
                f"<b>{old_payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(old_payment['harga'])}</b>\n\n"

                "Bukti transfer sudah dikirim ke admin.\n"

                "Mohon tunggu proses verifikasi.\n\n"

                "Anda tidak perlu melakukan /start ulang.",

                parse_mode="HTML"

            )

            return

        if old_status == "APPROVED":

            await message.answer(

                "🎉 <b>PEMBAYARAN ANDA SUDAH DISETUJUI</b>\n\n"

                "Status Anda saat ini: "
                "<b>ACTIVE</b>.\n\n"

                "👉 <a href=\"https://t.me/AIGOLDASSISTANT_BOT\">"
                "START @AIGOLDASSISTANT_BOT"
                "</a>",

                parse_mode="HTML",

                disable_web_page_preview=True

            )

            return

    # -----------------------------------------------------
    # BUAT TRANSAKSI
    # -----------------------------------------------------

    pending_payments[user_id] = {

        "package_code": package_code,

        "package_key": package_key,

        "package": package["label"],

        "harga": package["price"],

        "days": package["days"],

        "referral": referral,

        "telegram_id": user.id,

        "username": user.username or "",

        "nama": get_user_name(user),

        "status": "WAITING_PROOF",

        "created_at": datetime.now().isoformat(),

    }

    save_payment_state()

    # -----------------------------------------------------
    # CEK QRIS
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

        f"📦 <b>Paket:</b> {package['label']}\n"

        f"💰 <b>Harga:</b> "
        f"{format_rupiah(package['price'])}\n"

        f"⏳ <b>Masa akses:</b> "
        f"{package['days']} hari\n\n"

        "📲 <b>Silahkan lakukan pembayaran "
        "sesuai nominal paket.</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "📸 <b>SETELAH TRANSFER</b>\n\n"

        "Silahkan <b>screenshoot bukti Transfer</b> "
        "dan kirim ke chat ini.\n\n"

        "Setelah bukti transfer diterima, "
        "data Anda akan dikirim ke admin "
        "untuk proses verifikasi.\n\n"

        "⚠️ Pastikan screenshot bukti transfer "
        "terlihat jelas."

    )

    photo = FSInputFile(
        QRIS_PATH
    )

    await message.answer_photo(

        photo=photo,

        caption=caption,

        parse_mode="HTML"

    )


# =========================================================
# TOMBOL ADMIN
# =========================================================

def admin_proof_keyboard(user_id):

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="✅ TERIMA",

                    callback_data=(
                        f"proof_accept:{user_id}"
                    )

                ),

                InlineKeyboardButton(

                    text="❌ TOLAK",

                    callback_data=(
                        f"proof_reject:{user_id}"
                    )

                )

            ]

        ]

    )


# =========================================================
# CEK ADMIN
# =========================================================

async def check_admin(
    callback: CallbackQuery
):

    if callback.from_user.id not in ADMIN_IDS:

        await callback.answer(

            "❌ Anda tidak memiliki izin.",

            show_alert=True

        )

        return False

    return True


# =========================================================
# ADMIN TERIMA
# =========================================================

@DP.callback_query(
    F.data.startswith("proof_accept:")
)
async def proof_accept_callback(
    callback: CallbackQuery
):

    if not await check_admin(callback):
        return

    user_id = callback.data.split(
        ":",
        1
    )[1]

    payment = pending_payments.get(
        user_id
    )

    if not payment:

        await callback.answer(

            "❌ Data transaksi tidak ditemukan.",

            show_alert=True

        )

        return

    current_status = payment.get(
        "status",
        "WAITING_PROOF"
    )

    # -----------------------------------------------------
    # CEK STATUS
    # -----------------------------------------------------

    if current_status == "APPROVED":

        await callback.answer(
            "Transaksi sudah diterima.",
            show_alert=True
        )

        return

    if current_status == "REJECTED":

        await callback.answer(
            "Transaksi sudah ditolak.",
            show_alert=True
        )

        return

    if current_status != "PROOF_SENT":

        await callback.answer(

            "❌ Bukti transfer belum diterima.",

            show_alert=True

        )

        return

    # =====================================================
    # TANGGAL
    # =====================================================

    register_date = payment.get(
        "register"
    )

    expired_date = payment.get(
        "expired"
    )

    # -----------------------------------------------------
    # Untuk transaksi lama yang belum punya tanggal,
    # buat tanggal sekarang.
    # -----------------------------------------------------

    if not register_date:

        now = datetime.now()

        register_date = now.strftime(
            "%d-%m-%Y"
        )

        expired_date = (

            now
            + timedelta(
                days=payment["days"]
            )

        ).strftime(
            "%d-%m-%Y"
        )

        payment["register"] = register_date

        payment["expired"] = expired_date

    elif not expired_date:

        try:

            register_dt = datetime.strptime(
                register_date,
                "%d-%m-%Y"
            )

            expired_date = (

                register_dt
                + timedelta(
                    days=payment["days"]
                )

            ).strftime(
                "%d-%m-%Y"
            )

            payment["expired"] = expired_date

        except Exception:

            now = datetime.now()

            expired_date = (

                now
                + timedelta(
                    days=payment["days"]
                )

            ).strftime(
                "%d-%m-%Y"
            )

            payment["expired"] = expired_date

    # =====================================================
    # DATA MEMBER
    #
    # INI BARU DIBUAT SAAT ADMIN MENEKAN TERIMA
    # =====================================================

    member_data = {

        "telegram_id": payment.get(
            "telegram_id",
            user_id
        ),

        "username": payment.get(
            "username",
            ""
        ),

        "nama": payment.get(
            "nama",
            ""
        ),

        "paket": payment.get(
            "package",
            ""
        ),

        "harga": payment.get(
            "harga",
            ""
        ),

        "register": register_date,

        "expired": expired_date,

        # =================================================
        # STATUS LANGSUNG ACTIVE
        # =================================================

        "status": "ACTIVE",

        "referral": payment.get(
            "referral",
            ""
        )

    }

    print("")
    print("========================================")
    print("ADMIN APPROVE PAYMENT")
    print("========================================")
    print("DATA MEMBER:")
    print(member_data)

    # =====================================================
    # SIMPAN GOOGLE SHEETS
    #
    # HANYA DI SINI DATA MASUK GOOGLE SHEETS
    # =====================================================

    sheet_success = False

    try:

        sheet_success = await asyncio.to_thread(

            save_member,

            member_data

        )

    except Exception as e:

        print(
            "[GOOGLE SHEET ERROR]",
            e
        )

        sheet_success = False

    # =====================================================
    # GOOGLE SHEETS GAGAL
    #
    # USER BELUM ACTIVE
    # =====================================================

    if not sheet_success:

        await callback.answer(

            "❌ Gagal menyimpan ke Google Sheets. "
            "User belum diaktifkan.",

            show_alert=True

        )

        return

    # =====================================================
    # GOOGLE SHEETS BERHASIL
    #
    # BARU SEKARANG APPROVED
    # =====================================================

    payment["status"] = "APPROVED"

    payment["approved_at"] = (
        datetime.now().isoformat()
    )

    payment["approved_by"] = (
        callback.from_user.id
    )

    payment["sheet_success"] = True

    save_payment_state()

    # =====================================================
    # HAPUS TOMBOL ADMIN
    # =====================================================

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception as e:

        print(
            "[ADMIN BUTTON EDIT ERROR]",
            e
        )

    # =====================================================
    # UPDATE CAPTION ADMIN
    # =====================================================

    try:

        old_caption = (
            callback.message.caption or ""
        )

        new_caption = (

            old_caption

            + "\n\n"

            + "✅ <b>PEMBAYARAN DITERIMA</b>\n"

            + "📊 <b>GOOGLE SHEETS: ACTIVE</b>"

        )

        await callback.message.edit_caption(

            caption=new_caption,

            parse_mode="HTML"

        )

    except Exception as e:

        print(
            "[ADMIN CAPTION EDIT ERROR]",
            e
        )

    # =====================================================
    # BERITAHU USER
    # =====================================================

    try:

        await BOT.send_message(

            chat_id=int(user_id),

            text=(

                "🎉 <b>PAYMENT APPROVED</b> 🎉\n\n"

                f"📦 Paket: "
                f"<b>{payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

                "✅ <b>Status: ACTIVE</b>\n\n"

                "Pembayaran Anda telah "
                "diverifikasi dan disetujui oleh admin.\n\n"

                "🤖 <b>BOT AI ANDA SUDAH SIAP</b>\n\n"

                "Silahkan tekan <b>START</b> "
                "pada bot AI berikut.\n\n"

                "👉 <a href=\"https://t.me/AIGOLDASSISTANT_BOT\">"
                "START @AIGOLDASSISTANT_BOT"
                "</a>\n\n"

                "🚀 Selamat menggunakan "
                "layanan XAU AI Intelligence!"

            ),

            parse_mode="HTML",

            disable_web_page_preview=True

        )

    except Exception as e:

        print(
            "[USER NOTIFY ACCEPT ERROR]",
            e
        )

    await callback.answer(
        "✅ Pembayaran diterima & user ACTIVE."
    )


# =========================================================
# ADMIN TOLAK
# =========================================================

@DP.callback_query(
    F.data.startswith("proof_reject:")
)
async def proof_reject_callback(
    callback: CallbackQuery
):

    if not await check_admin(callback):
        return

    user_id = callback.data.split(
        ":",
        1
    )[1]

    payment = pending_payments.get(
        user_id
    )

    if not payment:

        await callback.answer(

            "❌ Data transaksi tidak ditemukan.",

            show_alert=True

        )

        return

    current_status = payment.get(
        "status",
        "WAITING_PROOF"
    )

    if current_status == "APPROVED":

        await callback.answer(

            "Transaksi sudah diterima.",

            show_alert=True

        )

        return

    if current_status == "REJECTED":

        await callback.answer(

            "Transaksi sudah ditolak.",

            show_alert=True

        )

        return

    payment["status"] = "REJECTED"

    payment["rejected_at"] = (
        datetime.now().isoformat()
    )

    payment["rejected_by"] = (
        callback.from_user.id
    )

    save_payment_state()

    # =====================================================
    # HAPUS TOMBOL
    # =====================================================

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception as e:

        print(
            "[ADMIN BUTTON EDIT ERROR]",
            e
        )

    # =====================================================
    # UPDATE CAPTION
    # =====================================================

    try:

        old_caption = (
            callback.message.caption or ""
        )

        new_caption = (

            old_caption

            + "\n\n"

            + "❌ <b>PEMBAYARAN DITOLAK</b>"

        )

        await callback.message.edit_caption(

            caption=new_caption,

            parse_mode="HTML"

        )

    except Exception as e:

        print(
            "[ADMIN CAPTION EDIT ERROR]",
            e
        )

    # =====================================================
    # BERITAHU USER
    # =====================================================

    try:

        await BOT.send_message(

            chat_id=int(user_id),

            text=(

                "❌ <b>BUKTI PEMBAYARAN DITOLAK</b>\n\n"

                f"📦 Paket: "
                f"<b>{payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

                "Admin belum dapat memverifikasi "
                "bukti pembayaran Anda.\n\n"

                "Silahkan hubungi admin untuk "
                "informasi lebih lanjut."

            ),

            parse_mode="HTML"

        )

    except Exception as e:

        print(
            "[USER NOTIFY REJECT ERROR]",
            e
        )

    await callback.answer(
        "❌ Pembayaran ditolak."
    )


# =========================================================
# USER KIRIM FOTO BUKTI TRANSFER
# =========================================================

@DP.message(F.photo)
async def proof_photo_handler(
    message: Message
):

    user = message.from_user

    user_id = str(
        user.id
    )

    payment = pending_payments.get(
        user_id
    )

    print(
        f"[PHOTO] user_id={user_id} "
        f"payment_found={bool(payment)}"
    )

    # =====================================================
    # TRANSAKSI TIDAK ADA
    # =====================================================

    if not payment:

        await message.answer(

            "⚠️ <b>Transaksi tidak ditemukan.</b>\n\n"

            "Silahkan pilih paket di bawah "
            "untuk membuat transaksi baru.",

            reply_markup=package_keyboard(),

            parse_mode="HTML"

        )

        return

    # =====================================================
    # SUDAH APPROVED
    # =====================================================

    if payment.get("status") == "APPROVED":

        await message.answer(

            "✅ <b>PEMBAYARAN SUDAH DITERIMA</b>\n\n"

            "Pembayaran Anda sudah diverifikasi oleh admin.\n\n"

            "Status: <b>ACTIVE</b>",

            parse_mode="HTML"

        )

        return

    # =====================================================
    # SUDAH REJECTED
    # =====================================================

    if payment.get("status") == "REJECTED":

        await message.answer(

            "❌ <b>BUKTI PEMBAYARAN DITOLAK</b>\n\n"

            "Silahkan hubungi admin untuk informasi "
            "lebih lanjut.",

            parse_mode="HTML"

        )

        return

    # =====================================================
    # BUKTI SUDAH DIKIRIM
    # =====================================================

    if payment.get("status") == "PROOF_SENT":

        await message.answer(

            "⏳ <b>BUKTI TRANSFER SUDAH DITERIMA</b>\n\n"

            f"📦 Paket: "
            f"<b>{payment['package']}</b>\n"

            f"💰 Nominal: "
            f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

            "Bukti sebelumnya sudah dikirim ke admin "
            "dan sedang menunggu verifikasi.\n\n"

            "Mohon tunggu proses aktivasi.\n"

            "Anda tidak perlu mengirim bukti ulang.",

            parse_mode="HTML"

        )

        return

    # =====================================================
    # FOTO RESOLUSI TERBESAR
    # =====================================================

    photo = message.photo[-1]

    telegram_id = user.id

    username = user.username or "-"

    nama = get_user_name(user)

    package_name = payment["package"]

    harga = payment["harga"]

    referral = payment.get(
        "referral",
        ""
    )

    # =====================================================
    # TANGGAL
    # =====================================================

    now = datetime.now()

    register_date = now.strftime(
        "%d-%m-%Y"
    )

    expired_date = (

        now
        + timedelta(
            days=payment["days"]
        )

    ).strftime(
        "%d-%m-%Y"
    )

    # =====================================================
    # SIMPAN TANGGAL KE PAYMENT STATE
    #
    # BUKAN GOOGLE SHEETS
    # =====================================================

    payment["register"] = register_date

    payment["expired"] = expired_date

    payment["username"] = (
        user.username or ""
    )

    payment["nama"] = nama

    payment["telegram_id"] = telegram_id

    save_payment_state()

    # =====================================================
    # ADMIN CAPTION
    # =====================================================

    referral_text = (
        referral
        if referral
        else "-"
    )

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

        "Status: <b>MENUNGGU APPROVAL</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        "📊 <b>GOOGLE SHEETS</b>\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "Status: <b>BELUM DISIMPAN</b>\n\n"

        "⚠️ Silahkan periksa bukti transfer.\n"

        "Data hanya akan dimasukkan ke Google Sheets "
        "setelah admin menekan tombol "
        "✅ <b>TERIMA</b>."

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

                reply_markup=admin_proof_keyboard(
                    telegram_id
                ),

                parse_mode="HTML"

            )

            admin_sent = True

            print(
                f"[ADMIN] Bukti transfer dikirim "
                f"ke {admin_id}"
            )

        except Exception as e:

            print(
                f"[ADMIN ERROR] {admin_id}: {e}"
            )

    # =====================================================
    # ADMIN BERHASIL MENERIMA
    # =====================================================

    if admin_sent:

        payment["status"] = "PROOF_SENT"

        payment["proof_file_id"] = (
            photo.file_id
        )

        payment["proof_sent_at"] = (
            datetime.now().isoformat()
        )

        save_payment_state()

        # -------------------------------------------------
        # BALAS USER
        # -------------------------------------------------

        await message.answer(

            "✅ <b>BUKTI TRANSFER BERHASIL DITERIMA</b>\n\n"

            f"📦 Paket: "
            f"<b>{package_name}</b>\n"

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

        payment["status"] = "WAITING_PROOF"

        save_payment_state()

        await message.answer(

            "⚠️ <b>BUKTI TRANSFER BELUM TERKIRIM KE ADMIN</b>\n\n"

            "Sistem gagal mengirim bukti ke admin.\n\n"

            "Silahkan coba kirim bukti transfer "
            "sekali lagi.\n\n"

            "Anda <b>tidak perlu /start ulang</b>.",

            parse_mode="HTML"

        )


# =========================================================
# USER MENGIRIM FILE / DOCUMENT
# =========================================================

@DP.message(F.document)
async def proof_document_handler(
    message: Message
):

    user = message.from_user

    user_id = str(
        user.id
    )

    payment = pending_payments.get(
        user_id
    )

    if not payment:

        await message.answer(

            "⚠️ Transaksi tidak ditemukan.\n\n"

            "Silahkan pilih paket terlebih dahulu.",

            reply_markup=package_keyboard()

        )

        return

    if payment.get("status") == "PROOF_SENT":

        await message.answer(

            "⏳ <b>BUKTI TRANSFER SUDAH DITERIMA</b>\n\n"

            "Bukti sebelumnya sudah dikirim "
            "ke admin untuk verifikasi.\n\n"

            "Mohon tunggu proses aktivasi.",

            parse_mode="HTML"

        )

        return

    if payment.get("status") == "APPROVED":

        await message.answer(

            "✅ <b>PEMBAYARAN SUDAH APPROVED</b>\n\n"

            "Status Anda: <b>ACTIVE</b>.",

            parse_mode="HTML"

        )

        return

    await message.answer(

        "📸 Silahkan kirim "
        "<b>screenshot/foto bukti transfer</b> "
        "langsung sebagai foto ke chat ini.\n\n"

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

    user_id = str(
        user.id
    )

    payment = pending_payments.get(
        user_id
    )

    if payment:

        status = payment.get(
            "status",
            "WAITING_PROOF"
        )

        if status == "APPROVED":

            await message.answer(

                "🎉 <b>PEMBAYARAN SUDAH APPROVED</b>\n\n"

                f"📦 Paket: "
                f"<b>{payment['package']}</b>\n\n"

                "✅ Status: <b>ACTIVE</b>\n\n"

                "👉 <a href=\"https://t.me/AIGOLDASSISTANT_BOT\">"
                "START @AIGOLDASSISTANT_BOT"
                "</a>",

                parse_mode="HTML",

                disable_web_page_preview=True

            )

            return

        if status == "REJECTED":

            await message.answer(

                "❌ <b>BUKTI PEMBAYARAN DITOLAK</b>\n\n"

                "Silahkan hubungi admin untuk "
                "informasi lebih lanjut.",

                parse_mode="HTML"

            )

            return

        if status == "PROOF_SENT":

            await message.answer(

                "⏳ <b>TRANSAKSI ANDA SEDANG DIPROSES</b>\n\n"

                f"📦 Paket: "
                f"<b>{payment['package']}</b>\n"

                f"💰 Nominal: "
                f"<b>{format_rupiah(payment['harga'])}</b>\n\n"

                "Bukti transfer sudah diterima "
                "dan dikirim ke admin.\n\n"

                "Mohon tunggu proses verifikasi.\n\n"

                "Anda tidak perlu menekan /start lagi.",

                parse_mode="HTML"

            )

            return

        await message.answer(

            "📸 <b>Bukti transfer belum diterima.</b>\n\n"

            "Silahkan kirim "
            "<b>screenshot bukti Transfer</b> "
            "sebagai foto di chat ini.\n\n"

            f"📦 Paket: "
            f"<b>{payment['package']}</b>\n"

            f"💰 Nominal: "
            f"<b>{format_rupiah(payment['harga'])}</b>",

            parse_mode="HTML"

        )

        return

    # -----------------------------------------------------
    # BELUM ADA TRANSAKSI
    # -----------------------------------------------------

    await message.answer(

        "Silahkan pilih paket terlebih dahulu:",

        reply_markup=package_keyboard()

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

    print(
        "========================================"
    )

    print(
        "🤖 XAU AI ASSISTANT BOT"
    )

    print(
        "========================================"
    )

    print(
        "BOT RUNNING"
    )

    print(
        "QRIS:",
        QRIS_PATH
    )

    print(
        "PAYMENT STATE:",
        PAYMENT_STATE_FILE
    )

    print(
        "TRANSAKSI AKTIF:",
        len(pending_payments)
    )

    print(
        "PACKAGES:"
    )

    print(
        " - Trial 4 Hari : Rp34.000"
    )

    print(
        " - 1 Bulan      : Rp149.000"
    )

    print(
        "========================================"
    )

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
