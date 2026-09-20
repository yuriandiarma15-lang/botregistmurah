import os

# ==========================================
# TELEGRAM
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN tidak ditemukan di Railway Variables")


# ==========================================
# ADMIN
# ==========================================

ADMIN_ID = 1305881282
