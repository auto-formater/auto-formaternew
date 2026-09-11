import os, re, sqlite3
from datetime import datetime
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# === RAILWAY VARIABLES - JANGAN HARDCODE DI FILE ===
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "GANTI_DENGAN_TOKEN_BOTFATHER"
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
if ADMIN_IDS_RAW:
    try:
        ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]
    except:
        ADMIN_IDS = []
else:
    ADMIN_IDS = []
DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_PATH = os.getenv("DB_PATH", "bot_data.db")
GARIS = "___________________"
DEFAULT_TEMPLATE = """SEX {KODE_ATAS}
KAB : {KAB}
KEC : {KEC}
KEL : {KEL}
SALDO : {SALDO}
KELAMIN : {KELAMIN}
KPJ : {KPJ}
SENSOR: {SENSOR}
IT : {IURAN_T}
PT : {PT}
DPT JMO LASIK"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, join_date TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_by INTEGER, added_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, template TEXT, kode_atas TEXT, kode_bawah TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS hasil_format (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, content_raw TEXT, content_formatted TEXT, content_display TEXT, kode TEXT, kab TEXT, kec TEXT, kel TEXT, saldo TEXT, kelamin TEXT, kpj TEXT, sensor TEXT, iuran_t TEXT, pt TEXT, akun TEXT, created_at TEXT, sex_code TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS hasil_akun (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, kode TEXT, akun TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS riwayat (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tipe TEXT, content_raw TEXT, content TEXT, content_formatted TEXT, content_display TEXT, kode TEXT, kab TEXT, kec TEXT, kel TEXT, saldo TEXT, kelamin TEXT, kpj TEXT, sensor TEXT, iuran_t TEXT, pt TEXT, akun TEXT, sex_code TEXT, deleted_at TEXT, original_id INTEGER)""")
    conn.commit()
    conn.close()

def get_setting(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT template, kode_atas, kode_bawah FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"template": row[0] or DEFAULT_TEMPLATE, "kode_atas": row[1] or "", "kode_bawah": row[2] or ""}
    return {"template": DEFAULT_TEMPLATE, "kode_atas": "", "kode_bawah": ""}

def save_setting(user_id, template=None, kode_atas=None, kode_bawah=None):
    cur = get_setting(user_id)
    if template is None: template = cur["template"]
    if kode_atas is None: kode_atas = cur["kode_atas"]
    if kode_bawah is None: kode_bawah = cur["kode_bawah"]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (user_id, template, kode_atas, kode_bawah) VALUES (?,?,?,?)", (user_id, template, kode_atas, kode_bawah))
    conn.commit()
    conn.close()

def get_next_sex_code(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    max_code = 0
    try:
        c.execute("SELECT MAX(CAST(sex_code AS INTEGER)) FROM hasil_format WHERE user_id=?", (user_id,))
        r = c.fetchone()[0]
        if r is not None:
            max_code = max(max_code, int(str(r).strip()))
    except: pass
    try:
        c.execute("SELECT MAX(CAST(sex_code AS INTEGER)) FROM riwayat WHERE user_id=?", (user_id,))
        r = c.fetchone()[0]
        if r is not None:
            max_code = max(max_code, int(str(r).strip()))
    except: pass
    conn.close()
    try:
        setting = get_setting(user_id)
        ka = setting.get('kode_atas','')
        if ka and ka.strip().isdigit():
            base = int(ka.strip())
            if base > max_code:
                max_code = base - 1
    except: pass
    return max_code + 1

def get_all_admins():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT user_id FROM admins")
        rows = c.fetchall()
        db_admins = [r[0] for r in rows]
    except:
        db_admins = []
    conn.close()
    return list(set(ADMIN_IDS + db_admins))

def is_admin(user_id):
    return user_id in get_all_admins()

def add_admin_db(new_admin_id, added_by):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?,?,?)", (new_admin_id, added_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def remove_admin_db(admin_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id=?", (admin_id,))
    conn.commit()
    conn.close()

def add_user(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?,?,?,?)", (user.id, user.username, user.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def make_display_text(detail, sex_code="005"):
    s = f"""        SEX {sex_code}
___________________

📍 KAB : {detail['kab'].upper()}
📍 KEC : {detail['kec'].upper()}
📍 KEL : {detail['kel'].upper()}

💰 SALDO : {detail['saldo']}

🆔 KELAMIN : {detail['kelamin']}
💳 KPJ : {detail['kpj']}
📡 SENSOR: {detail['sensor']}
📅 IT : {detail['iuran_t']}
🏛️ PT : {detail['pt'].upper()}

🏆 DPT JMO LASIK ✅"""
    return s

