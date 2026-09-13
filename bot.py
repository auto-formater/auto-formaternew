
import sqlite3
import os
import re
from datetime import datetime
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ====== RAILWAY VARIABLES - JANGAN TARUH DI FILE ======
# Set di Railway -> Variables:
# BOT_TOKEN = token dari @BotFather
# ADMIN_IDS = 123456789,987654321 (pisah koma)

TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or os.getenv("TELEGRAM_TOKEN") or "GANTI_DENGAN_TOKEN_BOTFATHER"
if not os.getenv("BOT_TOKEN"):
    print("⚠️ BOT_TOKEN tidak di ENV - pakai fallback, set di Railway!")

admin_env = os.getenv("ADMIN_IDS", "")
if admin_env:
    try:
        ADMIN_IDS = [int(x.strip()) for x in admin_env.split(",") if x.strip().lstrip("-").isdigit() or x.strip().isdigit()]
    except:
        ADMIN_IDS = [123456789]
else:
    ADMIN_IDS = [123456789]

DB_PATH = os.getenv("DB_PATH", "bot_baru.db")

print(f"🔑 TOKEN: {'✅ ENV' if os.getenv('BOT_TOKEN') else '❌ FALLBACK'} | ADMIN: {ADMIN_IDS}")

DEFAULT_TEMPLATE = """{KODE}
━━━━━━━━━━━━━━━━━━━
📍 KAB  : {KAB}
📍 KEC  : {KEC}
📍 KEL  : {KEL}

💰 SALDO  : {SALDO}

🆔 KELAMIN : {KELAMIN}
💳 KPJ  : {KPJ}
🔰 SENSOR: {SENSOR}
📅 IT   : {IT}
🏛️ PT   : {PT}

🏆 DPT JMO LASIK ✅"""

def init_db():
    # FIX permanen: buat folder /data kalau belum ada (untuk Volume Railway)
    try:
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    except:
        pass
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, total_format INTEGER DEFAULT 0, saldo TEXT DEFAULT "0", expired TEXT DEFAULT "UNLIMITED", nama TEXT DEFAULT "")""")
    try:
        c.execute("ALTER TABLE users ADD COLUMN saldo TEXT DEFAULT '0'")
    except:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN expired TEXT DEFAULT 'UNLIMITED'")
    except:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN nama TEXT DEFAULT ''")
    except:
        pass
    c.execute("""CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, template TEXT, kode_atas TEXT DEFAULT '0000001', kode_prefix TEXT DEFAULT 'MGB', kode_pos TEXT DEFAULT 'atas', kode_base_count INTEGER DEFAULT 0)""")
    try:
        c.execute("ALTER TABLE settings ADD COLUMN kode_base_count INTEGER DEFAULT 0")
    except:
        pass
    try:
        c.execute("ALTER TABLE settings ADD COLUMN kode_pos TEXT DEFAULT 'atas'")
    except:
        pass
    c.execute("""CREATE TABLE IF NOT EXISTS hasil_format (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kode TEXT, kab TEXT, kec TEXT, kel TEXT, saldo TEXT, kelamin TEXT, kpj TEXT, sensor TEXT, it TEXT, pt TEXT, nik_lengkap TEXT, kpj_lengkap TEXT, nama_lengkap TEXT, tgl_lahir TEXT, akun TEXT, display_format TEXT, display_full TEXT, status TEXT DEFAULT 'ready', created_at TEXT)""")
    for col in ["nik_lengkap", "kpj_lengkap", "nama_lengkap", "tgl_lahir"]:
        try:
            c.execute(f"ALTER TABLE hasil_format ADD COLUMN {col} TEXT")
        except:
            pass
    c.execute("""CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, aksi TEXT, detail TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)""")
    c.execute("""CREATE TABLE IF NOT EXISTS data_saya (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kode TEXT,
            kab TEXT,
            kec TEXT,
            kel TEXT,
            saldo TEXT,
            kelamin TEXT,
            kpj TEXT,
            sensor TEXT,
            it TEXT,
            pt TEXT,
            nik_lengkap TEXT,
            kpj_lengkap TEXT,
            nama_lengkap TEXT,
            tgl_lahir TEXT,
            raw_text TEXT,
            display_text TEXT,
            display_full TEXT,
            tipe TEXT,
            created_at TEXT
        )""")
    for col in ["kode","raw_text","display_text","nik_lengkap","kpj_lengkap","nama_lengkap","tgl_lahir"]:
        try:
            c.execute(f"ALTER TABLE data_saya ADD COLUMN {col} TEXT")
        except:
            pass
    # === FITUR LANGGANAN BARU ===
    c.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        paket TEXT,
        harga INTEGER,
        durasi_hari INTEGER,
        tgl_mulai TEXT,
        tgl_expired TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS topup_pending (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        paket TEXT,
        harga INTEGER,
        durasi_hari INTEGER,
        bukti_file_id TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    conn.commit()
    conn.close()

def get_setting(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT template, kode_atas, kode_prefix, kode_pos, kode_base_count FROM settings WHERE user_id=?", (user_id,))
    except:
        c.execute("SELECT template, kode_atas, kode_prefix, kode_pos FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO settings (user_id, template, kode_atas, kode_prefix, kode_pos, kode_base_count) VALUES (?, ?, ?, ?, ?, ?)", (user_id, DEFAULT_TEMPLATE, "0000001", "MGB", "atas", 0))
        conn.commit()
        template, kode_atas, kode_prefix, kode_pos, base_count = DEFAULT_TEMPLATE, "0000001", "MGB", "atas", 0
    else:
        if len(row) == 3:
            template, kode_atas, kode_prefix = row
            kode_pos = "atas"
            base_count = 0
        elif len(row) == 4:
            template, kode_atas, kode_prefix, kode_pos = row
            base_count = 0
            if not kode_pos:
                kode_pos = "atas"
        else:
            template, kode_atas, kode_prefix, kode_pos, base_count = row
            if not kode_pos:
                kode_pos = "atas"
            if base_count is None:
                base_count = 0
    conn.close()
    return template, kode_atas, kode_prefix, kode_pos, base_count

def get_setting_simple(user_id):
    # wrapper for backward compatibility - returns 4 values
    t, ka, kp, kpos, _ = get_setting(user_id)
    return t, ka, kp, kpos

def is_admin_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT user_id FROM admins")
        admin_rows = c.fetchall()
        admin_ids_db = [r[0] for r in admin_rows]
    except:
        admin_ids_db = []
    conn.close()
    all_admins = list(set(ADMIN_IDS + admin_ids_db))
    return user_id in all_admins

def get_user_subscription(user_id):
    if is_admin_user(user_id):
        return True, "UNLIMITED", "ADMIN"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT paket, tgl_expired, status FROM subscriptions WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False, None, None
    paket, tgl_expired, status = row
    if paket and "UNLIMITED" in paket.upper():
        return True, "UNLIMITED", paket
    if not tgl_expired:
        return True, "UNLIMITED", paket
    try:
        from datetime import datetime
        exp = datetime.fromisoformat(tgl_expired)
        if datetime.now() <= exp:
            return True, tgl_expired, paket
        else:
            return False, tgl_expired, paket
    except:
        return True, tgl_expired, paket

def has_access(user_id):
    ok, _, _ = get_user_subscription(user_id)
    return ok

PACKAGES = {
    "3bulan": {"label": "3 bulan", "harga": 25000, "durasi": 90, "label_full": "3 bulan", "emoji": "📦"},
    "6bulan": {"label": "6 bulan", "harga": 50000, "durasi": 180, "label_full": "6 bulan", "emoji": "📦"},
    "1tahun": {"label": "1 tahun", "harga": 100000, "durasi": 365, "label_full": "1 tahun", "emoji": "📦"},
    "unlimited": {"label": "Unlimited", "harga": 250000, "durasi": 36500, "label_full": "Unlimited", "emoji": "♾️"},
}

def get_topup_text(paket_key):
    pkg = PACKAGES.get(paket_key)
    if not pkg:
        return "Paket tidak ditemukan"
    # Format sesuai permintaan user
    if paket_key == "3bulan":
        paket_display = "3 bulan"
        minggu = "📦Paket 3 bulan"
    elif paket_key == "6bulan":
        paket_display = "6 bulan"
        minggu = "📦Paket 6 bulan"
    elif paket_key == "1tahun":
        paket_display = "1 tahun"
        minggu = "📦Paket 1 tahun"
    else:
        paket_display = "Unlimited"
        minggu = "📦Paket Unlimited"
    
    text = f"""💳 TOP UP TAMBAH KOTA

🎁 Paket: {pkg['label'].upper()}
{minggu} 
💰 Harga {pkg['harga']:,}
📆 Durasi {paket_display}

💳 TOP UP SALDO 

🏦 SEABANK
   901040978290 - HAMBALI

💰 DANA
   083824101264 - HAMBALI

💳 GOPAY
   083824101264 - HAMBALI

