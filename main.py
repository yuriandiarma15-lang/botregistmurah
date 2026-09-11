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

from config import (
    BOT_TOKEN,
    ADMIN_ID
)

from spreadsheet import (
    save_member,
    get_expired_group_members,
    update_member_status
)


# =========================================================
# BOT
# =========================================================

BOT = Bot(
    token=BOT_TOKEN
)

DP = Dispatcher()


# =========================================================
# PRIVATE GROUP
# =========================================================

PRIVATE_GROUP_ID = -1004448252129


# =========================================================
# QRIS
# =========================================================

QRIS_PATH = "assets/qris.jpg"


# =========================================================
# PAYMENT STATE
# =========================================================

PAYMENT_STATE_FILE = "payment_state.json"


# =========================================================
# ADMIN IDS
# =========================================================

if isinstance(ADMIN_ID, (list, tuple, set)):

    ADMIN_IDS = [
        int(x)
        for x in ADMIN_ID
    ]

else:

    ADMIN_IDS = [
        int(ADMIN_ID)
    ]


# =========================================================
# PACKAGE
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
# CALLBACK PACKAGE
# =========================================================

CALLBACK_PACKAGE_MAP = {

    "TRIAL4": "4 hari",

    "1BLN": "1BLN"

}


# =========================================================
# LOAD PAYMENT STATE
# =========================================================

def load_payment_state():

    if not os.path.exists(
        PAYMENT_STATE_FILE
    ):

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


# =========================================================
# SAVE PAYMENT STATE
# =========================================================

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

        print(
            "[PAYMENT STATE SAVE ERROR]",
            e
        )

        return False


# =========================================================
# GLOBAL PAYMENT STATE
# =========================================================

pending_payments = load_payment_state()


# =========================================================
# START PAYLOAD PARSER
# =========================================================

def parse_start_payload(
    payload
):

    payload = (
        payload or ""
    ).strip()


    if not payload:

        return {
            "package": None,
            "referral": ""
        }


    # -----------------------------------------------------
    # JOIN_TRIAL4
    # JOIN_1BLN
    # -----------------------------------------------------

    match = re.match(
        r"^JOIN_(TRIAL4|1BLN)$",
        payload,
        re.IGNORECASE
    )

    if match:

        code = match.group(1).upper()

        return {

            "package":
                CALLBACK_PACKAGE_MAP.get(
                    code
                ),

            "referral": ""

        }


    # -----------------------------------------------------
    # JOIN_TRIAL4_ref_AKMAL
    # JOIN_1BLN_ref_AKMAL
    # -----------------------------------------------------

    match = re.match(
        r"^JOIN_(TRIAL4|1BLN)_ref_(.+)$",
        payload,
        re.IGNORECASE
    )

    if match:

        code = match.group(1).upper()

        referral = match.group(2).strip()


        return {

            "package":
                CALLBACK_PACKAGE_MAP.get(
                    code
                ),

            "referral": referral

        }


    return {

        "package": None,

        "referral": ""

    }


# =========================================================
# PACKAGE KEYBOARD
# =========================================================

def package_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🔥 TRIAL 4 HARI — Rp34.000",
                    callback_data="pkg_TRIAL4"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⭐ 1 BULAN — Rp149.000",
                    callback_data="pkg_1BLN"
                )
            ]

        ]
    )


# =========================================================
# PAYMENT KEYBOARD
# =========================================================

def admin_payment_keyboard(
    user_id
):

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
# CREATE ONE-TIME INVITE
# =========================================================

async def create_one_time_invite_link():

    try:

        invite = await BOT.create_chat_invite_link(

            chat_id=PRIVATE_GROUP_ID,

            member_limit=1

        )


        print(
            "[INVITE] Berhasil dibuat:"
        )

        print(
            invite.invite_link
        )


        return invite.invite_link


    except Exception as e:

        print(
            "[INVITE LINK ERROR]",
            e
        )

        return None


# =========================================================
# KICK EXPIRED MEMBER
# =========================================================