def move_to_riwayat(user_id, tipe, data_row):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if tipe == "format":
        c.execute("""INSERT INTO riwayat (user_id, tipe, content_raw, content, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, sex_code, deleted_at, original_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (user_id, tipe, data_row.get('content_raw',''), data_row.get('content',''), data_row.get('content_formatted',''), data_row.get('content_display',''), data_row.get('kode',''), data_row.get('kab',''), data_row.get('kec',''), data_row.get('kel',''), data_row.get('saldo',''), data_row.get('kelamin',''), data_row.get('kpj',''), data_row.get('sensor',''), data_row.get('iuran_t',''), data_row.get('pt',''), data_row.get('akun',''), data_row.get('sex_code','005'), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data_row.get('id',0)))
    else:
        c.execute("""INSERT INTO riwayat (user_id, tipe, content_raw, content, kode, akun, deleted_at, original_id, content_display, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (user_id, tipe, data_row.get('content',''), data_row.get('content',''), data_row.get('kode',''), data_row.get('akun',''), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data_row.get('id',0), data_row.get('content',''), "005"))
    conn.commit()
    conn.close()

def parse_jmo_block(text_block, user_id, sex_counter=1):
    lines = [l.strip() for l in text_block.strip().splitlines()]
    clean = [l for l in lines if l != ""]
    if len(clean) < 9:
        return None, f"Minimal 9 baris, kamu kirim {len(clean)}"
    raw_format_lines = clean[:9]
    raw_akun_lines = clean[9:]
    kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt = raw_format_lines[:9]
    raw_format = "\n".join(raw_format_lines)
    raw_akun = "\n".join(raw_akun_lines) if raw_akun_lines else "-"
    kode = ""
    if raw_akun_lines:
        for l in raw_akun_lines:
            if re.match(r"^\d{16}$", l.replace(" ","")):
                kode = l; break
        if not kode:
            kode = raw_akun_lines[0] if raw_akun_lines else sensor
    else:
        kode = sensor
    sex_code = f"{sex_counter:03d}" if isinstance(sex_counter, int) else "005"
    detail_temp = {"kab": kab, "kec": kec, "kel": kel, "saldo": saldo, "kelamin": kelamin, "kpj": kpj, "sensor": sensor, "iuran_t": iuran_t, "pt": pt}
    display_text = make_display_text(detail_temp, sex_code)
    setting = get_setting(user_id)
    try:
        formatted_template = setting["template"].format(KAB=kab, KEC=kec, KEL=kel, SALDO=saldo, KELAMIN=kelamin, KPJ=kpj, SENSOR=sensor, IURAN_T=iuran_t, PT=pt, AKUN=raw_akun, KODE_ATAS=sex_code)
    except:
        formatted_template = display_text + f"\n\n{raw_akun}"
    parts = []
    if setting["kode_atas"]:
        parts.append(setting["kode_atas"])
        parts.append(GARIS)
    parts.append(formatted_template)
    if setting["kode_bawah"]:
        parts.append(GARIS)
        parts.append(setting["kode_bawah"])
    full_formatted = "\n".join(parts)
    detail = {"kab": kab, "kec": kec, "kel": kel, "saldo": saldo,"kelamin": kelamin, "kpj": kpj, "sensor": sensor,"iuran_t": iuran_t, "pt": pt,"akun": raw_akun,"raw_format": raw_format,"raw_akun": raw_akun,"content_formatted": full_formatted,"content_display": display_text,"kode": kode,"sex_code": sex_code}
    return detail, None

def process_blocks(full_text, user_id):
    blocks = re.split(r'\n\s*\n', full_text.strip())
    if len(blocks)==1:
        lines=[l for l in full_text.strip().splitlines() if l.strip()!=""]
        if len(lines)>14 and len(lines)%13==0:
            blocks=["\n".join(lines[i:i+13]) for i in range(0,len(lines),13)]
    res=[]
    start_code = get_next_sex_code(user_id)
    counter = start_code
    for b in blocks:
        if not b.strip(): continue
        p,e=parse_jmo_block(b,user_id, sex_counter=counter)
        res.append((p,e))
        counter+=1
    return res

# ===== INLINE MENU 2 BARIS =====
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 PROFIL", callback_data="profil"), InlineKeyboardButton("⌨️ BIKIN FORMAT", callback_data="bikin_format")],
        [InlineKeyboardButton("📄 HASIL FORMAT", callback_data="hasil_format"), InlineKeyboardButton("💳 HASIL AKUN", callback_data="hasil_akun")],
        [InlineKeyboardButton("⚙️ SETTING", callback_data="setting"), InlineKeyboardButton("📁 DATA SAYA", callback_data="data_saya")],
        [InlineKeyboardButton("🕘 RIWAYAT", callback_data="riwayat"), InlineKeyboardButton("👑 PANEL ADMIN", callback_data="panel_admin")],
    ])

def bikin_format_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⌨️ MANUAL", callback_data="bf_manual"), InlineKeyboardButton("📤 Upload .xlsx", callback_data="bf_excel")],
        [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
    ])

def hasil_format_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 UTUH", callback_data="hf_utuh"), InlineKeyboardButton("🔑 KODE", callback_data="hf_kode")],
        [InlineKeyboardButton("🔍 CARI", callback_data="hf_cari"), InlineKeyboardButton("🗑️ HAPUS", callback_data="hf_hapus_menu")],
        [InlineKeyboardButton("📋 SALIN SEMUA", callback_data="hf_salin"), InlineKeyboardButton("📤 EXPORT .xlsx", callback_data="hf_export")],
        [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
    ])

def hasil_akun_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 AKUN UTUH", callback_data="ha_utuh"), InlineKeyboardButton("🔑 KODE", callback_data="ha_kode")],
        [InlineKeyboardButton("🔍 CARI", callback_data="ha_cari"), InlineKeyboardButton("🗑️ HAPUS", callback_data="ha_hapus_menu")],
        [InlineKeyboardButton("📋 SALIN SEMUA", callback_data="ha_salin"), InlineKeyboardButton("📤 EXPORT .xlsx", callback_data="ha_export")],
        [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
    ])

def setting_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 TEMPLAT", callback_data="set_templat"), InlineKeyboardButton("🔢 KODE ATAS", callback_data="set_kode_atas")],
        [InlineKeyboardButton("🔢 KODE BAWAH", callback_data="set_kode_bawah"), InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
    ])

def riwayat_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 LIHAT", callback_data="rw_lihat"), InlineKeyboardButton("🔍 CARI", callback_data="rw_cari")],
        [InlineKeyboardButton("🗑️ HAPUS SEMUA", callback_data="rw_hapus_all"), InlineKeyboardButton("♻️ PULIHKAN SEMUA", callback_data="rw_pulihkan_all")],
        [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 CEK USER", callback_data="admin_cek_user"), InlineKeyboardButton("🗑️ HAPUS USER", callback_data="admin_hapus_user")],
        [InlineKeyboardButton("➕ TAMBAH ADMIN", callback_data="admin_tambah_admin"), InlineKeyboardButton("➖ HAPUS ADMIN", callback_data="admin_hapus_admin")],
        [InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast"), InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
    ])

