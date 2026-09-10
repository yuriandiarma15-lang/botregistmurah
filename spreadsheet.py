import os
import json

import gspread

from google.oauth2.service_account import Credentials


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
# SAVE MEMBER
# ==========================================

def save_member(data):

    try:

        print(
            "=== DATA KE GOOGLE SHEET ==="
        )

        print(data)


        sheet.append_row([

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

            data.get(
                "referral",
                ""
            )

        ])


        print(
            "STATUS:"
        )

        print(
            "SUCCESS"
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
