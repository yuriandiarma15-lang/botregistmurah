
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
    InlineKeyboardButton
)

from config import BOT_TOKEN, ADMIN_ID

from spreadsheet import (
    save_member,
    get_expired_group_members,
    update_member_status
)


# =========================================================
# BOT CONFIGURATION
# =========================================================

BOT = Bot(token=BOT_TOKEN)
DP = Dispatcher()

PRIVATE_GROUP_ID = -1002510797113

QRIS_PATH = "assets/qris.jpg"
PAYMENT_STATE_FILE = "payment_state.json"


# =========================================================
# ADMIN IDS
# =========================================================

if isinstance(ADMIN_ID, (list, tuple, set)):
    ADMIN_IDS = [int(x) for x in ADMIN_ID]
else:
    ADMIN_IDS = [int(ADMIN_ID)]


# =========================================================
# PACKAGE
# =========================================================

PACKAGE_MAP = {
    "4 hari": {
        "label": "4 hari",
        "price": 68000,
        "days": 4
    },

    "1BLN": {
        "label": "1 Bulan",
        "price": 199000,
        "days": 30
    }
}

CALLBACK_PACKAGE_MAP = {
    "TRIAL4": "4 hari",
    "1BLN": "1BLN"
}


# =========================================================
# PAYMENT STATE
# =========================================================

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

        return data if isinstance(data, dict) else {}

    except Exception as e:
        print("[PAYMENT STATE LOAD ERROR]", e)
        return {}


pending_payments = load_payment_state()


def save_payment_state():

    try:
        with open(
            PAYMENT_STATE_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                pending_payments,
                f,
                ensure_ascii=False,
                indent=2
            )

        return True

    except Exception as e:
        print("[PAYMENT STATE SAVE ERROR]", e)
        return False


# =========================================================
# HELPERS
# =========================================================

def format_rupiah(value):

    try:
        return f"Rp{int(value):,}".replace(",", ".")
    except Exception:
        return str(value)


def parse_start_payload(payload):

    payload = (payload or "").strip()

    if not payload:
        return {
            "package": None,
            "referral": ""
        }

    match = re.match(
        r"^JOIN_(TRIAL4|1BLN)$",
        payload,
        re.IGNORECASE
    )

    if match:
        code = match.group(1).upper()

        return {
            "package": CALLBACK_PACKAGE_MAP.get(code),
            "referral": ""
        }

    match = re.match(
        r"^JOIN_(TRIAL4|1BLN)_ref_(.+)$",
        payload,
        re.IGNORECASE
    )

    if match:
        code = match.group(1).upper()

        return {
            "package": CALLBACK_PACKAGE_MAP.get(code),
            "referral": match.group(2).strip()
        }

    return {
        "package": None,
        "referral": ""
    }


def package_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔥 TRIAL 4 HARI — Rp68.000",
                    callback_data="pkg_TRIAL4"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ 1 BULAN — Rp199.000",
                    callback_data="pkg_1BLN"
                )
            ]
        ]
    )


def admin_payment_keyboard(user_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ TERIMA",
                    callback_data=f"approve_{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ TOLAK",
                    callback_data=f"reject_{user_id}"
                )
            ]
        ]
    )


# =========================================================
# INVITE LINK
# =========================================================

async def create_one_time_invite_link():

    try:
        invite = await BOT.create_chat_invite_link(
            chat_id=PRIVATE_GROUP_ID,
            member_limit=1
        )

        print("[INVITE] Created:", invite.invite_link)

        return invite.invite_link

    except Exception as e:
        print("[INVITE LINK ERROR]", e)
        return None


# =========================================================
# EXPIRED MEMBER
# =========================================================

async def kick_expired_member(telegram_id):

    try:
        telegram_id = int(telegram_id)

        await BOT.ban_chat_member(
            chat_id=PRIVATE_GROUP_ID,
            user_id=telegram_id
        )

        print(f"[KICK] {telegram_id} removed")

        try:
            await BOT.unban_chat_member(
                chat_id=PRIVATE_GROUP_ID,
                user_id=telegram_id,
                only_if_banned=True
            )
        except Exception as e:
            print("[UNBAN ERROR]", e)

        return True

    except Exception as e:
        print(f"[KICK ERROR] {telegram_id}: {e}")
        return False