def four_buttons_format(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 COPY", callback_data=f"copy_format_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_format_{rid}")],
        [InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_format_{rid}"), InlineKeyboardButton("🔁 BUAT LAGI", callback_data=f"dup_format_{rid}")],
        [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
    ])

def four_buttons_akun(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 COPY", callback_data=f"copy_akun_{rid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_akun_{rid}")],
        [InlineKeyboardButton("🗑️ HAPUS", callback_data=f"del_akun_{rid}"), InlineKeyboardButton("🔁 BUAT LAGI", callback_data=f"dup_akun_{rid}")],
        [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
    ])

async def start(update, context):
    add_user(update.effective_user)
    user = update.effective_user
    first_name = user.first_name or "SAHABAT JHT"
    welcome_text = f"""🟢 MODE ON DI AKTIFKAN
━━━━━━━━━━━━━━━━━━━━━
👋 Selamat datang, {first_name}! Sukses selalu, tetap semangat dan jangan lupa bersyukur untuk hari ini. Silahkan pilih menu di bawah ini : 👇"""
    await update.message.reply_text(welcome_text, reply_markup=main_menu())

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "main":
        first_name = query.from_user.first_name or "SAHABAT JHT"
        welcome_text = f"""🟢 MODE ON DI AKTIFKAN
━━━━━━━━━━━━━━━━━━━━━
👋 Selamat datang, {first_name}! Sukses selalu, tetap semangat dan jangan lupa bersyukur untuk hari ini. Silahkan pilih menu di bawah ini : 👇"""
        await query.edit_message_text(welcome_text, reply_markup=main_menu())
        return

    if data == "profil":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT username, first_name FROM users WHERE user_id=?", (user_id,))
        row=c.fetchone()
        conn.close()
        uname = row[0] if row else "-"
        fname = row[1] if row else "-"
        await query.edit_message_text(f"👤 PROFIL\nID: {user_id}\nUsername: @{uname}\nNama: {fname}\nAdmin: {'Ya' if is_admin(user_id) else 'Tidak'}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "bikin_format":
        await query.edit_message_text("⌨️ BIKIN FORMAT", reply_markup=bikin_format_menu())
        return

    if data == "bf_manual":
        context.user_data["state"]="awaiting_manual"
        await query.edit_message_text("Kirim 13 baris (9 format + 4 akun) per data. Bisa banyak sekaligus pisah baris kosong.\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "bf_excel":
        context.user_data["state"]="awaiting_excel"
        await query.edit_message_text("📤 Upload file .xlsx sekarang\nFormat: tiap baris 13 kolom\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "hasil_format":
        await query.edit_message_text("📄 HASIL FORMAT", reply_markup=hasil_format_menu())
        return

    if data == "hf_utuh":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, content_display, kode, sex_code FROM hasil_format WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC, id ASC LIMIT 100", (user_id,))
        rows=c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada format", reply_markup=hasil_format_menu())
            return
        await query.edit_message_text(f"📋 {len(rows)} HASIL FORMAT (urut kode):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        for rid, display, kode, sex in rows:
            kb = four_buttons_format(rid)
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"{display}\n\nID:{rid} KODE:{kode}"[:4000], reply_markup=kb)
        return

    if data == "hf_kode":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, kode, content_display, sex_code FROM hasil_format WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC LIMIT 100", (user_id,))
        rows=c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada", reply_markup=hasil_format_menu())
            return
        await query.edit_message_text(f"🔑 {len(rows)} KODE:")
        for rid, kode, display, sex in rows:
            kb = four_buttons_format(rid)
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"SEX {sex} KODE:{kode}\n{display}"[:4000], reply_markup=kb)
        return

    if data == "hf_cari":
        context.user_data["state"]="awaiting_search_format"
        await query.edit_message_text("🔍 CARI FORMAT - kirim kata kunci\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "hf_hapus_menu":
        context.user_data["state"]="awaiting_delete_format_kode"
        await query.edit_message_text("🗑️ HAPUS - kirim kata kunci kode untuk hapus -> RIWAYAT\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "hf_salin":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT content_display FROM hasil_format WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC", (user_id,))
        rows=c.fetchall()
        conn.close()
        txt = "\n\n".join([r[0] for r in rows]) if rows else "Belum ada"
        await query.edit_message_text(f"📋 SALIN SEMUA:\n\n{txt}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "hf_export":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, content_display, kode, sex_code FROM hasil_format WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC", (user_id,))
        rows=c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada", reply_markup=hasil_format_menu())
            return
        df = pd.DataFrame(rows, columns=["KAB","KEC","KEL","SALDO","KELAMIN","KPJ","SENSOR","IURAN_T","PT","DISPLAY","KODE","SEX"])
        path = f"/tmp/hf_{user_id}.xlsx"
        df.to_excel(path, index=False)
        await context.bot.send_document(chat_id=query.message.chat_id, document=open(path,'rb'), filename="hasil_format.xlsx", caption="Export HASIL FORMAT")
        os.remove(path)
        return

    if data == "hasil_akun":
        await query.edit_message_text("💳 HASIL AKUN", reply_markup=hasil_akun_menu())
        return

    if data == "ha_utuh":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, content, kode FROM hasil_akun WHERE user_id=? ORDER BY id ASC LIMIT 100", (user_id,))
        rows=c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada", reply_markup=hasil_akun_menu())
            return
        await query.edit_message_text(f"💳 {len(rows)} HASIL AKUN:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        for rid, content, kode in rows:
            kb = four_buttons_akun(rid)
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"ID:{rid} KODE:{kode}\n{content}"[:4000], reply_markup=kb)
        return

    if data == "ha_kode":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, kode, content FROM hasil_akun WHERE user_id=? ORDER BY id ASC LIMIT 100", (user_id,))
        rows=c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada", reply_markup=hasil_akun_menu())
            return
        await query.edit_message_text(f"🔑 {len(rows)} AKUN KODE:")
        for rid, kode, content in rows:
            kb = four_buttons_akun(rid)
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"KODE:{kode}\n{content}"[:4000], reply_markup=kb)
        return

    if data == "ha_cari":
        context.user_data["state"]="awaiting_search_akun"
        await query.edit_message_text("🔍 CARI AKUN - kata kunci\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "ha_hapus_menu":
        context.user_data["state"]="awaiting_delete_akun_kode"
        await query.edit_message_text("🗑️ HAPUS AKUN - kata kunci\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "ha_salin":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT content FROM hasil_akun WHERE user_id=? ORDER BY id ASC", (user_id,))
        rows=c.fetchall()
        conn.close()
        txt = "\n\n".join([r[0] for r in rows]) if rows else "Belum ada"
        await query.edit_message_text(f"📋 SALIN AKUN:\n{txt}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "ha_export":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT content, kode FROM hasil_akun WHERE user_id=? ORDER BY id ASC", (user_id,))
        rows=c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Belum ada", reply_markup=hasil_akun_menu())
            return
        df = pd.DataFrame(rows, columns=["AKUN","KODE"])
        path = f"/tmp/ha_{user_id}.xlsx"
        df.to_excel(path, index=False)
        await context.bot.send_document(chat_id=query.message.chat_id, document=open(path,'rb'), filename="hasil_akun.xlsx")
        os.remove(path)
        return

    if data.startswith("copy_format_"):
        rid = int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        q = "SELECT content_display FROM hasil_format WHERE id=?" if is_admin(user_id) else "SELECT content_display FROM hasil_format WHERE id=? AND user_id=?"
        params = (rid,) if is_admin(user_id) else (rid, user_id)
        c.execute(q, params)
        row=c.fetchone()
        conn.close()
        if row:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"📋 COPY ID {rid}:\n\n{row[0]}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data.startswith("del_format_"):
        rid = int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        if is_admin(user_id):
            c.execute("SELECT * FROM hasil_format WHERE id=?", (rid,))
        else:
            c.execute("SELECT * FROM hasil_format WHERE id=? AND user_id=?", (rid, user_id))
        cols=[d[0] for d in c.description]
        row=c.fetchone()
        if row:
            d=dict(zip(cols,row))
            move_to_riwayat(d['user_id'], "format", d)
            c.execute("DELETE FROM hasil_format WHERE id=?", (rid,))
            conn.commit()
            await query.edit_message_text(f"🗑️ ID {rid} -> RIWAYAT", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        conn.close()
        return

    if data.startswith("edit_format_"):
        rid = int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT content_raw, akun FROM hasil_format WHERE id=?", (rid,))
        row=c.fetchone()
        conn.close()
        if not row:
            await query.edit_message_text("❌ Tidak ditemukan", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
            return
        context.user_data["editing_format_id"]=rid
        context.user_data["state"]="awaiting_edit_format"
        await query.edit_message_text(f"✏️ EDIT ID {rid}\nLama:\n{row[0]}\n{row[1]}\n\nKirim 13 baris baru\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data.startswith("dup_format_"):
        rid = int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT * FROM hasil_format WHERE id=?", (rid,))
        cols=[d[0] for d in c.description]
        row=c.fetchone()
        if not row:
            conn.close()
            await query.edit_message_text("❌ Tidak ditemukan", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
            return
        d=dict(zip(cols,row))
        new_code = get_next_sex_code(d['user_id'])
        detail_temp = {"kab": d['kab'], "kec": d['kec'], "kel": d['kel'], "saldo": d['saldo'], "kelamin": d['kelamin'], "kpj": d['kpj'], "sensor": d['sensor'], "iuran_t": d['iuran_t'], "pt": d['pt']}
        new_display = make_display_text(detail_temp, f"{new_code:03d}")
        setting = get_setting(d['user_id'])
        try:
            new_formatted = setting["template"].format(KAB=d['kab'], KEC=d['kec'], KEL=d['kel'], SALDO=d['saldo'], KELAMIN=d['kelamin'], KPJ=d['kpj'], SENSOR=d['sensor'], IURAN_T=d['iuran_t'], PT=d['pt'], AKUN=d['akun'], KODE_ATAS=f"{new_code:03d}")
        except:
            new_formatted = new_display + f"\n\n{d['akun']}"
        c.execute("INSERT INTO hasil_format (user_id, content, content_raw, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, created_at, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (d['user_id'], d['content_raw'], d['content_raw'], new_formatted, new_display, d['kode'], d['kab'], d['kec'], d['kel'], d['saldo'], d['kelamin'], d['kpj'], d['sensor'], d['iuran_t'], d['pt'], d['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{new_code:03d}"))
        new_id = c.lastrowid
        c.execute("INSERT INTO hasil_akun (user_id, content, kode, akun, created_at) VALUES (?,?,?,?,?)",(d['user_id'], d['akun'], d['kode'], d['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🔁 BUAT LAGI OK ID baru {new_id} SEX {new_code:03d}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        kb = four_buttons_format(new_id)
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"{new_display}\nID:{new_id}"[:4000], reply_markup=kb)
        return

    if data.startswith("copy_akun_"):
        rid=int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT content FROM hasil_akun WHERE id=?", (rid,))
        row=c.fetchone()
        conn.close()
        if row:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"📋 COPY AKUN {rid}:\n{row[0]}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data.startswith("del_akun_"):
        rid=int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT * FROM hasil_akun WHERE id=?", (rid,))
        cols=[d[0] for d in c.description]
        row=c.fetchone()
        if row:
            d=dict(zip(cols,row))
            move_to_riwayat(d['user_id'], "akun", d)
            c.execute("DELETE FROM hasil_akun WHERE id=?", (rid,))
            conn.commit()
            await query.edit_message_text(f"🗑️ Akun {rid} -> RIWAYAT", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        conn.close()
        return

    if data.startswith("edit_akun_"):
        rid=int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT content FROM hasil_akun WHERE id=?", (rid,))
        row=c.fetchone()
        conn.close()
        if not row:
            await query.edit_message_text("❌ Tidak ada", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
            return
        context.user_data["editing_akun_id"]=rid
        context.user_data["state"]="awaiting_edit_akun"
        await query.edit_message_text(f"✏️ EDIT AKUN {rid}\nLama: {row[0]}\nKirim baru", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data.startswith("dup_akun_"):
        rid=int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT * FROM hasil_akun WHERE id=?", (rid,))
        cols=[d[0] for d in c.description]
        row=c.fetchone()
        if not row:
            conn.close()
            await query.edit_message_text("❌ Tidak ada", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
            return
        d=dict(zip(cols,row))
        c.execute("INSERT INTO hasil_akun (user_id, content, kode, akun, created_at) VALUES (?,?,?,?,?)",(d['user_id'], d['content'], d['kode'], d['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        new_id=c.lastrowid
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🔁 BUAT LAGI AKUN {new_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "data_saya":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
        f=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hasil_akun WHERE user_id=?", (user_id,))
        a=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM riwayat WHERE user_id=?", (user_id,))
        rw=c.fetchone()[0]
        if is_admin(user_id):
            c.execute("SELECT COUNT(*) FROM hasil_format")
            f_all=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM hasil_akun")
            a_all=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users")
            u_all=c.fetchone()[0]
        conn.close()
        if is_admin(user_id):
            txt = f"📁 DATA SAYA (ADMIN)\nKamu: F:{f} A:{a} R:{rw}\nSemua: User:{u_all} F:{f_all} A:{a_all}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ SEMUA USER", callback_data="data_saya_all"), InlineKeyboardButton("🔍 CARI SEMUA", callback_data="data_cari_all")],
                [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
            ])
        else:
            txt = f"📁 DATA SAYA\nFormat:{f} Akun:{a} Riwayat:{rw}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]])
        await query.edit_message_text(txt, reply_markup=kb)
        return

    if data == "data_saya_all":
        if not is_admin(user_id):
            await query.edit_message_text("⛔ Hanya admin", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT user_id, username, first_name FROM users LIMIT 30")
        users=c.fetchall()
        msg="🌐 SEMUA USER:\n"
        for uid, uname, fname in users:
            c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (uid,))
            jf=c.fetchone()[0]
            msg+=f"ID:{uid} @{uname or '-'} F:{jf}\n"
        conn.close()
        await query.edit_message_text(msg[:4000], reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 FORMAT ALL", callback_data="data_saya_all_format"), InlineKeyboardButton("💳 AKUN ALL", callback_data="data_saya_all_akun")],
            [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
        ]))
        return

    if data == "data_saya_all_format":
        if not is_admin(user_id):
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, content_display, kode FROM hasil_format ORDER BY CAST(sex_code AS INTEGER) ASC LIMIT 20")
        rows=c.fetchall()
        conn.close()
        await query.edit_message_text(f"📋 FORMAT ALL {len(rows)}")
        for rid, display, kode in rows:
            kb = four_buttons_format(rid)
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"{display}\nID:{rid}"[:4000], reply_markup=kb)
        return

    if data == "data_saya_all_akun":
        if not is_admin(user_id):
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, content, kode FROM hasil_akun ORDER BY id ASC LIMIT 20")
        rows=c.fetchall()
        conn.close()
        await query.edit_message_text(f"💳 AKUN ALL {len(rows)}")
        for rid, content, kode in rows:
            kb = four_buttons_akun(rid)
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"ID:{rid} {kode}\n{content}"[:4000], reply_markup=kb)
        return

    if data == "riwayat":
        await query.edit_message_text("🕘 RIWAYAT", reply_markup=riwayat_menu())
        return

    if data == "rw_lihat":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, tipe, kode, content_display, content, deleted_at, sex_code FROM riwayat WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC LIMIT 100", (user_id,))
        rows=c.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Riwayat kosong", reply_markup=riwayat_menu())
            return
        await query.edit_message_text(f"📋 {len(rows)} RIWAYAT:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        for rid, tipe, kode, display, content, deleted_at, sex in rows:
            txt = display if tipe=="format" else content
            card = f"{txt}\n\nID:{rid} Dihapus:{deleted_at}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"restore_rw_{rid}"), InlineKeyboardButton("🗑️ HAPUS PERMANEN", callback_data=f"del_rw_{rid}")],
                [InlineKeyboardButton("📋 COPY", callback_data=f"copy_rw_{rid}"), InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
            ])
            await context.bot.send_message(chat_id=query.message.chat_id, text=card[:4000], reply_markup=kb)
        return

    if data == "rw_cari":
        context.user_data["state"]="awaiting_search_riwayat"
        await query.edit_message_text("🔍 CARI RIWAYAT - kata kunci", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "rw_hapus_all":
        await query.edit_message_text("Yakin HAPUS PERMANEN SEMUA RIWAYAT?", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ YA", callback_data="rw_hapus_all_confirm"), InlineKeyboardButton("❌ Batal", callback_data="riwayat")],
            [InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
        ]))
        return

    if data == "rw_hapus_all_confirm":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("DELETE FROM riwayat WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ Riwayat hapus permanen", reply_markup=riwayat_menu())
        return

    if data == "rw_pulihkan_all":
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT * FROM riwayat WHERE user_id=?", (user_id,))
        cols=[d[0] for d in c.description]
        rows=c.fetchall()
        for r in rows:
            d=dict(zip(cols,r))
            if d['tipe']=="format":
                c.execute("INSERT INTO hasil_format (user_id, content, content_raw, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, created_at, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (user_id, d.get('content_raw',''), d.get('content_raw',''), d.get('content_formatted',''), d.get('content_display',''), d.get('kode',''), d.get('kab',''), d.get('kec',''), d.get('kel',''), d.get('saldo',''), d.get('kelamin',''), d.get('kpj',''), d.get('sensor',''), d.get('iuran_t',''), d.get('pt',''), d.get('akun',''), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), d.get('sex_code','005')))
            else:
                c.execute("INSERT INTO hasil_akun (user_id, content, kode, akun, created_at) VALUES (?,?,?,?,?)",(user_id, d.get('content',''), d.get('kode',''), d.get('akun',''), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.execute("DELETE FROM riwayat WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"♻️ {len(rows)} dipulihkan", reply_markup=riwayat_menu())
        return

    if data.startswith("copy_rw_"):
        rid=int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT content_display, content FROM riwayat WHERE id=?", (rid,))
        row=c.fetchone()
        conn.close()
        if row:
            txt = row[0] or row[1]
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"📋 COPY RW {rid}:\n{txt}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data.startswith("del_rw_"):
        rid=int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("DELETE FROM riwayat WHERE id=?", (rid,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🗑️ RW {rid} hapus permanen", reply_markup=riwayat_menu())
        return

    if data.startswith("restore_rw_"):
        rid=int(data.split("_")[-1])
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT * FROM riwayat WHERE id=?", (rid,))
        cols=[d[0] for d in c.description]
        row=c.fetchone()
        if row:
            d=dict(zip(cols,row))
            if d['tipe']=="format":
                c.execute("INSERT INTO hasil_format (user_id, content, content_raw, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, created_at, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (user_id, d.get('content_raw',''), d.get('content_raw',''), d.get('content_formatted',''), d.get('content_display',''), d.get('kode',''), d.get('kab',''), d.get('kec',''), d.get('kel',''), d.get('saldo',''), d.get('kelamin',''), d.get('kpj',''), d.get('sensor',''), d.get('iuran_t',''), d.get('pt',''), d.get('akun',''), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), d.get('sex_code','005')))
            else:
                c.execute("INSERT INTO hasil_akun (user_id, content, kode, akun, created_at) VALUES (?,?,?,?,?)",(user_id, d.get('content',''), d.get('kode',''), d.get('akun',''), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            c.execute("DELETE FROM riwayat WHERE id=?", (rid,))
            conn.commit()
            await query.edit_message_text(f"♻️ RW {rid} dipulihkan", reply_markup=riwayat_menu())
        conn.close()
        return

    if data == "setting":
        await query.edit_message_text("⚙️ SETTING", reply_markup=setting_menu())
        return

    if data == "set_templat":
        context.user_data["state"]="awaiting_template"
        await query.edit_message_text("📝 SET TEMPLAT - kirim template baru\nGunakan {KAB} {KEC} dll\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "set_kode_atas":
        context.user_data["state"]="awaiting_kode_atas"
        await query.edit_message_text("🔢 SET KODE ATAS - kirim angka awal misal 001\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "set_kode_bawah":
        context.user_data["state"]="awaiting_kode_bawah"
        await query.edit_message_text("🔢 SET KODE BAWAH", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "panel_admin":
        if not is_admin(user_id):
            await query.edit_message_text("⛔ Bukan admin!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_user=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM admins")
        total_admin=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hasil_format")
        total_format=c.fetchone()[0]
        conn.close()
        txt = f"👑 PANEL ADMIN\nUser:{total_user} AdminDB:{total_admin} Format:{total_format}\nID:{user_id}"
        await query.edit_message_text(txt, reply_markup=admin_menu())
        return

    if data == "admin_cek_user":
        if not is_admin(user_id):
            await query.edit_message_text("⛔ Bukan admin", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT user_id, username, first_name FROM users ORDER BY user_id DESC LIMIT 20")
        rows=c.fetchall()
        msg="👥 USER AKTIF:\n"
        for uid, uname, fname in rows:
            c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (uid,))
            jf=c.fetchone()[0]
            msg+=f"ID:{uid} @{uname or '-'} F:{jf}\n"
        conn.close()
        await query.edit_message_text(msg[:4000], reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_cek_user"), InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
        ]))
        return

    if data == "admin_hapus_user":
        if not is_admin(user_id):
            return
        context.user_data["state"]="awaiting_admin_hapus_user"
        await query.edit_message_text("🗑️ HAPUS USER - kirim ID\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "admin_tambah_admin":
        if not is_admin(user_id):
            return
        context.user_data["state"]="awaiting_admin_tambah_admin"
        await query.edit_message_text("➕ TAMBAH ADMIN - kirim ID", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "admin_hapus_admin":
        if not is_admin(user_id):
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT user_id FROM admins")
        rows=c.fetchall()
        conn.close()
        txt = "Admin DB:\n" + "\n".join([str(r[0]) for r in rows]) if rows else "Belum ada admin DB"
        await query.edit_message_text(txt + "\n\nKirim ID admin hapus", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        context.user_data["state"]="awaiting_admin_hapus_admin"
        return

    if data == "admin_broadcast":
        if not is_admin(user_id):
            return
        context.user_data["state"]="awaiting_admin_broadcast"
        await query.edit_message_text("📢 BROADCAST - kirim pesan", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

    if data == "data_cari_all":
        if not is_admin(user_id):
            return
        context.user_data["state"]="awaiting_search_all_admin"
        await query.edit_message_text("🔍 CARI SEMUA USER", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]]))
        return

async def message_handler(update, context):
    user_id=update.effective_user.id
    text=update.message.text or ""
    state=context.user_data.get("state")
    if text=="/cancel":
        context.user_data["state"]=None
        await update.message.reply_text("Dibatalkan", reply_markup=main_menu())
        return
    if state=="awaiting_template":
        save_setting(user_id, template=text)
        context.user_data["state"]=None
        await update.message.reply_text("✅ Templat disimpan!", reply_markup=setting_menu())
        return
    if state=="awaiting_kode_atas":
        save_setting(user_id, kode_atas=text)
        context.user_data["state"]=None
        await update.message.reply_text(f"✅ KODE ATAS: {text}", reply_markup=setting_menu())
        return
    if state=="awaiting_kode_bawah":
        save_setting(user_id, kode_bawah=text)
        context.user_data["state"]=None
        await update.message.reply_text(f"✅ KODE BAWAH: {text}", reply_markup=setting_menu())
        return
    if state=="awaiting_search_format":
        keyword=text.lower()
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, content_display, kode FROM hasil_format WHERE user_id=?", (user_id,))
        rows=c.fetchall()
        conn.close()
        found=[r for r in rows if keyword in f"{r[1]}{r[2]}".lower()]
        if not found:
            await update.message.reply_text("Tidak ditemukan", reply_markup=hasil_format_menu())
        else:
            await update.message.reply_text(f"🔍 {len(found)} ditemukan:")
            for rid, display, kode in found[:10]:
                kb = four_buttons_format(rid)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{display}\nKODE:{kode}"[:4000], reply_markup=kb)
        context.user_data["state"]=None
        return
    if state=="awaiting_delete_format_kode":
        keyword=text.lower()
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT * FROM hasil_format WHERE user_id=?", (user_id,))
        cols=[d[0] for d in c.description]
        rows=c.fetchall()
        to_del=[]
        for r in rows:
            d=dict(zip(cols,r))
            if keyword in f"{d.get('kode','')}{d.get('content_display','')}".lower():
                to_del.append(d)
                move_to_riwayat(user_id, "format", d)
        if to_del:
            ids=[d['id'] for d in to_del]
            c.execute(f"DELETE FROM hasil_format WHERE id IN ({','.join(['?']*len(ids))})", ids)
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🗑️ {len(to_del)} -> RIWAYAT", reply_markup=hasil_format_menu())
        context.user_data["state"]=None
        return
    if state=="awaiting_search_akun":
        keyword=text.lower()
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, content, kode FROM hasil_akun WHERE user_id=?", (user_id,))
        rows=c.fetchall()
        conn.close()
        found=[r for r in rows if keyword in f"{r[1]}{r[2]}".lower()]
        if not found:
            await update.message.reply_text("Tidak ditemukan", reply_markup=hasil_akun_menu())
        else:
            await update.message.reply_text(f"🔍 {len(found)} ditemukan:")
            for rid, content, kode in found[:10]:
                kb = four_buttons_akun(rid)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"ID:{rid} KODE:{kode}\n{content}"[:4000], reply_markup=kb)
        context.user_data["state"]=None
        return
    if state=="awaiting_delete_akun_kode":
        keyword=text.lower()
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT * FROM hasil_akun WHERE user_id=?", (user_id,))
        cols=[d[0] for d in c.description]
        rows=c.fetchall()
        to_del=[]
        for r in rows:
            d=dict(zip(cols,r))
            if keyword in f"{d.get('content','')}{d.get('kode','')}".lower():
                to_del.append(d)
                move_to_riwayat(user_id, "akun", d)
        if to_del:
            ids=[d['id'] for d in to_del]
            c.execute(f"DELETE FROM hasil_akun WHERE id IN ({','.join(['?']*len(ids))})", ids)
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🗑️ {len(to_del)} -> RIWAYAT", reply_markup=hasil_akun_menu())
        context.user_data["state"]=None
        return
    if state=="awaiting_search_riwayat":
        keyword=text.lower()
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, tipe, kode, content_display, content, deleted_at FROM riwayat WHERE user_id=?", (user_id,))
        rows=c.fetchall()
        conn.close()
        found=[r for r in rows if keyword in f"{r[2]}{r[3]}{r[4]}".lower()]
        if not found:
            await update.message.reply_text("Tidak ditemukan di RIWAYAT", reply_markup=riwayat_menu())
        else:
            await update.message.reply_text(f"🔍 {len(found)} di RIWAYAT:")
            for rid, tipe, kode, display, content, deleted_at in found[:10]:
                txt = display if tipe=="format" else content
                card = f"{txt}\nID:{rid} Dihapus:{deleted_at}"
                kb=InlineKeyboardMarkup([
                    [InlineKeyboardButton("♻️ PULIHKAN", callback_data=f"restore_rw_{rid}"), InlineKeyboardButton("🗑️ HAPUS PERMANEN", callback_data=f"del_rw_{rid}")],
                    [InlineKeyboardButton("📋 COPY", callback_data=f"copy_rw_{rid}"), InlineKeyboardButton("🔙 KEMBALI MENU UTAMA", callback_data="main")]
                ])
                await context.bot.send_message(chat_id=update.effective_chat.id, text=card[:4000], reply_markup=kb)
        context.user_data["state"]=None
        return
    if state=="awaiting_search_all_admin":
        if not is_admin(user_id):
            context.user_data["state"]=None
            return
        keyword=text.lower()
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT id, content_display, kode, sex_code, user_id FROM hasil_format")
        rows=c.fetchall()
        conn.close()
        found=[r for r in rows if keyword in f"{r[1]}{r[2]}{r[3]}".lower()]
        if not found:
            await update.message.reply_text("Tidak ditemukan", reply_markup=admin_menu())
        else:
            await update.message.reply_text(f"🔍 {len(found)} di SEMUA USER:")
            for rid, display, kode, sex, uid in found[:10]:
                kb = four_buttons_format(rid)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"User:{uid} SEX:{sex} KODE:{kode}\n{display}"[:4000], reply_markup=kb)
        context.user_data["state"]=None
        return
    if state=="awaiting_admin_hapus_user":
        if not is_admin(user_id):
            context.user_data["state"]=None
            return
        try:
            target_id = int(text.strip())
        except:
            await update.message.reply_text("❌ ID harus angka!")
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE user_id=?", (target_id,))
        exists=c.fetchone()[0]
        if not exists:
            await update.message.reply_text(f"❌ User {target_id} tidak ditemukan")
            conn.close()
            context.user_data["state"]=None
            return
        c.execute("DELETE FROM hasil_format WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM hasil_akun WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM riwayat WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM settings WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM users WHERE user_id=?", (target_id,))
        c.execute("DELETE FROM admins WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User {target_id} dihapus!", reply_markup=admin_menu())
        context.user_data["state"]=None
        return
    if state=="awaiting_admin_tambah_admin":
        if not is_admin(user_id):
            context.user_data["state"]=None
            return
        try:
            target_id = int(text.strip())
        except:
            await update.message.reply_text("❌ ID harus angka!")
            return
        add_admin_db(target_id, user_id)
        await update.message.reply_text(f"✅ ID {target_id} jadi ADMIN!", reply_markup=admin_menu())
        context.user_data["state"]=None
        return
    if state=="awaiting_admin_hapus_admin":
        if not is_admin(user_id):
            context.user_data["state"]=None
            return
        try:
            target_id = int(text.strip())
        except:
            await update.message.reply_text("❌ ID harus angka!")
            return
        remove_admin_db(target_id)
        await update.message.reply_text(f"✅ Admin {target_id} dihapus!", reply_markup=admin_menu())
        context.user_data["state"]=None
        return
    if state=="awaiting_admin_broadcast":
        if not is_admin(user_id):
            context.user_data["state"]=None
            return
        broadcast_text = text
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("SELECT user_id FROM users")
        rows=c.fetchall()
        conn.close()
        success=0
        for (uid,) in rows:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 BROADCAST:\n{broadcast_text}")
                success+=1
            except:
                pass
        await update.message.reply_text(f"✅ Broadcast ke {success} user", reply_markup=admin_menu())
        context.user_data["state"]=None
        return
    if state=="awaiting_edit_format":
        editing_id = context.user_data.get("editing_format_id")
        if not editing_id:
            context.user_data["state"]=None
            return
        results=process_blocks(text,user_id)
        if not results or not results[0][0]:
            await update.message.reply_text("❌ Format tidak valid")
            return
        p,e = results[0]
        if e:
            await update.message.reply_text(f"❌ {e}")
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("UPDATE hasil_format SET content=?, content_raw=?, content_formatted=?, content_display=?, kode=?, kab=?, kec=?, kel=?, saldo=?, kelamin=?, kpj=?, sensor=?, iuran_t=?, pt=?, akun=? WHERE id=?",
                  (p['raw_format'], p['raw_format'], p['content_formatted'], p['content_display'], p['kode'], p['kab'], p['kec'], p['kel'], p['saldo'], p['kelamin'], p['kpj'], p['sensor'], p['iuran_t'], p['pt'], p['akun'], editing_id))
        conn.commit()
        conn.close()
        context.user_data["state"]=None
        context.user_data["editing_format_id"]=None
        await update.message.reply_text(f"✅ EDIT OK ID {editing_id}", reply_markup=main_menu())
        kb = four_buttons_format(editing_id)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{p['content_display']}\nID:{editing_id}"[:4000], reply_markup=kb)
        return
    if state=="awaiting_edit_akun":
        editing_id = context.user_data.get("editing_akun_id")
        if not editing_id:
            context.user_data["state"]=None
            return
        new_content = text.strip()
        import re as re2
        kode=""
        lines=[l.strip() for l in new_content.splitlines() if l.strip()!=""]
        for l in lines:
            if re2.match(r"^\d{16}$", l.replace(" ","")):
                kode=l; break
        if not kode:
            kode=lines[0] if lines else ""
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        c.execute("UPDATE hasil_akun SET content=?, kode=?, akun=? WHERE id=?", (new_content, kode, new_content, editing_id))
        conn.commit()
        conn.close()
        context.user_data["state"]=None
        context.user_data["editing_akun_id"]=None
        await update.message.reply_text(f"✅ EDIT AKUN OK ID {editing_id}", reply_markup=main_menu())
        kb = four_buttons_akun(editing_id)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"ID:{editing_id} {kode}\n{new_content}"[:4000], reply_markup=kb)
        return
    if state=="awaiting_manual":
        results=process_blocks(text,user_id)
        if not results:
            await update.message.reply_text("❌ Format tidak terbaca")
            return
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        success=0
        new_ids=[]
        for p,e in results:
            if e:
                continue
            c.execute("INSERT INTO hasil_format (user_id, content, content_raw, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, created_at, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (user_id, p['raw_format'], p['raw_format'], p['content_formatted'], p['content_display'], p['kode'], p['kab'], p['kec'], p['kel'], p['saldo'], p['kelamin'], p['kpj'], p['sensor'], p['iuran_t'], p['pt'], p['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p['sex_code']))
            nid=c.lastrowid
            new_ids.append(nid)
            c.execute("INSERT INTO hasil_akun (user_id, content, kode, akun, created_at) VALUES (?,?,?,?,?)",(user_id, p['raw_akun'], p['kode'], p['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            success+=1
        conn.commit()
        conn.close()
        context.user_data["state"]=None
        await update.message.reply_text(f"✅ Berhasil {success} data! Kode urut otomatis.", reply_markup=main_menu())
        # Kirim hasil langsung dengan 4 tombol
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        for nid in new_ids:
            c.execute("SELECT content_display, kode FROM hasil_format WHERE id=?", (nid,))
            row=c.fetchone()
            if row:
                display, kode = row
                kb = four_buttons_format(nid)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{display}\n\nID:{nid} KODE:{kode}"[:4000], reply_markup=kb)
        conn.close()
        return
    await update.message.reply_text("Pilih menu:", reply_markup=main_menu())

async def excel_handler(update, context):
    if context.user_data.get("state")!="awaiting_excel":
        await update.message.reply_text("Klik BIKIN FORMAT -> Upload .xlsx", reply_markup=main_menu())
        return
    user_id=update.effective_user.id
    file=await update.message.document.get_file()
    path=f"/tmp/temp_{user_id}.xlsx"
    await file.download_to_drive(path)
    try:
        df=pd.read_excel(path,dtype=str).fillna("")
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        success=0
        start_code = get_next_sex_code(user_id)
        new_ids=[]
        for idx,row in df.iterrows():
            vals=[str(v).strip() for v in row.tolist() if str(v).strip()!=""]
            if len(vals)<9: continue
            block="\n".join(vals)
            p,e=parse_jmo_block(block,user_id, sex_counter=start_code+idx)
            if e: continue
            c.execute("INSERT INTO hasil_format (user_id, content, content_raw, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, created_at, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (user_id, p['raw_format'], p['raw_format'], p['content_formatted'], p['content_display'], p['kode'], p['kab'], p['kec'], p['kel'], p['saldo'], p['kelamin'], p['kpj'], p['sensor'], p['iuran_t'], p['pt'], p['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p['sex_code']))
            new_ids.append(c.lastrowid)
            c.execute("INSERT INTO hasil_akun (user_id, content, kode, akun, created_at) VALUES (?,?,?,?,?)",(user_id, p['raw_akun'], p['kode'], p['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            success+=1
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ {success} data dari .xlsx (urut kode)", reply_markup=main_menu())
        # Kirim hasil dengan 4 tombol
        conn=sqlite3.connect(DB_PATH)
        c=conn.cursor()
        for nid in new_ids:
            c.execute("SELECT content_display, kode FROM hasil_format WHERE id=?", (nid,))
            row=c.fetchone()
            if row:
                display, kode = row
                kb = four_buttons_format(nid)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{display}\nID:{nid} KODE:{kode}"[:4000], reply_markup=kb)
        conn.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal: {e}")
    finally:
        if os.path.exists(path): os.remove(path)
        context.user_data["state"]=None

if __name__=="__main__":
    init_db()
    print("Bot JMO INLINE 2 baris ready - Railway Variables mode")
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, excel_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()
