
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, total_format INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, template TEXT, kode_atas TEXT DEFAULT '0000001', kode_prefix TEXT DEFAULT 'MGB', kode_pos TEXT DEFAULT 'atas')""")
    try:
        c.execute("ALTER TABLE settings ADD COLUMN kode_pos TEXT DEFAULT 'atas'")
    except:
        pass
    c.execute("""CREATE TABLE IF NOT EXISTS hasil_format (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kode TEXT, kab TEXT, kec TEXT, kel TEXT, saldo TEXT, kelamin TEXT, kpj TEXT, sensor TEXT, it TEXT, pt TEXT, akun TEXT, display_format TEXT, display_full TEXT, status TEXT DEFAULT 'ready', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, aksi TEXT, detail TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)""")
    conn.commit()
    conn.close()

def get_setting(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT template, kode_atas, kode_prefix, kode_pos FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO settings (user_id, template, kode_atas, kode_prefix, kode_pos) VALUES (?, ?, ?, ?, ?)", (user_id, DEFAULT_TEMPLATE, "0000001", "MGB", "atas"))
        conn.commit()
        template, kode_atas, kode_prefix, kode_pos = DEFAULT_TEMPLATE, "0000001", "MGB", "atas"
    else:
        if len(row) == 3:
            template, kode_atas, kode_prefix = row
            kode_pos = "atas"
        else:
            template, kode_atas, kode_prefix, kode_pos = row
            if not kode_pos:
                kode_pos = "atas"
    conn.close()
    return template, kode_atas, kode_prefix, kode_pos

def get_next_code(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    _, kode_atas, kode_prefix, _ = get_setting(user_id)
    try:
        base = int(re.search(r"\d+", kode_atas).group()) if re.search(r"\d+", kode_atas) else 1
    except:
        base = 1
    num = base + count
    return f"{kode_prefix}  {num:07d}"

def parse_jmo_block(block_text, kode):
    lines = [l.strip() for l in block_text.strip().splitlines() if l.strip()!=""]
    if len(lines) < 9:
        return None
    kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt = lines[:9]
    akun_lines = lines[9:] if len(lines) > 9 else []
    akun = "\n".join(akun_lines) if akun_lines else "-"
    return {"KAB": kab, "KEC": kec, "KEL": kel, "SALDO": saldo, "KELAMIN": kelamin, "KPJ": kpj, "SENSOR": sensor, "IT": it, "PT": pt, "KODE": kode, "AKUN": akun}

def build_display(data_dict, template, kode_pos="atas"):
    kode = data_dict.get("KODE", "")
    try:
        formatted = template.format(**data_dict)
    except:
        formatted = DEFAULT_TEMPLATE.format(**data_dict)
    
    if kode_pos == "bawah":
        lines = formatted.split("\n")
        filtered = []
        for l in lines:
            if kode in l and len(l.strip()) < 30 and ("MGB" in l or "JPG" in l or re.search(r"\d{3,}", l)):
                continue
            filtered.append(l)
        body = "\n".join(filtered).strip()
        if not body:
            body = formatted.replace(kode, "").strip()
        display_format = f"{body}\n━━━━━━━━━━━━━━━━━━━\n     {kode}"
    else:
        lines = formatted.split("\n")
        new_lines = []
        found = False
        for l in lines:
            if not found and kode in l and len(l.strip()) < 30:
                new_lines.append(f"     {kode}")
                found = True
            else:
                new_lines.append(l)
        if not found:
            new_lines = [f"     {kode}", "━━━━━━━━━━━━━━━━━━━"] + new_lines
        display_format = "\n".join(new_lines).strip()
    
    if data_dict["AKUN"] != "-":
        display_full = display_format + "\n\nAKUN:\n" + data_dict["AKUN"]
    else:
        display_full = display_format + "\n\nAKUN:\n-"
    return display_format, display_full

def main_menu_keyboard():
    # INLINE 2 BARIS di setiap menu
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 PROFIL", callback_data="menu_profil"),
         InlineKeyboardButton("⌨️ BUAT FORMAT", callback_data="menu_buat")],
        [InlineKeyboardButton("📄 HASIL FORMAT", callback_data="menu_hasil_format"),
         InlineKeyboardButton("📑 FORMAT+AKUN", callback_data="menu_hasil_full")],
        [InlineKeyboardButton("⚙️ SETTING", callback_data="menu_setting"),
         InlineKeyboardButton("🕘 HISTORY", callback_data="menu_history")],
        [InlineKeyboardButton("👑 PANEL ADMIN", callback_data="menu_admin")],
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
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()
    conn.close()

    welcome_text = (
        "🟢 MODE ON DI AKTIFKAN\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Selamat datang, {first_name}! Gimana kabarnya nih, saya berharap kabar baik-baik saja yah, tetap semangat dan jangan lupa bersyukur. Silahkan pilih menu di bawah ini : 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())

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
        await query.edit_message_text(welcome_text, reply_markup=main_menu_keyboard())
        return

    if data == "menu_profil":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
        total = c.fetchone()[0]
        conn.close()
        await query.edit_message_text(f"👤 PROFIL\nID: {user_id}\nTotal: {total}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))

    elif data == "menu_buat":
        await query.edit_message_text("⌨️ BUAT FORMAT\nPilih metode:", reply_markup=buat_menu())

    elif data == "buat_manual":
        context.user_data["mode"] = "manual"
        await query.edit_message_text(
            "⌨️ BUAT FORMAT\n\nKetik data tanpa perlu menulis KAB/KEC/KEL. Bot otomatis membaca urutannya:\n\n1️⃣ KAB\n2️⃣ KEC\n3️⃣ KEL\n4️⃣ SALDO\n5️⃣ KELAMIN\n6️⃣ KPJ\n7️⃣ SENSOR\n8️⃣ IT\n9️⃣ PT\n\nContoh:\nDEPOK\nCILODONG\nKALIBARU\n10.000.000\nPEREMPUAN 1992\n2019\n23****\n01-07-2022\nINDONESIA MERDEKA\n\nHasilnya otomatis menjadi format JMO.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_buat")]]),
        )

    elif data == "buat_excel":
        context.user_data["mode"] = "excel"
        await query.edit_message_text(
            "📊 UPLOAD FILE EXCEL\n\nUpload .xlsx (A=KAB B=KEC C=KEL D=SALDO E=KELAMIN F=KPJ G=SENSOR H=IT I=PT J=NIK K=NO_KPJ L=NAMA M=TGL)\nKirim file sekarang 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="menu_buat")]]),
        )

    elif data == "menu_hasil_format":
        # ORDER BY kode terkecil ke terbesar (ASD 001, 002, 003...)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Ambil yang ready saja, urut dari kecil ke besar berdasarkan kode angka
        c.execute("SELECT id, kode, display_format, kab, kec, kel, saldo, kelamin, kpj, pt FROM hasil_format WHERE user_id=? AND status='ready' ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC", (user_id,))
        rows = c.fetchall()
        # Fallback jika query gagal (kode format beda), pakai id ASC
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
            [InlineKeyboardButton("🗑️ HAPUS SEMUA HASIL", callback_data="hapus_semua")],
            [InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]
        ]))

    elif data == "tampilkan_format":
        # alias untuk menu_hasil_format
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
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
        # ORDER BY kode terkecil ke terbesar untuk FORMAT+AKUN juga
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
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
            [InlineKeyboardButton("🗑️ HAPUS SEMUA AKUN", callback_data="hapus_semua")],
            [InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]
        ]))

    elif data == "tampilkan_full":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
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
        c.execute("SELECT kode, display_full FROM hasil_format WHERE id=? AND user_id=?", (rid, user_id))
        row = c.fetchone()
        if row:
            kode, disp_full = row
            c.execute("UPDATE hasil_format SET status='terjual' WHERE id=?", (rid,))
            c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "JUAL", f"ID {rid} {kode}", datetime.now().isoformat()))
            conn.commit()
            await context.bot.send_message(chat_id=user_id, text=f"💰 ID {rid} terjual!\n{disp_full}")
        conn.close()

    elif data.startswith("del_"):
        rid = int(data.split("_")[1])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM hasil_format WHERE id=? AND user_id=?", (rid, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🗑️ ID {rid} dihapus.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI", callback_data="back_main")]]))

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

    elif data == "menu_setting":
        template, kode_atas, kode_prefix, kode_pos = get_setting(user_id)
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
        template, kode_atas, kode_prefix, kode_pos = get_setting(user_id)
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

    elif data == "menu_history":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 1. FORMAT", callback_data="history_format")],
            [InlineKeyboardButton("📑 2. FORMAT+AKUN", callback_data="history_full")],
            [InlineKeyboardButton("🔢 3. CEK KODE SAJA", callback_data="history_kode")],
            [InlineKeyboardButton("⬅️ 4. KEMBALI", callback_data="back_main")]
        ])
        await query.edit_message_text("🕘 **HISTORY**\n\nPilih menu:\n1. Format (yang sudah dijual)\n2. Format+Akun (yang sudah dijual)\n3. Cek Kode saja (kode yang sudah dijual)\n4. Kembali", reply_markup=kb, parse_mode="Markdown")

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
            [InlineKeyboardButton("⬅️ 6. KEMBALI", callback_data="back_main")]
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
        await update.message.reply_text("Template disimpan", reply_markup=main_menu_keyboard())
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
        c.execute("UPDATE settings SET kode_atas=?, kode_prefix=?, kode_pos=? WHERE user_id=?", (num, prefix, kode_pos, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO settings (user_id, template, kode_atas, kode_prefix, kode_pos) VALUES (?, ?, ?, ?, ?)", (user_id, DEFAULT_TEMPLATE, num, prefix, kode_pos))
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
            await update.message.reply_text(f"KODE DISIMPAN\nKode aktif: {kode_aktif} ({kode_pos})", reply_markup=main_menu_keyboard())
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
            await update.message.reply_text("Minimal 9 baris", reply_markup=main_menu_keyboard())
            return
        _, _, _, kode_pos = get_setting(user_id)
        user_template, _, _, _ = get_setting(user_id)
        disp_format, disp_full = build_display(parsed, user_template, kode_pos)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""UPDATE hasil_format SET kab=?, kec=?, kel=?, saldo=?, kelamin=?, kpj=?, sensor=?, it=?, pt=?, akun=?, display_format=?, display_full=? WHERE id=? AND user_id=?""",
                  (parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"], parsed["AKUN"], disp_format, disp_full, rid, user_id))
        conn.commit()
        conn.close()
        context.user_data["mode"] = None
        await update.message.reply_text(f"ID {rid} diedit\n{disp_format}", reply_markup=main_menu_keyboard())
        return

    if mode and mode.startswith("cari"):
        keyword = text.strip()
        like = f"%{keyword}%"
        if "history" in mode:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""SELECT id, display_full, kode FROM hasil_format 
                         WHERE user_id=? AND status='terjual' 
                         AND (kode LIKE ? OR kab LIKE ? OR kec LIKE ? OR kel LIKE ? OR pt LIKE ? OR akun LIKE ? OR display_full LIKE ?)
                         ORDER BY CAST(SUBSTR(kode, -7) AS INTEGER) ASC, id ASC""", 
                      (user_id, like, like, like, like, like, like, like))
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
                await update.message.reply_text(f"🔍 Tidak ada hasil untuk '{keyword}'\nCoba cari dengan:\n- Kode: ASD 001\n- Nama: RIO\n- KAB: JAKARTA\n- KEC, KEL, dll.", reply_markup=main_menu_keyboard())
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
    for block in blocks:
        if len([l for l in block.splitlines() if l.strip()!=""]) < 9:
            continue
        kode = get_next_code(user_id)
        parsed = parse_jmo_block(block, kode)
        if not parsed:
            continue
        _, _, _, kode_pos = get_setting(user_id)
        user_template, _, _, _ = get_setting(user_id)
        disp_format, disp_full = build_display(parsed, user_template, kode_pos)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""INSERT INTO hasil_format (user_id, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, akun, display_format, display_full, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (user_id, kode, parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"], parsed["AKUN"], disp_format, disp_full, datetime.now().isoformat()))
        c.execute("INSERT INTO history (user_id, aksi, detail, created_at) VALUES (?,?,?,?)", (user_id, "BUAT FORMAT", kode, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        saved += 1
        await update.message.reply_text(f"```\n{disp_format}\n```", parse_mode="Markdown")
    if saved > 0:
        await update.message.reply_text(f"✅ {saved} format tersimpan", reply_markup=main_menu_keyboard())

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc_name = update.message.document.file_name or ""
    if not doc_name.lower().endswith((".xlsx", ".xls")):
        await update.message.reply_text("File harus .xlsx", reply_markup=main_menu_keyboard())
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
            _, _, _, kode_pos = get_setting(user_id)
            user_template, _, _, _ = get_setting(user_id)
            disp_format, disp_full = build_display(parsed, user_template, kode_pos)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""INSERT INTO hasil_format (user_id, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, it, pt, akun, display_format, display_full, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (user_id, kode, parsed["KAB"], parsed["KEC"], parsed["KEL"], parsed["SALDO"], parsed["KELAMIN"], parsed["KPJ"], parsed["SENSOR"], parsed["IT"], parsed["PT"], parsed["AKUN"], disp_format, disp_full, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            saved += 1
        await update.message.reply_text(f"✅ {saved} data masuk", reply_markup=main_menu_keyboard())
    except Exception as e:
        await update.message.reply_text(f"Gagal: {e}", reply_markup=main_menu_keyboard())
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
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())

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
    c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user.id,))
    total = c.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"👤 PROFIL\nID: {user.id}\nTotal: {total}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ KEMBALI KE MENU", callback_data="back_main")]]))

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