async def check_expired_members():

    print("[EXPIRED CHECK] Starting")

    try:
        expired_members = await asyncio.to_thread(
            get_expired_group_members
        )

        if not expired_members:
            print("[EXPIRED] No expired members")
            return

        for member in expired_members:

            telegram_id = member.get("telegram_id")

            if not telegram_id:
                continue

            kicked = await kick_expired_member(
                telegram_id
            )

            if kicked:
                updated = await asyncio.to_thread(
                    update_member_status,
                    telegram_id,
                    "EXPIRED"
                )

                print(
                    f"[SHEET] {telegram_id} EXPIRED: {updated}"
                )

    except Exception as e:
        print("[CHECK EXPIRED ERROR]", e)


async def expired_monitor():

    print("[EXPIRED MONITOR] Started")

    await asyncio.sleep(10)

    while True:

        try:
            await check_expired_members()

        except Exception as e:
            print("[EXPIRED MONITOR ERROR]", e)

        await asyncio.sleep(600)


# =========================================================
# START
# =========================================================

@DP.message(CommandStart())
async def start_handler(message: Message):

    user_id = message.from_user.id
    username = message.from_user.username or ""
    nama = message.from_user.full_name or ""

    payload = ""

    if message.text:
        parts = message.text.split(maxsplit=1)

        if len(parts) > 1:
            payload = parts[1].strip()

    parsed = parse_start_payload(payload)

    package = parsed.get("package")
    referral = parsed.get("referral", "")

    print(
        f"[START] {user_id} @{username} payload={payload}"
    )

    if str(user_id) not in pending_payments:

        pending_payments[str(user_id)] = {
            "telegram_id": user_id,
            "username": username,
            "nama": nama,
            "package": "",
            "harga": "",
            "days": 0,
            "referral": referral,
            "status": "STARTED",
            "created_at": datetime.now().isoformat()
        }

    else:
        pending_payments[str(user_id)]["username"] = username
        pending_payments[str(user_id)]["nama"] = nama

        if referral:
            pending_payments[str(user_id)]["referral"] = referral

    save_payment_state()

    if package and package in PACKAGE_MAP:
        await send_payment_instruction(
            message,
            package
        )
        return

    text = (
        "🤖 <b>XAU AI ASSISTANT</b>\n\n"
        "Private AI Assistant untuk analisis XAUUSD "
        "menggunakan Smart Money Concept (SMC).\n\n"
        "📊 Market Structure\n"
        "💧 Liquidity\n"
        "📦 Order Block\n"
        "⚡ FVG\n"
        "🎯 Real-time Signal\n"
        "🛡 Risk Management\n\n"
        "Pilih paket membership:"
    )

    await message.answer(
        text,
        reply_markup=package_keyboard(),
        parse_mode="HTML"
    )


# =========================================================
# PAYMENT INSTRUCTION
# =========================================================

async def send_payment_instruction(message, package_name):

    user_id = message.from_user.id
    package = PACKAGE_MAP.get(package_name)

    if not package:
        await message.answer("❌ Paket tidak ditemukan.")
        return

    username = message.from_user.username or ""
    nama = message.from_user.full_name or ""

    existing = pending_payments.get(str(user_id), {})
    referral = existing.get("referral", "")

    pending_payments[str(user_id)] = {
        "telegram_id": user_id,
        "username": username,
        "nama": nama,
        "package": package_name,
        "harga": package["price"],
        "days": package["days"],
        "referral": referral,
        "status": "WAITING_PROOF",
        "created_at": datetime.now().isoformat()
    }

    save_payment_state()

    text = (
        "💳 <b>PEMBAYARAN XAU AI ASSISTANT</b>\n\n"
        f"📦 Paket: <b>{package['label']}</b>\n"
        f"💰 Harga: <b>{format_rupiah(package['price'])}</b>\n\n"
        "Silakan lakukan pembayaran melalui QRIS.\n\n"
        "Setelah pembayaran selesai:\n"
        "1️⃣ Screenshot bukti pembayaran\n"
        "2️⃣ Kirim foto bukti pembayaran ke bot ini\n"
        "3️⃣ Ikuti instruksi pengisian data broker\n\n"
        "Admin akan melakukan verifikasi pembayaran."
    )

    if os.path.exists(QRIS_PATH):

        await message.answer_photo(
            photo=FSInputFile(QRIS_PATH),
            caption=text,
            parse_mode="HTML"
        )

    else:
        await message.answer(
            text,
            parse_mode="HTML"
        )

        print("[QRIS ERROR] File not found:", QRIS_PATH)