📸 Kirim foto bukti transfer di sini ya bos!
"""
    return text

def paket_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 3 BULAN - Rp 25.000", callback_data="paket_3bulan")],
        [InlineKeyboardButton("📦 6 BULAN - Rp 50.000", callback_data="paket_6bulan")],
        [InlineKeyboardButton("📦 1 TAHUN - Rp 100.000", callback_data="paket_1tahun")],
        [InlineKeyboardButton("♾️ UNLIMITED - Rp 250.000", callback_data="paket_unlimited")],
        [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")],
    ])




def get_next_code(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    try:
        template, kode_atas, kode_prefix, kode_pos, base_count = get_setting(user_id)
    except:
        template, kode_atas, kode_prefix, kode_pos = get_setting_simple(user_id)
        base_count = 0
    try:
        base = int(re.search(r"\d+", kode_atas).group()) if re.search(r"\d+", kode_atas) else 1
    except:
        base = 1
    # FIX: lebar digit ngikutin yang di-SET (AS 001 -> 3 digit, AS 0000001 -> 7 digit)
    kode_atas_str = str(kode_atas).strip()
    if kode_atas_str.isdigit():
        width = len(kode_atas_str)
    else:
        # cari angka di dalamnya
        m = re.search(r"\d+", kode_atas_str)
        width = len(m.group()) if m else 3
    if width < 3:
        width = 3  # minimal 3 digit biar AS 001
    num = base + (count - base_count)
    if num < base:
        num = base
    # Format: AS 001 (spasi satu, digit sesuai SET)
    return f"{kode_prefix} {num:0{width}d}"

def get_next_code_preview(user_id):
    return get_next_code(user_id)

def parse_jmo_block(block_text, kode):
    lines = [l.strip() for l in block_text.strip().splitlines() if l.strip()!=""]
    # Support new 13-field format, fallback to 9 for old data
    if len(lines) < 9:
        return None
    if len(lines) >= 13:
        kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir = lines[:13]
        akun_lines = lines[13:] if len(lines) > 13 else []
    else:
        # legacy 9 fields - fill empty for new fields
        kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt = lines[:9]
        nik_lengkap = kpj_lengkap = nama_lengkap = tgl_lahir = ""
        akun_lines = lines[9:] if len(lines) > 9 else []
    akun = "\n".join(akun_lines) if akun_lines else "-"
    return {
        "KAB": kab, "KEC": kec, "KEL": kel, "SALDO": saldo,
        "KELAMIN": kelamin, "KPJ": kpj, "SENSOR": sensor, "IT": it, "PT": pt,
        "NIK_LENGKAP": nik_lengkap, "KPJ_LENGKAP": kpj_lengkap,
        "NAMA_LENGKAP": nama_lengkap, "TGL_LAHIR": tgl_lahir,
        # also support short keys for template compatibility
        "NIK": nik_lengkap, "NAMA": nama_lengkap,
        "KODE": kode, "AKUN": akun
    }

def build_display(data_dict, template, kode_pos="atas"):
    kode = data_dict.get("KODE", "")
    # Build base JMO format - tapi kita bikin body tanpa kode dulu
    # Buat template bersih tanpa {KODE} dan tanpa garis atas yang duplikat
    try:
        # Buat dict tanpa kode untuk body
        dict_no_kode = {k: v for k, v in data_dict.items() if k != "KODE"}
        dict_no_kode["KODE"] = ""  # kosongkan kode di template
        base_no_kode = template.format(**dict_no_kode)
    except Exception:
        safe_dict = {k: data_dict.get(k, "") for k in ["KAB","KEC","KEL","SALDO","KELAMIN","KPJ","SENSOR","IT","PT","KODE","NIK_LENGKAP","KPJ_LENGKAP","NAMA_LENGKAP","TGL_LAHIR","NIK","NAMA","AKUN"]}
        safe_dict["KODE"] = ""
        try:
            base_no_kode = DEFAULT_TEMPLATE.format(**safe_dict)
        except:
            base_no_kode = DEFAULT_TEMPLATE.format(**{k: data_dict.get(k,"") for k in ["KAB","KEC","KEL","SALDO","KELAMIN","KPJ","SENSOR","IT","PT","KODE"]}).replace(kode, "")

    # Bersihkan body: hapus baris kosong di awal dan hapus garis separator di paling atas jika ada
    lines = [l for l in base_no_kode.split("\n")]
    # Hapus baris kosong di awal
    while lines and not lines[0].strip():
        lines.pop(0)
    # Jika baris pertama adalah garis separator (━━━━━━━━), hapus untuk kasus bawah, karena garis hanya boleh di bawah kode bawah
    # Untuk atas, garis tetap ada setelah kode
    # Jadi untuk body bersih, kita hapus semua garis separator di awal
    while lines and "━━━━━━━━" in lines[0] and len(lines[0].strip()) >= 10:
        lines.pop(0)
        # hapus juga baris kosong setelahnya
        while lines and not lines[0].strip():
            lines.pop(0)
    
    # Juga hapus baris yang hanya berisi kode lama jika masih tersisa
    cleaned_lines = []
    for l in lines:
        if kode and l.strip() == kode.strip():
            continue
        if kode and kode in l and len(l.strip()) < 40 and re.search(r"\d{3,}", l):
            # ini kemungkinan baris kode lama
            if l.strip().startswith(kode[:3]) or kode in l:
                continue
        cleaned_lines.append(l)
    
    body = "\n".join(cleaned_lines).strip()
    # Hapus separator ganda di dalam body yang mungkin ada di awal
    body = re.sub(r"^(━━━━━━━━+\s*\n)+", "", body).strip()

    # Atur posisi KODE sesuai setting
    if kode_pos == "bawah":
        # KODE DI BAWAH SAJA - tanpa garis di atas, hanya garis di bawah sebelum kode
        # Format: [body]\n━━━━━━━━\n     KODE
        if not body:
            body = f"📍 KAB  : {data_dict.get('KAB','')}\n📍 KEC  : {data_dict.get('KEC','')}\n📍 KEL  : {data_dict.get('KEL','')}"
        display_format = f"{body}\n━━━━━━━━━━━━━━━━━━━\n     {kode}"
    else:
        # KODE DI ATAS - dengan garis di atas (sesuai request: garis di atas itu buat SET KODE ATAS saja)
        # Format: KODE\n━━━━━━━━\n[body]
        display_format = f"{kode}\n━━━━━━━━━━━━━━━━━━━\n{body}"
        # Rapikan double separator
        display_format = display_format.replace("━━━━━━━━━━━━━━━━━━━\n━━━━━━━━━━━━━━━━━━━", "━━━━━━━━━━━━━━━━━━━")

    # FORMAT BIASA = display_format saja
    # FORMAT+AKUN = display_format + DATA LENGKAP section sesuai request
    nik = data_dict.get("NIK_LENGKAP") or data_dict.get("NIK") or ""
    kpj_lengkap = data_dict.get("KPJ_LENGKAP") or ""
    nama = data_dict.get("NAMA_LENGKAP") or data_dict.get("NAMA") or ""
    tgl = data_dict.get("TGL_LAHIR") or ""

    data_lengkap_section = f"""\n\n━━━━━━━━━━━━━━━━━━━\n📋 DATA LENGKAP\n\n🆔 NIK : {nik}\n💳 KPJ : {kpj_lengkap}\n👤 NAMA : {nama}\n🎂LAHIR : {tgl}"""

    display_full = display_format + data_lengkap_section

    # jika ada AKUN tambahan, append setelah data lengkap
    if data_dict.get("AKUN") and data_dict["AKUN"] != "-":
        display_full += f"\n\nAKUN:\n{data_dict['AKUN']}"

    return display_format, display_full

def main_menu_keyboard(user_id=None):
    show_admin = True
    if user_id is not None:
        show_admin = is_admin_user(user_id)
    buttons = [
        [InlineKeyboardButton("👤 PROFIL", callback_data="menu_profil"),
         InlineKeyboardButton("⌨️ BUAT FORMAT", callback_data="menu_buat")],
        [InlineKeyboardButton("⚙️ SETTING", callback_data="menu_setting"),
         InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format")],
        [InlineKeyboardButton("📑 FORMAT+AKUN", callback_data="menu_hasil_full")],
        [InlineKeyboardButton("🕘 HISTORY FORMAT", callback_data="menu_history")],
        [InlineKeyboardButton("📂 DATA SAYA", callback_data="menu_data_saya"),
         InlineKeyboardButton("📊 HASIL DATA SAYA", callback_data="menu_hasil_data_saya")],
        [InlineKeyboardButton("🕘 HISTORY DATA SAYA", callback_data="menu_history_data_saya")],
        [InlineKeyboardButton("📞 HUBUNGI ADMIN", callback_data="menu_hubungi_admin")],
    ]
    if show_admin:
        buttons.append([InlineKeyboardButton("👑 PANEL ADMIN", callback_data="menu_admin")])
    return InlineKeyboardMarkup(buttons)

def buat_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ MANUAL", callback_data="buat_manual")],
        [InlineKeyboardButton("📊 UPLOAD EXCEL .xlsx", callback_data="buat_excel")],
        [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()

    user = update.effective_user
    if user is None:
        await update.message.reply_text("❌ User tidak dapat dibaca. Silakan coba /start lagi.")
        return

    # Pakai getattr agar tidak crash jika objek User dari versi library
    # tidak memiliki atribut username atau first_name.
    user_id = getattr(user, "id", None)
    username = getattr(user, "username", "") or ""
    first_name = getattr(user, "first_name", "") or username or "SAHABAT"

    if user_id is None:
        await update.message.reply_text("❌ ID user tidak dapat dibaca. Silakan coba /start lagi.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, username, nama, saldo, expired) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, first_name, "0", "UNLIMITED")
    )
    c.execute("UPDATE users SET username=?, nama=? WHERE user_id=?", (username, first_name, user_id))
    conn.commit()
    conn.close()

    welcome_text = (
        "🟢 MODE ON DI AKTIFKAN\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Selamat datang, {first_name}! Gimana kabarnya nih, saya berharap kabar baik-baik saja yah, tetap semangat dan jangan lupa bersyukur. Silahkan pilih menu di bawah ini : 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(user_id))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "back_main":
        welcome_text = (
            "🟢 MODE ON DI AKTIFKAN\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👋 Selamat datang, SAHABAT JHT! Gimana kabarnya nih, saya berharap kabar baik-baik saja yah, tetap semangat dan jangan lupa bersyukur. Silahkan pilih menu di bawah ini : 👇"
        )
        await query.edit_message_text(welcome_text, reply_markup=main_menu_keyboard(user_id))
        return

    if data == "menu_profil":
        init_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT username, saldo, expired, nama, total_format FROM users WHERE user_id=?", (user_id,))
        urow = c.fetchone()
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        try:
            c.execute("SELECT user_id FROM admins")
            admin_rows = c.fetchall()
            admin_ids_db = [r[0] for r in admin_rows]
        except:
            admin_ids_db = []
        conn.close()
        all_admins = list(set(ADMIN_IDS + admin_ids_db))
        is_admin = user_id in all_admins
        username_db = urow[0] if urow and urow[0] else query.from_user.username or ""
        saldo_db = urow[1] if urow and urow[1] else "0"
        expired_db = urow[2] if urow and urow[2] else "UNLIMITED"
        nama_db = urow[3] if urow and len(urow) > 3 and urow[3] else query.from_user.first_name or "SAHABAT"
        
        has_sub, exp_date, paket_name = get_user_subscription(user_id)
        if is_admin:
            paket_display = "ADMIN (UNLIMITED)"
            expired_display = "UNLIMITED"
            status_display = "🟢 AKTIF - ADMIN"
        elif has_sub:
            paket_display = paket_name or "Aktif"
            if exp_date == "UNLIMITED" or (paket_name and "UNLIMITED" in str(paket_name).upper()):
                expired_display = "UNLIMITED ♾️"
            else:
                try:
                    from datetime import datetime
                    if "T" in str(exp_date):
                        exp_dt = datetime.fromisoformat(exp_date)
                        expired_display = exp_dt.strftime("%d-%m-%Y %H:%M")
                    else:
                        expired_display = str(exp_date)[:16]
                except:
                    expired_display = str(exp_date)
            status_display = "🟢 AKTIF"
        else:
            paket_display = "❌ BELUM LANGGANAN"
            expired_display = "-"
            status_display = "🔴 TIDAK AKTIF - Beli paket dulu"
        
        username_display = f"@{username_db}" if username_db else f"@{(query.from_user.username or 'user')}"
        profil_text = (
            f"👤 PROFIL USER\n\n"
            f"🆔 Telegram ID : {user_id}\n"
            f"👤 Nama : {nama_db}\n"
            f"📱 Username : {username_display}\n"
            f"💰 Saldo : Rp {saldo_db}\n\n"
            f"📦 Paket : {paket_display}\n"
            f"📅 Expired : {expired_display}\n"
            f"📊 Status : {status_display}\n"
            f"📄 Total Format : {total}"
        )
        if not has_sub and not is_admin:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 BELI PAKET", callback_data="menu_buat")],
                [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
            ])
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]])
        await query.edit_message_text(profil_text, reply_markup=kb)

    elif data == "menu_buat":
        if not has_access(user_id):
            await query.edit_message_text(
                "🔒 **MENU TERKUNCI**\n\n"
                "Untuk menggunakan **BUAT FORMAT**, kamu harus berlangganan dulu.\n\n"
                "Pilih paket di bawah:",
                reply_markup=paket_menu_keyboard(),
                parse_mode="Markdown"
            )
            return
        await query.edit_message_text("⌨️ BUAT FORMAT\nPilih metode:", reply_markup=buat_menu())

    elif data == "buat_manual":
        if not has_access(user_id):
            await query.edit_message_text(
                "🔒 **AKSES DITOLAK**\n\nKamu belum berlangganan. Silahkan pilih paket dulu:",
                reply_markup=paket_menu_keyboard(),
                parse_mode="Markdown"
            )
            return
        context.user_data["mode"] = "manual"
        await query.edit_message_text(
            "⌨️ BUAT FORMAT\n\nKetik data tanpa perlu menulis KAB/KEC/KEL. Bot otomatis membaca urutannya:\n\n1️⃣ KAB\n2️⃣ KEC\n3️⃣ KEL\n4️⃣ SALDO\n5️⃣ KELAMIN\n6️⃣ KPJ\n7️⃣ SENSOR\n8️⃣ IT\n9️⃣ PT\n🔟 NIK LENGKAP\n1️⃣1️⃣ KPJ\n1️⃣2️⃣ NAMA LENGKAP\n1️⃣3️⃣ TANGGAL LAHIR\n\nContoh:\nDEPOK\nCILODONG\nKALIBARU\n10.000.000\nPEREMPUAN 1992\n2019\n23****\n01-07-2022\nINDONESIA MERDEKA\n3201234589920002\n19000378990\nLIA\n12-12-1990\n\nHasilnya otomatis menjadi format JMO.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_buat")]]),
        )

    elif data == "buat_excel":
        if not has_access(user_id):
            await query.edit_message_text(
                "🔒 **AKSES DITOLAK**\n\nKamu belum berlangganan. Silahkan pilih paket dulu:",
                reply_markup=paket_menu_keyboard(),
                parse_mode="Markdown"
            )
            return
        context.user_data["mode"] = "excel"
        await query.edit_message_text(
            "📊 UPLOAD FILE EXCEL\n\nUpload .xlsx (A=KAB B=KEC C=KEL D=SALDO E=KELAMIN F=KPJ G=SENSOR H=IT I=PT J=NIK K=NO_KPJ L=NAMA M=TGL)\nKirim file sekarang 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_buat")]]),
        )


    elif data.startswith("paket_"):
        paket_key = data.replace("paket_", "")
        if paket_key not in PACKAGES:
            await query.edit_message_text("❌ Paket tidak valid.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        pkg = PACKAGES[paket_key]
        # Simpan pending topup
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO topup_pending (user_id, paket, harga, durasi_hari, status, created_at) VALUES (?,?,?,?,?,?)",
                  (user_id, pkg['label'], pkg['harga'], pkg['durasi'], 'menunggu_bukti', datetime.now().isoformat()))
        conn.commit()
        conn.close()
        context.user_data['topup_paket'] = paket_key
        text_topup = get_topup_text(paket_key)
        await query.edit_message_text(
            text_topup,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ SUDAH TRANSFER", callback_data=f"topup_sudah_{paket_key}")],
                [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
            ])
        )
        return

    elif data.startswith("topup_sudah_"):
        paket_key = data.replace("topup_sudah_", "")
        context.user_data['mode'] = 'topup_bukti'
        context.user_data['topup_paket'] = paket_key
        await query.edit_message_text(
            f"📸 Silahkan kirim foto bukti transfer untuk paket {PACKAGES.get(paket_key, {}).get('label','')} di chat ini.\n\nAdmin akan cek dan aktifkan dalam 1x24 jam.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]])
        )
        return

    elif data.startswith("approve_topup_"):
        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        tid = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, paket, harga, durasi_hari FROM topup_pending WHERE id=?", (tid,))
        row = c.fetchone()
        if not row:
            conn.close()
            await query.edit_message_text("❌ Topup tidak ditemukan")
            return
        target_user, paket_label, harga, durasi = row
        from datetime import datetime, timedelta
        tgl_mulai = datetime.now()
        tgl_expired = tgl_mulai + timedelta(days=durasi) if durasi < 10000 else datetime(2099,12,31)
        c.execute("INSERT INTO subscriptions (user_id, paket, harga, durasi_hari, tgl_mulai, tgl_expired, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                  (target_user, paket_label, harga, durasi, tgl_mulai.isoformat(), tgl_expired.isoformat(), 'active', datetime.now().isoformat()))
        c.execute("UPDATE topup_pending SET status='approved' WHERE id=?", (tid,))
        c.execute("UPDATE users SET expired=? WHERE user_id=?", (tgl_expired.strftime("%d-%m-%Y") if durasi < 10000 else "UNLIMITED", target_user))
        conn.commit()
        conn.close()
        try:
            await context.bot.send_message(chat_id=target_user, text=f"✅ **TOP UP DISETUJUI!**\n\nPaket: {paket_label}\nBerakhir: {tgl_expired.strftime('%d-%m-%Y') if durasi < 10000 else 'UNLIMITED'}\n\nSekarang kamu bisa pakai BUAT FORMAT & DATA SAYA ✅", parse_mode="Markdown")
        except:
            pass
        await query.edit_message_text(f"✅ Topup ID {tid} untuk user {target_user} ({paket_label}) di-approve.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="admin_topup")]]))
        return

    elif data.startswith("reject_topup_"):
        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        tid = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE topup_pending SET status='rejected' WHERE id=?", (tid,))
        conn.commit()
        c.execute("SELECT user_id FROM topup_pending WHERE id=?", (tid,))
        row = c.fetchone()
        conn.close()
        if row:
            try:
                await context.bot.send_message(chat_id=row[0], text="❌ Top up ditolak. Silahkan hubungi admin atau kirim bukti yang valid.")
            except:
                pass
        await query.edit_message_text(f"❌ Topup ID {tid} ditolak.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="admin_topup")]]))
        return

    elif data == "admin_topup":
        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, user_id, paket, harga, status, created_at FROM topup_pending WHERE status IN ('menunggu_bukti','pending','bukti_terkirim') ORDER BY id DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("📭 Tidak ada topup pending.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
            return
        await query.edit_message_text(f"💳 {len(rows)} TOPUP PENDING:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        for tid, uid, paket, harga, status, created in rows:
            txt_msg = f"ID:{tid} | User:{uid} | {paket} Rp{harga:,} | {status} | {created[:16]}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_topup_{tid}"), InlineKeyboardButton("❌ REJECT", callback_data=f"reject_topup_{tid}")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=txt_msg, reply_markup=kb)
            except:
                pass
        return

    elif data == "menu_hasil_format" or data.startswith("hasil_format_page_") or data == "tampilkan_format" or data.startswith("tampilkan_format_page_"):
        # PAGINATION 50 DATA PER HALAMAN dengan tombol BERIKUTNYA, SEBELUMNYA, KEMBALI
        # Parse halaman
        page = 1
        if "_" in data:
            try:
                # format: hasil_format_page_2 atau tampilkan_format_page_2 atau menu_hasil_format_page_2
                parts = data.split("_")
                # ambil angka terakhir
                for p in reversed(parts):
                    if p.isdigit():
                        page = int(p)
                        break
            except:
                page = 1
        # Kalau data == menu_hasil_format tanpa page, page =1
        if data == "menu_hasil_format" or data == "tampilkan_format":
            page = 1
        # Simpan page ke user_data untuk navigasi
        context.user_data["hasil_format_page"] = page
        per_page = 50
        offset = (page - 1) * per_page

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Total count
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=? AND status='ready'", (user_id,))
        total = c.fetchone()[0]
        # Ambil 50 data sesuai halaman, urut kecil ke besar
        c.execute("SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC LIMIT ? OFFSET ?", (user_id, per_page, offset))
        rows = c.fetchall()
        if not rows:
            # Fallback tanpa CAST
            c.execute("SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY id ASC LIMIT ? OFFSET ?", (user_id, per_page, offset))
            rows = c.fetchall()
        conn.close()
        if total==0:
            await query.edit_message_text("Belum ada HASIL FORMAT.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        if not rows and page>1:
            # Jika halaman melebihi, kembali ke halaman 1
            page = 1
            offset = 0
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC LIMIT ? OFFSET ?", (user_id, per_page, offset))
            rows = c.fetchall()
            conn.close()

        total_pages = (total + per_page - 1) // per_page
        start_num = offset + 1
        end_num = min(offset + len(rows), total)
        first_kode = rows[0][1] if rows else "-"
        last_kode = rows[-1][1] if rows else "-"

        # Tombol navigasi BERIKUTNYA, SEBELUMNYA, KEMBALI
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ SEBELUMNYA", callback_data=f"hasil_format_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("➡️ BERIKUTNYA", callback_data=f"hasil_format_page_{page+1}"))
        nav_row = nav_buttons if nav_buttons else []
        kb_top = [
            [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_format")],
        ]
        if nav_row:
            kb_top.append(nav_row)
        kb_top.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")])

        await query.edit_message_text(
            f"📄 **HASIL FORMAT** - Halaman {page}/{total_pages}\n"
            f"Total: {total} data | Tampil: {start_num}-{end_num} (50 per halaman)\n"
            f"Urutan: {first_kode} → {last_kode}",
            reply_markup=InlineKeyboardMarkup(kb_top),
            parse_mode="Markdown"
        )
        # Kirim 50 data per halaman
        for idx, (rid, kode, disp, kab, kec, kel, saldo, kelamin, kpj, pt) in enumerate(rows, start=start_num):
            try:
                kode_num = int(re.search(r"(\d+)", kode).group())
            except:
                kode_num = rid
            header = f"{kode} (ID {kode_num})"
            text = f"{header}\n```\n{disp}\n```"
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
            kb = InlineKeyboardMarkup([
                [jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")],
                [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_format"), InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp}", reply_markup=kb)
        # Menu bawah setelah 50 data
        bottom_nav = []
        if page > 1:
            bottom_nav.append(InlineKeyboardButton("⬅️ SEBELUMNYA", callback_data=f"hasil_format_page_{page-1}"))
        if page < total_pages:
            bottom_nav.append(InlineKeyboardButton("➡️ BERIKUTNYA", callback_data=f"hasil_format_page_{page+1}"))
        kb_bottom = []
        if bottom_nav:
            kb_bottom.append(bottom_nav)
        kb_bottom.append([InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_format")])
        kb_bottom.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")])
        await context.bot.send_message(chat_id=user_id, text=f"📄 Halaman {page}/{total_pages} | {start_num}-{end_num} dari {total}", reply_markup=InlineKeyboardMarkup(kb_bottom))

    elif data == "menu_hasil_full" or data.startswith("hasil_full_page_") or data == "tampilkan_full" or data.startswith("tampilkan_full_page_"):
        # PAGINATION 50 DATA PER HALAMAN untuk FORMAT+AKUN
        page = 1
        if "_" in data:
            try:
                parts = data.split("_")
                for p in reversed(parts):
                    if p.isdigit():
                        page = int(p)
                        break
            except:
                page = 1
        if data in ("menu_hasil_full", "tampilkan_full"):
            page = 1
        per_page = 50
        offset = (page - 1) * per_page

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=? AND status='ready'", (user_id,))
        total = c.fetchone()[0]
        c.execute("SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC LIMIT ? OFFSET ?", (user_id, per_page, offset))
        rows = c.fetchall()
        if not rows:
            c.execute("SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY id ASC LIMIT ? OFFSET ?", (user_id, per_page, offset))
            rows = c.fetchall()
        conn.close()
        if total==0:
            await query.edit_message_text("Belum ada HASIL FORMAT+AKUN.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        if not rows and page>1:
            page = 1
            offset = 0
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC LIMIT ? OFFSET ?", (user_id, per_page, offset))
            rows = c.fetchall()
            conn.close()

        total_pages = (total + per_page - 1) // per_page
        start_num = offset + 1
        end_num = min(offset + len(rows), total)
        first_kode = rows[0][1] if rows else "-"
        last_kode = rows[-1][1] if rows else "-"

        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ SEBELUMNYA", callback_data=f"hasil_full_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("➡️ BERIKUTNYA", callback_data=f"hasil_full_page_{page+1}"))
        kb_top = [[InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_akun")]]
        if nav_buttons:
            kb_top.append(nav_buttons)
        kb_top.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")])

        await query.edit_message_text(
            f"📑 **HASIL FORMAT+AKUN** - Halaman {page}/{total_pages}\n"
            f"Total: {total} data | Tampil: {start_num}-{end_num} (50 per halaman)\n"
            f"Urutan: {first_kode} → {last_kode}",
            reply_markup=InlineKeyboardMarkup(kb_top),
            parse_mode="Markdown"
        )
        for idx, (rid, kode, disp_full, kab, kec, kel, pt, akun) in enumerate(rows, start=start_num):
            try:
                kode_num = int(re.search(r"(\d+)", kode).group())
            except:
                kode_num = rid
            header = f"{kode} (ID {kode_num})"
            text = f"{header}\n```\n{disp_full}\n```"
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp_full))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
            kb = InlineKeyboardMarkup([
                [jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")],
                [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_akun"), InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp_full}", reply_markup=kb)
        bottom_nav = []
        if page > 1:
            bottom_nav.append(InlineKeyboardButton("⬅️ SEBELUMNYA", callback_data=f"hasil_full_page_{page-1}"))
        if page < total_pages:
            bottom_nav.append(InlineKeyboardButton("➡️ BERIKUTNYA", callback_data=f"hasil_full_page_{page+1}"))
        kb_bottom = []
        if bottom_nav:
            kb_bottom.append(bottom_nav)
        kb_bottom.append([InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_akun")])
        kb_bottom.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")])
        await context.bot.send_message(chat_id=user_id, text=f"📑 Halaman {page}/{total_pages} | {start_num}-{end_num} dari {total}", reply_markup=InlineKeyboardMarkup(kb_bottom))

    elif data.startswith("jual_"):
        rid = int(data.split("_")[1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT kode, display_full, display_format FROM hasil_format WHERE id=? AND user_id=?", (rid, user_id))
        row = c.fetchone()
        if row:
            kode, disp_full, disp_format = row
            if not disp_format:
                disp_format = disp_full
            c.execute("UPDATE hasil_format SET status='terjual' WHERE id=?", (rid,))
            now_iso = datetime.now().isoformat()
            c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "JUAL", f"ID {rid} {kode}", now_iso))
            conn.commit()
            # Ambil info seller
            seller_id = user_id
            seller_username = query.from_user.username or "-"
            seller_name = query.from_user.first_name or "ADMIN"
            # Cek apakah seller adalah admin
            try:
                c.execute("SELECT user_id FROM admins")
                admin_rows = c.fetchall()
                admin_ids_db = [r[0] for r in admin_rows]
            except:
                admin_ids_db = []
            all_admins = list(set(ADMIN_IDS + admin_ids_db))
            is_admin_seller = seller_id in all_admins
            conn.close()
            
            await context.bot.send_message(chat_id=user_id, text=f"💰 ID {rid} terjual!\n{disp_full}")
            
            # JIKA ADMIN YANG JUAL -> BROADCAST KE SEMUA USER
            if is_admin_seller:
                conn2 = sqlite3.connect(DB_PATH)
                c2 = conn2.cursor()
                c2.execute("SELECT user_id FROM users WHERE user_id!=?", (seller_id,))
                all_users = c2.fetchall()
                conn2.close()
                now_display = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                username_display = f"@{seller_username}" if seller_username and seller_username!="-" else f"@{seller_name}"
                notif_text = (
                    f"🔔 NOTIFIKASI DATA TERJUAL\n\n"
                    f"Data {kode} telah terjual!\n\n"
                    f"👑 Dijual oleh ADMIN:\n"
                    f"🆔 ID : {seller_id}\n"
                    f"👤 Nama : {seller_name}\n"
                    f"📱 Username : {username_display}\n"
                    f"📅 Tanggal : {now_display}\n\n"
                    f"Detail data:\n"
                    f"{disp_format[:800]}\n\n"
                    f"⚠️ Data ini sudah tidak tersedia lagi."
                )
                count_notif=0
                for (uid,) in all_users:
                    try:
                        await context.bot.send_message(chat_id=uid, text=notif_text)
                        count_notif+=1
                    except:
                        continue
                try:
                    await context.bot.send_message(chat_id=seller_id, text=f"📢 Notifikasi terjual telah dikirim ke {count_notif} user.")
                except:
                    pass
        else:
            conn.close()
            await query.edit_message_text("❌ Data tidak ditemukan atau bukan milikmu.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))

    elif data.startswith("del_") and not data.startswith("del_permanen_") and not data.startswith("del_data_") and not data.startswith("del_admin_"):
        rid = int(data.split("_")[1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # SOFT DELETE ke Recycle Bin
        c.execute("UPDATE hasil_format SET status='deleted' WHERE id=? AND user_id=?", (rid, user_id))
        c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "HAPUS", f"ID {rid} -> Sampah", datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🗑️ ID {rid} dipindah ke DATA YG DI HAPUS (HISTORY). Bisa dipulihkan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ LIHAT SAMPAH", callback_data="history_deleted")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))

    elif data.startswith("edit_"):
        rid = int(data.split("_")[1])
        context.user_data["edit_id"] = rid
        context.user_data["mode"] = "edit_format"
        await query.edit_message_text(f"✏️ EDIT ID {rid}\nKirim data baru 9 baris.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="back_main")]]))

    elif data == "hapus_semua":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ YA, HAPUS SEMUA", callback_data="confirm_hapus_semua")],[InlineKeyboardButton("❌ BATAL", callback_data="back_main")]])
        await query.edit_message_text("⚠️ Yakin hapus SEMUA?", reply_markup=kb)

    elif data == "confirm_hapus_semua":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM hasil_format WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("🗑️ Semua dihapus.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))

    elif data.startswith("cari_"):
        if "akun" in data:
            context.user_data["mode"] = "cari_akun"
            await query.edit_message_text(
                "🔍 **CARI FORMAT+AKUN**\n\n"
                "Ketik yang mau dicari:\n"
                "- Kode: ASD 001\n"
                "- Nama: RIO\n"
                "- NIK, KAB, KEC, KEL\n"
                "- Saldo, PT, dll\n\n"
                "Bot akan cari di semua data dan tampil urut kecil→besar:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]),
                parse_mode="Markdown"
            )
        else:
            context.user_data["mode"] = "cari_format"
            await query.edit_message_text(
                "🔍 **CARI HASIL FORMAT**\n\n"
                "Ketik yang mau dicari:\n"
                "- Kode: ASD 001\n"
                "- KAB: JAKARTA\n"
                "- KEC, KEL, PT, Saldo\n"
                "- Kata apapun\n\n"
                "Bot akan tampil urut ASD 001, 002, 003...:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]),
                parse_mode="Markdown"
            )

    elif data == "menu_data_saya":
        if not has_access(user_id):
            await query.edit_message_text(
                "🔒 **MENU TERKUNCI**\n\n"
                "Untuk menggunakan **DATA SAYA**, kamu harus berlangganan dulu.\n\n"
                "Pilih paket di bawah:",
                reply_markup=paket_menu_keyboard(),
                parse_mode="Markdown"
            )
            return
        # KONSEP BARU: DATA SAYA bisa format saja atau format+akun
        await query.edit_message_text(
            "📂 DATA SAYA\n\n"
            "Silahkan kirimkan data Anda di sini bisa format saja atau format+akun, "
            "nanti hasilnya akan di tampilkan di menu HASIL DATA SAYA.\n\n"
            "Pilih jenis format:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 1. FORMAT SAJA", callback_data="data_saya_format")],
                [InlineKeyboardButton("📑 2. KIRIM FORMAT+AKUN", callback_data="data_saya_full")],
                [InlineKeyboardButton("⬅️ 3. KEMBALI", callback_data="back_main")]
            ])
        )

    elif data == "data_saya_manual":
        context.user_data["mode"] = "data_saya_manual"
        await query.edit_message_text(
            "📂 DATA SAYA - MANUAL\n\n"
            "⌨️ BUAT FORMAT\n\n"
            "Ketik data tanpa perlu menulis KAB/KEC/KEL. Bot otomatis membaca urutannya:\n\n"
            "1️⃣ KAB\n2️⃣ KEC\n3️⃣ KEL\n4️⃣ SALDO\n5️⃣ KELAMIN\n6️⃣ KPJ\n7️⃣ SENSOR\n8️⃣ IT\n9️⃣ PT\n"
            "🔟 NIK LENGKAP\n1️⃣1️⃣ KPJ\n1️⃣2️⃣ NAMA LENGKAP\n1️⃣3️⃣ TANGGAL LAHIR\n\n"
            "Contoh:\nDEPOK\nCILODONG\nKALIBARU\n10.000.000\nPEREMPUAN 1992\n2019\n23****\n01-07-2022\nINDONESIA MERDEKA\n3201234589920002\n19000378990\nLIA\n12-12-1990\n\n"
            "Kirim data sekarang 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_data_saya")]])
        )

    elif data == "data_saya_excel":
        context.user_data["mode"] = "data_saya_excel"
        await query.edit_message_text(
            "📊 DATA SAYA - UPLOAD EXCEL\n\n"
            "Upload file .xlsx dengan format:\n"
            "A=KAB B=KEC C=KEL D=SALDO E=KELAMIN F=KPJ G=SENSOR H=IT I=PT J=NIK K=KPJ_LENGKAP L=NAMA M=TGL_LAHIR\n\n"
            "Kirim file sekarang 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_data_saya")]])
        )

    elif data == "menu_hasil_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if total==0:
            await query.edit_message_text(
                "📊 HASIL DATA SAYA\n\nBelum ada data. Silahkan tambah di menu DATA SAYA dulu.\nKirim 30 data sekaligus juga bisa!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📂 TAMBAH DATA", callback_data="menu_data_saya")],
                    [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
                ])
            )
            return
        # Menu utama HASIL DATA SAYA - konsep baru
        await query.edit_message_text(
            f"📊 HASIL DATA SAYA\n\n"
            f"Total: {total} data tersimpan\n"
            f"Pilih tampilan hasil:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 1. HASIL FORMAT DATA SAYA", callback_data="hasil_data_format")],
                [InlineKeyboardButton("📑 2. HASIL FORMAT+AKUN", callback_data="hasil_data_full")],
                [InlineKeyboardButton("⬅️ 3. KEMBALI", callback_data="back_main")]
            ])
        )
        return

    elif data == "hasil_data_format":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, display_text, raw_text, kode FROM data_saya WHERE user_id=? AND (status='ready' OR status IS NULL) ORDER BY id ASC LIMIT 30", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada data.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        await query.edit_message_text(f"📄 HASIL DATA SAYA - FORMAT SAJA\nTotal: {total} data, tampil {len(rows)} (kirim 30 sekaligus bisa!)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        for rid, disp, raw, kode in rows:
            display = disp or raw or "-"
            try:
                kode_num = int(re.search(r"(\d+)", kode).group()) if kode else rid
            except:
                kode_num = rid
            header = f"{kode} (ID {kode_num})" if kode else f"ID {rid}"
            # FORMAT SAJA = hanya data + kode, tanpa DATA LENGKAP tambahan
            # Pastikan display sudah ada kode, kalau belum tambahkan
            if kode and kode not in display:
                try:
                    _, _, _, kode_pos, _ = get_setting(user_id)
                except:
                    kode_pos = "atas"
                if kode_pos == "bawah":
                    display_out = f"{raw or disp}\n━━━━━━━━━━━━━━━━━━━\n     {kode}"
                else:
                    display_out = f"{kode}\n━━━━━━━━━━━━━━━━━━━\n{raw or disp}"
            else:
                display_out = display
            preview = display_out[:600]
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(display_out))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_data_{rid}")
            kb = InlineKeyboardMarkup([
                [jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_data_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_data_{rid}")],
                [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya"), InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n```\n{preview}\n```", reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header} - {preview[:500]}", reply_markup=kb)
        return

    elif data == "hasil_data_full":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, display_text, raw_text, kode, kab, kec, kel, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir FROM data_saya WHERE user_id=? AND (status='ready' OR status IS NULL) ORDER BY id ASC LIMIT 30", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada data.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        await query.edit_message_text(f"📑 HASIL DATA SAYA - FORMAT+AKUN\nTotal: {total} data, tampil {len(rows)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        for rid, disp, raw, kode, kab, kec, kel, nik_l, kpj_l, nama_l, tgl_l in rows:
            display = disp or raw or "-"
            try:
                kode_num = int(re.search(r"(\d+)", kode).group()) if kode else rid
            except:
                kode_num = rid
            header = f"{kode} (ID {kode_num})" if kode else f"ID {rid}"
            # FORMAT+AKUN = tambahkan DATA LENGKAP jika ada
            if nik_l or kpj_l or nama_l or tgl_l:
                data_lengkap = f"\n\n━━━━━━━━━━━━━━━━━━━\n📋 DATA LENGKAP\n\n🆔 NIK : {nik_l or '-'}\n💳 KPJ : {kpj_l or '-'}\n👤 NAMA : {nama_l or '-'}\n🎂LAHIR : {tgl_l or '-'}"
                display_out = display + data_lengkap
            else:
                display_out = display
            preview = display_out[:700]
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(display_out))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_data_{rid}")
            kb = InlineKeyboardMarkup([
                [jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_data_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_data_{rid}")],
                [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya"), InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n```\n{preview}\n```", reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header} - {preview[:500]}", reply_markup=kb)
        return

    elif data == "cari_data_saya":
        context.user_data["mode"] = "cari_data_saya"
        await query.edit_message_text(
            "🔍 CARI DATA SAYA\n\nKetik yang mau dicari:\n- NIK, Nama, KAB, KEC, KEL\n- KPJ, PT, Saldo\n- Kata apapun\n\nContoh: DEPOK atau LIA atau 320123...\nBisa cari 1 atau banyak data sekaligus.\n\nKetik sekarang:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya")],
                [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]
            ])
        )

    elif data == "export_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT kode, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir, display_text FROM data_saya WHERE user_id=? ORDER BY id ASC", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada DATA SAYA untuk di-export.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        try:
            import pandas as pd
            df = pd.DataFrame(rows, columns=["KAB","KEC","KEL","SALDO","KELAMIN","KPJ","SENSOR","IT","PT","NIK_LENGKAP","KPJ_LENGKAP","NAMA_LENGKAP","TGL_LAHIR","DISPLAY"])
            tmp_path = f"/tmp/data_saya_{user_id}.xlsx"
            df.to_excel(tmp_path, index=False)
            await context.bot.send_document(chat_id=user_id, document=open(tmp_path, "rb"), filename=f"DATA_SAYA_{user_id}.xlsx", caption=f"📤 EXPORT DATA SAYA - {len(rows)} data")
            await query.edit_message_text(f"✅ Export {len(rows)} data berhasil!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        except Exception as e:
            await query.edit_message_text(f"❌ Gagal export: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))

    elif data == "hapus_satu_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, kab, kec, nama_lengkap FROM data_saya WHERE user_id=? ORDER BY id ASC LIMIT 20", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Tidak ada data.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        kb_rows=[]
        for rid, kab, kec, nama in rows:
            label = f"{rid} - {kab}/{nama or kec}"
            kb_rows.append([InlineKeyboardButton(f"🗑️ {label}", callback_data=f"del_data_{rid}")])
        kb_rows.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")])
        await query.edit_message_text(f"🗑️ HAPUS PER SATU - Pilih ID ({len(rows)} terbaru):", reply_markup=InlineKeyboardMarkup(kb_rows))

    elif data == "hapus_semua_data_saya":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ YA, HAPUS SEMUA", callback_data="confirm_hapus_semua_data")],
            [InlineKeyboardButton("❌ BATAL", callback_data="menu_hasil_data_saya")]
        ])
        await query.edit_message_text("⚠️ Yakin hapus SEMUA DATA SAYA? Tidak bisa dikembalikan!", reply_markup=kb)

    elif data == "confirm_hapus_semua_data":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM data_saya WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("🗑️ Semua DATA SAYA dihapus.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))

    elif data.startswith("jual_data_"):
        rid = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT display_text, raw_text, kode FROM data_saya WHERE id=? AND user_id=?", (rid, user_id))
        row = c.fetchone()
        if row:
            disp = row[0] or row[1]
            kode = row[2] if len(row)>2 else ""
            # Update status jadi terjual
            try:
                c.execute("UPDATE data_saya SET status='terjual' WHERE id=? AND user_id=?", (rid, user_id))
                c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "JUAL DATA SAYA", f"{kode} ID {rid}", datetime.now().isoformat()))
                conn.commit()
            except:
                pass
            try:
                from telegram import CopyTextButton
                await context.bot.send_message(chat_id=user_id, text=f"💰 DATA {kode} (ID {rid}) TERJUAL!\n```\n{disp}\n```", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 COPY", copy_text=CopyTextButton(disp))]]))
            except:
                await context.bot.send_message(chat_id=user_id, text=f"💰 DATA ID {rid} TERJUAL!\n{disp}")
            await query.edit_message_text(f"✅ ID {rid} ditandai terjual. Cek di HISTORY DATA SAYA > HISTORY JUAL", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🕘 HISTORY JUAL", callback_data="history_data_jual")],[InlineKeyboardButton("📊 HASIL DATA SAYA", callback_data="menu_hasil_data_saya")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
        else:
            await query.edit_message_text("❌ Data tidak ditemukan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        conn.close()
        return

    elif data.startswith("del_data_") and not data.startswith("del_data_permanen_"):
        rid = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS data_saya_deleted (id INTEGER PRIMARY KEY AUTOINCREMENT, orig_id INTEGER, user_id INTEGER, display_text TEXT, kab TEXT, kec TEXT, kel TEXT, raw_text TEXT, deleted_at TEXT)")
        except:
            pass
        c.execute("SELECT display_text, kab, kec, kel, raw_text FROM data_saya WHERE id=? AND user_id=?", (rid, user_id))
        row = c.fetchone()
        if row:
            disp, kab, kec, kel, raw = row
            c.execute("INSERT INTO data_saya_deleted (orig_id, user_id, display_text, kab, kec, kel, raw_text, deleted_at) VALUES (?,?,?,?,?,?,?,?)", (rid, user_id, disp, kab, kec, kel, raw, datetime.now().isoformat()))
            c.execute("DELETE FROM data_saya WHERE id=? AND user_id=?", (rid, user_id))
            conn.commit()
            await query.edit_message_text(f"🗑️ DATA SAYA ID {rid} dipindah ke DATA YG DI HAPUS.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ LIHAT SAMPAH", callback_data="history_deleted")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        else:
            await query.edit_message_text("❌ Data tidak ditemukan.")
        conn.close()

    elif data.startswith("edit_data_"):
        rid = int(data.split("_")[-1])
        context.user_data["edit_data_id"] = rid
        context.user_data["mode"] = "edit_data_saya"
        await query.edit_message_text(f"✏️ EDIT DATA SAYA ID {rid}\nKirim data baru 13 baris (KAB sampai TGL LAHIR):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_hasil_data_saya")]]))


    elif data == "history_deleted":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS data_saya_deleted (id INTEGER PRIMARY KEY AUTOINCREMENT, orig_id INTEGER, user_id INTEGER, display_text TEXT, kab TEXT, kec TEXT, kel TEXT, raw_text TEXT, deleted_at TEXT)")
        c.execute("SELECT id, kode, display_format, kab, kec FROM hasil_format WHERE user_id=? AND status='deleted' ORDER BY id DESC LIMIT 20", (user_id,))
        rows_f = c.fetchall()
        c.execute("SELECT id, orig_id, kab, kec, deleted_at FROM data_saya_deleted WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,))
        rows_d = c.fetchall()
        conn.close()
        total = len(rows_f) + len(rows_d)
        if total==0:
            await query.edit_message_text("🗑️ DATA YG DI HAPUS\n\nKosong. Data yang kamu hapus akan muncul di sini.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
            return
        txt_info = f"🗑️ DATA YG DI HAPUS\nTotal: {total}\n\nFORMAT: {len(rows_f)} | DATA SAYA: {len(rows_d)}\n"
        await query.edit_message_text(txt_info, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"♻️ FORMAT TERHAPUS ({len(rows_f)})", callback_data="list_deleted_format")],
            [InlineKeyboardButton(f"♻️ DATA SAYA TERHAPUS ({len(rows_d)})", callback_data="list_deleted_data_saya")],
            [InlineKeyboardButton("🗑️ HAPUS PERMANEN SEMUA SAMPAH", callback_data="confirm_permanen_hapus_semua_deleted")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]
        ]))
        # Kirim 5 terbaru format dengan tombol pulihkan
        if rows_f:
            for rid, kode, disp, kab, kec in rows_f[:5]:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"restore_{rid}"), InlineKeyboardButton("🗑️ HAPUS PERMANEN", callback_data=f"del_permanen_{rid}")]])
                try:
                    await context.bot.send_message(chat_id=user_id, text=f"🗑️ {kode} ID {rid} {kab}/{kec}\n```\n{disp[:1000]}\n```", reply_markup=kb, parse_mode="Markdown")
                except:
                    await context.bot.send_message(chat_id=user_id, text=f"🗑️ {kode} ID {rid}", reply_markup=kb)

    elif data == "list_deleted_format":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, kode, display_format FROM hasil_format WHERE user_id=? AND status='deleted' ORDER BY id DESC LIMIT 20", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Tidak ada FORMAT dihapus.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="history_deleted")]]))
            return
        await query.edit_message_text(f"🗑️ {len(rows)} FORMAT di Recycle Bin:")
        for rid, kode, disp in rows:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"restore_{rid}"), InlineKeyboardButton("🗑️ PERMANEN", callback_data=f"del_permanen_{rid}")]])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"{kode} ID {rid}\n```\n{disp[:1200]}\n```", reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{kode} ID {rid}", reply_markup=kb)

    elif data == "list_deleted_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, orig_id, kab, kec, display_text FROM data_saya_deleted WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Tidak ada DATA SAYA dihapus.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="history_deleted")]]))
            return
        await query.edit_message_text(f"🗑️ {len(rows)} DATA SAYA di Recycle Bin:")
        for del_id, orig_id, kab, kec, disp in rows:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"restore_data_{del_id}"), InlineKeyboardButton("🗑️ PERMANEN", callback_data=f"del_data_permanen_{del_id}")]])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"ID {orig_id} del {del_id} {kab}/{kec}\n```\n{disp[:1200]}\n```", reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"ID {orig_id}", reply_markup=kb)

    elif data.startswith("restore_") and not data.startswith("restore_data_"):
        rid = int(data.split("_")[1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE hasil_format SET status='ready' WHERE id=? AND user_id=? AND status='deleted'", (rid, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"♻️ ID {rid} dipulihkan!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format")],[InlineKeyboardButton("🗑️ SAMPAH", callback_data="history_deleted")]]))

    elif data.startswith("restore_data_"):
        del_id = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT display_text, kab, kec, kel, raw_text FROM data_saya_deleted WHERE id=? AND user_id=?", (del_id, user_id))
        row = c.fetchone()
        if row:
            disp, kab, kec, kel, raw = row
            c.execute("INSERT INTO data_saya (user_id, kab, kec, kel, display_text, raw_text, created_at) VALUES (?,?,?,?,?,?,?)", (user_id, kab, kec, kel, disp, raw, datetime.now().isoformat()))
            c.execute("DELETE FROM data_saya_deleted WHERE id=?", (del_id,))
            conn.commit()
            await query.edit_message_text(f"♻️ DATA SAYA dipulihkan!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 DATA SAYA", callback_data="menu_hasil_data_saya")],[InlineKeyboardButton("🗑️ SAMPAH", callback_data="history_deleted")]]))
        else:
            await query.edit_message_text("Tidak ditemukan.")
        conn.close()

    elif data.startswith("del_permanen_"):
        rid = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM hasil_format WHERE id=? AND user_id=? AND status='deleted'", (rid, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🗑️ ID {rid} hapus permanen.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="history_deleted")]]))

    elif data.startswith("del_data_permanen_"):
        del_id = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM data_saya_deleted WHERE id=? AND user_id=?", (del_id, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🗑️ del_id {del_id} hapus permanen.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="history_deleted")]]))

    elif data == "confirm_permanen_hapus_semua_deleted":
        await query.edit_message_text("⚠️ Hapus permanen semua sampah? Tidak bisa dipulihkan!", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ YA, HAPUS SEMUA PERMANEN", callback_data="exec_permanen_hapus_semua_deleted")],
            [InlineKeyboardButton("❌ BATAL", callback_data="history_deleted")]
        ]))

    elif data == "exec_permanen_hapus_semua_deleted":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM hasil_format WHERE user_id=? AND status='deleted'", (user_id,))
        c.execute("DELETE FROM data_saya_deleted WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("🗑️ Semua sampah dihapus permanen.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))



    elif data == "menu_hubungi_admin":
        text = (
            "📞 HUBUNGI ADMIN\n"
            "Jika membutuhkan bantuan, silakan hubungi Admin:\n"
            "👤 Telegram @Hambali1995\n"
            "📱 WhatsApp 083160776091"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Chat di Telegram", url="https://t.me/Hambali1995")],
            [InlineKeyboardButton("💬 Chat di WhatsApp", url="https://wa.me/6283160776091")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
        ])
        await query.edit_message_text(text, reply_markup=kb)
        return

    elif data == "menu_admin":

        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT user_id FROM admins")
            admin_rows = c.fetchall()
            admin_ids_db = [r[0] for r in admin_rows]
        except:
            admin_ids_db = []
        all_admins = list(set(ADMIN_IDS + admin_ids_db))
        if user_id not in all_admins:
            conn.close()
            await query.edit_message_text("⛔ Bukan admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE status='ready'")
        total_ready = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE status='terjual'")
        total_terjual = c.fetchone()[0]
        try:
            c.execute("SELECT COUNT(*) FROM topup_pending WHERE status IN ('menunggu_bukti','pending','bukti_terkirim')")
            pending_topup = c.fetchone()[0]
        except:
            pending_topup = 0
        conn.close()
        await query.edit_message_text(
            f"👑 **PANEL ADMIN**\n\n👥 Total User: {total_users}\n📄 Ready: {total_ready}\n💰 Terjual: {total_terjual}\n💳 Topup Pending: {pending_topup}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 1. CEK USER AKTIF", callback_data="admin_cek_user")],
                [InlineKeyboardButton("⏰ 2. CEK EXPIRED/HAMPIR HABIS", callback_data="admin_cek_expired")],
                [InlineKeyboardButton("🗑️ 3. HAPUS USER/EXPIRE", callback_data="admin_hapus_user")],
                [InlineKeyboardButton("➕ 4. TAMBAH ADMIN", callback_data="admin_tambah_admin")],
                [InlineKeyboardButton("➖ 5. HAPUS ADMIN", callback_data="admin_hapus_admin")],
                [InlineKeyboardButton("📢 6. BROADCAST", callback_data="admin_broadcast")],
                [InlineKeyboardButton("💳 7. CEK TOPUP", callback_data="admin_topup")],
                [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
            ]),
            parse_mode="Markdown"
        )
        return

    elif data == "menu_setting":



        template, kode_atas, kode_prefix, kode_pos, base_count = get_setting(user_id)
        next_kode = get_next_code(user_id)
        pos_label = "ATAS" if kode_pos == "atas" else "BAWAH"
        await query.edit_message_text(
            f"⚙️ **SETTING**\n\nKode aktif: {next_kode} ({pos_label})\nPilih yang mau di-setting:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 1. SET TEMPLAT", callback_data="setting_template_view")],
                [InlineKeyboardButton("⬆️ 2. SET KODE ATAS", callback_data="setting_kode_atas")],
                [InlineKeyboardButton("⬇️ 3. SET KODE BAWAH", callback_data="setting_kode_bawah")],
                [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
            ]),
            parse_mode="Markdown"
        )

    elif data == "setting_template_view":
        template, kode_atas, kode_prefix, kode_pos, base_count = get_setting(user_id)
        next_kode = get_next_code(user_id)
        preview_template = template if "{KAB}" in template else """📍 KAB  : {KAB}\n📍 KEC  : {KEC}\n📍 KEL  : {KEL}\n\n💰 SALDO  : {SALDO}\n\n🆔 KELAMIN : {KELAMIN}\n💳 KPJ  : {KPJ}\n🔰 SENSOR: {SENSOR}\n📅 IT   : {IT}\n🏛️ PT   : {PT}\n\n🏆 DPT JMO LASIK ✅"""
        header = "⚙️ SETTING AUTO FORMAT\n\n"
        kode_line = f"🔢 Kode: 🟢 {next_kode}\n\n"
        template_label = "📋 Template aktif:\n"
        box_content = preview_template
        placeholder_info = "\n\nKamu bisa memakai placeholder:\n{KAB}  {KEC}  {KEL}  {SALDO}\n{KELAMIN}  {KPJ}  {SENSOR}  {IT}\n{PT}"
        full_text = f"{header}{kode_line}{template_label}```\n{box_content}\n```{placeholder_info}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ UBAH TEMPLATE", callback_data="ubah_template")],
            [InlineKeyboardButton("📋 TEMPLAT SAYA", callback_data="templat_saya"), InlineKeyboardButton("⬅️ MENU AUTO FORMAT", callback_data="menu_setting")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
        ])
        try:
            await query.edit_message_text(full_text, reply_markup=kb, parse_mode="Markdown")
        except:
            await query.edit_message_text(f"SETTING AUTO FORMAT\nKode: {next_kode}\n\nTemplate aktif:\n{box_content}", reply_markup=kb)

    elif data == "ubah_template":
        context.user_data["mode"] = "set_template"
        await query.edit_message_text(
            "✏️ **UBAH TEMPLATE**\n\nKirim template baru. Gunakan placeholder:\n`{KODE} {KAB} {KEC} {KEL} {SALDO} {KELAMIN} {KPJ} {SENSOR} {IT} {PT}`\n\nContoh:\n```\n{KODE}\nKAB : {KAB}\nKEC : {KEC}\n```\n\nKetik template baru sekarang:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="setting_template_view")]]),
            parse_mode="Markdown"
        )

    elif data == "templat_saya":
        template, kode_atas, kode_prefix, _ = get_setting(user_id)
        next_kode = get_next_code(user_id)
        text = f"📋 **TEMPLAT SAYA**\n\nKode aktif: {next_kode}\n\nTemplate:\n```\n{template}\n```"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ EDIT", callback_data="ubah_template")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="setting_template_view")]
        ])
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except:
            await query.edit_message_text(f"TEMPLAT SAYA\nKode: {next_kode}\nTemplate:\n{template}", reply_markup=kb)

    elif data == "setting_kode_atas":
        context.user_data["mode"] = "set_kode_atas"
        context.user_data["kode_pos"] = "atas"
        text = (
            "🔢 SET KODE FORMAT - ATAS\n\n"
            "Ketik kode awal yang kamu mau.\n"
            "Contoh:\n"
            "JPG  -  001\n"
            "ABC  -  001\n\n"
            "Bot akan otomatis urut: 001, 002, 003...\n"
            "tanpa duplikat dan muncul di ATAS\n"
            "format.\n\n"
            "Ketik kode sekarang:"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_setting")]])
        await query.edit_message_text(text, reply_markup=kb)

    elif data == "setting_kode_bawah":
        context.user_data["mode"] = "set_kode_bawah"
        context.user_data["kode_pos"] = "bawah"
        text = (
            "🔢 SET KODE FORMAT - BAWAH\n\n"
            "Ketik kode awal yang kamu mau.\n"
            "Contoh:\n"
            "JPG  -  001\n"
            "ABC  -  001\n\n"
            "Bot akan otomatis urut: 001, 002, 003...\n"
            "tanpa duplikat dan muncul di BAWAH\n"
            "format (di tengah).\n\n"
            "Ketik kode sekarang:"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_setting")]])
        await query.edit_message_text(text, reply_markup=kb)

    elif data == "setting_kode":
        context.user_data["mode"] = "set_kode_atas"
        context.user_data["kode_pos"] = "atas"
        text = (
            "🔢 SET KODE FORMAT\n\n"
            "Ketik kode awal yang kamu mau.\n"
            "Contoh:\n"
            "JPG  -  001\n"
            "ABC  -  001\n\n"
            "Bot akan otomatis urut: 001, 002, 003...\n"
            "tanpa duplikat dan muncul di atas\n"
            "format.\n\n"
            "Ketik kode sekarang:"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_setting")]])
        await query.edit_message_text(text, reply_markup=kb)

    elif data == "setting_kode_atas":
        context.user_data["mode"] = "set_kode_atas"
        context.user_data["kode_pos"] = "atas"
        template, kode_atas, kode_prefix, kode_pos, base_count = get_setting(user_id)
        next_kode = get_next_code(user_id)
        text = (
            f"⬆️ SET KODE ATAS\n\n"
            f"Kode aktif sekarang: {next_kode} ({kode_pos.upper()})\n\n"
            f"Ketik kode awal baru untuk posisi ATAS.\n"
            f"Contoh:\n"
            f"MGB - 001\n"
            f"JPG - 001\n\n"
            f"Kode akan muncul DI ATAS format, otomatis urut 001, 002, 003...\n\n"
            f"Ketik kode sekarang:"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_setting")]])
        await query.edit_message_text(text, reply_markup=kb)

    elif data == "setting_kode_bawah":
        context.user_data["mode"] = "set_kode_bawah"
        context.user_data["kode_pos"] = "bawah"
        template, kode_atas, kode_prefix, kode_pos, base_count = get_setting(user_id)
        next_kode = get_next_code(user_id)
        text = (
            f"⬇️ SET KODE BAWAH\n\n"
            f"Kode aktif sekarang: {next_kode} ({kode_pos.upper()})\n\n"
            f"Ketik kode awal baru untuk posisi BAWAH.\n"
            f"Contoh:\n"
            f"MGB - 001\n"
            f"JPG - 001\n\n"
            f"Kode akan muncul DI BAWAH format (di tengah), otomatis urut 001, 002, 003...\n\n"
            f"Ketik kode sekarang:"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_setting")]])
        await query.edit_message_text(text, reply_markup=kb)

    elif data == "setting_template_view":
        template, kode_atas, kode_prefix, kode_pos, base_count = get_setting(user_id)
        next_kode = get_next_code(user_id)
        pos_label = "ATAS" if kode_pos == "atas" else "BAWAH"
        preview_at = f"     {next_kode}\n━━━━━━━━━━━━━━━━━━━\n[FORMAT KAMU]" if kode_pos=="atas" else f"[FORMAT KAMU]\n━━━━━━━━━━━━━━━━━━━\n     {next_kode}"
        text = (
            f"⚙️ SETTING SAAT INI\n\n"
            f"Kode Aktif : {next_kode}\n"
            f"Posisi    : {pos_label} ✅ (sesuai yang dipilih)\n"
            f"Prefix    : {kode_prefix}\n"
            f"Angka Awal: {kode_atas}\n\n"
            f"Preview posisi {pos_label}:\n"
            f"```\n{preview_at}\n```\n\n"
            f"Template:\n{template[:500]}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 1. SET TEMPLAT", callback_data="setting_template_view")],
            [InlineKeyboardButton("⬆️ 2. SET KODE ATAS", callback_data="setting_kode_atas")],
            [InlineKeyboardButton("⬇️ 3. SET KODE BAWAH", callback_data="setting_kode_bawah")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_setting")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "menu_data_saya":
        if not has_access(user_id):
            await query.edit_message_text(
                "🔒 **MENU TERKUNCI**\n\n"
                "Untuk menggunakan **DATA SAYA**, kamu harus berlangganan dulu.\n\n"
                "Pilih paket di bawah:",
                reply_markup=paket_menu_keyboard(),
                parse_mode="Markdown"
            )
            return
        # KONSEP BARU: DATA SAYA bisa format saja atau format+akun
        await query.edit_message_text(
            "📂 DATA SAYA\n\n"
            "Silahkan kirimkan data Anda di sini bisa format saja atau format+akun, "
            "nanti hasilnya akan di tampilkan di menu HASIL DATA SAYA.\n\n"
            "Pilih jenis format:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 1. FORMAT SAJA", callback_data="data_saya_format")],
                [InlineKeyboardButton("📑 2. KIRIM FORMAT+AKUN", callback_data="data_saya_full")],
                [InlineKeyboardButton("⬅️ 3. KEMBALI", callback_data="back_main")]
            ])
        )

    elif data == "data_saya_manual":
        context.user_data["mode"] = "data_saya_manual"
        await query.edit_message_text(
            "📂 DATA SAYA - MANUAL\n\n"
            "⌨️ BUAT FORMAT\n\n"
            "Ketik data tanpa perlu menulis KAB/KEC/KEL. Bot otomatis membaca urutannya:\n\n"
            "1️⃣ KAB\n2️⃣ KEC\n3️⃣ KEL\n4️⃣ SALDO\n5️⃣ KELAMIN\n6️⃣ KPJ\n7️⃣ SENSOR\n8️⃣ IT\n9️⃣ PT\n"
            "🔟 NIK LENGKAP\n1️⃣1️⃣ KPJ\n1️⃣2️⃣ NAMA LENGKAP\n1️⃣3️⃣ TANGGAL LAHIR\n\n"
            "Contoh:\nDEPOK\nCILODONG\nKALIBARU\n10.000.000\nPEREMPUAN 1992\n2019\n23****\n01-07-2022\nINDONESIA MERDEKA\n3201234589920002\n19000378990\nLIA\n12-12-1990\n\n"
            "Kirim data sekarang 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_data_saya")]])
        )

    elif data == "data_saya_excel":
        context.user_data["mode"] = "data_saya_excel"
        await query.edit_message_text(
            "📊 DATA SAYA - UPLOAD EXCEL\n\n"
            "Upload file .xlsx dengan format:\n"
            "A=KAB B=KEC C=KEL D=SALDO E=KELAMIN F=KPJ G=SENSOR H=IT I=PT J=NIK K=KPJ_LENGKAP L=NAMA M=TGL_LAHIR\n\n"
            "Kirim file sekarang 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_data_saya")]])
        )

    elif data == "menu_hasil_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if total==0:
            await query.edit_message_text(
                "📊 HASIL DATA SAYA\n\nBelum ada data. Silahkan tambah di menu DATA SAYA dulu.\nKirim 30 data sekaligus juga bisa!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📂 TAMBAH DATA", callback_data="menu_data_saya")],
                    [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
                ])
            )
            return
        # Menu utama HASIL DATA SAYA - konsep baru
        await query.edit_message_text(
            f"📊 HASIL DATA SAYA\n\n"
            f"Total: {total} data tersimpan\n"
            f"Pilih tampilan hasil:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 1. HASIL FORMAT DATA SAYA", callback_data="hasil_data_format")],
                [InlineKeyboardButton("📑 2. HASIL FORMAT+AKUN", callback_data="hasil_data_full")],
                [InlineKeyboardButton("⬅️ 3. KEMBALI", callback_data="back_main")]
            ])
        )
        return

    elif data == "hasil_data_format":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, display_text, raw_text, kode FROM data_saya WHERE user_id=? AND (status='ready' OR status IS NULL) ORDER BY id ASC LIMIT 30", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada data.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        await query.edit_message_text(f"📄 HASIL DATA SAYA - FORMAT SAJA\nTotal: {total} data, tampil {len(rows)} (kirim 30 sekaligus bisa!)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        for rid, disp, raw, kode in rows:
            display = disp or raw or "-"
            try:
                kode_num = int(re.search(r"(\d+)", kode).group()) if kode else rid
            except:
                kode_num = rid
            header = f"{kode} (ID {kode_num})" if kode else f"ID {rid}"
            # FORMAT SAJA = hanya data + kode, tanpa DATA LENGKAP tambahan
            # Pastikan display sudah ada kode, kalau belum tambahkan
            if kode and kode not in display:
                try:
                    _, _, _, kode_pos, _ = get_setting(user_id)
                except:
                    kode_pos = "atas"
                if kode_pos == "bawah":
                    display_out = f"{raw or disp}\n━━━━━━━━━━━━━━━━━━━\n     {kode}"
                else:
                    display_out = f"{kode}\n━━━━━━━━━━━━━━━━━━━\n{raw or disp}"
            else:
                display_out = display
            preview = display_out[:600]
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(display_out))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_data_{rid}")
            kb = InlineKeyboardMarkup([
                [jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_data_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_data_{rid}")],
                [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya"), InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n```\n{preview}\n```", reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header} - {preview[:500]}", reply_markup=kb)
        return

    elif data == "hasil_data_full":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, display_text, raw_text, kode, kab, kec, kel, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir FROM data_saya WHERE user_id=? AND (status='ready' OR status IS NULL) ORDER BY id ASC LIMIT 30", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada data.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        await query.edit_message_text(f"📑 HASIL DATA SAYA - FORMAT+AKUN\nTotal: {total} data, tampil {len(rows)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        for rid, disp, raw, kode, kab, kec, kel, nik_l, kpj_l, nama_l, tgl_l in rows:
            display = disp or raw or "-"
            try:
                kode_num = int(re.search(r"(\d+)", kode).group()) if kode else rid
            except:
                kode_num = rid
            header = f"{kode} (ID {kode_num})" if kode else f"ID {rid}"
            # FORMAT+AKUN = tambahkan DATA LENGKAP jika ada
            if nik_l or kpj_l or nama_l or tgl_l:
                data_lengkap = f"\n\n━━━━━━━━━━━━━━━━━━━\n📋 DATA LENGKAP\n\n🆔 NIK : {nik_l or '-'}\n💳 KPJ : {kpj_l or '-'}\n👤 NAMA : {nama_l or '-'}\n🎂LAHIR : {tgl_l or '-'}"
                display_out = display + data_lengkap
            else:
                display_out = display
            preview = display_out[:700]
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(display_out))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_data_{rid}")
            kb = InlineKeyboardMarkup([
                [jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_data_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_data_{rid}")],
                [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya"), InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n```\n{preview}\n```", reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header} - {preview[:500]}", reply_markup=kb)
        return

    elif data == "cari_data_saya":
        context.user_data["mode"] = "cari_data_saya"
        await query.edit_message_text(
            "🔍 CARI DATA SAYA\n\nKetik yang mau dicari:\n- NIK, Nama, KAB, KEC, KEL\n- KPJ, PT, Saldo\n- Kata apapun\n\nContoh: DEPOK atau LIA atau 320123...\nBisa cari 1 atau banyak data sekaligus.\n\nKetik sekarang:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI DATA", callback_data="cari_data_saya")],
                [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]
            ])
        )

    elif data == "export_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT kode, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir, display_text FROM data_saya WHERE user_id=? ORDER BY id ASC", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada DATA SAYA untuk di-export.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        try:
            import pandas as pd
            df = pd.DataFrame(rows, columns=["KAB","KEC","KEL","SALDO","KELAMIN","KPJ","SENSOR","IT","PT","NIK_LENGKAP","KPJ_LENGKAP","NAMA_LENGKAP","TGL_LAHIR","DISPLAY"])
            tmp_path = f"/tmp/data_saya_{user_id}.xlsx"
            df.to_excel(tmp_path, index=False)
            await context.bot.send_document(chat_id=user_id, document=open(tmp_path, "rb"), filename=f"DATA_SAYA_{user_id}.xlsx", caption=f"📤 EXPORT DATA SAYA - {len(rows)} data")
            await query.edit_message_text(f"✅ Export {len(rows)} data berhasil!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        except Exception as e:
            await query.edit_message_text(f"❌ Gagal export: {e}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))

    elif data == "hapus_satu_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, kab, kec, nama_lengkap FROM data_saya WHERE user_id=? ORDER BY id ASC LIMIT 20", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Tidak ada data.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        kb_rows=[]
        for rid, kab, kec, nama in rows:
            label = f"{rid} - {kab}/{nama or kec}"
            kb_rows.append([InlineKeyboardButton(f"🗑️ {label}", callback_data=f"del_data_{rid}")])
        kb_rows.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")])
        await query.edit_message_text(f"🗑️ HAPUS PER SATU - Pilih ID ({len(rows)} terbaru):", reply_markup=InlineKeyboardMarkup(kb_rows))

    elif data == "hapus_semua_data_saya":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ YA, HAPUS SEMUA", callback_data="confirm_hapus_semua_data")],
            [InlineKeyboardButton("❌ BATAL", callback_data="menu_hasil_data_saya")]
        ])
        await query.edit_message_text("⚠️ Yakin hapus SEMUA DATA SAYA? Tidak bisa dikembalikan!", reply_markup=kb)

    elif data == "confirm_hapus_semua_data":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM data_saya WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("🗑️ Semua DATA SAYA dihapus.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))

    elif data.startswith("jual_data_"):
        rid = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT display_text, raw_text, kode FROM data_saya WHERE id=? AND user_id=?", (rid, user_id))
        row = c.fetchone()
        if row:
            disp = row[0] or row[1]
            kode = row[2] if len(row)>2 else ""
            # Update status jadi terjual
            try:
                c.execute("UPDATE data_saya SET status='terjual' WHERE id=? AND user_id=?", (rid, user_id))
                c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "JUAL DATA SAYA", f"{kode} ID {rid}", datetime.now().isoformat()))
                conn.commit()
            except:
                pass
            try:
                from telegram import CopyTextButton
                await context.bot.send_message(chat_id=user_id, text=f"💰 DATA {kode} (ID {rid}) TERJUAL!\n```\n{disp}\n```", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 COPY", copy_text=CopyTextButton(disp))]]))
            except:
                await context.bot.send_message(chat_id=user_id, text=f"💰 DATA ID {rid} TERJUAL!\n{disp}")
            await query.edit_message_text(f"✅ ID {rid} ditandai terjual. Cek di HISTORY DATA SAYA > HISTORY JUAL", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🕘 HISTORY JUAL", callback_data="history_data_jual")],[InlineKeyboardButton("📊 HASIL DATA SAYA", callback_data="menu_hasil_data_saya")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
        else:
            await query.edit_message_text("❌ Data tidak ditemukan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        conn.close()
        return

    elif data.startswith("del_data_") and not data.startswith("del_data_permanen_"):
        rid = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS data_saya_deleted (id INTEGER PRIMARY KEY AUTOINCREMENT, orig_id INTEGER, user_id INTEGER, display_text TEXT, kab TEXT, kec TEXT, kel TEXT, raw_text TEXT, deleted_at TEXT)")
        except:
            pass
        c.execute("SELECT display_text, kab, kec, kel, raw_text FROM data_saya WHERE id=? AND user_id=?", (rid, user_id))
        row = c.fetchone()
        if row:
            disp, kab, kec, kel, raw = row
            c.execute("INSERT INTO data_saya_deleted (orig_id, user_id, display_text, kab, kec, kel, raw_text, deleted_at) VALUES (?,?,?,?,?,?,?,?)", (rid, user_id, disp, kab, kec, kel, raw, datetime.now().isoformat()))
            c.execute("DELETE FROM data_saya WHERE id=? AND user_id=?", (rid, user_id))
            conn.commit()
            await query.edit_message_text(f"🗑️ DATA SAYA ID {rid} dipindah ke DATA YG DI HAPUS.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ LIHAT SAMPAH", callback_data="history_deleted")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
        else:
            await query.edit_message_text("❌ Data tidak ditemukan.")
        conn.close()

    elif data.startswith("edit_data_"):
        rid = int(data.split("_")[-1])
        context.user_data["edit_data_id"] = rid
        context.user_data["mode"] = "edit_data_saya"
        await query.edit_message_text(f"✏️ EDIT DATA SAYA ID {rid}\nKirim data baru 13 baris (KAB sampai TGL LAHIR):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_hasil_data_saya")]]))


    elif data == "menu_admin":
        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT user_id FROM admins")
            admin_rows = c.fetchall()
            admin_ids_db = [r[0] for r in admin_rows]
        except:
            admin_ids_db = []
        all_admins = list(set(ADMIN_IDS + admin_ids_db))
        if user_id not in all_admins:
            conn.close()
            await query.edit_message_text("⛔ Bukan admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE status='ready'")
        total_ready = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE status='terjual'")
        total_terjual = c.fetchone()[0]
        try:
            c.execute("SELECT COUNT(*) FROM topup_pending WHERE status IN ('menunggu_bukti','pending','bukti_terkirim')")
            pending_topup = c.fetchone()[0]
        except:
            pending_topup = 0
        conn.close()
        await query.edit_message_text(
            f"👑 **PANEL ADMIN**\n\n👥 Total User: {total_users}\n📄 Ready: {total_ready}\n💰 Terjual: {total_terjual}\n💳 Topup Pending: {pending_topup}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 1. CEK USER AKTIF", callback_data="admin_cek_user")],
                [InlineKeyboardButton("⏰ 2. CEK EXPIRED/HAMPIR HABIS", callback_data="admin_cek_expired")],
                [InlineKeyboardButton("🗑️ 3. HAPUS USER/EXPIRE", callback_data="admin_hapus_user")],
                [InlineKeyboardButton("➕ 4. TAMBAH ADMIN", callback_data="admin_tambah_admin")],
                [InlineKeyboardButton("➖ 5. HAPUS ADMIN", callback_data="admin_hapus_admin")],
                [InlineKeyboardButton("📢 6. BROADCAST", callback_data="admin_broadcast")],
                [InlineKeyboardButton("💳 7. CEK TOPUP", callback_data="admin_topup")],
                [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
            ]),
            parse_mode="Markdown"
        )
        return

    elif data == "menu_setting":


        template, kode_atas, kode_prefix, kode_pos, base_count = get_setting(user_id)
        next_kode = get_next_code(user_id)
        pos_label = "ATAS" if kode_pos == "atas" else "BAWAH"
        text = (
            f"⚙️ SETTING\n\n"
            f"Kode aktif: {next_kode} ({pos_label})\n"
            f"Posisi kode sesuai yang dipilih ✅\n\n"
            f"Pilih menu:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 1. SET TEMPLAT", callback_data="setting_template_view")],
            [InlineKeyboardButton("⬆️ 2. SET KODE ATAS", callback_data="setting_kode_atas")],
            [InlineKeyboardButton("⬇️ 3. SET KODE BAWAH", callback_data="setting_kode_bawah")],
            [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
        ])
        await query.edit_message_text(text, reply_markup=kb)

    elif data == "menu_history_data_saya":
        # HISTORY DATA SAYA - menu baru
        await query.edit_message_text(
            "🕘 HISTORY DATA SAYA\n\n"
            "Pilih history yang mau dilihat:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 1. HISTORY JUAL", callback_data="history_data_jual")],
                [InlineKeyboardButton("🗑️ 2. HISTORY HAPUS", callback_data="history_data_hapus")],
                [InlineKeyboardButton("⬅️ 3. KEMBALI", callback_data="back_main")]
            ])
        )
        return

    elif data == "history_data_jual":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, display_text, display_full, kode, created_at FROM data_saya WHERE user_id=? AND status='terjual' ORDER BY id DESC LIMIT 20", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=? AND status='terjual'", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if not rows:
            await query.edit_message_text(
                f"💰 HISTORY JUAL - DATA SAYA\n\nBelum ada data terjual. Total: {total}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 CARI", callback_data="cari_history_data_jual")],
                    [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history_data_saya")]
                ])
            )
            return
        await query.edit_message_text(
            f"💰 HISTORY JUAL - DATA SAYA\nTotal terjual: {total} data (tampil {len(rows)} terbaru)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI", callback_data="cari_history_data_jual")],
                [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history_data_saya")]
            ])
        )
        for rid, disp, disp_full, kode, created in rows:
            display = disp_full or disp or "-"
            try:
                kode_num = int(__import__('re').search(r"(\d+)", kode).group()) if kode else rid
            except:
                kode_num = rid
            header = f"{kode} (ID {kode_num}) TERJUAL" if kode else f"ID {rid} TERJUAL"
            preview = display[:500]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI", callback_data="cari_history_data_jual"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_data_permanen_{rid}"), InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"pulihkan_data_{rid}")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n```\n{preview}\n```", reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header} - {preview[:400]}", reply_markup=kb)
        return

    elif data == "history_data_hapus":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, display_text, display_full, kode, created_at FROM data_saya WHERE user_id=? AND status='terhapus' ORDER BY id DESC LIMIT 20", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=? AND status='terhapus'", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if not rows:
            await query.edit_message_text(
                f"🗑️ HISTORY HAPUS - DATA SAYA\n\nBelum ada data terhapus. Total: {total}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 CARI", callback_data="cari_history_data_hapus")],
                    [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history_data_saya")]
                ])
            )
            return
        await query.edit_message_text(
            f"🗑️ HISTORY HAPUS - DATA SAYA\nTotal terhapus: {total} data (tampil {len(rows)} terbaru)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI", callback_data="cari_history_data_hapus")],
                [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history_data_saya")]
            ])
        )
        for rid, disp, disp_full, kode, created in rows:
            display = disp_full or disp or "-"
            try:
                kode_num = int(__import__('re').search(r"(\d+)", kode).group()) if kode else rid
            except:
                kode_num = rid
            header = f"{kode} (ID {kode_num}) TERHAPUS" if kode else f"ID {rid} TERHAPUS"
            preview = display[:500]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"pulihkan_data_{rid}"), InlineKeyboardButton("🗑️ HAPUS PERMANEN", callback_data=f"del_data_permanen_{rid}")],
                [InlineKeyboardButton("🔍 CARI", callback_data="cari_history_data_hapus"), InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history_data_saya")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n```\n{preview}\n```", reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header} - {preview[:400]}", reply_markup=kb)
        return

    elif data == "menu_history":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 1. FORMAT", callback_data="history_format")],
            [InlineKeyboardButton("📑 2. FORMAT+AKUN", callback_data="history_full")],
            [InlineKeyboardButton("🔢 3. CEK KODE SAJA", callback_data="history_kode")],
            [InlineKeyboardButton("🗑️ 4. DATA YG DI HAPUS", callback_data="history_deleted")],
            [InlineKeyboardButton("⬅️ 4. KEMBALI", callback_data="back_main")]
        ])
        await query.edit_message_text("🕘 **HISTORY**\n\nPilih menu:\n1. Format (yang sudah dijual)\n2. Format+Akun (yang sudah dijual)\n3. Cek Kode saja\n4. Data yg dihapus (Recycle Bin)\n5. Kembali", reply_markup=kb, parse_mode="Markdown")

    elif data == "history_format":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, kode, display_format, created_at FROM hasil_format WHERE user_id=? AND status='terjual' ORDER BY id ASC", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("📄 Belum ada FORMAT yang dijual.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
            return
        await query.edit_message_text(f"📄 HISTORY FORMAT - {len(rows)} terjual:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
        for rid, kode, disp, created in rows:
            # cari waktu jual dari history
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT created_at FROM history WHERE user_id=? AND aksi='JUAL' AND detail LIKE ? ORDER BY id DESC LIMIT 1", (user_id, f"%ID {rid}%"))
            hrow = c.fetchone()
            conn.close()
            waktu = hrow[0] if hrow else created
            try:
                waktu_fmt = waktu[:19].replace("T", " ")
            except:
                waktu_fmt = waktu
            header = f"ID {rid} | {kode} | Dijual: {waktu_fmt}"
            text = f"{header}\n```\n{disp}\n```"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI", callback_data=f"cari_history_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"pulihkan_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp}", reply_markup=kb)

    elif data == "history_full":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, kode, display_full, created_at FROM hasil_format WHERE user_id=? AND status='terjual' ORDER BY id ASC", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("📑 Belum ada FORMAT+AKUN yang dijual.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
            return
        await query.edit_message_text(f"📑 HISTORY FORMAT+AKUN - {len(rows)} terjual:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
        for rid, kode, disp_full, created in rows:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT created_at FROM history WHERE user_id=? AND aksi='JUAL' AND detail LIKE ? ORDER BY id DESC LIMIT 1", (user_id, f"%ID {rid}%"))
            hrow = c.fetchone()
            conn.close()
            waktu = hrow[0] if hrow else created
            try:
                waktu_fmt = waktu[:19].replace("T", " ")
            except:
                waktu_fmt = waktu
            header = f"ID {rid} | {kode} | Dijual: {waktu_fmt}"
            text = f"{header}\n```\n{disp_full}\n```"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI", callback_data=f"cari_history_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"pulihkan_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp_full}", reply_markup=kb)

    elif data == "history_kode":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, kode, created_at FROM hasil_format WHERE user_id=? AND status='terjual' ORDER BY id ASC", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("🔢 Belum ada KODE yang dijual.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
            return
        # tampilkan list kode saja
        kode_list = []
        for rid, kode, created in rows:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT created_at FROM history WHERE user_id=? AND aksi='JUAL' AND detail LIKE ? ORDER BY id DESC LIMIT 1", (user_id, f"%ID {rid}%"))
            hrow = c.fetchone()
            conn.close()
            waktu = hrow[0] if hrow else created
            try:
                waktu_fmt = waktu[:16].replace("T", " ")
            except:
                waktu_fmt = waktu
            kode_list.append(f"{rid}. {kode} - {waktu_fmt}")
        
        text = "🔢 **CEK KODE SAJA - Terjual**\n\n" + "\n".join(kode_list) + "\n\nTotal: " + str(len(rows)) + " kode"
        # untuk tiap kode tetap ada tombol
        kb_rows = []
        for rid, kode, _ in rows[:20]:  # batasi 20 tombol biar tidak kepanjangan
            kb_rows.append([InlineKeyboardButton(f"ID {rid}: {kode}", callback_data=f"detail_kode_{rid}")])
        kb_rows.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="Markdown")

    elif data.startswith("detail_kode_"):
        rid = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT kode, display_full FROM hasil_format WHERE id=? AND user_id=?", (rid, user_id))
        row = c.fetchone()
        c.execute("SELECT created_at FROM history WHERE user_id=? AND aksi='JUAL' AND detail LIKE ? ORDER BY id DESC LIMIT 1", (user_id, f"%ID {rid}%"))
        hrow = c.fetchone()
        conn.close()
        if row:
            kode, disp_full = row
            waktu = hrow[0] if hrow else "-"
            try:
                waktu_fmt = waktu[:19].replace("T", " ")
            except:
                waktu_fmt = waktu
            text = f"🔢 KODE: {kode}\nID {rid} | Dijual: {waktu_fmt}\n```\n{disp_full}\n```"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI", callback_data=f"cari_history_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"pulihkan_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")],
                [InlineKeyboardButton("⬅️ KEMBALI", callback_data="history_kode")]
            ])
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            except:
                await query.edit_message_text(f"KODE: {kode} ID {rid}", reply_markup=kb)

    elif data.startswith("pulihkan_"):
        rid = int(data.split("_")[1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE hasil_format SET status='ready' WHERE id=? AND user_id=?", (rid, user_id))
        c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "PULIHKAN", f"ID {rid}", datetime.now().isoformat()))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"♻️ ID {rid} dipulihkan ke ready.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))

    elif data.startswith("cari_history_"):
        rid = int(data.split("_")[-1])
        context.user_data["mode"] = f"cari_history_{rid}"
        await query.edit_message_text(f"🔍 CARI untuk ID {rid} - ketik kata kunci:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))

    elif data == "admin_cek_user":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, username, nama, expired FROM users ORDER BY user_id DESC LIMIT 30")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada user.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
            return
        await query.edit_message_text(f"👥 CEK USER + STATUS ({len(rows)} user terbaru):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        for uid, username, nama, expired in rows:
            has_sub, exp_date, paket_name = get_user_subscription(uid)
            if is_admin_user(uid):
                status = "👑 ADMIN - UNLIMITED"
                paket_display = "ADMIN"
                exp_display = "UNLIMITED"
            elif has_sub:
                paket_display = paket_name or "Aktif"
                if exp_date == "UNLIMITED" or (paket_name and "UNLIMITED" in str(paket_name).upper()):
                    exp_display = "UNLIMITED"
                    status = "🟢 AKTIF UNLIMITED"
                else:
                    try:
                        from datetime import datetime
                        exp_dt = datetime.fromisoformat(exp_date) if "T" in str(exp_date) else datetime.strptime(str(exp_date)[:10], "%Y-%m-%d")
                        now = datetime.now()
                        sisa = (exp_dt - now).days
                        exp_display = exp_dt.strftime("%d-%m-%Y")
                        if sisa < 0:
                            status = f"🔴 EXPIRED ({sisa} hari)"
                        elif sisa <= 3:
                            status = f"🟡 HAMPIR HABIS ({sisa} hari)"
                        else:
                            status = f"🟢 AKTIF ({sisa} hari lagi)"
                    except:
                        exp_display = str(exp_date)[:10]
                        status = "🟢 AKTIF"
            else:
                paket_display = "Belum langganan"
                exp_display = "-"
                status = "🔴 TIDAK AKTIF"
            
            username_display = f"@{username}" if username else "-"
            text_user = (
                f"👤 {nama or 'User'} | ID: {uid}\n"
                f"📱 {username_display}\n"
                f"📦 Paket: {paket_display}\n"
                f"📅 Exp: {exp_display}\n"
                f"Status: {status}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ HAPUS LANGGANAN", callback_data=f"admin_expire_{uid}"),
                 InlineKeyboardButton("💳 +LANGGANAN", callback_data=f"admin_addsub_{uid}")],
                [InlineKeyboardButton("🗑️ HAPUS USER", callback_data=f"admin_deluser_{uid}")]
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=text_user, reply_markup=kb)
            except:
                pass
        return
        msg = "👥 **CEK USER AKTIF**\n\n"
        for idx, (uid, uname, total) in enumerate(rows, 1):
            is_admin = "👑" if uid in all_admins else ""
            msg += f"{idx}. ID:{uid} @{uname or '-'} - {total} format {is_admin}\n"
        msg += f"\nTotal: {len(rows)} user (top 30)"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 CARI USER", callback_data="admin_cari_user"), InlineKeyboardButton("🗑️ HAPUS USER", callback_data="admin_hapus_user")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]
        ])
        await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")


    elif data == "admin_cek_expired":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, username, nama FROM users")
        all_users = c.fetchall()
        conn.close()
        expired_list=[]
        almost_list=[]
        no_sub_list=[]
        from datetime import datetime
        for uid, username, nama in all_users:
            if is_admin_user(uid):
                continue
            has_sub, exp_date, paket_name = get_user_subscription(uid)
            if not has_sub:
                no_sub_list.append((uid, username, nama, paket_name, exp_date))
            else:
                if exp_date == "UNLIMITED" or (paket_name and "UNLIMITED" in str(paket_name).upper()):
                    continue
                try:
                    exp_dt = datetime.fromisoformat(exp_date) if "T" in str(exp_date) else datetime.strptime(str(exp_date)[:10], "%Y-%m-%d")
                    sisa = (exp_dt - datetime.now()).days
                    if sisa < 0:
                        expired_list.append((uid, username, nama, paket_name, exp_date, sisa))
                    elif sisa <= 7:
                        almost_list.append((uid, username, nama, paket_name, exp_date, sisa))
                except:
                    pass
        if not expired_list and not almost_list and not no_sub_list:
            await query.edit_message_text("✅ Semua user aktif, tidak ada yang expired/hampir habis.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
            return
        await query.edit_message_text(f"⏰ CEK EXPIRED:\n🔴 Expired: {len(expired_list)}\n🟡 Hampir habis (≤7 hari): {len(almost_list)}\n⚪ Belum langganan: {len(no_sub_list)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        for uid, username, nama, paket, exp_date, sisa in expired_list[:20]:
            text_user = f"🔴 EXPIRED\n👤 {nama or 'User'} | ID: {uid}\n📱 @{username or '-'}\n📦 {paket} Exp: {exp_date[:10]} ({sisa} hari)\n"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 PERPANJANG", callback_data=f"admin_addsub_{uid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"admin_deluser_{uid}")]])
            try:
                await context.bot.send_message(chat_id=user_id, text=text_user, reply_markup=kb)
            except:
                pass
        for uid, username, nama, paket, exp_date, sisa in almost_list[:20]:
            text_user = f"🟡 HAMPIR HABIS {sisa} hari\n👤 {nama or 'User'} | ID: {uid}\n📱 @{username or '-'}\n📦 {paket} Exp: {exp_date[:10]}\n"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 PERPANJANG", callback_data=f"admin_addsub_{uid}"), InlineKeyboardButton("❌ EXPIRE", callback_data=f"admin_expire_{uid}")]])
            try:
                await context.bot.send_message(chat_id=user_id, text=text_user, reply_markup=kb)
            except:
                pass
        return

    elif data == "admin_hapus_user":

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, username, nama FROM users ORDER BY user_id DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada user.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
            return
        kb_rows=[]
        for uid, username, nama in rows:
            has_sub, exp_date, paket_name = get_user_subscription(uid)
            if is_admin_user(uid):
                label = f"👑 {uid} {nama or username} - ADMIN"
            elif has_sub:
                label = f"🟢 {uid} {nama or username} - {paket_name}"
            else:
                label = f"🔴 {uid} {nama or username} - NO SUB"
            kb_rows.append([InlineKeyboardButton(label, callback_data=f"admin_deluser_{uid}")])
        kb_rows.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")])
        await query.edit_message_text(
            "🗑️ **HAPUS USER / EXPIRE LANGGANAN**\n\n"
            "Pilih user untuk dihapus/expire:\n"
            "🟢 = Aktif langganan\n"
            "🔴 = Tidak aktif\n"
            "👑 = Admin\n\n"
            "Setelah pilih, kamu bisa hapus langganan atau hapus user total.",
            reply_markup=InlineKeyboardMarkup(kb_rows),
            parse_mode="Markdown"
        )
        return

    elif data.startswith("admin_expire_"):
        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        target_id = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE subscriptions SET status='expired' WHERE user_id=? AND status='active'", (target_id,))
        c.execute("UPDATE users SET expired='EXPIRED' WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        try:
            await context.bot.send_message(chat_id=target_id, text="⚠️ Langganan kamu telah dihapus/expired oleh admin. Silahkan beli paket lagi untuk pakai BUAT FORMAT & DATA SAYA.", reply_markup=paket_menu_keyboard())
        except:
            pass
        await query.edit_message_text(f"✅ Langganan user {target_id} berhasil di-expire/hapus. Status sekarang TIDAK AKTIF.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥 CEK USER LAGI", callback_data="admin_cek_user")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        return

    elif data.startswith("admin_addsub_"):
        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        target_id = int(data.split("_")[-1])
        context.user_data["mode"] = f"admin_addsub_{target_id}"
        await query.edit_message_text(
            f"💳 Tambah langganan untuk user {target_id}\n\nKetik paket:\n- 3bulan\n- 6bulan\n- 1tahun\n- unlimited\n\nContoh: 3bulan",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="admin_cek_user")]])
        )
        return

    elif data.startswith("admin_deluser_"):
        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        target_id = int(data.split("_")[-1])
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ YA, HAPUS TOTAL", callback_data=f"confirm_deluser_{target_id}")],
            [InlineKeyboardButton("❌ BATAL", callback_data="admin_hapus_user")]
        ])
        await query.edit_message_text(f"⚠️ Yakin hapus user {target_id} total?\nSemua data format & langganannya akan hilang!", reply_markup=kb)
        return

    elif data.startswith("confirm_deluser_"):
        if not is_admin_user(user_id):
            await query.answer("⛔ Bukan admin", show_alert=True)
            return
        target_id = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM subscriptions WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM topup_pending WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM hasil_format WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM data_saya WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🗑️ User {target_id} berhasil dihapus total.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        return

        kb_rows = []
        for (uid,) in rows:
            kb_rows.append([InlineKeyboardButton(f"🗑️ Hapus {uid}", callback_data=f"admin_del_admin_{uid}")])
        kb_rows.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")])
        await query.edit_message_text(f"➖ **HAPUS ADMIN**\n\nPilih admin yang mau dihapus ({len(rows)}):", reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="Markdown")

    elif data.startswith("admin_del_admin_"):
        del_id = int(data.split("_")[-1])
        if del_id in ADMIN_IDS:
            await query.edit_message_text("❌ Tidak bisa hapus admin utama (dari config).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id=?", (del_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ Admin {del_id} dihapus.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))

    elif data == "admin_broadcast":
        context.user_data["mode"] = "admin_broadcast"
        await query.edit_message_text(
            "📢 **BROADCAST**\n\nKirim pesan yang mau di-broadcast ke semua user.\n\nBisa text, foto, atau format panjang.\n\nKetik pesan sekarang:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_admin")]]),
            parse_mode="Markdown"
        )

    elif data == "admin_cari_user":
        context.user_data["mode"] = "admin_cari_user"
        await query.edit_message_text(
            "🔍 **CARI USER**\n\nKetik username atau ID yang mau dicari:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]),
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = context.user_data.get("mode")
    text = update.message.text or ""

    # ===== DATA SAYA MODES - BARU =====
    if mode == "data_saya_manual":
        parsed = parse_jmo_block(text, f"DATA-{user_id}")
        if not parsed:
            await update.message.reply_text("❌ Minimal 13 baris! Contoh:\nDEPOK\nCILODONG\nKALIBARU\n10.000.000\nPEREMPUAN 1992\n2019\n23****\n01-07-2022\nINDONESIA MERDEKA\n320123...\n190003...\nLIA\n12-12-1990", reply_markup=main_menu_keyboard(user_id))
            return
        try:
            template, _, _, _, _ = get_setting(user_id)
        except:
            template = DEFAULT_TEMPLATE
        disp_format, disp_full = build_display(parsed, template, "atas")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""INSERT INTO data_saya (user_id, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir, raw_text, display_text, created_at) 
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (user_id, parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"],
                   parsed.get("NIK_LENGKAP",""), parsed.get("KPJ_LENGKAP",""), parsed.get("NAMA_LENGKAP",""), parsed.get("TGL_LAHIR",""),
                   text, disp_full, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ DATA SAYA disimpan!\n\n{disp_full}", reply_markup=main_menu_keyboard(user_id))
        return

    if mode == "edit_data_saya":
        rid = context.user_data.get("edit_data_id")
        parsed = parse_jmo_block(text, f"DATA-{user_id}")
        if not parsed:
            await update.message.reply_text("❌ Minimal 13 baris!")
            return
        try:
            template, _, _, _, _ = get_setting(user_id)
        except:
            template = DEFAULT_TEMPLATE
        disp_format, disp_full = build_display(parsed, template, "atas")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""UPDATE data_saya SET kab=?, kec=?, kel=?, saldo=?, kelamin=?, kpj=?, sensor=?, it=?, pt=?, nik_lengkap=?, kpj_lengkap=?, nama_lengkap=?, tgl_lahir=?, raw_text=?, display_text=? WHERE id=? AND user_id=?""",
                  (parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"],
                   parsed.get("NIK_LENGKAP",""), parsed.get("KPJ_LENGKAP",""), parsed.get("NAMA_LENGKAP",""), parsed.get("TGL_LAHIR",""),
                   text, disp_full, rid, user_id))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        context.user_data["edit_data_id"] = None
        await update.message.reply_text(f"✅ DATA SAYA ID {rid} diupdate!\n\n{disp_full}", reply_markup=main_menu_keyboard(user_id))
        return

    if mode == "cari_data_saya":
        keyword = text.strip()
        like = f"%{keyword}%"
        like_upper = f"%{keyword.upper()}%"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT id, display_text FROM data_saya 
                     WHERE user_id=? AND (kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR saldo LIKE ? OR kelamin LIKE ? OR kpj LIKE ? OR pt LIKE ? OR nik_lengkap LIKE ? OR kpj_lengkap LIKE ? OR nama_lengkap LIKE ? OR tgl_lahir LIKE ? OR display_text LIKE ? OR display_text LIKE ?)
                     ORDER BY id ASC""",
                  (user_id, like, like, like, like, like, like, like, like, like, like, like, like, like_upper))
        rows = c.fetchall()
        conn.close()
        context.user_data["mode"] = None
        if not rows:
            await update.message.reply_text(f"🔍 Tidak ada DATA SAYA untuk '{keyword}'", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_hasil_data_saya")]]))
            return
        await update.message.reply_text(f"🔍 Ditemukan {len(rows)} DATA SAYA untuk '{keyword}':")
        for rid, disp in rows[:20]:
            try:
                await context.bot.send_message(chat_id=user_id, text=f"ID {rid}\n```\n{disp[:3000]}\n```", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_data_{rid}")]]))
            except:
                await context.bot.send_message(chat_id=user_id, text=f"ID {rid} - {disp[:500]}")
        return


    # ===== TOPUP MODES =====
    if mode == "topup_bukti":
        await update.message.reply_text("📸 Silahkan kirim FOTO bukti transfer, bukan teks.\nJika sudah transfer, kirim fotonya di sini.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
        return

    # ===== ADMIN MODES =====
    if mode and mode.startswith("admin_addsub_"):
        if not is_admin_user(user_id):
            await update.message.reply_text("⛔ Bukan admin")
            return
        target_id = int(mode.split("_")[-1])
        paket_key = text.lower().strip()
        if paket_key in ["3bulan","3","3 bulan"]:
            paket_key = "3bulan"
        elif paket_key in ["6bulan","6","6 bulan"]:
            paket_key = "6bulan"
        elif paket_key in ["1tahun","1 tahun","12bulan","1th","setahun"]:
            paket_key = "1tahun"
        elif paket_key in ["unlimited","unli","selamanya"]:
            paket_key = "unlimited"
        if paket_key not in PACKAGES:
            await update.message.reply_text("❌ Paket tidak valid. Ketik: 3bulan, 6bulan, 1tahun, unlimited")
            return
        pkg = PACKAGES[paket_key]
        from datetime import datetime, timedelta
        tgl_mulai = datetime.now()
        tgl_expired = tgl_mulai + timedelta(days=pkg['durasi']) if pkg['durasi'] < 10000 else datetime(2099,12,31)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO subscriptions (user_id, paket, harga, durasi_hari, tgl_mulai, tgl_expired, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                  (target_id, pkg['label'], pkg['harga'], pkg['durasi'], tgl_mulai.isoformat(), tgl_expired.isoformat(), 'active', datetime.now().isoformat()))
        c.execute("UPDATE users SET expired=? WHERE user_id=?", (tgl_expired.strftime("%d-%m-%Y") if pkg['durasi'] < 10000 else "UNLIMITED", target_id))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ Langganan {pkg['label']} untuk user {target_id} berhasil ditambahkan! Exp: {tgl_expired.strftime('%d-%m-%Y') if pkg['durasi'] < 10000 else 'UNLIMITED'}", reply_markup=main_menu_keyboard(user_id))
        try:
            await context.bot.send_message(chat_id=target_id, text=f"✅ Langganan {pkg['label']} aktif! Exp: {tgl_expired.strftime('%d-%m-%Y') if pkg['durasi'] < 10000 else 'UNLIMITED'} - Sekarang bisa pakai BUAT FORMAT & DATA SAYA")
        except:
            pass
        return

    if mode == "admin_hapus_user":
        try:
            target_id = int(re.search(r"\d+", text).group())
        except:
            await update.message.reply_text("❌ ID tidak valid. Contoh: 123456789")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE user_id=?", (target_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            await update.message.reply_text(f"❌ User {target_id} tidak ditemukan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
            return
        # hapus semua data user
        c.execute("DELETE FROM hasil_format WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM history WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM settings WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM users WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ User {target_id} (@{row[0] or '-'}) berhasil dihapus semua datanya.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        return

    if mode == "admin_tambah_admin":
        try:
            target_id = int(re.search(r"\d+", text).group())
        except:
            await update.message.reply_text("❌ ID tidak valid. Contoh: 123456789")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (target_id,))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ {target_id} sekarang jadi admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        return

    if mode == "admin_broadcast":
        broadcast_msg = text
        if not broadcast_msg.strip():
            await update.message.reply_text("❌ Pesan kosong.")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        all_users = c.fetchall()
        conn.close()
        sent = 0
        failed = 0
        await update.message.reply_text(f"📢 Broadcasting ke {len(all_users)} user...")
        for (uid,) in all_users:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 **BROADCAST ADMIN**\n\n{broadcast_msg}", parse_mode="Markdown")
                sent += 1
            except:
                failed += 1
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ Broadcast selesai.\nTerkirim: {sent}\nGagal: {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        return

    if mode == "admin_cari_user":
        keyword = text.strip()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, username, total_format FROM users WHERE CAST(user_id AS TEXT) LIKE ? OR username LIKE ? ORDER BY total_format DESC LIMIT 20", (f"%{keyword}%", f"%{keyword}%"))
        rows = c.fetchall()
        conn.close()
        context.user_data["mode"] = None
        if not rows:
            await update.message.reply_text(f"❌ Tidak ada user dengan kata kunci '{keyword}'", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
            return
        msg = f"🔍 Hasil cari '{keyword}' ({len(rows)}):\n\n"
        for uid, uname, total in rows:
            msg += f"ID:{uid} @{uname or '-'} - {total} format\n"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        return
    
    if mode == "set_template":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE settings SET template=? WHERE user_id=?", (text, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO settings (user_id, template, kode_atas, kode_prefix, kode_pos) VALUES (?, ?, ?, ?, ?)", (user_id, text, "0000001", "MGB", "atas"))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text("Template disimpan", reply_markup=main_menu_keyboard(user_id))
        return

    if mode in ["set_kode", "set_kode_atas", "set_kode_bawah"]:
        raw = text.strip()
        m = re.search(r"(\d+)", raw)
        num = m.group(1) if m else "001"
        prefix = re.sub(r"\d+", "", raw)
        prefix = prefix.replace("-", " ").strip()
        prefix = re.sub(r"\s+", " ", prefix)
        if not prefix:
            prefix = "MGB"
        kode_pos = context.user_data.get("kode_pos", "atas")
        if mode == "set_kode_bawah":
            kode_pos = "bawah"
        elif mode == "set_kode_atas":
            kode_pos = "atas"
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # FIX AS - 001 harus mulai dari 001 lagi, bukan 002
        conn2 = sqlite3.connect(DB_PATH)
        c2 = conn2.cursor()
        c2.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
        current_count = c2.fetchone()[0]
        conn2.close()
        c.execute("UPDATE settings SET kode_atas=?, kode_prefix=?, kode_pos=?, kode_base_count=? WHERE user_id=?", (num, prefix, kode_pos, current_count, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO settings (user_id, template, kode_atas, kode_prefix, kode_pos, kode_base_count) VALUES (?, ?, ?, ?, ?, ?)", (user_id, DEFAULT_TEMPLATE, num, prefix, kode_pos, current_count))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        context.user_data["kode_pos"] = None
        
        kode_aktif = f"{prefix} {int(num):03d}" if num.isdigit() and len(num) <= 4 else f"{prefix}  {num}"
        if len(num) > 3 and "  " not in kode_aktif:
            kode_aktif = f"{prefix}  {num}"
        
        if kode_pos == "bawah":
            preview_box = f"   [FORMAT KAMU]             \n━━━━━━━━━━━━━━━━━━━\n{prefix} - {num}"
            msg = (
                f"✅ KODE DISIMPAN\n\n"
                f"Kode aktif: {kode_aktif}\n\n"
                f"Format selanjutnya akan otomatis jadi:\n"
                f"```\n{preview_box}\n```\n\n"
                f"Dan berikutnya otomatis berurutan tanpa\n"
                f"duplikat. Posisi kode selalu di TENGAH."
            )
        else:
            preview_box = f"     {kode_aktif}\n--------------------------\n[FORMAT  KAMU]"
            msg = (
                f"✅ KODE DISIMPAN\n\n"
                f"Kode aktif: {kode_aktif}\n\n"
                f"Format selanjutnya akan otomatis jadi:\n"
                f"```\n{preview_box}\n```\n\n"
                f"Dan berikutnya otomatis berurutan tanpa\n"
                f"duplikat. Posisi kode selalu di TENGAH."
            )
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ LIHAT SETTING", callback_data="setting_template_view")],
            [InlineKeyboardButton("⌨️ BUAT FORMAT", callback_data="menu_buat")],
            [InlineKeyboardButton("⬅️ MENU UTAMA", callback_data="back_main")]
        ])
        try:
            await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
        except:
            await update.message.reply_text(f"KODE DISIMPAN\nKode aktif: {kode_aktif} ({kode_pos})", reply_markup=main_menu_keyboard(user_id))
        return

    if mode in ("set_kode_atas", "set_kode_bawah"):
        # MODE SET KODE ATAS/BAWAH - FIX AGAR SESUAI PILIHAN
        kode_pos = "atas" if mode == "set_kode_atas" else "bawah"
        raw = text.strip()
        # parse prefix and number: MGB - 001 or MGB 001
        m = re.search(r"([A-Za-z]+)[\s\-]*([0-9]+)", raw)
        if m:
            prefix = m.group(1).upper()
            num = m.group(2)
        else:
            # fallback: whole text as prefix, number 1
            prefix = re.sub(r"[^A-Za-z]", "", raw).upper() or "MGB"
            num = re.search(r"\d+", raw)
            num = num.group() if num else "1"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # FIX AS - 001 harus mulai dari 001 lagi, bukan 002
        conn2 = sqlite3.connect(DB_PATH)
        c2 = conn2.cursor()
        c2.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
        current_count = c2.fetchone()[0]
        conn2.close()
        c.execute("UPDATE settings SET kode_atas=?, kode_prefix=?, kode_pos=?, kode_base_count=? WHERE user_id=?", (num, prefix, kode_pos, current_count, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO settings (user_id, template, kode_atas, kode_prefix, kode_pos, kode_base_count) VALUES (?, ?, ?, ?, ?, ?)", (user_id, DEFAULT_TEMPLATE, num, prefix, kode_pos, current_count))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        context.user_data["kode_pos"] = None
        kode_aktif = f"{prefix} {int(num):0{len(num)}d}" if num.isdigit() else f"{prefix} {num}"
        pos_label = "ATAS" if kode_pos=="atas" else "BAWAH"
        if kode_pos == "bawah":
            preview = f"[FORMAT KAMU]\n━━━━━━━━━━━━━━━━━━━\n     {kode_aktif}"
        else:
            preview = f"     {kode_aktif}\n━━━━━━━━━━━━━━━━━━━\n[FORMAT KAMU]"
        msg = (
            f"✅ KODE {pos_label} DISIMPAN\n\n"
            f"Kode aktif: {kode_aktif}\n"
            f"Posisi: {pos_label} ✅ Sesuai pilihan\n\n"
            f"Preview:\n```\n{preview}\n```\n\n"
            f"Selanjutnya format akan pakai kode {pos_label} otomatis urut."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ LIHAT SETTING", callback_data="setting_template_view")],
            [InlineKeyboardButton("⬅️ MENU UTAMA", callback_data="back_main")]
        ])
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
        return

    if mode == "edit_format":
        rid = context.user_data.get("edit_id")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT kode FROM hasil_format WHERE id=?", (rid,))
        row = c.fetchone()
        kode = row[0] if row else get_next_code(user_id)
        conn.close()
        parsed = parse_jmo_block(text, kode)
        if not parsed:
            await update.message.reply_text("Minimal 9 baris", reply_markup=main_menu_keyboard(user_id))
            return
        _, _, _, kode_pos, _ = get_setting(user_id)
        user_template, _, _, _, _ = get_setting(user_id)
        disp_format, disp_full = build_display(parsed, user_template, kode_pos)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""UPDATE hasil_format SET kab=?, kec=?, kel=?, saldo=?, kelamin=?, kpj=?, sensor=?, it=?, pt=?, akun=?, display_format=?, display_full=? WHERE id=? AND user_id=?""",
                  (parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"], parsed.get("NIK_LENGKAP",""), parsed.get("KPJ_LENGKAP",""), parsed.get("NAMA_LENGKAP",""), parsed.get("TGL_LAHIR",""), parsed["AKUN"], disp_format, disp_full, rid, user_id))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text(f"ID {rid} diedit\n{disp_format}", reply_markup=main_menu_keyboard(user_id))
        return

    if mode and mode.startswith("cari"):
        keyword = text.strip()
        keyword_upper = keyword.upper()
        # FIX CARI: AS 001 harus ketemu AS 0000001, AS 1, AS 0000001 dll
        search_prefix = "".join(re.findall(r"[A-Z]+", keyword_upper))
        num_match = re.search(r"\d+", keyword)
        likes_code_patterns = []
        if search_prefix and num_match:
            try:
                num_val = int(num_match.group())
                padded7 = f"{num_val:07d}"
                padded3 = f"{num_val:03d}"
                likes_code_patterns = [
                    f"%{search_prefix}%{padded7}%",
                    f"%{search_prefix} %{padded7}%",
                    f"%{search_prefix}  {padded7}%",
                    f"%{search_prefix}%{padded3}%",
                    f"%{search_prefix} {num_match.group()}%",
                    f"%{search_prefix}%{num_val}%",
                ]
            except:
                likes_code_patterns = [f"%{keyword}%", f"%{keyword_upper}%"]
        else:
            likes_code_patterns = [f"%{keyword}%", f"%{keyword_upper}%", f"%{keyword_upper}%"]

        like = f"%{keyword}%"
        like_upper = f"%{keyword_upper}%"

        if "history" in mode:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            kode_conds = " OR ".join(["kode LIKE ?" for _ in likes_code_patterns])
            sql = f"""SELECT id, display_full, kode FROM hasil_format 
                         WHERE user_id=? AND status='terjual' 
                         AND (({kode_conds}) OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_full LIKE ? OR nik_lengkap LIKE ? OR nama_lengkap LIKE ?)
                         ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC"""
            params = [user_id] + likes_code_patterns + [like, like, like, like, like, like, like, like]
            c.execute(sql, tuple(params))
            rows = c.fetchall()
            conn.close()
            context.user_data["mode"] = None
            if not rows:
                await update.message.reply_text(f"🔍 Tidak ada hasil terjual untuk '{keyword}'\nCoba cari: AS 001, AS 1, atau nama KAB dll.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
                return
            await update.message.reply_text(f"🔍 Ditemukan {len(rows)} hasil untuk '{keyword}' (terjual, urut kecil→besar):")
            for rid, disp_full, kode in rows:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT created_at FROM history WHERE user_id=? AND aksi='JUAL' AND detail LIKE ? ORDER BY id DESC LIMIT 1", (user_id, f"%ID {rid}%"))
                hrow = c.fetchone()
                conn.close()
                waktu = hrow[0][:19].replace("T", " ") if hrow and hrow[0] else "-"
                text_out = f"ID {rid} | {kode} | {waktu}\n```\n{disp_full}\n```"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 CARI", callback_data=f"cari_history_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"pulihkan_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]
                ])
                try:
                    await context.bot.send_message(chat_id=user_id, text=text_out, reply_markup=kb, parse_mode="Markdown")
                except:
                    await context.bot.send_message(chat_id=user_id, text=f"ID {rid} {kode}", reply_markup=kb)
            return
        else:
            # Pencarian untuk HASIL FORMAT & FORMAT+AKUN yang READY
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            kode_conds = " OR ".join(["kode LIKE ?" for _ in likes_code_patterns])
            # Cek apakah mode cari_akun (format+akun) atau cari_format
            is_cari_akun = "akun" in mode
            if is_cari_akun:
                sql = f"""SELECT id, display_full, kode FROM hasil_format 
                             WHERE user_id=? AND status='ready' 
                             AND (({kode_conds}) OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_full LIKE ? OR nik_lengkap LIKE ? OR kpj_lengkap LIKE ? OR nama_lengkap LIKE ? OR tgl_lahir LIKE ?)
                             ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC"""
                params = [user_id] + likes_code_patterns + [like, like, like, like, like, like, like, like, like, like]
            else:
                sql = f"""SELECT id, display_format, kode, display_full FROM hasil_format 
                             WHERE user_id=? AND status='ready' 
                             AND (({kode_conds}) OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_format LIKE ? OR display_full LIKE ?)
                             ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC"""
                params = [user_id] + likes_code_patterns + [like, like, like, like, like, like, like]
            c.execute(sql, tuple(params))
            rows = c.fetchall()
            conn.close()
            context.user_data["mode"] = None
            if not rows:
                await update.message.reply_text(f"🔍 Tidak ada hasil untuk '{keyword}'\nCoba ketik: AS 001, AS 1, Bandung, dll.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
                return
            await update.message.reply_text(f"🔍 Ditemukan {len(rows)} hasil untuk '{keyword}' (urut kecil→besar):")
            for row in rows:
                if is_cari_akun:
                    rid, disp_full, kode = row
                    text_out = f"{kode} (ID {rid})\n```\n{disp_full}\n```"
                    try:
                        from telegram import CopyTextButton
                        jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp_full))
                    except:
                        jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
                    kb = InlineKeyboardMarkup([[jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]])
                else:
                    rid, disp, kode, disp_full = row
                    text_out = f"{kode} (ID {rid})\n```\n{disp}\n```"
                    try:
                        from telegram import CopyTextButton
                        jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp))
                    except:
                        jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
                    kb = InlineKeyboardMarkup([[jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]])
                try:
                    await context.bot.send_message(chat_id=user_id, text=text_out, reply_markup=kb, parse_mode="Markdown")
                except:
                    await context.bot.send_message(chat_id=user_id, text=f"{kode} ID {rid}", reply_markup=kb)
            return

    if mode in ("set_kode_atas", "set_kode_bawah"):
        # MODE SET KODE ATAS/BAWAH - FIX AGAR SESUAI PILIHAN
        kode_pos = "atas" if mode == "set_kode_atas" else "bawah"
        raw = text.strip()
        # parse prefix and number: MGB - 001 or MGB 001
        m = re.search(r"([A-Za-z]+)[\s\-]*([0-9]+)", raw)
        if m:
            prefix = m.group(1).upper()
            num = m.group(2)
        else:
            # fallback: whole text as prefix, number 1
            prefix = re.sub(r"[^A-Za-z]", "", raw).upper() or "MGB"
            num = re.search(r"\d+", raw)
            num = num.group() if num else "1"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # FIX AS - 001 harus mulai dari 001 lagi, bukan 002
        conn2 = sqlite3.connect(DB_PATH)
        c2 = conn2.cursor()
        c2.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
        current_count = c2.fetchone()[0]
        conn2.close()
        c.execute("UPDATE settings SET kode_atas=?, kode_prefix=?, kode_pos=?, kode_base_count=? WHERE user_id=?", (num, prefix, kode_pos, current_count, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO settings (user_id, template, kode_atas, kode_prefix, kode_pos, kode_base_count) VALUES (?, ?, ?, ?, ?, ?)", (user_id, DEFAULT_TEMPLATE, num, prefix, kode_pos, current_count))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        context.user_data["kode_pos"] = None
        kode_aktif = f"{prefix} {int(num):0{len(num)}d}" if num.isdigit() else f"{prefix} {num}"
        pos_label = "ATAS" if kode_pos=="atas" else "BAWAH"
        if kode_pos == "bawah":
            preview = f"[FORMAT KAMU]\n━━━━━━━━━━━━━━━━━━━\n     {kode_aktif}"
        else:
            preview = f"     {kode_aktif}\n━━━━━━━━━━━━━━━━━━━\n[FORMAT KAMU]"
        msg = (
            f"✅ KODE {pos_label} DISIMPAN\n\n"
            f"Kode aktif: {kode_aktif}\n"
            f"Posisi: {pos_label} ✅ Sesuai pilihan\n\n"
            f"Preview:\n```\n{preview}\n```\n\n"
            f"Selanjutnya format akan pakai kode {pos_label} otomatis urut."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ LIHAT SETTING", callback_data="setting_template_view")],
            [InlineKeyboardButton("⬅️ MENU UTAMA", callback_data="back_main")]
        ])
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
        return

    if mode == "edit_format":
        rid = context.user_data.get("edit_id")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT kode FROM hasil_format WHERE id=?", (rid,))
        row = c.fetchone()
        kode = row[0] if row else get_next_code(user_id)
        conn.close()
        parsed = parse_jmo_block(text, kode)
        if not parsed:
            await update.message.reply_text("Minimal 9 baris", reply_markup=main_menu_keyboard(user_id))
            return
        _, _, _, kode_pos, _ = get_setting(user_id)
        user_template, _, _, _, _ = get_setting(user_id)
        disp_format, disp_full = build_display(parsed, user_template, kode_pos)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""UPDATE hasil_format SET kab=?, kec=?, kel=?, saldo=?, kelamin=?, kpj=?, sensor=?, it=?, pt=?, akun=?, display_format=?, display_full=? WHERE id=? AND user_id=?""",
                  (parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"], parsed.get("NIK_LENGKAP",""), parsed.get("KPJ_LENGKAP",""), parsed.get("NAMA_LENGKAP",""), parsed.get("TGL_LAHIR",""), parsed["AKUN"], disp_format, disp_full, rid, user_id))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text(f"ID {rid} diedit\n{disp_format}", reply_markup=main_menu_keyboard(user_id))
        return

    if mode and mode.startswith("cari"):
        keyword = text.strip()
        keyword_upper = keyword.upper()
        # FIX CARI: AS 001 harus ketemu AS 0000001
        # Extract prefix and number from keyword
        search_prefix = "".join(re.findall(r"[A-Z]+", keyword_upper))
        num_match = re.search(r"\d+", keyword)
        likes = []
        params = []
        # Build flexible LIKE patterns
        base_like = f"%{keyword}%"
        base_like_upper = f"%{keyword_upper}%"
        # Normalisasi kode: AS 001, AS 1, AS 0000001 semua harus ketemu AS 0000001
        if search_prefix and num_match:
            try:
                num_val = int(num_match.group())
                padded7 = f"{num_val:07d}"
                padded3 = f"{num_val:03d}"
                # berbagai format kode yang mungkin
                likes_code_patterns = [
                    f"%{search_prefix}%{padded7}%",
                    f"%{search_prefix} %{padded7}%",
                    f"%{search_prefix}  {padded7}%",
                    f"%{search_prefix}%{padded3}%",
                    f"%{search_prefix} {num_match.group()}%",
                    f"%{search_prefix}%{num_val}%",
                ]
            except:
                likes_code_patterns = [base_like, base_like_upper]
        else:
            likes_code_patterns = [base_like, base_like_upper, f"%{keyword_upper}%"]

        like = base_like
        if "history" in mode:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            # Build flexible search for kode
            kode_conditions = " OR ".join(["kode LIKE ?" for _ in likes_code_patterns])
            # total params: user_id + kode patterns + other fields
            query_sql = f"""SELECT id, display_full, kode FROM hasil_format 
                         WHERE user_id=? AND status='terjual' 
                         AND (({kode_conditions}) OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_full LIKE ? OR display_full LIKE ?)
                         ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC"""
            # params: user_id, kode patterns, then 6 other likes
            other_like = f"%{keyword}%"
            params_history = [user_id] + likes_code_patterns + [other_like, other_like, other_like, other_like, other_like, other_like, other_like]
            c.execute(query_sql, tuple(params_history))
            rows = c.fetchall()
            conn.close()
            context.user_data["mode"] = None
            if not rows:
                await update.message.reply_text(f"🔍 Tidak ada hasil terjual untuk '{keyword}'\nCoba cari dengan kode (ASD 001), nama, KAB, KEC, dll.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
                return
            await update.message.reply_text(f"🔍 Ditemukan {len(rows)} hasil untuk '{keyword}' (terjual, urut kecil→besar):")
            for rid, disp_full, kode in rows:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT created_at FROM history WHERE user_id=? AND aksi='JUAL' AND detail LIKE ? ORDER BY id DESC LIMIT 1", (user_id, f"%ID {rid}%"))
                hrow = c.fetchone()
                conn.close()
                waktu = hrow[0][:19].replace("T", " ") if hrow and hrow[0] else "-"
                text_out = f"ID {rid} | {kode} | {waktu}\n```\n{disp_full}\n```"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 CARI", callback_data=f"cari_history_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"pulihkan_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]
                ])
                try:
                    await context.bot.send_message(chat_id=user_id, text=text_out, reply_markup=kb, parse_mode="Markdown")
                except:
                    await context.bot.send_message(chat_id=user_id, text=f"ID {rid} {kode}", reply_markup=kb)
            return
        else:
            # Pencarian untuk HASIL FORMAT & FORMAT+AKUN - bisa cari kode, nama, KAB, dll
            is_akun_search = "akun" in mode.lower()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            # Cari di semua kolom: kode, kab, kec, kel, saldo, kelamin, kpj, pt, akun, display_full
            c.execute("""SELECT id, display_full, kode, display_format FROM hasil_format 
                         WHERE user_id=? AND status='ready'
                         AND (kode LIKE ? OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR saldo LIKE ? OR kelamin LIKE ? OR kpj LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_full LIKE ?)
                         ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC""",
                      (user_id, like, like, like, like, like, like, like, like, like, like))
            rows = c.fetchall()
            conn.close()
            context.user_data["mode"] = None
            if not rows:
                await update.message.reply_text(f"🔍 Tidak ada hasil untuk '{keyword}'\nCoba cari dengan:\n- Kode: ASD 001\n- Nama: RIO\n- KAB: JAKARTA\n- KEC, KEL, dll.", reply_markup=main_menu_keyboard(user_id))
                return
            
            await update.message.reply_text(f"🔍 Ditemukan {len(rows)} hasil untuk '{keyword}'\nUrutan terkecil→terbesar:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 CARI LAGI", callback_data="cari_format" if not is_akun_search else "cari_akun")]]))
            
            for rid, disp_full, kode, disp_format in rows:
                disp = disp_full if is_akun_search else disp_format
                try:
                    kode_num = int(re.search(r"(\d+)", kode).group())
                except:
                    kode_num = rid
                header = f"{kode} (ID {kode_num})"
                text_out = f"{header}\n```\n{disp}\n```"
                try:
                    from telegram import CopyTextButton
                    jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp))
                except:
                    jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
                kb = InlineKeyboardMarkup([[jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]])
                try:
                    await context.bot.send_message(chat_id=user_id, text=text_out, reply_markup=kb, parse_mode="Markdown")
                except:
                    await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp}", reply_markup=kb)
            return

    # Cek apakah ini mode manual buat format (tanpa mode khusus atau mode manual)
    is_manual_format = context.user_data.get("mode") == "manual" or (context.user_data.get("mode") is None and len([l for l in text.splitlines() if l.strip()!=""]) >= 9)
    if is_manual_format and not has_access(user_id):
        await update.message.reply_text("🔒 **MENU TERKUNCI**\n\nBUAT FORMAT hanya untuk member berlangganan.\nSilahkan pilih paket:", reply_markup=paket_menu_keyboard(), parse_mode="Markdown")
        context.user_data["mode"] = None
        return

    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()!=""]
    if not blocks:
        blocks = [text]
    saved = 0
    last_id = None
    last_kode = ""
    for block in blocks:
        if len([l for l in block.splitlines() if l.strip()!=""]) < 9:
            continue
        kode = get_next_code(user_id)
        parsed = parse_jmo_block(block, kode)
        if not parsed:
            continue
        _, _, _, kode_pos, _ = get_setting(user_id)
        user_template, _, _, _, _ = get_setting(user_id)
        disp_format, disp_full = build_display(parsed, user_template, kode_pos)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""INSERT INTO hasil_format (user_id, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir, akun, display_format, display_full, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (user_id, kode, parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"], parsed.get("NIK_LENGKAP",""), parsed.get("KPJ_LENGKAP",""), parsed.get("NAMA_LENGKAP",""), parsed.get("TGL_LAHIR",""), parsed["AKUN"], disp_format, disp_full, datetime.now().isoformat()))
        last_id = c.lastrowid
        last_kode = kode
        c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "BUAT FORMAT", kode, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        saved += 1
        await update.message.reply_text(f"```\n{disp_format}\n```", parse_mode="Markdown")
    if saved > 0:
        # BARU: jangan langsung ke menu utama, kasih opsi BUAT LAGI / EDIT / HAPUS / KEMBALI
        if saved == 1 and last_id:
            kb_after = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ 1. BUAT LAGI", callback_data="buat_manual")],
                [InlineKeyboardButton("✏️ 2. EDIT", callback_data=f"edit_{last_id}"), InlineKeyboardButton("🗑️ 3. HAPUS", callback_data=f"del_{last_id}")],
                [InlineKeyboardButton("⬅️ 4. KEMBALI", callback_data="back_main")]
            ])
            await update.message.reply_text(f"✅ {saved} format tersimpan - {last_kode}\nMau apa selanjutnya?", reply_markup=kb_after)
        else:
            kb_after = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ BUAT LAGI", callback_data="buat_manual")],
                [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
            ])
            await update.message.reply_text(f"✅ {saved} format tersimpan", reply_markup=kb_after)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = context.user_data.get("mode", "")
    # ===== DATA SAYA EXCEL - SIMPAN DATA MENTAH (BUKAN FORMAT JMO) =====
    if mode == "data_saya_excel":
        try:
            file = await update.message.document.get_file()
            tmp = f"/tmp/data_saya_{user_id}.xlsx"
            await file.download_to_drive(tmp)
            import pandas as pd
            saved=0
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            # Support .xlsx and .csv
            try:
                if tmp.endswith(".csv"):
                    df = pd.read_csv(tmp)
                else:
                    df = pd.read_excel(tmp)
            except Exception as e:
                await update.message.reply_text(f"❌ Gagal baca file: {e}", reply_markup=main_menu_keyboard(user_id))
                context.user_data["mode"]=None
                return
            # Ambil setting kode
            try:
                _, _, _, kode_pos, _ = get_setting(user_id)
            except:
                kode_pos = "atas"
            for _, row in df.iterrows():
                try:
                    vals = []
                    for v in row:
                        sv = str(v).strip()
                        if sv and sv.lower()!="nan":
                            vals.append(sv)
                    if not vals:
                        continue
                    raw_text = " | ".join(vals) if len(vals)>1 else vals[0]
                    kode = get_next_code(user_id)
                    if kode_pos == "bawah":
                        display_text = f"{raw_text}\n━━━━━━━━━━━━━━━━━━━\n     {kode}"
                    else:
                        display_text = f"{kode}\n━━━━━━━━━━━━━━━━━━━\n{raw_text}"
                    kab = vals[0] if len(vals)>0 else ""
                    kec = vals[1] if len(vals)>1 else ""
                    kel = vals[2] if len(vals)>2 else ""
                    try:
                        c.execute("INSERT INTO data_saya (user_id, kode, kab, kec, kel, raw_text, display_text, created_at) VALUES (?,?,?,?,?,?,?,?)",
                                  (user_id, kode, kab, kec, kel, raw_text, display_text, datetime.now().isoformat()))
                    except:
                        c.execute("INSERT INTO data_saya (user_id, kab, kec, kel, raw_text, display_text, created_at) VALUES (?,?,?,?,?,?)",
                                  (user_id, kab, kec, kel, raw_text, display_text, datetime.now().isoformat()))
                    saved+=1
                except Exception as e:
                    print(f"row error {e}")
                    continue
            conn.commit()
            conn.close()
            context.user_data["mode"]=None
            await update.message.reply_text(
                f"✅ {saved} data dari Excel berhasil disimpan ke HASIL DATA SAYA!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 LIHAT HASIL DATA SAYA", callback_data="menu_hasil_data_saya")],
                    [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
                ])
            )
            try:
                os.remove(tmp)
            except:
                pass
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Gagal proses Excel: {e}", reply_markup=main_menu_keyboard(user_id))
            context.user_data["mode"]=None
            return


            await update.message.reply_text(f"✅ DATA SAYA Excel masuk {saved} data!", reply_markup=main_menu_keyboard(user_id))
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Gagal baca Excel DATA SAYA: {e}", reply_markup=main_menu_keyboard(user_id))
            context.user_data["mode"]=None
            return

    # lanjut ke handler lama - buat_excel dll

    user_id = update.effective_user.id
    doc_name = update.message.document.file_name or ""
    if not doc_name.lower().endswith((".xlsx", ".xls")):
        await update.message.reply_text("File harus .xlsx", reply_markup=main_menu_keyboard(user_id))
        return
    file = await update.message.document.get_file()
    path = f"/tmp/{user_id}_{doc_name}"
    await file.download_to_drive(path)
    await update.message.reply_text(f"Memproses {doc_name}...")
    try:
        try:
            df = pd.read_excel(path, header=None, dtype=str)
        except:
            df = pd.read_excel(path, dtype=str)
        first_row = [str(x).upper() for x in df.iloc[0].tolist()]
        if "KAB" in first_row:
            df = df.iloc[1:]
        saved = 0
        for _, row in df.iterrows():
            vals = [str(v).strip() if pd.notna(v) and str(v).strip().lower() != "nan" else "" for v in row.tolist()]
            if len([v for v in vals if v]) < 9:
                continue
            while len(vals) < 13:
                vals.append("")
            block_text = "\n".join(vals[:13])
            kode = get_next_code(user_id)
            parsed = parse_jmo_block(block_text, kode)
            if not parsed:
                continue
            _, _, _, kode_pos, _ = get_setting(user_id)
            user_template, _, _, _, _ = get_setting(user_id)
            disp_format, disp_full = build_display(parsed, user_template, kode_pos)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""INSERT INTO hasil_format (user_id, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir, akun, display_format, display_full, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (user_id, kode, parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"], parsed.get("NIK_LENGKAP",""), parsed.get("KPJ_LENGKAP",""), parsed.get("NAMA_LENGKAP",""), parsed.get("TGL_LAHIR",""), parsed["AKUN"], disp_format, disp_full, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            saved += 1
        await update.message.reply_text(f"✅ {saved} data masuk", reply_markup=main_menu_keyboard(user_id))
    except Exception as e:
        await update.message.reply_text(f"Gagal: {e}", reply_markup=main_menu_keyboard(user_id))
    finally:
        try:
            os.remove(path)
        except:
            pass


# ===== COMMAND HANDLER TAMBAHAN =====
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user = update.effective_user
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user.id, user.username or ""))
    conn.commit()
    conn.close()
    welcome_text = (
        "🟢 MODE ON DI AKTIFKAN\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Selamat datang, {user.first_name}! Gimana kabarnya nih, saya berharap kabar baik-baik saja yah, tetap semangat dan jangan lupa bersyukur. Silahkan pilih menu di bawah ini : 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(user_id))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 **BANTUAN BOT SAHABAT JHT**\n\n"
        "🟢 MODE ON - Bot siap dipakai\n\n"
        "📌 **Command yang bisa diklik:**\n"
        "/start - Mulai bot & tampilkan menu utama\n"
        "/menu - Tampilkan menu utama\n"
        "/help - Bantuan\n"
        "/profil - Cek profil\n"
        "/buat - Buat format\n"
        "/hasil - Hasil format\n"
        "/setting - Setting template & kode\n"
        "/history - History jual\n"
        "/admin - Panel admin (khusus admin)\n\n"
        "👇 Klik command di atas atau pilih menu di bawah:"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

async def profil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user = update.effective_user
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, saldo, expired, nama FROM users WHERE user_id=?", (user.id,))
    urow = c.fetchone()
    try:
        c.execute("SELECT user_id FROM admins")
        admin_rows = c.fetchall()
        admin_ids_db = [r[0] for r in admin_rows]
    except:
        admin_ids_db = []
    conn.close()
    all_admins = list(set(ADMIN_IDS + admin_ids_db))
    is_admin = user.id in all_admins
    username_db = urow[0] if urow and urow[0] else user.username or ""
    saldo_db = urow[1] if urow and urow[1] else "0"
    expired_db = urow[2] if urow and urow[2] else "UNLIMITED"
    nama_db = urow[3] if urow and len(urow) > 3 and urow[3] else user.first_name or "SAHABAT"
    
    # Cek langganan aktif dari tabel subscriptions
    has_sub, exp_date, paket_name = get_user_subscription(user.id)
    
    if is_admin:
        paket_display = "ADMIN (UNLIMITED)"
        expired_display = "UNLIMITED"
        status_display = "🟢 AKTIF - ADMIN"
    elif has_sub:
        paket_display = paket_name or "Aktif"
        if exp_date == "UNLIMITED" or (paket_name and "UNLIMITED" in str(paket_name).upper()):
            expired_display = "UNLIMITED ♾️"
        else:
            try:
                from datetime import datetime
                if "T" in str(exp_date):
                    exp_dt = datetime.fromisoformat(exp_date)
                    expired_display = exp_dt.strftime("%d-%m-%Y %H:%M")
                else:
                    expired_display = str(exp_date)[:16]
            except:
                expired_display = str(exp_date)
        status_display = "🟢 AKTIF"
    else:
        paket_display = "❌ BELUM LANGGANAN"
        expired_display = "-"
        status_display = "🔴 TIDAK AKTIF - Silahkan beli paket"
    
    username_display = f"@{username_db}" if username_db else f"@{user.username or 'user'}"
    profil_text = (
        f"👤 PROFIL USER\n\n"
        f"🆔 Telegram ID : {user.id}\n"
        f"👤 Nama : {nama_db}\n"
        f"📱 Username : {username_display}\n"
        f"💰 Saldo : Rp {saldo_db}\n\n"
        f"📦 Paket : {paket_display}\n"
        f"📅 Expired : {expired_display}\n"
        f"📊 Status : {status_display}"
    )
    # Tombol tambahan jika belum langganan
    if not has_sub and not is_admin:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 BELI PAKET", callback_data="menu_buat")],
            [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
        ])
    else:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]])
    await update.message.reply_text(profil_text, reply_markup=kb)

async def buat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⌨️ BUAT FORMAT\nPilih metode:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ MANUAL", callback_data="buat_manual"), InlineKeyboardButton("📊 EXCEL", callback_data="buat_excel")],
        [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
    ]))

async def hasil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 HASIL FORMAT", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format"), InlineKeyboardButton("📑 FORMAT+AKUN", callback_data="menu_hasil_full")],
        [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
    ]))

async def setting_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    template, kode_atas, kode_prefix, kode_pos = get_setting(user_id)
    next_kode = get_next_code(user_id)
    pos_label = "ATAS" if kode_pos == "atas" else "BAWAH"
    await update.message.reply_text(
        f"⚙️ SETTING\nKode aktif: {next_kode} ({pos_label})",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 1. SET TEMPLAT", callback_data="setting_template_view")],
            [InlineKeyboardButton("⬆️ 2. SET KODE ATAS", callback_data="setting_kode_atas")],
            [InlineKeyboardButton("⬇️ 3. SET KODE BAWAH", callback_data="setting_kode_bawah")],
            [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
        ])
    )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🕘 HISTORY", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 1. FORMAT", callback_data="history_format")],
        [InlineKeyboardButton("📑 2. FORMAT+AKUN", callback_data="history_full")],
        [InlineKeyboardButton("🔢 3. CEK KODE SAJA", callback_data="history_kode")],
        [InlineKeyboardButton("🗑️ 4. DATA YG DI HAPUS", callback_data="history_deleted")],
        [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
    ]))

async def hubungi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📞 HUBUNGI ADMIN\n"
        "Jika membutuhkan bantuan, silakan hubungi Admin:\n"
        "👤 Telegram @Hambali1995\n"
        "📱 WhatsApp 083160776091"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Chat di Telegram", url="https://t.me/Hambali1995")],
        [InlineKeyboardButton("💬 Chat di WhatsApp", url="https://wa.me/6283160776091")],
        [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
    ])
    await update.message.reply_text(text, reply_markup=kb)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT user_id FROM admins")
        admin_rows = c.fetchall()
        admin_ids_db = [r[0] for r in admin_rows]
    except:
        admin_ids_db = []
    conn.close()
    all_admins = list(set(ADMIN_IDS + admin_ids_db))
    if user_id not in all_admins:
        await update.message.reply_text("⛔ Bukan admin.")
        return
    await update.message.reply_text("👑 PANEL ADMIN", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 1. CEK USER AKTIF", callback_data="admin_cek_user")],
        [InlineKeyboardButton("🗑️ 2. HAPUS USER", callback_data="admin_hapus_user")],
        [InlineKeyboardButton("➕ 3. TAMBAH ADMIN", callback_data="admin_tambah_admin")],
        [InlineKeyboardButton("➖ 4. HAPUS ADMIN", callback_data="admin_hapus_admin")],
        [InlineKeyboardButton("📢 5. BROADCAST", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
    ]))


async def addlangganan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin_user(user_id):
        await update.message.reply_text("⛔ Hanya admin yang bisa pakai command ini.")
        return
    # Format: /addlangganan <user_id> <paket>
    # paket: 3bulan, 6bulan, 1tahun, unlimited
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Format salah.\n\nGunakan:\n/addlangganan <user_id> <paket>\n\nPaket:\n- 3bulan (25k)\n- 6bulan (50k)\n- 1tahun (100k)\n- unlimited (250k)\n\nContoh:\n/addlangganan 123456789 3bulan",
            parse_mode="Markdown"
        )
        return
    try:
        target_id = int(args[0])
    except:
        await update.message.reply_text("❌ User ID harus angka.")
        return
    paket_key = args[1].lower().replace(" ", "")
    # Normalisasi
    if paket_key in ["3bulan","3","3 bulan","3bulan"]:
        paket_key = "3bulan"
    elif paket_key in ["6bulan","6","6 bulan"]:
        paket_key = "6bulan"
    elif paket_key in ["1tahun","1 tahun","12bulan","1th","setahun"]:
        paket_key = "1tahun"
    elif paket_key in ["unlimited","unli","selamanya","lifetime"]:
        paket_key = "unlimited"
    
    if paket_key not in PACKAGES:
        await update.message.reply_text(f"❌ Paket '{args[1]}' tidak dikenal. Pilih: 3bulan, 6bulan, 1tahun, unlimited")
        return
    
    pkg = PACKAGES[paket_key]
    from datetime import datetime, timedelta
    tgl_mulai = datetime.now()
    tgl_expired = tgl_mulai + timedelta(days=pkg['durasi']) if pkg['durasi'] < 10000 else datetime(2099,12,31)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO subscriptions (user_id, paket, harga, durasi_hari, tgl_mulai, tgl_expired, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
              (target_id, pkg['label'], pkg['harga'], pkg['durasi'], tgl_mulai.isoformat(), tgl_expired.isoformat(), 'active', datetime.now().isoformat()))
    c.execute("UPDATE users SET expired=? WHERE user_id=?", (tgl_expired.strftime("%d-%m-%Y") if pkg['durasi'] < 10000 else "UNLIMITED", target_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ **LANGGANAN DITAMBAHKAN**\n\n"
        f"User ID: {target_id}\n"
        f"Paket: {pkg['label']}\n"
        f"Harga: Rp{pkg['harga']:,}\n"
        f"Durasi: {pkg['durasi']} hari\n"
        f"Expired: {tgl_expired.strftime('%d-%m-%Y %H:%M') if pkg['durasi'] < 10000 else 'UNLIMITED'}\n\n"
        f"User sekarang bisa pakai BUAT FORMAT & DATA SAYA ✅",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"✅ **LANGGANAN AKTIF!**\n\n"
                 f"Paket kamu: {pkg['label']}\n"
                 f"Berakhir: {tgl_expired.strftime('%d-%m-%Y') if pkg['durasi'] < 10000 else 'UNLIMITED ♾️'}\n\n"
                 f"Sekarang kamu bisa pakai:\n"
                 f"⌨️ BUAT FORMAT\n"
                 f"📂 DATA SAYA\n\n"
                 f"Terimakasih sudah berlangganan! 🙏",
            parse_mode="Markdown"
        )
    except:
        pass

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = context.user_data.get("mode")
    paket_key = context.user_data.get("topup_paket")
    
    if mode != "topup_bukti":
        return
    
    if not update.message.photo:
        await update.message.reply_text("❌ Kirim foto bukti transfer ya bos!")
        return
    
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM topup_pending WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
    row = c.fetchone()
    if row:
        tid = row[0]
        c.execute("UPDATE topup_pending SET bukti_file_id=?, status='bukti_terkirim' WHERE id=?", (file_id, tid))
        conn.commit()
        try:
            c.execute("SELECT user_id FROM admins")
            admin_rows = c.fetchall()
        except:
            admin_rows = []
        all_admins = list(set(ADMIN_IDS + [r[0] for r in admin_rows]))
        pkg = PACKAGES.get(paket_key, {"label": "Unknown", "harga": 0})
        caption = f"💳 TOPUP BARU!\n\nUser: {user_id} (@{update.effective_user.username or '-'})\nPaket: {pkg.get('label')} Rp{pkg.get('harga'):,}\nID Topup: {tid}\n\nCek dan approve di PANEL ADMIN > CEK TOPUP"
        for admin_id in all_admins:
            try:
                await context.bot.send_photo(chat_id=admin_id, photo=file_id, caption=caption, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_topup_{tid}"), InlineKeyboardButton("❌ REJECT", callback_data=f"reject_topup_{tid}")]]))
            except:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=caption + f"\nFileID: {file_id}")
                except:
                    pass
        conn.close()
        context.user_data["mode"] = None
        context.user_data["topup_paket"] = None
        await update.message.reply_text(
            f"✅ Bukti transfer diterima!\n\nPaket: {pkg.get('label')}\nHarga: Rp{pkg.get('harga'):,}\n\nAdmin akan cek dalam 1x24 jam. Jika valid, akses BUAT FORMAT & DATA SAYA akan otomatis terbuka ✅",
            reply_markup=main_menu_keyboard(user_id)
        )
    else:
        conn.close()
        await update.message.reply_text("❌ Tidak ada paket pending. Silahkan pilih paket dulu.", reply_markup=paket_menu_keyboard())

async def setup_commands(app):
    from telegram import BotCommand
    commands = [
        BotCommand("start", "🟢 Mulai bot & tampilkan menu"),
        BotCommand("menu", "📋 Tampilkan menu utama"),
        BotCommand("help", "📖 Bantuan"),
        BotCommand("profil", "👤 Cek profil"),
        BotCommand("buat", "⌨️ Buat format"),
        BotCommand("hasil", "📄 Hasil format"),
        BotCommand("setting", "⚙️ Setting"),
        BotCommand("history", "🕘 History"),
        BotCommand("admin", "👑 Panel admin"),
        BotCommand("addlangganan", "💳 Tambah langganan manual (admin)"),
        BotCommand("hubungi", "📞 Hubungi admin"),
    ]
    try:
        await app.bot.set_my_commands(commands)
        print("✅ Commands set di Menu button")
    except Exception as e:
        print(f"Gagal set commands: {e}")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profil", profil_command))
    app.add_handler(CommandHandler("buat", buat_command))
    app.add_handler(CommandHandler("hasil", hasil_command))
    app.add_handler(CommandHandler("setting", setting_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("hubungi", hubungi_command))
    app.add_handler(CommandHandler("addlangganan", addlangganan_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.post_init = setup_commands
    print("Bot jalan dengan COMMAND HANDLER...")
    print("Menu hot: /start, /menu, /help, /profil, /buat, /hasil, /setting, /history, /admin")
    app.run_polling()

if __name__ == "__main__":
    main()
