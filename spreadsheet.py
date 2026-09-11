import os
import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials


# ==========================================
# GOOGLE SHEET CONFIG
# ==========================================

SPREADSHEET_ID = "1J3_Go0MdiNaDxVl6EuA00hJMsamB35Gjq0eHEg96ZMw"

SHEET_NAME = "Members"


SCOPES = [

    "https://www.googleapis.com/auth/spreadsheets",

    "https://www.googleapis.com/auth/drive"

]


# ==========================================
# GOOGLE SERVICE ACCOUNT
# ==========================================

service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT"]
)


creds = Credentials.from_service_account_info(

    service_account_info,

    scopes=SCOPES

)


client = gspread.authorize(
    creds
)


spreadsheet = client.open_by_key(
    SPREADSHEET_ID
)


sheet = spreadsheet.worksheet(
    SHEET_NAME
)


# ==========================================
# COLUMN
# ==========================================
#
# A = telegram_id
# B = username
# C = nama
# D = paket
# E = harga
# F = register
# G = expired
# H = status
# I = referral / reff
#
# ==========================================


# ==========================================
# SAVE MEMBER
# ==========================================

def save_member(data):

    try:

        print("")
        print("========================================")
        print("DATA KE GOOGLE SHEET")
        print("========================================")

        print(data)

        # ----------------------------------
        # UNTUK BOT GRUP
        # KOLOM I SELALU "grup"
        # ----------------------------------

        referral = data.get(
            "referral",
            "grup"
        )

        if not referral:

            referral = "grup"


        row = [

            data.get(
                "telegram_id",
                ""
            ),

            data.get(
                "username",
                ""
            ),

            data.get(
                "nama",
                ""
            ),

            data.get(
                "paket",
                ""
            ),

            data.get(
                "harga",
                ""
            ),

            data.get(
                "register",
                ""
            ),

            data.get(
                "expired",
                ""
            ),

            data.get(
                "status",
                ""
            ),

            referral

        ]


        sheet.append_row(
            row,
            value_input_option="USER_ENTERED"
        )


        print(
            "STATUS: SUCCESS"
        )

        print(
            "REFF:",
            referral
        )

        print(
            "RESPON GOOGLE SHEET:"
        )

        print(
            "Member berhasil disimpan"
        )

        return True


    except Exception as e:

        print(
            "Google Sheet Error:"
        )

        print(e)

        return False


# ==========================================
# GET GROUP MEMBERS
# ==========================================
#
# Mengambil member yang Reff = grup.
#
# Jika user mempunyai beberapa transaksi,
# yang digunakan adalah DATA TERBARU.
#
# ==========================================

def get_group_members():

    try:

        records = sheet.get_all_records()

        latest_members = {}

        for index, row in enumerate(
            records,
            start=2
        ):

            telegram_id = str(
                row.get(
                    "telegram_id",
                    ""
                )
            ).strip()

            referral = str(
                row.get(
                    "referral",
                    ""
                )
            ).strip().lower()

            # ----------------------------------
            # HANYA DATA BOT GRUP
            # ----------------------------------

            if referral != "grup":
                continue

            if not telegram_id:
                continue

            # ----------------------------------
            # Data terakhir user digunakan
            # ----------------------------------

            latest_members[telegram_id] = {

                "row_number": index,

                "telegram_id": telegram_id,

                "username": row.get(
                    "username",
                    ""
                ),

                "nama": row.get(
                    "nama",
                    ""
                ),

                "paket": row.get(
                    "paket",
                    ""
                ),

                "harga": row.get(
                    "harga",
                    ""
                ),

                "register": row.get(
                    "register",
                    ""
                ),

                "expired": row.get(
                    "expired",
                    ""
                ),

                "status": row.get(
                    "status",
                    ""
                ),

                "referral": referral

            }


        return list(
            latest_members.values()
        )


    except Exception as e:

        print(
            "[GET GROUP MEMBERS ERROR]",
            e
        )

        return []


# ==========================================
# UPDATE STATUS MEMBER
# ==========================================

def update_member_status(
    telegram_id,
    status
):

    try:

        telegram_id = str(
            telegram_id
        ).strip()


        records = sheet.get_all_records()


        # ----------------------------------
        # Cari dari bawah
        # karena transaksi terbaru
        # berada di baris paling bawah.
        # ----------------------------------

        for index in range(
            len(records) - 1,
            -1,
            -1
        ):

            row = records[index]

            row_telegram_id = str(
                row.get(
                    "telegram_id",
                    ""
                )
            ).strip()

            referral = str(
                row.get(
                    "referral",
                    ""
                )
            ).strip().lower()


            if (
                row_telegram_id == telegram_id
                and referral == "grup"
            ):

                # Google Sheet row:
                # records index 0 = row 2
                sheet_row = index + 2

                # H = status
                sheet.update_cell(
                    sheet_row,
                    8,
                    status
                )


                print(
                    f"[SHEET STATUS] "
                    f"{telegram_id} -> {status}"
                )

                return True


        print(
            f"[SHEET STATUS] "
            f"User {telegram_id} tidak ditemukan."
        )

        return False


    except Exception as e:

        print(
            "[UPDATE STATUS ERROR]",
            e
        )

        return False


# ==========================================
# GET EXPIRED GROUP MEMBERS
# ==========================================

def get_expired_group_members():

    members = get_group_members()

    expired_members = []

    today = datetime.now().date()


    for member in members:

        status = str(
            member.get(
                "status",
                ""
            )
        ).strip().upper()


        # ----------------------------------
        # HANYA ACTIVE
        # ----------------------------------

        if status != "ACTIVE":
            continue


        expired_text = str(
            member.get(
                "expired",
                ""
            )
        ).strip()


        if not expired_text:
            continue


        try:

            expired_date = datetime.strptime(
                expired_text,
                "%d-%m-%Y"
            ).date()


        except Exception as e:

            print(
                "[EXPIRED DATE ERROR]",
                member.get("telegram_id"),
                expired_text,
                e
            )

            continue


        # ----------------------------------
        # EXPIRED JIKA TANGGAL SUDAH LEWAT
        # ----------------------------------

        if expired_date < today:

            expired_members.append(
                member
            )


    return expired_members