async def kick_expired_member(
    telegram_id
):

    try:

        telegram_id = int(
            telegram_id
        )


        # -------------------------------------------------
        # BAN TERLEBIH DAHULU
        # -------------------------------------------------

        await BOT.ban_chat_member(

            chat_id=PRIVATE_GROUP_ID,

            user_id=telegram_id

        )


        print(
            f"[KICK] "
            f"{telegram_id} berhasil dikeluarkan."
        )


        # -------------------------------------------------
        # UNBAN
        #
        # Tujuannya seperti KICK biasa.
        # User tidak permanent ban.
        # Jika renew nanti bisa masuk lagi.
        # -------------------------------------------------

        try:

            await BOT.unban_chat_member(

                chat_id=PRIVATE_GROUP_ID,

                user_id=telegram_id,

                only_if_banned=True

            )


            print(
                f"[UNBAN] "
                f"{telegram_id} berhasil."
            )


        except Exception as e:

            print(
                f"[UNBAN ERROR] "
                f"{telegram_id}: {e}"
            )


        return True


    except Exception as e:

        print(
            f"[KICK ERROR] "
            f"{telegram_id}: {e}"
        )

        return False


# =========================================================
# CHECK EXPIRED MEMBERS
# =========================================================

async def check_expired_members():

    print("")
    print(
        "========================================"
    )

    print(
        "[EXPIRED CHECK]"
    )

    print(
        "========================================"
    )


    try:

        expired_members = await asyncio.to_thread(

            get_expired_group_members

        )


        if not expired_members:

            print(
                "[EXPIRED] "
                "Tidak ada member expired."
            )

            return


        print(
            f"[EXPIRED] "
            f"Ditemukan {len(expired_members)} member."
        )


        for member in expired_members:

            telegram_id = member.get(
                "telegram_id"
            )

            username = member.get(
                "username",
                ""
            )

            nama = member.get(
                "nama",
                ""
            )

            paket = member.get(
                "paket",
                ""
            )

            expired = member.get(
                "expired",
                ""
            )


            print("")
            print(
                "----------------------------------------"
            )

            print(
                "Telegram ID:",
                telegram_id
            )

            print(
                "Username:",
                username
            )

            print(
                "Nama:",
                nama
            )

            print(
                "Paket:",
                paket
            )

            print(
                "Expired:",
                expired
            )


            # -------------------------------------------------
            # KICK
            # -------------------------------------------------

            kicked = await kick_expired_member(

                telegram_id

            )


            # -------------------------------------------------
            # UPDATE SHEET
            # -------------------------------------------------

            if kicked:

                updated = await asyncio.to_thread(

                    update_member_status,

                    telegram_id,

                    "EXPIRED"

                )


                if updated:

                    print(
                        f"[SHEET] "
                        f"{telegram_id} -> EXPIRED"
                    )


                else:

                    print(
                        f"[SHEET ERROR] "
                        f"{telegram_id} gagal update."
                    )


            print(
                "----------------------------------------"
            )


    except Exception as e:

        print(
            "[CHECK EXPIRED ERROR]",
            e
        )


# =========================================================
# EXPIRED MONITOR
# =========================================================

async def expired_monitor():

    print(
        "[EXPIRED MONITOR] STARTED"
    )

    print(
        "[EXPIRED MONITOR] "
        "Check setiap 10 menit."
    )


    # -----------------------------------------------------
    # Tunggu bot startup
    # -----------------------------------------------------

    await asyncio.sleep(
        10
    )


    while True:

        try:

            await check_expired_members()


        except Exception as e:

            print(
                "[EXPIRED MONITOR ERROR]",
                e
            )


        # -------------------------------------------------
        # 10 MENIT
        # -------------------------------------------------

        await asyncio.sleep(
            600
        )


# =========================================================
# /START
# =========================================================

