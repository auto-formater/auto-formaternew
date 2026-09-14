
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

# === FIX PERSISTENT DATABASE UNTUK RAILWAY ===
# Agar data tidak hilang saat deploy ulang, gunakan Volume /data
# Di Railway: Add Volume -> Mount Path = /data
# Set Variables: DB_PATH = /data/bot_baru.db
if os.path.exists("/data"):
    DEFAULT_DB = "/data/bot_baru.db"
else:
    DEFAULT_DB = "bot_baru.db"

DB_PATH = os.getenv("DB_PATH", DEFAULT_DB)

print(f"✅ BOT READY | ADMIN: {ADMIN_IDS} | DB: {DB_PATH}")

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
    # FIX PERSISTEN: buat folder /data kalau belum ada (untuk Volume Railway)
    try:
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"📁 Membuat folder DB: {db_dir}")
    except Exception as e:
        print(f"⚠️ Gagal buat folder DB: {e}")
        pass
    print(f"💾 Menggunakan database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # === TABEL BERSIH - TIDAK PAKAI ALTER LAGI ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            total_format INTEGER DEFAULT 0,
            saldo TEXT DEFAULT '0',
            expired TEXT DEFAULT 'BELUM AKTIF',
            nama TEXT DEFAULT ''
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY,
            template TEXT,
            kode_atas TEXT DEFAULT '001',
            kode_prefix TEXT DEFAULT 'SEXS',
            kode_pos TEXT DEFAULT 'atas',
            kode_base_count INTEGER DEFAULT 0
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS hasil_format (
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
            akun TEXT,
            display_format TEXT,
            display_full TEXT,
            status TEXT DEFAULT 'ready',
            created_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            aksi TEXT,
            detail TEXT,
            created_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS data_saya (
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
            created_at TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS paket_user (
            user_id INTEGER PRIMARY KEY,
            paket_name TEXT,
            added_by INTEGER,
            created_at TEXT,
            expired_at TEXT
        )
    """)
    
    # Index biar cepat
    c.execute("CREATE INDEX IF NOT EXISTS idx_hasil_user ON hasil_format(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_hasil_status ON hasil_format(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_paket_user ON paket_user(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id)")
    
    conn.commit()
    conn.close()
    print("✅ Database tabel siap")

def get_setting(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT template, kode_atas, kode_prefix, kode_pos, kode_base_count FROM settings WHERE user_id=?", (user_id,))
    except:
        c.execute("SELECT template, kode_atas, kode_prefix, kode_pos FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO settings (user_id, template, kode_atas, kode_prefix, kode_pos, kode_base_count) VALUES (?, ?, ?, ?, ?, ?)", (user_id, DEFAULT_TEMPLATE, "001", "SEXS", "atas", 0))
        conn.commit()
        template, kode_atas, kode_prefix, kode_pos, base_count = DEFAULT_TEMPLATE, "001", "SEXS", "atas", 0
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

def check_is_admin(user_id):
    """Cek apakah user adalah admin dari Railway ADMIN_IDS atau database admins."""
    if user_id is None:
        return False

    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False

    if uid in ADMIN_IDS:
        return True

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM admins WHERE user_id=? LIMIT 1", (uid,))
        row = c.fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        print(f"⚠️ Gagal cek admin: {e}")
        return False


def is_paket_aktif(user_id):
    """Cek apakah user punya paket aktif / admin bypass"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT user_id FROM admins")
            admin_db = [r[0] for r in c.fetchall()]
        except:
            admin_db = []
        conn.close()
    except:
        admin_db = []
    all_admins = list(set(ADMIN_IDS + admin_db))
    if user_id in all_admins:
        return True
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT expired_at FROM paket_user WHERE user_id=?", (user_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return False
        exp = row[0]
        if not exp or str(exp).upper() == "UNLIMITED":
            return True
        from datetime import datetime as _dt
        try:
            dt = _dt.fromisoformat(exp)
            return _dt.now() <= dt
        except:
            return True
    except:
        return False

def get_setting_simple(user_id):
    # wrapper for backward compatibility - returns 4 values
    t, ka, kp, kpos, _ = get_setting(user_id)
    return t, ka, kp, kpos


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
    lines = [l.strip().upper() for l in block_text.strip().splitlines() if l.strip()!=""]
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
    akun = "\n".join([a.upper() for a in akun_lines]) if akun_lines else "-"
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
    data_dict = {k: (v.upper() if isinstance(v, str) else v) for k, v in data_dict.items()}
    kode = data_dict.get("KODE", "")
    # Build base JMO format
    try:
        base_formatted = template.format(**data_dict)
    except Exception:
        # fallback if template missing keys
        safe_dict = {k: data_dict.get(k, "") for k in ["KAB","KEC","KEL","SALDO","KELAMIN","KPJ","SENSOR","IT","PT","KODE","NIK_LENGKAP","KPJ_LENGKAP","NAMA_LENGKAP","TGL_LAHIR","NIK","NAMA","AKUN"]}
        safe_dict["KODE"]=kode
        try:
            base_formatted = DEFAULT_TEMPLATE.format(**safe_dict)
        except:
            base_formatted = DEFAULT_TEMPLATE.format(**{k: data_dict.get(k,"") for k in ["KAB","KEC","KEL","SALDO","KELAMIN","KPJ","SENSOR","IT","PT","KODE"]})

    # Atur posisi KODE sesuai setting ATAS/BAWAH - FIX SESUAI PILIHAN
    if kode_pos == "bawah":
        # kode di bawah
        lines = base_formatted.split("\n")
        filtered = []
        for l in lines:
            if kode and kode in l and len(l.strip()) < 35 and ("MGB" in l or "JPG" in l or re.search(r"\d{3,}", l) or l.strip()==kode.strip()):
                continue
            filtered.append(l)
        body = "\n".join(filtered).strip()
        if not body:
            body = base_formatted.replace(kode, "").strip()
        display_format = f"{body}\n━━━━━━━━━━━━━━━━━━━\n     {kode}"
    else:
        # kode di atas
        lines = base_formatted.split("\n")
        new_lines = []
        found = False
        for l in lines:
            if not found and kode and kode in l and len(l.strip()) < 35:
                new_lines.append(f"{kode}")
                found = True
            else:
                new_lines.append(l)
        if not found:
            # pastikan kode di paling atas
            if new_lines and "━━━━━━━━" in new_lines[0]:
                new_lines = [f"{kode}"] + new_lines
            else:
                # cari header, sisipkan
                new_lines = [f"{kode}", "━━━━━━━━━━━━━━━━━━━"] + [x for x in new_lines if x.strip()!=kode]
        display_format = "\n".join(new_lines).strip()
        # rapikan kalau double separator di atas
        display_format = display_format.replace(f"{kode}\n━━━━━━━━━━━━━━━━━━━\n━━━━━━━━━━━━━━━━━━━", f"{kode}\n━━━━━━━━━━━━━━━━━━━")

    # FORMAT BIASA = display_format saja
    # FORMAT+AKUN = display_format + DATA LENGKAP section sesuai request
    nik = data_dict.get("NIK_LENGKAP") or data_dict.get("NIK") or ""
    kpj_lengkap = data_dict.get("KPJ_LENGKAP") or ""
    nama = data_dict.get("NAMA_LENGKAP") or data_dict.get("NAMA") or ""
    tgl = data_dict.get("TGL_LAHIR") or ""

    data_lengkap_section = f"""\n\n━━━━━━━━━━━━━━━━━━━\n📋 DATA LENGKAP\n\n🆔 NIK : {nik}\n💳 KPJ : {kpj_lengkap}\n👤 NAMA : {nama}\n💞 LAHIR : {tgl}"""

    display_full = display_format + data_lengkap_section

    # jika ada AKUN tambahan, append setelah data lengkap
    if data_dict.get("AKUN") and data_dict["AKUN"] != "-":
        display_full += f"\n\nAKUN:\n{data_dict['AKUN']}"

    return display_format, display_full

def main_menu_keyboard(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("👤 PROFIL", callback_data="menu_profil"),
         InlineKeyboardButton("📝 BUAT FORMAT", callback_data="menu_buat")],
        [InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format"),
         InlineKeyboardButton("📂 FORMAT+AKUN", callback_data="menu_hasil_full")],
        [InlineKeyboardButton("⚙️ SETTING", callback_data="menu_setting"),
         InlineKeyboardButton("🕘 HISTORY", callback_data="menu_history")],
        [InlineKeyboardButton("📞 HUBUNGI ADMIN", callback_data="hubungi_admin")],
    ]

    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 PANEL ADMIN", callback_data="menu_admin")])

    return InlineKeyboardMarkup(keyboard)

def hubungi_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 CHAT DI TELEGRAM", url="https://t.me/Hambali1995")],
        [InlineKeyboardButton("💬 CHAT DI WHATSAPP", url="https://wa.me/6283160776091")],
        [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")],
    ])

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
        (user_id, username, first_name, "0", "BELUM AKTIF")
    )
    c.execute("UPDATE users SET username=?, nama=? WHERE user_id=?", (username, first_name, user_id))
    conn.commit()
    conn.close()

    welcome_text = (
        "🟢 MODE ON DI AKTIFKAN\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Selamat datang, {first_name}! Gassskeun bosssqu jangan malu-malu, pakai auto format dong biarr pro..wkwk, jangan lupa ngopi biar gak oleng yah bosquu. Silahkan pilih menu di bawah ini : 👇"
    )
    is_admin = check_is_admin(user_id)
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(is_admin))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "back_main":
        welcome_text = (
            "🟢 MODE ON DI AKTIFKAN\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👋 Ketemu lagi deh, SAHABAT JHT! tetap semangat kalau lelah jangan lupa istirahat yahhh. Silahkan pilih menu lagi di bawah ini : 👇"
        )
        is_admin = check_is_admin(user_id)
        await query.edit_message_text(welcome_text, reply_markup=main_menu_keyboard(is_admin))
        return

    if data == "hubungi_admin":
        text = (
            "📞 HUBUNGI ADMIN\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Jika membutuhkan bantuan, silakan hubungi Admin:\n\n"
            "👤 Telegram @Hambali1995\n"
            "📱 WhatsApp 083160776091"
        )
        await query.edit_message_text(text, reply_markup=hubungi_admin_keyboard())
        return

    # === LOCK BUAT FORMAT ===
    if data in ["menu_buat", "buat_manual", "buat_excel"]:
        if not is_paket_aktif(user_id):
            await query.edit_message_text(
                "🔒 FITUR TERKUNCI\n\n"
                "untuk mengaktifkan menu ini silahkan hubungi admin dan memilih paket yang tersedia.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 HUBUNGI ADMIN", callback_data="hubungi_admin")],
                    [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
                ])
            )
            return

    if data == "menu_profil":
        init_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT username, saldo, nama FROM users WHERE user_id=?", (user_id,))
        urow = c.fetchone()
        try:
            c.execute("SELECT paket_name, expired_at FROM paket_user WHERE user_id=?", (user_id,))
            paket_row = c.fetchone()
        except:
            paket_row = None
        conn.close()

        is_admin = check_is_admin(user_id)
        username_db = urow[0] if urow and urow[0] else query.from_user.username or ""
        saldo_db = urow[1] if urow and urow[1] else "0"
        nama_db = urow[2] if urow and len(urow) > 2 and urow[2] else query.from_user.first_name or "SAHABAT"

        if is_admin:
            paket_display = "ADMIN"
            expired_display = "UNLIMITED ADMIN"
            status_display = "🟢 AKTIF (ADMIN)"
        elif not paket_row:
            paket_display = "BELUM ADA PAKET"
            expired_display = "-"
            status_display = "🔴 TIDAK AKTIF (Belum diaktifkan admin)"
        else:
            paket_name, expired_at = paket_row
            paket_display = paket_name or "-"
            if expired_at and str(expired_at).upper() == "UNLIMITED":
                expired_display = "UNLIMITED"
            else:
                try:
                    dt = datetime.fromisoformat(expired_at)
                    expired_display = dt.strftime("%d-%m-%Y %H:%M")
                except:
                    expired_display = str(expired_at or "-")
            if is_paket_aktif(user_id):
                status_display = "🟢 AKTIF"
            else:
                status_display = "🔴 TIDAK AKTIF (EXPIRED)"

        username_display = f"@{username_db}" if username_db else f"@{(query.from_user.username or 'user')}"
        profil_text = (
            f"👤 PROFIL USER\n\n"
            f"🆔 Telegram ID : {user_id}\n"
            f"👤 Nama : {nama_db}\n"
            f"📱 Username : {username_display}\n"
            f"💰 Saldo : Rp {saldo_db}\n"
            f"📦 Paket : {paket_display}\n\n"
            f"📅 Berakhir : {expired_display}\n"
            f"📊 Status : {status_display}"
        )
        await query.edit_message_text(profil_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))

    elif data == "menu_buat":
        await query.edit_message_text("⌨️ BUAT FORMAT\nPilih metode:", reply_markup=buat_menu())

    elif data == "buat_manual":
        context.user_data["mode"] = "manual"
        await query.edit_message_text(
            "⌨️ BUAT FORMAT\n\nKetik data tanpa perlu menulis KAB/KEC/KEL. Bot otomatis membaca urutannya:\n\n1️⃣ KAB\n2️⃣ KEC\n3️⃣ KEL\n4️⃣ SALDO\n5️⃣ KELAMIN\n6️⃣ KPJ\n7️⃣ SENSOR\n8️⃣ IT\n9️⃣ PT\n🔟 NIK LENGKAP\n1️⃣1️⃣ KPJ LENGKAP\n1️⃣2️⃣ NAMA LENGKAP\n1️⃣3️⃣ TANGGAL LAHIR\n\nContoh:\nDEPOK\nCILODONG\nKALIBARU\n10.000.000\nPEREMPUAN 1992\n2019\n23****\n01-07-2022\nINDONESIA MERDEKA\n3201234589920002\n19000378990\nLIA\n12-12-1990\n\nHasilnya otomatis menjadi format JMO.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_buat")]]),
        )

    elif data == "buat_excel":
        context.user_data["mode"] = "excel"
        await query.edit_message_text(
            "📊 UPLOAD FILE EXCEL\n\nUpload .xlsx (A=KAB B=KEC C=KEL D=SALDO E=KELAMIN F=KPJ G=SENSOR H=IT I=PT J=NIK K=NO_KPJ L=NAMA M=TGL)\nKirim file sekarang 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_buat")]]),
        )

    elif data == "menu_hasil_format":
        # ADMIN HANYA LIHAT DATA SESAMA ADMIN (tidak lihat data user biasa)
        is_admin_view = check_is_admin(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if is_admin_view:
            try:
                c.execute("SELECT user_id FROM admins")
                db_admins = [r[0] for r in c.fetchall()]
            except:
                db_admins = []
            all_admins_list = list(set(ADMIN_IDS + db_admins))
            if all_admins_list:
                placeholders = ",".join(["?" for _ in all_admins_list])
                try:
                    c.execute(f"SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", tuple(all_admins_list))
                    rows = c.fetchall()
                    if not rows:
                        c.execute(f"SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY id ASC", tuple(all_admins_list))
                        rows = c.fetchall()
                except:
                    c.execute(f"SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY id ASC", tuple(all_admins_list))
                    rows = c.fetchall()
            else:
                rows = []
        else:
            c.execute("SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", (user_id,))
            rows = c.fetchall()
            if not rows:
                c.execute("SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY id ASC", (user_id,))
                rows = c.fetchall()
        conn.close()
        if not rows:
            # cek apakah ada yang terjual semua
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
            total = c.fetchone()[0]
            conn.close()
            if total > 0:
                await query.edit_message_text("📄 Semua format sudah terjual. Cek di HISTORY.", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🕘 BUKA HISTORY", callback_data="menu_history")],
                    [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
                ]))
            else:
                await query.edit_message_text("Belum ada HASIL FORMAT.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        
        # Tombol pencarian di ATAS agar user langsung cari
        await query.edit_message_text(
            f"📄 **HASIL FORMAT** - {len(rows)} data\n\nUrutan: terkecil ke terbesar\n{rows[0][1]} → {rows[-1][1]}\n\nMenampilkan urut ASD 001, 002, 003...",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI (Kode/Nama/KAB/dll)", callback_data="cari_format")],
                [InlineKeyboardButton("➡️ TAMPILKAN SEMUA", callback_data="tampilkan_format")]
            ]),
            parse_mode="Markdown"
        )
        # Kirim per format urut kecil ke besar
        for idx, (rid, kode, disp, kab, kec, kel, saldo, kelamin, kpj, pt) in enumerate(rows, start=1):
            header = f"{idx}. {kode} (ID {rid})"
            text = f"{header}\n```\n{disp}\n```"
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
            kb = InlineKeyboardMarkup([[jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]])
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp}", reply_markup=kb)
        await context.bot.send_message(chat_id=user_id, text="🔍 MENU LANJUTAN", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 CARI HASIL FORMAT", callback_data="cari_format")],
            [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
        ]))

    elif data == "tampilkan_format":
        is_admin_view = check_is_admin(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if is_admin_view:
            try:
                c.execute("SELECT user_id FROM admins")
                db_admins = [r[0] for r in c.fetchall()]
            except:
                db_admins = []
            all_admins_list = list(set(ADMIN_IDS + db_admins))
            if all_admins_list:
                placeholders = ",".join(["?" for _ in all_admins_list])
                try:
                    c.execute(f"SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", tuple(all_admins_list))
                    rows = c.fetchall()
                    if not rows:
                        c.execute(f"SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY id ASC", tuple(all_admins_list))
                        rows = c.fetchall()
                except:
                    c.execute(f"SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY id ASC", tuple(all_admins_list))
                    rows = c.fetchall()
            else:
                rows = []
        else:
            c.execute("SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", (user_id,))
            rows = c.fetchall()
            if not rows:
                c.execute("SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY id ASC", (user_id,))
                rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada HASIL FORMAT.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        await query.edit_message_text(f"Menampilkan {len(rows)} format urut terkecil ke terbesar...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 CARI", callback_data="cari_format")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
        for idx, (rid, kode, disp, kab, kec, kel, saldo, kelamin, kpj, pt) in enumerate(rows, start=1):
            header = f"{idx}. {kode} (ID {rid})"
            text = f"{header}\n```\n{disp}\n```"
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
            kb = InlineKeyboardMarkup([[jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]])
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp}", reply_markup=kb)

    elif data == "menu_hasil_full":
        is_admin_view = check_is_admin(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if is_admin_view:
            try:
                c.execute("SELECT user_id FROM admins")
                db_admins = [r[0] for r in c.fetchall()]
            except:
                db_admins = []
            all_admins_list = list(set(ADMIN_IDS + db_admins))
            if all_admins_list:
                placeholders = ",".join(["?" for _ in all_admins_list])
                try:
                    c.execute(f"SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", tuple(all_admins_list))
                    rows = c.fetchall()
                    if not rows:
                        c.execute(f"SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY id ASC", tuple(all_admins_list))
                        rows = c.fetchall()
                except:
                    c.execute(f"SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY id ASC", tuple(all_admins_list))
                    rows = c.fetchall()
            else:
                rows = []
        else:
            c.execute("SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", (user_id,))
            rows = c.fetchall()
            if not rows:
                c.execute("SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY id ASC", (user_id,))
                rows = c.fetchall()
        conn.close()
        if not rows:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
            total = c.fetchone()[0]
            conn.close()
            if total > 0:
                await query.edit_message_text("📑 Semua FORMAT+AKUN sudah terjual. Cek di HISTORY.", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🕘 BUKA HISTORY", callback_data="menu_history")],
                    [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
                ]))
            else:
                await query.edit_message_text("Belum ada HASIL FORMAT+AKUN.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        
        await query.edit_message_text(
            f"📑 **HASIL FORMAT+AKUN** - {len(rows)} data\n\nUrutan: terkecil ke terbesar\n{rows[0][1]} → {rows[-1][1]}\n\nMenampilkan urut ASD 001, 002, 003...",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 CARI (Kode/Nama/KAB/Akun)", callback_data="cari_akun")],
                [InlineKeyboardButton("➡️ TAMPILKAN SEMUA", callback_data="tampilkan_full")]
            ]),
            parse_mode="Markdown"
        )
        for idx, (rid, kode, disp_full, kab, kec, kel, pt, akun) in enumerate(rows, start=1):
            header = f"{idx}. {kode} (ID {rid})"
            text = f"{header}\n```\n{disp_full}\n```"
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp_full))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
            kb = InlineKeyboardMarkup([[jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]])
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp_full}", reply_markup=kb)
        await context.bot.send_message(chat_id=user_id, text="🔍 MENU AKUN LAINNYA", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 CARI AKUN", callback_data="cari_akun")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
        ]))

    elif data == "tampilkan_full":
        is_admin_view = check_is_admin(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if is_admin_view:
            try:
                c.execute("SELECT user_id FROM admins")
                db_admins = [r[0] for r in c.fetchall()]
            except:
                db_admins = []
            all_admins_list = list(set(ADMIN_IDS + db_admins))
            if all_admins_list:
                placeholders = ",".join(["?" for _ in all_admins_list])
                try:
                    c.execute(f"SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", tuple(all_admins_list))
                    rows = c.fetchall()
                    if not rows:
                        c.execute(f"SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY id ASC", tuple(all_admins_list))
                        rows = c.fetchall()
                except:
                    c.execute(f"SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE status='ready' AND user_id IN ({placeholders}) ORDER BY id ASC", tuple(all_admins_list))
                    rows = c.fetchall()
            else:
                rows = []
        else:
            c.execute("SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", (user_id,))
            rows = c.fetchall()
            if not rows:
                c.execute("SELECT id, kode, display_full, kab, kec, kel, pt, akun FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY id ASC", (user_id,))
                rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada HASIL FORMAT+AKUN.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        await query.edit_message_text(f"Menampilkan {len(rows)} akun urut terkecil ke terbesar...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 CARI", callback_data="cari_akun")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
        for idx, (rid, kode, disp_full, kab, kec, kel, pt, akun) in enumerate(rows, start=1):
            header = f"{idx}. {kode} (ID {rid})"
            text = f"{header}\n```\n{disp_full}\n```"
            try:
                from telegram import CopyTextButton
                jual_btn = InlineKeyboardButton("💰 JUAL", copy_text=CopyTextButton(disp_full))
            except:
                jual_btn = InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{rid}")
            kb = InlineKeyboardMarkup([[jual_btn, InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_{rid}")]])
            try:
                await context.bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=user_id, text=f"{header}\n{disp_full}", reply_markup=kb)

    elif data.startswith("jual_"):
        rid = int(data.split("_")[1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # ADMIN BOLEH JUAL DATA SESAMA ADMIN
        is_admin_seller = check_is_admin(user_id)
        if is_admin_seller:
            c.execute("SELECT kode, display_full, display_format, user_id, kab, kec, kel FROM hasil_format WHERE id=?", (rid,))
        else:
            c.execute("SELECT kode, display_full, display_format, user_id, kab, kec, kel FROM hasil_format WHERE id=? AND user_id=?", (rid, user_id))
        row = c.fetchone()
        if row:
            kode, disp_full, disp_format, owner_id, kab, kec, kel = row
            if not disp_format:
                disp_format = disp_full
            # Update status - admin bisa jual data admin lain
            if is_admin_seller:
                c.execute("UPDATE hasil_format SET status='terjual' WHERE id=?", (rid,))
            else:
                c.execute("UPDATE hasil_format SET status='terjual' WHERE id=? AND user_id=?", (rid, user_id))
            now_iso = datetime.now().isoformat()
            c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "JUAL", f"ID {rid} {kode}", now_iso))
            conn.commit()
            
            # Ambil info seller dan owner
            seller_id = user_id
            seller_username = query.from_user.username or "-"
            seller_name = query.from_user.first_name or "ADMIN"
            try:
                c.execute("SELECT username, nama FROM users WHERE user_id=?", (owner_id,))
                owner_row = c.fetchone()
                owner_username = owner_row[0] if owner_row and owner_row[0] else str(owner_id)
                owner_nama = owner_row[1] if owner_row and len(owner_row)>1 and owner_row[1] else "-"
            except:
                owner_username = str(owner_id)
                owner_nama = "-"
            try:
                c.execute("SELECT user_id FROM admins")
                admin_rows = c.fetchall()
                admin_ids_db = [r[0] for r in admin_rows]
            except:
                admin_ids_db = []
            all_admins = list(set(ADMIN_IDS + admin_ids_db))
            conn.close()
            
            # Ambil saldo dari DB untuk notif lengkap
            try:
                conn2 = sqlite3.connect(DB_PATH)
                c2 = conn2.cursor()
                c2.execute("SELECT saldo FROM hasil_format WHERE id=?", (rid,))
                saldo_row = c2.fetchone()
                saldo_notif = saldo_row[0] if saldo_row and saldo_row[0] else "-"
                conn2.close()
            except:
                saldo_notif = "-"
            
            # FORMAT NOTIFIKASI SESUAI REQUEST KAMU - YANG JUAL JUGA DAPAT
            waktu_str = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            # Format pemilik awal dan penjual sesuai contoh
            pemilik_display = f"{owner_nama} (@{owner_username})" if owner_username and owner_username != "-" else f"{owner_nama} (@-)"
            penjual_display = f"{seller_name} (@{seller_username})" if seller_username and seller_username != "-" else f"{seller_name} (@-)"
            
            notif_text = (
                f"🔔 DATA TERJUAL - NOTIF ADMIN\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📦 Kode: {kode} (ID {rid})\n"
                f"\n"
                f"📍 KAB : {kab}\n"
                f"📍 KEC : {kec}\n"
                f"📍 KEL : {kel}\n"
                f"\n"
                f"💰 SALDO : {saldo_notif}\n"
                f"\n"
                f"👤 Pemilik awal: {pemilik_display} ID {owner_id}\n"
                f"\n"
                f"💰 Dijual oleh: {penjual_display} ID {seller_id}\n"
                f"⏰ Waktu: {waktu_str}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"Data sudah dipindah ke HISTORY (terjual)"
            )
            
            # Notif ke seller dulu (yang jual juga dapat)
            try:
                await context.bot.send_message(chat_id=user_id, text=notif_text)
            except:
                pass
            
            # NOTIFIKASI KE SESAMA ADMIN LAIN (user biasa tidak dapat)
            if is_admin_seller:
                for admin_id in all_admins:
                    if admin_id != seller_id:  # seller sudah dapat di atas
                        try:
                            await context.bot.send_message(chat_id=admin_id, text=notif_text)
                        except Exception as e:
                            print(f"Gagal notif admin {admin_id}: {e}")
                            continue
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
        # MENU BARU: DATA SAYA
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✍️ KETIK MANUAL", callback_data="data_saya_manual"),
             InlineKeyboardButton("📊 KIRIM EXCEL", callback_data="data_saya_excel")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
        ])
        await query.edit_message_text(
            "📂 DATA SAYA\n\nSilahkan ketik manual ataupun kirim file Excel.\nNanti otomatis jadi Data user sesuai user pinta.\n\nPilih metode di bawah:",
            reply_markup=kb
        )

    elif data == "data_saya_manual":
        context.user_data["mode"] = "data_saya_manual"
        await query.edit_message_text(
            "📂 DATA SAYA - MANUAL\n\n"
            "⌨️ BUAT FORMAT\n\n"
            "Ketik data tanpa perlu menulis KAB/KEC/KEL. Bot otomatis membaca urutannya:\n\n"
            "1️⃣ KAB\n2️⃣ KEC\n3️⃣ KEL\n4️⃣ SALDO\n5️⃣ KELAMIN\n6️⃣ KPJ\n7️⃣ SENSOR\n8️⃣ IT\n9️⃣ PT\n"
            "🔟 NIK LENGKAP\n1️⃣1️⃣ KPJ LENGKAP\n1️⃣2️⃣ NAMA LENGKAP\n1️⃣3️⃣ TANGGAL LAHIR\n\n"
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
        c.execute("SELECT id, display_text, kab, kec, kel FROM data_saya WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if total==0:
            await query.edit_message_text(
                "📊 HASIL DATA SAYA\n\nBelum ada data. Silahkan tambah di menu DATA SAYA dulu.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📂 TAMBAH DATA", callback_data="menu_data_saya")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]])
            )
            return
        text = f"📊 HASIL DATA SAYA\n\nTotal: {total} data\nMenampilkan 10 terbaru:\n\n"
        for idx, (rid, disp, kab, kec, kel) in enumerate(rows,1):
            text+=f"{idx}. ID {rid} - {kab}/{kec}/{kel}\n"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 1. CARI DATA SAYA", callback_data="cari_data_saya")],
            [InlineKeyboardButton("📤 2. EXPORT DATA SAYA", callback_data="export_data_saya")],
            [InlineKeyboardButton("🗑️ 3. HAPUS PER SATU", callback_data="hapus_satu_data_saya")],
            [InlineKeyboardButton("⬅️ 4. KEMBALI", callback_data="back_main")]
        ])
        await query.edit_message_text(text, reply_markup=kb)
        # kirim detail 10 terbaru
        for rid, disp, kab, kec, kel in rows:
            if disp:
                try:
                    await context.bot.send_message(chat_id=user_id, text=f"ID {rid}\n```\n{disp}\n```", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_data_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_data_{rid}")]]))
                except:
                    await context.bot.send_message(chat_id=user_id, text=f"ID {rid} - {disp[:500]}")

    elif data == "cari_data_saya":
        context.user_data["mode"] = "cari_data_saya"
        await query.edit_message_text(
            "🔍 CARI DATA SAYA\n\nKetik yang mau dicari:\n- NIK, Nama, KAB, KEC, KEL\n- KPJ, PT, Saldo\n- Kata apapun\n\nContoh: DEPOK atau LIA atau 320123...\n\nKetik sekarang:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_hasil_data_saya")]])
        )

    elif data == "export_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir, display_text FROM data_saya WHERE user_id=? ORDER BY id ASC", (user_id,))
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


    elif data == "history_jualan_admin":
        if not check_is_admin(user_id):
            await query.edit_message_text("⛔ Hanya admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT user_id FROM admins")
            db_admins = [r[0] for r in c.fetchall()]
        except:
            db_admins = []
        all_admins_list = list(set(ADMIN_IDS + db_admins))
        if not all_admins_list:
            await query.edit_message_text("Belum ada admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
            conn.close()
            return
        ph = ",".join(["?" for _ in all_admins_list])
        # Ambil semua yang terjual milik admin
        c.execute(f"SELECT id, kode, kab, kec, kel, user_id, display_format, created_at FROM hasil_format WHERE status='terjual' AND user_id IN ({ph}) ORDER BY id DESC LIMIT 50", tuple(all_admins_list))
        rows = c.fetchall()
        # Hitung total terjual hari ini, minggu ini
        c.execute(f"SELECT COUNT(*) FROM hasil_format WHERE status='terjual' AND user_id IN ({ph})", tuple(all_admins_list))
        total_jual = c.fetchone()[0]
        # Ambil log jualan dari history untuk info penjual
        c.execute(f"SELECT user_id, aksi, detail, created_at FROM history WHERE aksi='JUAL' ORDER BY id DESC LIMIT 100")
        history_rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("💰 HISTORY JUALAN ADMIN\n\nBelum ada data terjual sesama admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
            return
        text = f"💰 **HISTORY JUALAN ADMIN**\nTotal terjual: {total_jual} data\nMenampilkan 50 terbaru:\n\n"
        for idx, (rid, kode, kab, kec, kel, owner_id, disp, created) in enumerate(rows,1):
            # cari penjual dari history
            penjual_id = None
            waktu_jual = created
            for h_uid, h_aksi, h_detail, h_created in history_rows:
                if f"ID {rid}" in h_detail or kode in h_detail:
                    penjual_id = h_uid
                    waktu_jual = h_created
                    break
            try:
                waktu_fmt = waktu_jual[:19].replace("T"," ")
            except:
                waktu_fmt = str(waktu_jual)
            text += f"{idx}. {kode} | {kab} - Penjual ID {penjual_id or '?'} | {waktu_fmt}\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]), parse_mode="Markdown")
        # Kirim detail 10 terbaru
        for rid, kode, kab, kec, kel, owner_id, disp, created in rows[:10]:
            penjual_id = None
            waktu_jual = created
            for h_uid, h_aksi, h_detail, h_created in history_rows:
                if f"ID {rid}" in h_detail or kode in h_detail:
                    penjual_id = h_uid
                    waktu_jual = h_created
                    break
            try:
                waktu_fmt = waktu_jual[:19].replace("T"," ")
            except:
                waktu_fmt = str(waktu_jual)
            header = f"ID {rid} | {kode} | Jual: {waktu_fmt} | Owner:{owner_id} Seller:{penjual_id}"
            full_text = f"{header}\n```\n{disp[:2000]}\n```"
            try:
                await context.bot.send_message(chat_id=user_id, text=full_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"pulihkan_{rid}")]]))
            except:
                await context.bot.send_message(chat_id=user_id, text=header)

    elif data.startswith("pulihkan_"):
        rid = int(data.split("_")[1])
        if not check_is_admin(user_id):
            # user biasa hanya bisa pulihkan punya sendiri
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE hasil_format SET status='ready' WHERE id=? AND user_id=? AND status='terjual'", (rid, user_id))
            conn.commit()
            conn.close()
            await query.edit_message_text(f"♻️ ID {rid} dipulihkan ke HASIL FORMAT!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format")]]))
            return
        # admin bisa pulihkan data sesama admin
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT user_id FROM admins")
            db_admins = [r[0] for r in c.fetchall()]
        except:
            db_admins = []
        all_admins_list = list(set(ADMIN_IDS + db_admins))
        if all_admins_list:
            ph = ",".join(["?" for _ in all_admins_list])
            c.execute(f"SELECT id FROM hasil_format WHERE id=? AND user_id IN ({ph}) AND status='terjual'", tuple(all_admins_list))
            row = c.fetchone()
            if row:
                c.execute("UPDATE hasil_format SET status='ready' WHERE id=?", (rid,))
                conn.commit()
                conn.close()
                await query.edit_message_text(f"♻️ ID {rid} dipulihkan! (admin)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format")]]))
                # Notif ke sesama admin
                notif_pulih = f"♻️ **DATA DIPULIHKAN**\nKode: ID {rid}\nDipulihkan oleh admin ID {user_id}\nSekarang kembali ke HASIL FORMAT"
                for admin_id in all_admins_list:
                    if admin_id != user_id:
                        try:
                            await context.bot.send_message(chat_id=admin_id, text=notif_pulih)
                        except:
                            pass
                return
        # fallback untuk user biasa
        c.execute("UPDATE hasil_format SET status='ready' WHERE id=? AND user_id=? AND status='terjual'", (rid, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"♻️ ID {rid} dipulihkan!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format")]]))


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
        # MENU BARU: DATA SAYA
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✍️ KETIK MANUAL", callback_data="data_saya_manual"),
             InlineKeyboardButton("📊 KIRIM EXCEL", callback_data="data_saya_excel")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
        ])
        await query.edit_message_text(
            "📂 DATA SAYA\n\nSilahkan ketik manual ataupun kirim file Excel.\nNanti otomatis jadi Data user sesuai user pinta.\n\nPilih metode di bawah:",
            reply_markup=kb
        )

    elif data == "data_saya_manual":
        context.user_data["mode"] = "data_saya_manual"
        await query.edit_message_text(
            "📂 DATA SAYA - MANUAL\n\n"
            "⌨️ BUAT FORMAT\n\n"
            "Ketik data tanpa perlu menulis KAB/KEC/KEL. Bot otomatis membaca urutannya:\n\n"
            "1️⃣ KAB\n2️⃣ KEC\n3️⃣ KEL\n4️⃣ SALDO\n5️⃣ KELAMIN\n6️⃣ KPJ\n7️⃣ SENSOR\n8️⃣ IT\n9️⃣ PT\n"
            "🔟 NIK LENGKAP\n1️⃣1️⃣ KPJ LENGKAP\n1️⃣2️⃣ NAMA LENGKAP\n1️⃣3️⃣ TANGGAL LAHIR\n\n"
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
        c.execute("SELECT id, display_text, kab, kec, kel FROM data_saya WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT COUNT(*) FROM data_saya WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        if total==0:
            await query.edit_message_text(
                "📊 HASIL DATA SAYA\n\nBelum ada data. Silahkan tambah di menu DATA SAYA dulu.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📂 TAMBAH DATA", callback_data="menu_data_saya")],[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]])
            )
            return
        text = f"📊 HASIL DATA SAYA\n\nTotal: {total} data\nMenampilkan 10 terbaru:\n\n"
        for idx, (rid, disp, kab, kec, kel) in enumerate(rows,1):
            text+=f"{idx}. ID {rid} - {kab}/{kec}/{kel}\n"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 1. CARI DATA SAYA", callback_data="cari_data_saya")],
            [InlineKeyboardButton("📤 2. EXPORT DATA SAYA", callback_data="export_data_saya")],
            [InlineKeyboardButton("🗑️ 3. HAPUS PER SATU", callback_data="hapus_satu_data_saya")],
            [InlineKeyboardButton("⬅️ 4. KEMBALI", callback_data="back_main")]
        ])
        await query.edit_message_text(text, reply_markup=kb)
        # kirim detail 10 terbaru
        for rid, disp, kab, kec, kel in rows:
            if disp:
                try:
                    await context.bot.send_message(chat_id=user_id, text=f"ID {rid}\n```\n{disp}\n```", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_data_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_data_{rid}")]]))
                except:
                    await context.bot.send_message(chat_id=user_id, text=f"ID {rid} - {disp[:500]}")

    elif data == "cari_data_saya":
        context.user_data["mode"] = "cari_data_saya"
        await query.edit_message_text(
            "🔍 CARI DATA SAYA\n\nKetik yang mau dicari:\n- NIK, Nama, KAB, KEC, KEL\n- KPJ, PT, Saldo\n- Kata apapun\n\nContoh: DEPOK atau LIA atau 320123...\n\nKetik sekarang:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_hasil_data_saya")]])
        )

    elif data == "export_data_saya":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir, display_text FROM data_saya WHERE user_id=? ORDER BY id ASC", (user_id,))
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

    elif data == "menu_history":
        is_admin_hist = check_is_admin(user_id)
        if is_admin_hist:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 1. FORMAT", callback_data="history_format")],
                [InlineKeyboardButton("📑 2. FORMAT+AKUN", callback_data="history_full")],
                [InlineKeyboardButton("🔢 3. CEK KODE SAJA", callback_data="history_kode")],
                [InlineKeyboardButton("🗑️ 4. DATA YG DI HAPUS", callback_data="history_deleted")],
                [InlineKeyboardButton("💰 5. HISTORY JUALAN (ADMIN)", callback_data="history_jualan_admin")],
                [InlineKeyboardButton("⬅️ 6. KEMBALI", callback_data="back_main")]
            ])
            await query.edit_message_text("🕘 **HISTORY**\n\nPilih menu:\n1. Format (yang sudah dijual)\n2. Format+Akun (yang sudah dijual)\n3. Cek Kode saja\n4. Data yg dihapus (Recycle Bin)\n5. **History Jualan Sesama Admin**\n6. Kembali", reply_markup=kb, parse_mode="Markdown")
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📄 1. FORMAT", callback_data="history_format")],
                [InlineKeyboardButton("📑 2. FORMAT+AKUN", callback_data="history_full")],
                [InlineKeyboardButton("🔢 3. CEK KODE SAJA", callback_data="history_kode")],
                [InlineKeyboardButton("🗑️ 4. DATA YG DI HAPUS", callback_data="history_deleted")],
                [InlineKeyboardButton("⬅️ 5. KEMBALI", callback_data="back_main")]
            ])
            await query.edit_message_text("🕘 **HISTORY**\n\nPilih menu:\n1. Format (yang sudah dijual)\n2. Format+Akun (yang sudah dijual)\n3. Cek Kode saja\n4. Data yg dihapus (Recycle Bin)\n5. Kembali", reply_markup=kb, parse_mode="Markdown")

    elif data == "history_format":
        is_admin_hist_f = check_is_admin(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if is_admin_hist_f:
            try:
                c.execute("SELECT user_id FROM admins")
                db_admins = [r[0] for r in c.fetchall()]
            except:
                db_admins = []
            all_admins_list = list(set(ADMIN_IDS + db_admins))
            if all_admins_list:
                ph = ",".join(["?" for _ in all_admins_list])
                c.execute(f"SELECT id, kode, display_format, created_at, user_id FROM hasil_format WHERE status='terjual' AND user_id IN ({ph}) ORDER BY id DESC", tuple(all_admins_list))
            else:
                c.execute("SELECT id, kode, display_format, created_at, user_id FROM hasil_format WHERE status='terjual' AND user_id=? ORDER BY id DESC", (user_id,))
        else:
            c.execute("SELECT id, kode, display_format, created_at, user_id FROM hasil_format WHERE user_id=? AND status='terjual' ORDER BY id DESC", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("📄 Belum ada FORMAT yang dijual.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
            return
        await query.edit_message_text(f"📄 HISTORY FORMAT - {len(rows)} terjual:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
        for row in rows:
            if len(row)==5:
                rid, kode, disp, created, owner_id = row
            else:
                rid, kode, disp, created = row
                owner_id = user_id
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
        is_admin_hist_full = check_is_admin(user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if is_admin_hist_full:
            try:
                c.execute("SELECT user_id FROM admins")
                db_admins = [r[0] for r in c.fetchall()]
            except:
                db_admins = []
            all_admins_list = list(set(ADMIN_IDS + db_admins))
            if all_admins_list:
                ph = ",".join(["?" for _ in all_admins_list])
                c.execute(f"SELECT id, kode, display_full, created_at, user_id FROM hasil_format WHERE status='terjual' AND user_id IN ({ph}) ORDER BY id DESC", tuple(all_admins_list))
            else:
                c.execute("SELECT id, kode, display_full, created_at, user_id FROM hasil_format WHERE status='terjual' AND user_id=? ORDER BY id DESC", (user_id,))
        else:
            c.execute("SELECT id, kode, display_full, created_at, user_id FROM hasil_format WHERE user_id=? AND status='terjual' ORDER BY id DESC", (user_id,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("📑 Belum ada FORMAT+AKUN yang dijual.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
            return
        await query.edit_message_text(f"📑 HISTORY FORMAT+AKUN - {len(rows)} terjual:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_history")]]))
        for row in rows:
            if len(row)==5:
                rid, kode, disp_full, created, owner_id = row
            else:
                rid, kode, disp_full, created = row
                owner_id = user_id
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

    elif data == "menu_admin":
        # Cek apakah user admin (dari ADMIN_IDS atau dari tabel admins)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        admin_rows = c.fetchall()
        admin_ids_db = [r[0] for r in admin_rows] if admin_rows else []
        conn.close()
        all_admins = list(set(ADMIN_IDS + admin_ids_db))
        if user_id not in all_admins:
            await query.edit_message_text("⛔ Bukan admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))
            return
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hasil_format")
        total_format = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE status='terjual'")
        total_terjual = c.fetchone()[0]
        conn.close()
        
        text = f"👑 **PANEL ADMIN**\n\n👥 Total User: {total_users}\n📄 Total Format: {total_format}\n💰 Terjual: {total_terjual}\n👑 Total Admin: {len(all_admins)}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 1. CEK USER AKTIF", callback_data="admin_cek_user")],
            [InlineKeyboardButton("🗑️ 2. HAPUS USER", callback_data="admin_hapus_user")],
            [InlineKeyboardButton("➕ 3. TAMBAH ADMIN", callback_data="admin_tambah_admin")],
            [InlineKeyboardButton("➖ 4. HAPUS ADMIN", callback_data="admin_hapus_admin")],
            [InlineKeyboardButton("📢 5. BROADCAST", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📦 6. TAMBAH PAKET USER", callback_data="admin_tambah_paket")],
            [InlineKeyboardButton("❌ 7. HAPUS PAKET USER", callback_data="admin_hapus_paket")],
            [InlineKeyboardButton("⬅️ 8. KEMBALI", callback_data="back_main")]
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "admin_cek_user":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, username, total_format FROM users ORDER BY total_format DESC LIMIT 30")
        rows = c.fetchall()
        c.execute("SELECT user_id FROM admins")
        admin_rows = c.fetchall()
        admin_ids_db = [r[0] for r in admin_rows]
        all_admins = list(set(ADMIN_IDS + admin_ids_db))
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada user.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
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

    elif data == "admin_hapus_user":
        context.user_data["mode"] = "admin_hapus_user"
        await query.edit_message_text(
            "🗑️ **HAPUS USER**\n\nKirim ID user yang mau dihapus.\nContoh: `123456789`\n\nBot akan hapus semua format & history user tersebut.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_admin")]]),
            parse_mode="Markdown"
        )

    elif data == "admin_tambah_admin":
        context.user_data["mode"] = "admin_tambah_admin"
        await query.edit_message_text(
            "➕ **TAMBAH ADMIN**\n\nKirim ID user yang mau dijadikan admin.\nContoh: `123456789`\n\nCek ID via @userinfobot",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_admin")]]),
            parse_mode="Markdown"
        )

    elif data == "admin_hapus_admin":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        rows = c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada admin tambahan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
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

    elif data == "admin_tambah_paket":
        context.user_data["mode"] = "admin_tambah_paket"
        await query.edit_message_text(
            "📦 **TAMBAH PAKET USER**\n\n"
            "Kirim format: `ID_USER JUMLAH_HARI`\n"
            "Contoh: `123456789 30` = paket 30 hari\n"
            "Contoh: `123456789 UNLIMITED` = paket unlimited\n\n"
            "User akan otomatis bisa akses BUAT FORMAT.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BATAL", callback_data="menu_admin")]]),
            parse_mode="Markdown"
        )

    elif data == "admin_hapus_paket":
        context.user_data["mode"] = "admin_hapus_paket"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, paket_name, expired_at FROM paket_user LIMIT 30")
        rows = c.fetchall()
        conn.close()
        if not rows:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]])
            await query.edit_message_text("❌ Belum ada user yang punya paket.", reply_markup=kb)
            return
        msg = "❌ **HAPUS PAKET USER**\n\nPilih atau ketik ID manual:\n\n"
        kb_rows = []
        for uid, pname, exp in rows[:15]:
            msg += f"• {uid} - {pname} ({exp})\n"
            kb_rows.append([InlineKeyboardButton(f"❌ Hapus {uid}", callback_data=f"admin_del_paket_{uid}")])
        kb_rows.append([InlineKeyboardButton("⌨️ KETIK MANUAL", callback_data="admin_hapus_paket_manual")])
        kb_rows.append([InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="Markdown")

    elif data.startswith("admin_del_paket_"):
        del_id = int(data.split("_")[-1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM paket_user WHERE user_id=?", (del_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ Paket user {del_id} dihapus. User kembali TERKUNCI.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))

    elif data == "admin_hapus_paket_manual":
        context.user_data["mode"] = "admin_hapus_paket"
        await query.edit_message_text(
            "❌ **HAPUS PAKET USER - MANUAL**\n\nKirim ID user yang mau dihapus paketnya.\nContoh: `123456789`",
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

    # === LOCK untuk mode BUAT FORMAT ===
    if mode in ["manual", "excel", "manual_kode"] or text.strip().count("\n") >= 10:
        # jika mode buat format tapi paket tidak aktif, tolak (kecuali admin)
        if mode in ["manual", "excel", "manual_kode"] and not is_paket_aktif(user_id):
            await update.message.reply_text(
                "🔒 FITUR TERKUNCI\n\nuntuk mengaktifkan menu ini silahkan hubungi admin dan memilih paket yang tersedia.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 HUBUNGI ADMIN", callback_data="hubungi_admin")],
                    [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
                ])
            )
            context.user_data["mode"] = None
            return
    # ===== DATA SAYA MODES - BARU =====
    if mode == "data_saya_manual":
        parsed = parse_jmo_block(text, f"DATA-{user_id}")
        if not parsed:
            await update.message.reply_text("❌ Minimal 13 baris! Contoh:\nDEPOK\nCILODONG\nKALIBARU\n10.000.000\nPEREMPUAN 1992\n2019\n23****\n01-07-2022\nINDONESIA MERDEKA\n320123...\n190003...\nLIA\n12-12-1990", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
        await update.message.reply_text(f"✅ DATA SAYA disimpan!\n\n{disp_full}", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
        await update.message.reply_text(f"✅ DATA SAYA ID {rid} diupdate!\n\n{disp_full}", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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


    # ===== ADMIN MODES =====
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

    if mode == "admin_tambah_paket":
        # Format: ID HARI atau ID UNLIMITED
        try:
            parts = text.strip().split()
            if len(parts) < 1:
                raise ValueError()
            target_id = int(re.search(r"\d+", parts[0]).group())
            hari_raw = parts[1].upper() if len(parts) > 1 else "30"
            from datetime import timedelta
            if hari_raw == "UNLIMITED":
                expired_at = "UNLIMITED"
                paket_name = "UNLIMITED"
            else:
                hari = int(re.search(r"\d+", hari_raw).group())
                expired_at = (datetime.now() + timedelta(days=hari)).isoformat()
                paket_name = f"{hari}HARI"
        except Exception as e:
            await update.message.reply_text(f"❌ Format salah: {e}\nContoh: 123456789 30 atau 123456789 UNLIMITED")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO paket_user (user_id, paket_name, added_by, created_at, expired_at) VALUES (?,?,?,?,?)",
                  (target_id, paket_name, user_id, datetime.now().isoformat(), expired_at))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ Paket {paket_name} untuk user {target_id} berhasil ditambahkan!\nExpired: {expired_at}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        # Notif ke user
        try:
            await context.bot.send_message(chat_id=target_id, text=f"🎉 PAKET AKTIF!\n\nPaket {paket_name} Anda sudah diaktifkan admin.\nSekarang menu BUAT FORMAT sudah terbuka! Silahkan klik /start", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
        except:
            pass
        return

    if mode == "admin_hapus_paket":
        try:
            target_id = int(re.search(r"\d+", text).group())
        except:
            await update.message.reply_text("❌ ID tidak valid. Contoh: 123456789")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM paket_user WHERE user_id=?", (target_id,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        if deleted:
            await update.message.reply_text(f"✅ Paket user {target_id} dihapus. Fitur BUAT FORMAT kembali TERKUNCI.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
        else:
            await update.message.reply_text(f"❌ User {target_id} tidak punya paket.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_admin")]]))
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
        await update.message.reply_text("Template disimpan", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
            await update.message.reply_text(f"KODE DISIMPAN\nKode aktif: {kode_aktif} ({kode_pos})", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
            await update.message.reply_text("Minimal 9 baris", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
        await update.message.reply_text(f"ID {rid} diedit\n{disp_format}", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
            is_admin_search = check_is_admin(user_id)
            is_cari_akun = "akun" in mode
            if is_cari_akun:
                if is_admin_search:
                    try:
                        c.execute("SELECT user_id FROM admins")
                        db_a = [r[0] for r in c.fetchall()]
                    except:
                        db_a = []
                    all_a = list(set(ADMIN_IDS + db_a))
                    ph = ",".join(["?" for _ in all_a]) if all_a else ""
                    if all_a:
                        sql = f"""SELECT id, display_full, kode FROM hasil_format 
                                     WHERE status='ready' AND user_id IN ({ph})
                                     AND (({kode_conds}) OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_full LIKE ? OR nik_lengkap LIKE ? OR kpj_lengkap LIKE ? OR nama_lengkap LIKE ? OR tgl_lahir LIKE ?)
                                     ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC"""
                        params = all_a + likes_code_patterns + [like, like, like, like, like, like, like, like, like, like]
                    else:
                        sql = f"""SELECT id, display_full, kode FROM hasil_format WHERE 1=0"""
                        params = []
                else:
                    sql = f"""SELECT id, display_full, kode FROM hasil_format 
                                 WHERE user_id=? AND status='ready' 
                                 AND (({kode_conds}) OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_full LIKE ? OR nik_lengkap LIKE ? OR kpj_lengkap LIKE ? OR nama_lengkap LIKE ? OR tgl_lahir LIKE ?)
                                 ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC"""
                    params = [user_id] + likes_code_patterns + [like, like, like, like, like, like, like, like, like, like]
            else:
                if is_admin_search:
                    try:
                        c.execute("SELECT user_id FROM admins")
                        db_a = [r[0] for r in c.fetchall()]
                    except:
                        db_a = []
                    all_a = list(set(ADMIN_IDS + db_a))
                    ph = ",".join(["?" for _ in all_a]) if all_a else ""
                    if all_a:
                        sql = f"""SELECT id, display_format, kode, display_full FROM hasil_format 
                                     WHERE status='ready' AND user_id IN ({ph})
                                     AND (({kode_conds}) OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_format LIKE ? OR display_full LIKE ?)
                                     ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC"""
                        params = all_a + likes_code_patterns + [like, like, like, like, like, like, like]
                    else:
                        sql = f"""SELECT id, display_format, kode, display_full FROM hasil_format WHERE 1=0"""
                        params = []
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
            await update.message.reply_text("Minimal 9 baris", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
        await update.message.reply_text(f"ID {rid} diedit\n{disp_format}", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
                await update.message.reply_text(f"🔍 Tidak ada hasil untuk '{keyword}'\nCoba cari dengan:\n- Kode: ASD 001\n- Nama: RIO\n- KAB: JAKARTA\n- KEC, KEL, dll.", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
                return
            
            await update.message.reply_text(f"🔍 Ditemukan {len(rows)} hasil untuk '{keyword}'\nUrutan terkecil→terbesar:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 CARI LAGI", callback_data="cari_format" if not is_akun_search else "cari_akun")]]))
            
            for rid, disp_full, kode, disp_format in rows:
                disp = disp_full if is_akun_search else disp_format
                header = f"{kode} (ID {rid})"
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
    # If mode is data_saya_excel, handle separately
    if mode == "data_saya_excel":
        try:
            file = await update.message.document.get_file()
            tmp = f"/tmp/data_saya_{user_id}.xlsx"
            await file.download_to_drive(tmp)
            import pandas as pd
            df = pd.read_excel(tmp)
            # Expect columns A-M as described
            saved=0
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            try:
                template, _, _, _, _ = get_setting(user_id)
            except:
                template = DEFAULT_TEMPLATE
            for _, row in df.iterrows():
                try:
                    kab = str(row.iloc[0]) if len(row)>0 else ""
                    kec = str(row.iloc[1]) if len(row)>1 else ""
                    kel = str(row.iloc[2]) if len(row)>2 else ""
                    saldo = str(row.iloc[3]) if len(row)>3 else ""
                    kelamin = str(row.iloc[4]) if len(row)>4 else ""
                    kpj = str(row.iloc[5]) if len(row)>5 else ""
                    sensor = str(row.iloc[6]) if len(row)>6 else ""
                    it = str(row.iloc[7]) if len(row)>7 else ""
                    pt = str(row.iloc[8]) if len(row)>8 else ""
                    nik = str(row.iloc[9]) if len(row)>9 else ""
                    kpj_l = str(row.iloc[10]) if len(row)>10 else ""
                    nama = str(row.iloc[11]) if len(row)>11 else ""
                    tgl = str(row.iloc[12]) if len(row)>12 else ""
                    if not kab or kab=="nan":
                        continue
                    block_text = f"{kab}\n{kec}\n{kel}\n{saldo}\n{kelamin}\n{kpj}\n{sensor}\n{it}\n{pt}\n{nik}\n{kpj_l}\n{nama}\n{tgl}"
                    parsed = parse_jmo_block(block_text, f"DATA-{user_id}")
                    if not parsed:
                        continue
                    disp_f, disp_full = build_display(parsed, template, "atas")
                    c.execute('''INSERT INTO data_saya (user_id, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik_lengkap, kpj_lengkap, nama_lengkap, tgl_lahir, raw_text, display_text, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                              (user_id, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, nik, kpj_l, nama, tgl, block_text, disp_full, datetime.now().isoformat()))
                    saved+=1
                except Exception as e:
                    print(f"row error {e}")
                    continue
            conn.commit()
            conn.close()
            context.user_data["mode"]=None
            await update.message.reply_text(f"✅ DATA SAYA Excel masuk {saved} data!", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
            return
        except Exception as e:
            await update.message.reply_text(f"❌ Gagal baca Excel DATA SAYA: {e}", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
            context.user_data["mode"]=None
            return

    # lanjut ke handler lama - buat_excel dll

    user_id = update.effective_user.id
    doc_name = update.message.document.file_name or ""
    if not doc_name.lower().endswith((".xlsx", ".xls")):
        await update.message.reply_text("File harus .xlsx", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
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
            vals = [str(v).strip().upper() if pd.notna(v) and str(v).strip().lower() != "nan" else "" for v in row.tolist()]
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
        await update.message.reply_text(f"✅ {saved} data masuk", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
    except Exception as e:
        await update.message.reply_text(f"Gagal: {e}", reply_markup=main_menu_keyboard(check_is_admin(target_id)))
    finally:
        try:
            os.remove(path)
        except:
            pass


# ===== COMMAND HANDLER TAMBAHAN =====
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user = update.effective_user
    if user is None:
        return
    user_id = user.id
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
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(check_is_admin(target_id)))

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
    user = update.effective_user
    init_db()
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
    try:
        c.execute("SELECT paket_name, expired_at FROM paket_user WHERE user_id=?", (user.id,))
        paket_row = c.fetchone()
    except:
        paket_row = None
    conn.close()
    all_admins = list(set(ADMIN_IDS + admin_ids_db))
    is_admin = user.id in all_admins
    username_db = urow[0] if urow and urow[0] else user.username or ""
    saldo_db = urow[1] if urow and urow[1] else "0"
    nama_db = urow[3] if urow and len(urow) > 3 and urow[3] else user.first_name or "SAHABAT"
    
    if is_admin:
        expired_display = "UNLIMITED ADMIN"
        status_display = "🟢 AKTIF (ADMIN)"
        paket_display = "ADMIN"
    else:
        if paket_row:
            paket_name, expired_at = paket_row
            if expired_at and str(expired_at).upper() == "UNLIMITED":
                expired_display = "UNLIMITED"
            else:
                try:
                    from datetime import datetime as _dt
                    dt = _dt.fromisoformat(expired_at)
                    expired_display = dt.strftime("%d-%m-%Y %H:%M")
                    if _dt.now() > dt:
                        expired_display += " (EXPIRED)"
                except:
                    expired_display = str(expired_at)
            if is_paket_aktif(user.id):
                status_display = "🟢 AKTIF"
            else:
                status_display = "🔴 TIDAK AKTIF (EXPIRED)"
            paket_display = paket_name
        else:
            expired_display = "-"
            status_display = "🔴 TIDAK AKTIF (Belum diaktifkan admin)"
            paket_display = "-"
    
    username_display = f"@{username_db}" if username_db else f"@{user.username or 'user'}"
    profil_text = (
        f"👤 PROFIL USER\n\n"
        f"🆔 Telegram ID : {user.id}\n"
        f"👤 Nama : {nama_db}\n"
        f"📱 Username : {username_display}\n"
        f"💰 Saldo : Rp {saldo_db}\n"
        f"📦 Paket : {paket_display}\n\n"
        f"📅 Berakhir : {expired_display}\n"
        f"📊 Status : {status_display}"
    )
    await update.message.reply_text(profil_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]]))

async def buat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_paket_aktif(user_id):
        await update.message.reply_text(
            "🔒 FITUR TERKUNCI\n\nuntuk mengaktifkan menu ini silahkan hubungi admin dan memilih paket yang tersedia.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 HUBUNGI ADMIN", callback_data="hubungi_admin")],
                [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
            ])
        )
        return
    await update.message.reply_text("⌨️ BUAT FORMAT\nPilih metode:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ MANUAL", callback_data="buat_manual"), InlineKeyboardButton("📊 EXCEL", callback_data="buat_excel")],
        [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
    ]))

async def hasil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 HASIL FORMAT", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format"), InlineKeyboardButton("📑 HASIL AKUN", callback_data="menu_hasil_full")],
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
        [InlineKeyboardButton("📦 6. TAMBAH PAKET USER", callback_data="admin_tambah_paket")],
        [InlineKeyboardButton("❌ 7. HAPUS PAKET USER", callback_data="admin_hapus_paket")],
        [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
    ]))

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
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.post_init = setup_commands
    print("Bot jalan dengan COMMAND HANDLER...")
    print("Menu hot: /start, /menu, /help, /profil, /buat, /hasil, /setting, /history, /admin")
    app.run_polling()

if __name__ == "__main__":
    main()