# =========================================================
# PACKAGE CALLBACK
# =========================================================

@DP.callback_query(F.data.startswith("pkg_"))
async def package_callback(callback: CallbackQuery):

    user_id = callback.from_user.id

    code = callback.data.replace("pkg_", "", 1)
    package_name = CALLBACK_PACKAGE_MAP.get(code)

    if not package_name:
        await callback.answer(
            "Paket tidak ditemukan.",
            show_alert=True
        )
        return

    package = PACKAGE_MAP[package_name]

    user = callback.from_user

    existing = pending_payments.get(str(user_id), {})
    referral = existing.get("referral", "")

    pending_payments[str(user_id)] = {
        "telegram_id": user_id,
        "username": user.username or "",
        "nama": user.full_name or "",
        "package": package_name,
        "harga": package["price"],
        "days": package["days"],
        "referral": referral,
        "status": "WAITING_PROOF",
        "created_at": datetime.now().isoformat()
    }

    save_payment_state()

    text = (
        "💳 <b>PEMBAYARAN XAU AI ASSISTANT</b>\n\n"
        f"📦 Paket: <b>{package['label']}</b>\n"
        f"💰 Harga: <b>{format_rupiah(package['price'])}</b>\n\n"
        "Silakan lakukan pembayaran melalui QRIS.\n\n"
        "Setelah membayar, kirim foto bukti pembayaran "
        "ke bot ini.\n\n"
        "Admin akan melakukan verifikasi."
    )

    if os.path.exists(QRIS_PATH):

        await BOT.send_photo(
            chat_id=user_id,
            photo=FSInputFile(QRIS_PATH),
            caption=text,
            parse_mode="HTML"
        )

    else:
        await BOT.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML"
        )

    await callback.answer("Paket dipilih.")


# =========================================================
# RECEIVE PAYMENT PROOF
# =========================================================

@DP.message(F.photo)
async def payment_proof_handler(message: Message):

    user_id = message.from_user.id

    payment = pending_payments.get(str(user_id))

    if not payment:
        await message.answer(
            "❌ Belum ada transaksi aktif.\n\n"
            "Silakan tekan /start untuk memilih paket."
        )
        return

    status = payment.get("status", "")

    if status != "WAITING_PROOF":
        await message.answer(
            "❌ Bot tidak sedang menunggu bukti pembayaran."
        )
        return

    # Simpan file ID bukti transfer
    photo = message.photo[-1]

    payment["proof_file_id"] = photo.file_id
    payment["proof_time"] = datetime.now().isoformat()
    payment["status"] = "WAITING_PROFILE"

    save_payment_state()

    # Minta data broker dari user
    await message.answer(
        "✅ <b>Bukti transfer berhasil diterima!</b>\n\n"
        "Silakan isi data berikut untuk menyesuaikan "
        "Signal AI dengan broker yang kamu gunakan.\n\n"
        "📋 <b>FORMAT DATA</b>\n\n"
        "Nama :\n"
        "Broker :\n"
        "Gmail :\n\n"
        "Silakan isi format tersebut dan kirim kembali "
        "ke sini ya.\n\n"
        "Pastikan data yang kamu kirim sudah benar.",
        parse_mode="HTML"
    )

    print(
        f"[PAYMENT PROOF] User {user_id} waiting for profile"
    )


# =========================================================
# RECEIVE BROKER PROFILE
# =========================================================