@DP.message(
    CommandStart()
)
async def start_handler(
    message: Message
):

    user_id = message.from_user.id

    username = (
        message.from_user.username
        or ""
    )

    nama = (
        message.from_user.full_name
        or ""
    )


    # -----------------------------------------------------
    # PAYLOAD
    # -----------------------------------------------------

    payload = ""


    if message.text:

        parts = message.text.split(
            maxsplit=1
        )

        if len(parts) > 1:

            payload = parts[1].strip()


    parsed = parse_start_payload(
        payload
    )


    package = parsed.get(
        "package"
    )

    referral = parsed.get(
        "referral",
        ""
    )


    print(
        f"[START] "
        f"{user_id} "
        f"{username} "
        f"payload={payload}"
    )


    # -----------------------------------------------------
    # SIMPAN START DATA
    # -----------------------------------------------------

    if str(user_id) not in pending_payments:

        pending_payments[
            str(user_id)
        ] = {

            "telegram_id": user_id,

            "username": username,

            "nama": nama,

            "package": "",

            "harga": "",

            "days": 0,

            "referral": referral,

            "status": "STARTED",

            "created_at":
                datetime.now().isoformat()

        }

    else:

        pending_payments[
            str(user_id)
        ]["username"] = username

        pending_payments[
            str(user_id)
        ]["nama"] = nama


        if referral:

            pending_payments[
                str(user_id)
            ]["referral"] = referral


    save_payment_state()


    # -----------------------------------------------------
    # JIKA LANDING PAGE SUDAH PILIH PAKET
    # -----------------------------------------------------

    if package:

        if package in PACKAGE_MAP:

            await send_payment_instruction(

                message,

                package

            )

            return


    # -----------------------------------------------------
    # MENU UTAMA
    # -----------------------------------------------------

    text = (

        "🤖 <b>XAU AI ASSISTANT</b>\n\n"

        "Private AI Assistant untuk "
        "analisis XAUUSD menggunakan "
        "Smart Money Concept (SMC).\n\n"

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
# SEND PAYMENT INSTRUCTION
# =========================================================

async def send_payment_instruction(
    message,
    package_name
):

    user_id = message.from_user.id

    package = PACKAGE_MAP.get(
        package_name
    )


    if not package:

        await message.answer(
            "❌ Paket tidak ditemukan."
        )

        return


    # -----------------------------------------------------
    # USER DATA
    # -----------------------------------------------------

    username = (
        message.from_user.username
        or ""
    )

    nama = (
        message.from_user.full_name
        or ""
    )


    # -----------------------------------------------------
    # EXISTING REFERRAL
    # -----------------------------------------------------

    existing = pending_payments.get(
        str(user_id),
        {}
    )


    referral = existing.get(
        "referral",
        ""
    )


    # -----------------------------------------------------
    # UPDATE PAYMENT
    # -----------------------------------------------------

    pending_payments[
        str(user_id)
    ] = {

        "telegram_id": user_id,

        "username": username,

        "nama": nama,

        "package": package_name,

        "harga": package["price"],

        "days": package["days"],

        "referral": referral,

        "status": "WAITING_PROOF",

        "created_at":
            datetime.now().isoformat()

    }


    save_payment_state()


    # -----------------------------------------------------
    # PAYMENT TEXT
    # -----------------------------------------------------

    price_text = (
        f"Rp{package['price']:,}"
        .replace(",", ".")
    )


    text = (

        "💳 <b>PEMBAYARAN XAU AI ASSISTANT</b>\n\n"

        f"📦 Paket: <b>{package['label']}</b>\n"

        f"💰 Harga: <b>{price_text}</b>\n\n"

        "Silakan lakukan pembayaran "
        "melalui QRIS di bawah.\n\n"

        "Setelah pembayaran selesai:\n"

        "1️⃣ Screenshot bukti pembayaran\n"
        "2️⃣ Kirim screenshot tersebut "
        "langsung ke bot ini\n"
        "3️⃣ Tunggu konfirmasi admin\n\n"

        "Setelah pembayaran dikonfirmasi, "
        "bot akan memberikan <b>invite link "
        "private group</b>."
    )


    # -----------------------------------------------------
    # QRIS
    # -----------------------------------------------------

    if os.path.exists(
        QRIS_PATH
    ):

        await message.answer_photo(

            photo=FSInputFile(
                QRIS_PATH
            ),

            caption=text,

            parse_mode="HTML"

        )

    else:

        await message.answer(
            text,
            parse_mode="HTML"
        )

        print(
            "[QRIS ERROR] "
            f"File tidak ditemukan: {QRIS_PATH}"
        )


# =========================================================
# PACKAGE CALLBACK
# =========================================================

@DP.callback_query(
    F.data.startswith("pkg_")
)
async def package_callback(
    callback: CallbackQuery
):

    user_id = callback.from_user.id


    code = callback.data.replace(
        "pkg_",
        "",
        1
    )


    package_name = CALLBACK_PACKAGE_MAP.get(
        code
    )


    if not package_name:

        await callback.answer(
            "Paket tidak ditemukan.",
            show_alert=True
        )

        return


    # -----------------------------------------------------
    # FAKE MESSAGE OBJECT
    #
    # Kita kirim instruksi langsung ke chat.
    # -----------------------------------------------------

    user = callback.from_user

    username = (
        user.username
        or ""
    )

    nama = (
        user.full_name
        or ""
    )


    package = PACKAGE_MAP[
        package_name
    ]


    existing = pending_payments.get(
        str(user_id),
        {}
    )


    referral = existing.get(
        "referral",
        ""
    )


    pending_payments[
        str(user_id)
    ] = {

        "telegram_id": user_id,

        "username": username,

        "nama": nama,

        "package": package_name,

        "harga": package["price"],

        "days": package["days"],

        "referral": referral,

        "status": "WAITING_PROOF",

        "created_at":
            datetime.now().isoformat()

    }


    save_payment_state()


    price_text = (
        f"Rp{package['price']:,}"
        .replace(",", ".")
    )


    text = (

        "💳 <b>PEMBAYARAN XAU AI ASSISTANT</b>\n\n"

        f"📦 Paket: <b>{package['label']}</b>\n"

        f"💰 Harga: <b>{price_text}</b>\n\n"

        "Silakan lakukan pembayaran "
        "melalui QRIS.\n\n"

        "Setelah membayar, kirim "
        "<b>foto bukti pembayaran</b> "
        "ke bot ini.\n\n"

        "Admin akan melakukan verifikasi.\n\n"

        "Setelah disetujui, kamu akan "
        "mendapatkan invite link "
        "private group."
    )


    if os.path.exists(
        QRIS_PATH
    ):

        await BOT.send_photo(

            chat_id=user_id,

            photo=FSInputFile(
                QRIS_PATH
            ),

            caption=text,

            parse_mode="HTML"

        )

    else:

        await BOT.send_message(

            chat_id=user_id,

            text=text,

            parse_mode="HTML"

        )


    await callback.answer(
        "Paket dipilih."
    )


# =========================================================
# RECEIVE PAYMENT PROOF
# =========================================================

@DP.message(
    F.photo
)
async def payment_proof_handler(
    message: Message
):

    user_id = message.from_user.id


    payment = pending_payments.get(
        str(user_id)
    )


    if not payment:

        await message.answer(
            "❌ Belum ada transaksi aktif.\n\n"
            "Silakan tekan /start "
            "untuk memilih paket."
        )

        return


    status = payment.get(
        "status",
        ""
    )


    if status != "WAITING_PROOF":

        await message.answer(
            "❌ Saat ini bot tidak sedang "
            "menunggu bukti pembayaran."
        )

        return


    # -----------------------------------------------------
    # SAVE FILE ID
    # -----------------------------------------------------

    photo = message.photo[-1]

    file_id = photo.file_id


    payment["proof_file_id"] = file_id

    payment["status"] = "WAITING_ADMIN"

    payment["proof_time"] = (
        datetime.now().isoformat()
    )


    save_payment_state()


    # -----------------------------------------------------
    # SEND TO ALL ADMIN
    # -----------------------------------------------------

    package_name = payment.get(
        "package",
        ""
    )

    harga = payment.get(
        "harga",
        ""
    )

    username = payment.get(
        "username",
        ""
    )

    nama = payment.get(
        "nama",
        ""
    )


    price_text = (
        f"Rp{int(harga):,}"
        .replace(",", ".")
        if str(harga).isdigit()
        else str(harga)
    )


    caption = (

        "💳 <b>BUKTI PEMBAYARAN BARU</b>\n\n"

        f"👤 Nama: <b>{nama}</b>\n"

        f"🆔 Telegram ID: <code>{user_id}</code>\n"

        f"👤 Username: @{username if username else '-'}\n"

        f"📦 Paket: <b>{package_name}</b>\n"

        f"💰 Harga: <b>{price_text}</b>\n\n"

        "Silakan verifikasi pembayaran."
    )


    keyboard = admin_payment_keyboard(
        user_id
    )


    for admin_id in ADMIN_IDS:

        try:

            await BOT.send_photo(

                chat_id=admin_id,

                photo=file_id,

                caption=caption,

                reply_markup=keyboard,

                parse_mode="HTML"

            )


        except Exception as e:

            print(
                f"[ADMIN PROOF ERROR] "
                f"{admin_id}: {e}"
            )


    await message.answer(

        "✅ <b>Bukti pembayaran diterima.</b>\n\n"

        "Bukti sudah dikirim ke admin "
        "untuk diverifikasi.\n\n"

        "Mohon tunggu konfirmasi.",

        parse_mode="HTML"

    )


# =========================================================
# ADMIN APPROVE
# =========================================================

@DP.callback_query(
    F.data.startswith("approve_")
)
async def approve_payment(
    callback: CallbackQuery
):

    admin_id = callback.from_user.id


    if admin_id not in ADMIN_IDS:

        await callback.answer(
            "❌ Tidak memiliki akses.",
            show_alert=True
        )

        return


    try:

        user_id = int(
            callback.data.replace(
                "approve_",
                "",
                1
            )
        )


    except Exception:

        await callback.answer(
            "User ID tidak valid.",
            show_alert=True
        )

        return


    payment = pending_payments.get(
        str(user_id)
    )


    if not payment:

        await callback.answer(
            "❌ Data pembayaran tidak ditemukan.",
            show_alert=True
        )

        return


    current_status = payment.get(
        "status",
        ""
    )


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


    # =====================================================
    # CALCULATE MEMBERSHIP
    # =====================================================

    package_name = payment.get(
        "package",
        ""
    )


    package = PACKAGE_MAP.get(
        package_name
    )


    if not package:

        await callback.answer(
            "❌ Paket tidak ditemukan.",
            show_alert=True
        )

        return


    now = datetime.now()


    register_date = now.strftime(
        "%d-%m-%Y"
    )


    expired_date = (
        now + timedelta(
            days=package["days"]
        )
    ).strftime(
        "%d-%m-%Y"
    )


    # =====================================================
    # GOOGLE SHEETS
    #
    # PENTING:
    # Reff = grup
    # =====================================================

    member_data = {

        "telegram_id":
            payment.get(
                "telegram_id",
                user_id
            ),

        "username":
            payment.get(
                "username",
                ""
            ),

        "nama":
            payment.get(
                "nama",
                ""
            ),

        "paket":
            payment.get(
                "package",
                ""
            ),

        "harga":
            payment.get(
                "harga",
                ""
            ),

        "register":
            register_date,

        "expired":
            expired_date,

        "status":
            "ACTIVE",

        # -----------------------------------------------
        # BOT INI KHUSUS GRUP
        # KOLOM I / REFF = GRUP
        # -----------------------------------------------

        "referral":
            "grup"

    }


    print("")
    print(
        "========================================"
    )

    print(
        "[APPROVE] SAVE MEMBER"
    )

    print(
        member_data
    )

    print(
        "========================================"
    )


    # =====================================================
    # SAVE SHEET
    # =====================================================

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


    # =====================================================
    # CREATE ONE TIME INVITE
    # =====================================================

    invite_link = await create_one_time_invite_link()


    if not invite_link:

        # -------------------------------------------------
        # Member sudah tersimpan ACTIVE.
        # Tetapi invite gagal dibuat.
        # Jangan hapus data.
        # -------------------------------------------------

        payment["status"] = "APPROVED"

        payment["register"] = register_date

        payment["expired"] = expired_date

        payment["invite_link"] = ""

        save_payment_state()


        try:

            await BOT.send_message(

                chat_id=user_id,

                text=(

                    "✅ <b>Pembayaran kamu sudah "
                    "DISETUJUI.</b>\n\n"

                    f"📦 Paket: <b>{package_name}</b>\n"

                    f"📅 Aktif: <b>{register_date}</b>\n"

                    f"📅 Expired: <b>{expired_date}</b>\n\n"

                    "⚠️ Invite link grup gagal dibuat "
                    "sementara.\n\n"

                    "Silakan hubungi admin."

                ),

                parse_mode="HTML"

            )

        except Exception as e:

            print(
                "[USER APPROVE MESSAGE ERROR]",
                e
            )


        await callback.answer(

            "Pembayaran diterima, "
            "tetapi invite gagal dibuat.",

            show_alert=True

        )

        return


    # =====================================================
    # SAVE PAYMENT STATE
    # =====================================================

    payment["status"] = "APPROVED"

    payment["register"] = register_date

    payment["expired"] = expired_date

    payment["invite_link"] = invite_link

    payment["approved_at"] = (
        datetime.now().isoformat()
    )

    payment["approved_by"] = admin_id


    save_payment_state()


    # =====================================================
    # SEND INVITE TO USER
    # =====================================================

    try:

        await BOT.send_message(

            chat_id=user_id,

            text=(

                "🎉 <b>PEMBAYARAN BERHASIL!</b>\n\n"

                f"📦 Paket: <b>{package_name}</b>\n"

                f"💰 Harga: <b>Rp"
                f"{int(payment.get('harga', 0)):,}"
                .replace(",", ".")
                f"</b>\n\n"

                f"📅 Mulai: <b>{register_date}</b>\n"

                f"📅 Expired: <b>{expired_date}</b>\n\n"

                "🔐 <b>JOIN PRIVATE GROUP</b>\n\n"

                f"{invite_link}\n\n"

                "⚠️ Link ini hanya dapat digunakan "
                "untuk <b>1 member</b>.\n\n"

                "Jangan bagikan link ini kepada orang lain."

            ),

            parse_mode="HTML"

        )


    except Exception as e:

        print(
            "[SEND INVITE ERROR]",
            e
        )


    # =====================================================
    # UPDATE ADMIN MESSAGE
    # =====================================================

    try:

        await callback.message.edit_caption(

            caption=(

                "✅ <b>PAYMENT APPROVED</b>\n\n"

                f"👤 User: <code>{user_id}</code>\n"

                f"📦 Paket: <b>{package_name}</b>\n"

                f"📅 Expired: <b>{expired_date}</b>\n"

                "📊 Sheet: <b>ACTIVE</b>\n"

                "🔐 Invite: <b>CREATED</b>\n"

                "🏷 Reff: <b>grup</b>"

            ),

            parse_mode="HTML"

        )


    except Exception as e:

        print(
            "[ADMIN MESSAGE UPDATE ERROR]",
            e
        )


    await callback.answer(
        "✅ Pembayaran diterima."
    )


# =========================================================
# ADMIN REJECT
# =========================================================

@DP.callback_query(
    F.data.startswith("reject_")
)
async def reject_payment(
    callback: CallbackQuery
):

    admin_id = callback.from_user.id


    if admin_id not in ADMIN_IDS:

        await callback.answer(
            "❌ Tidak memiliki akses.",
            show_alert=True
        )

        return


    try:

        user_id = int(
            callback.data.replace(
                "reject_",
                "",
                1
            )
        )


    except Exception:

        await callback.answer(
            "User ID tidak valid.",
            show_alert=True
        )

        return


    payment = pending_payments.get(
        str(user_id)
    )


    if not payment:

        await callback.answer(
            "Data pembayaran tidak ditemukan.",
            show_alert=True
        )

        return


    payment["status"] = "REJECTED"

    payment["rejected_at"] = (
        datetime.now().isoformat()
    )

    payment["rejected_by"] = admin_id


    save_payment_state()


    # =====================================================
    # INFORM USER
    # =====================================================

    try:

        await BOT.send_message(

            chat_id=user_id,

            text=(

                "❌ <b>PEMBAYARAN DITOLAK</b>\n\n"

                "Bukti pembayaran kamu belum dapat "
                "diverifikasi oleh admin.\n\n"

                "Silakan lakukan pembayaran kembali "
                "dan kirim bukti pembayaran yang jelas."

            ),

            parse_mode="HTML"

        )


    except Exception as e:

        print(
            "[REJECT USER MESSAGE ERROR]",
            e
        )


    # =====================================================
    # UPDATE ADMIN MESSAGE
    # =====================================================

    try:

        if callback.message.photo:

            await callback.message.edit_caption(

                caption=(

                    "❌ <b>PAYMENT REJECTED</b>\n\n"

                    f"👤 User: <code>{user_id}</code>\n\n"

                    "Status: <b>REJECTED</b>"

                ),

                parse_mode="HTML"

            )

        else:

            await callback.message.edit_text(

                (

                    "❌ <b>PAYMENT REJECTED</b>\n\n"

                    f"User: <code>{user_id}</code>"

                ),

                parse_mode="HTML"

            )


    except Exception as e:

        print(
            "[REJECT ADMIN MESSAGE ERROR]",
            e
        )


    await callback.answer(
        "Pembayaran ditolak."
    )


# =========================================================
# /CANCEL
# =========================================================

@DP.message(
    Command("cancel")
)
async def cancel_handler(
    message: Message
):

    user_id = message.from_user.id


    if str(user_id) in pending_payments:

        payment = pending_payments[
            str(user_id)
        ]

        status = payment.get(
            "status",
            ""
        )


        if status not in (
            "APPROVED",
        ):

            payment["status"] = "CANCELLED"

            save_payment_state()


    await message.answer(

        "❌ Transaksi dibatalkan.\n\n"
        "Gunakan /start untuk memulai kembali."

    )


# =========================================================
# ADMIN /CHECKEXPIRED
# =========================================================

@DP.message(
    Command("checkexpired")
)
async def manual_check_expired(
    message: Message
):

    if message.from_user.id not in ADMIN_IDS:

        await message.answer(
            "❌ Tidak memiliki akses."
        )

        return


    await message.answer(
        "🔎 Mengecek member expired..."
    )


    await check_expired_members()


    await message.answer(
        "✅ Pengecekan expired selesai."
    )


# =========================================================
# ERROR HANDLER
# =========================================================

@DP.errors()
async def global_error_handler(
    event
):

    print(
        "[BOT ERROR]",
        event.exception
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    print("")
    print(
        "=========================================="
    )

    print(
        "🤖 XAU AI ASSISTANT BOT STARTING..."
    )

    print(
        "=========================================="
    )

    print(
        f"PRIVATE GROUP: {PRIVATE_GROUP_ID}"
    )

    print(
        f"ADMIN IDS: {ADMIN_IDS}"
    )

    print(
        f"QRIS PATH: {QRIS_PATH}"
    )

    print(
        f"PAYMENT STATE: {PAYMENT_STATE_FILE}"
    )

    print("")
    print(
        "PACKAGES:"
    )

    print(
        " - TRIAL 4 HARI : Rp34.000"
    )

    print(
        " - 1 BULAN      : Rp149.000"
    )

    print("")
    print(
        "REFERRAL / REFF:"
    )

    print(
        " - Bot ini      : grup"
    )

    print("")
    print(
        "EXPIRED MONITOR:"
    )

    print(
        " - Interval     : 10 menit"
    )

    print(
        " - Action       : KICK"
    )

    print(
        " - Sheet status : EXPIRED"
    )

    print(
        "=========================================="
    )

    print("")


    # =====================================================
    # START EXPIRED MONITOR
    # =====================================================

    monitor_task = asyncio.create_task(
        expired_monitor()
    )


    try:

        await DP.start_polling(
            BOT
        )


    finally:

        monitor_task.cancel()

        try:

            await monitor_task

        except asyncio.CancelledError:

            pass


        await BOT.session.close()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