@DP.message(F.text)
async def broker_profile_handler(message: Message):

    user_id = message.from_user.id

    payment = pending_payments.get(str(user_id))

    if not payment:
        return

    if payment.get("status") != "WAITING_PROFILE":
        return

    text = message.text.strip()

    profile = {}

    for line in text.splitlines():

        if ":" not in line:
            continue

        key, value = line.split(":", 1)

        key = key.strip().lower()
        value = value.strip()

        if key in ("nama", "name"):
            profile["nama"] = value

        elif key in ("broker", "broker yang digunakan"):
            profile["broker"] = value

        elif key in ("gmail", "email", "e-mail"):
            profile["gmail"] = value

    nama = profile.get("nama", "")
    broker = profile.get("broker", "")
    gmail = profile.get("gmail", "")

    # Validasi kelengkapan
    if not nama or not broker or not gmail:

        await message.answer(
            "⚠️ <b>Data belum lengkap.</b>\n\n"
            "Mohon kirim ulang dengan format:\n\n"
            "Nama : Nama Lengkap\n"
            "Broker : Nama Broker\n"
            "Gmail : email@gmail.com\n\n"
            "Pastikan ketiga data sudah diisi.",
            parse_mode="HTML"
        )
        return

    # Validasi format email
    if not re.match(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        gmail
    ):

        await message.answer(
            "⚠️ Format Gmail/email tidak valid.\n\n"
            "Mohon periksa kembali alamat email kamu."
        )
        return

    # Simpan data profil
    payment["nama"] = nama
    payment["broker"] = broker
    payment["gmail"] = gmail

    payment["profile_submitted_at"] = datetime.now().isoformat()
    payment["status"] = "WAITING_ADMIN"

    save_payment_state()

    package_name = payment.get("package", "")
    harga = payment.get("harga", "")
    username = payment.get("username", "")

    caption = (
        "💳 <b>PEMBAYARAN + DATA BROKER BARU</b>\n\n"

        "👤 <b>DATA USER</b>\n"
        f"Nama: <b>{nama}</b>\n"
        f"Broker: <b>{broker}</b>\n"
        f"Gmail: <code>{gmail}</code>\n\n"

        "📱 <b>DATA TELEGRAM</b>\n"
        f"Username: @{username if username else '-'}\n"
        f"Telegram ID: <code>{user_id}</code>\n\n"

        "💰 <b>DATA PEMBAYARAN</b>\n"
        f"Paket: <b>{package_name}</b>\n"
        f"Harga: <b>{format_rupiah(harga)}</b>\n\n"

        "📋 Status: <b>MENUNGGU VERIFIKASI ADMIN</b>\n\n"
        "Silakan periksa bukti transfer dan data user."
    )

    keyboard = admin_payment_keyboard(user_id)

    # Kirim bukti transfer dan data ke admin
    sent_to_admin = False

    for admin_id in ADMIN_IDS:

        try:
            await BOT.send_photo(
                chat_id=admin_id,
                photo=payment["proof_file_id"],
                caption=caption,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            sent_to_admin = True

            print(
                f"[ADMIN NOTIFICATION] User {user_id} sent to {admin_id}"
            )

        except Exception as e:
            print(
                f"[ADMIN NOTIFICATION ERROR] {admin_id}: {e}"
            )

    if not sent_to_admin:

        payment["status"] = "WAITING_PROFILE"
        save_payment_state()

        await message.answer(
            "⚠️ Data sudah diterima, tetapi notifikasi admin "
            "gagal dikirim.\n\n"
            "Silakan coba kirim kembali beberapa saat lagi."
        )
        return

    await message.answer(
        "✅ <b>Data berhasil diterima!</b>\n\n"
        f"👤 Nama: {nama}\n"
        f"🏦 Broker: {broker}\n"
        f"📧 Gmail: {gmail}\n\n"
        "Bukti transfer dan data kamu sudah dikirim "
        "ke admin untuk diverifikasi.\n\n"
        "Mohon tunggu konfirmasi pembayaran ya. 🙏",
        parse_mode="HTML"
    )

    print(
        f"[PROFILE COMPLETE] {user_id} | "
        f"{nama} | {broker} | {gmail}"
    )


# =========================================================
# ADMIN APPROVE
# =========================================================

@DP.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery):

    admin_id = callback.from_user.id

    if admin_id not in ADMIN_IDS:
        await callback.answer(
            "❌ Tidak memiliki akses.",
            show_alert=True
        )
        return

    try:
        user_id = int(
            callback.data.replace("approve_", "", 1)
        )
    except Exception:
        await callback.answer(
            "User ID tidak valid.",
            show_alert=True
        )
        return

    payment = pending_payments.get(str(user_id))

    if not payment:
        await callback.answer(
            "❌ Data pembayaran tidak ditemukan.",
            show_alert=True
        )
        return

    current_status = payment.get("status", "")

    if current_status == "APPROVED":
        await callback.answer(
            "Pembayaran sudah diterima.",
            show_alert=True
        )
        return

    if current_status != "WAITING_ADMIN":
        await callback.answer(
            f"Status saat ini: {current_status}",
            show_alert=True
        )
        return

    package_name = payment.get("package", "")
    package = PACKAGE_MAP.get(package_name)

    if not package:
        await callback.answer(
            "❌ Paket tidak ditemukan.",
            show_alert=True
        )
        return

    now = datetime.now()

    register_date = now.strftime("%d-%m-%Y")

    expired_date = (
        now + timedelta(days=package["days"])
    ).strftime("%d-%m-%Y")

    # Data member untuk Google Sheets
    member_data = {
        "telegram_id": payment.get("telegram_id", user_id),
        "username": payment.get("username", ""),
        "nama": payment.get("nama", ""),
        "broker": payment.get("broker", ""),
        "gmail": payment.get("gmail", ""),
        "paket": payment.get("package", ""),
        "harga": payment.get("harga", ""),
        "register": register_date,
        "expired": expired_date,
        "status": "ACTIVE",
        "referral": "grup"
    }

    print("[APPROVE] SAVE MEMBER")
    print(member_data)

    # Simpan ke Google Sheets
    saved = await asyncio.to_thread(
        save_member,
        member_data
    )

    if not saved:
        await callback.answer(
            "❌ Gagal menyimpan ke Google Sheets.",
            show_alert=True
        )
        return

    # Buat invite link sekali pakai
    invite_link = await create_one_time_invite_link()

    if not invite_link:

        payment["status"] = "APPROVED"
        payment["register"] = register_date
        payment["expired"] = expired_date
        payment["invite_link"] = ""

        save_payment_state()

        try:
            await BOT.send_message(
                chat_id=user_id,
                text=(
                    "✅ <b>Pembayaran kamu sudah DISETUJUI.</b>\n\n"
                    f"📦 Paket: <b>{package_name}</b>\n"
                    f"📅 Aktif: <b>{register_date}</b>\n"
                    f"📅 Expired: <b>{expired_date}</b>\n\n"
                    "⚠️ Invite link grup gagal dibuat sementara.\n"
                    "Silakan hubungi admin."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            print("[USER APPROVE MESSAGE ERROR]", e)

        await callback.answer(
            "Pembayaran diterima, tetapi invite gagal dibuat.",
            show_alert=True
        )
        return

    # Simpan status pembayaran
    payment["status"] = "APPROVED"
    payment["register"] = register_date
    payment["expired"] = expired_date
    payment["invite_link"] = invite_link
    payment["approved_at"] = datetime.now().isoformat()
    payment["approved_by"] = admin_id

    save_payment_state()

    # Kirim invite ke user
    success_text = (
        "🎉 <b>PEMBAYARAN BERHASIL!</b>\n\n"
        f"📦 Paket: <b>{package_name}</b>\n"
        f"💰 Harga: <b>{format_rupiah(payment.get('harga', 0))}</b>\n\n"
        f"📅 Mulai: <b>{register_date}</b>\n"
        f"📅 Expired: <b>{expired_date}</b>\n\n"
        "🔐 <b>JOIN PRIVATE GROUP</b>\n\n"
        f"{invite_link}\n\n"
        "⚠️ Link ini hanya dapat digunakan untuk "
        "<b>1 member</b>.\n\n"
        "Jangan bagikan link ini kepada orang lain."
    )

    try:
        await BOT.send_message(
            chat_id=user_id,
            text=success_text,
            parse_mode="HTML"
        )
    except Exception as e:
        print("[SEND INVITE ERROR]", e)

    # Update pesan admin
    try:
        await callback.message.edit_caption(
            caption=(
                "✅ <b>PAYMENT APPROVED</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"📦 Paket: <b>{package_name}</b>\n"
                f"📅 Expired: <b>{expired_date}</b>\n\n"
                f"👤 Nama: {payment.get('nama', '')}\n"
                f"🏦 Broker: {payment.get('broker', '')}\n"
                f"📧 Gmail: {payment.get('gmail', '')}\n\n"
                "📊 Sheet: <b>ACTIVE</b>\n"
                "🔐 Invite: <b>CREATED</b>\n"
                "🏷 Reff: <b>grup</b>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print("[ADMIN MESSAGE UPDATE ERROR]", e)

    await callback.answer("✅ Pembayaran diterima.")


# =========================================================
# ADMIN REJECT
# =========================================================

@DP.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):

    admin_id = callback.from_user.id

    if admin_id not in ADMIN_IDS:
        await callback.answer(
            "❌ Tidak memiliki akses.",
            show_alert=True
        )
        return

    try:
        user_id = int(
            callback.data.replace("reject_", "", 1)
        )
    except Exception:
        await callback.answer(
            "User ID tidak valid.",
            show_alert=True
        )
        return

    payment = pending_payments.get(str(user_id))

    if not payment:
        await callback.answer(
            "Data pembayaran tidak ditemukan.",
            show_alert=True
        )
        return

    payment["status"] = "REJECTED"
    payment["rejected_at"] = datetime.now().isoformat()
    payment["rejected_by"] = admin_id

    save_payment_state()

    try:
        await BOT.send_message(
            chat_id=user_id,
            text=(
                "❌ <b>PEMBAYARAN DITOLAK</b>\n\n"
                "Bukti pembayaran kamu belum dapat "
                "diverifikasi oleh admin.\n\n"
                "Silakan hubungi admin jika membutuhkan bantuan."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print("[REJECT USER MESSAGE ERROR]", e)

    try:
        await callback.message.edit_caption(
            caption=(
                "❌ <b>PAYMENT REJECTED</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"Status: <b>REJECTED</b>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print("[REJECT ADMIN MESSAGE ERROR]", e)

    await callback.answer("Pembayaran ditolak.")


# =========================================================
# CANCEL
# =========================================================

@DP.message(Command("cancel"))
async def cancel_handler(message: Message):

    user_id = message.from_user.id

    payment = pending_payments.get(str(user_id))

    if payment and payment.get("status") != "APPROVED":
        payment["status"] = "CANCELLED"
        save_payment_state()

    await message.answer(
        "❌ Transaksi dibatalkan.\n\n"
        "Gunakan /start untuk memulai kembali."
    )


# =========================================================
# ADMIN CHECK EXPIRED
# =========================================================

@DP.message(Command("checkexpired"))
async def manual_check_expired(message: Message):

    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Tidak memiliki akses.")
        return

    await message.answer("🔎 Mengecek member expired...")

    await check_expired_members()

    await message.answer("✅ Pengecekan expired selesai.")


# =========================================================
# ERROR HANDLER
# =========================================================

@DP.errors()
async def global_error_handler(event):

    print("[BOT ERROR]", event.exception)


# =========================================================
# MAIN
# =========================================================

async def main():

    print("==========================================")
    print("🤖 XAU AI ASSISTANT BOT STARTING...")
    print("==========================================")

    print("PRIVATE GROUP:", PRIVATE_GROUP_ID)
    print("ADMIN IDS:", ADMIN_IDS)
    print("QRIS PATH:", QRIS_PATH)

    print("")
    print("PACKAGES:")
    print(" - TRIAL 4 HARI : Rp68.000")
    print(" - 1 BULAN      : Rp199.000")

    print("")
    print("BROKER PROFILE:")
    print(" - Nama")
    print(" - Broker")
    print(" - Gmail")

    print("")
    print("EXPIRED MONITOR: EVERY 10 MINUTES")
    print("==========================================")

    monitor_task = asyncio.create_task(
        expired_monitor()
    )

    try:
        await DP.start_polling(BOT)

    finally:
        monitor_task.cancel()

        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        await BOT.session.close()


if __name__ == "__main__":
    asyncio.run(main())
