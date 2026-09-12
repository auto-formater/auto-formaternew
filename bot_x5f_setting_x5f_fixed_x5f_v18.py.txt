import os, re, sqlite3, logging, sys, traceback
from datetime import datetime
from pathlib import Path
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
try:
    from telegram import CopyTextButton
    HAS_COPY = True
except ImportError:
    CopyTextButton = None
    HAS_COPY = False

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# === LOGGING BIAR KELIATAN DI RAILWAY ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === ENV VARS ===
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
if ADMIN_IDS_RAW:
    try:
        ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().lstrip('-').isdigit()]
    except Exception as e:
        logger.error(f"ADMIN_IDS parse error: {e}")

DB_PATH = os.getenv("DB_PATH", "bot_data.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
GARIS = "━━━━━━━━━━━━━━━━━━━"
DEFAULT_TEMPLATE = """📍KAB : {KAB}
📍KEC : {KEC}
📍KEL : {KEL}
💰 SALDO : {SALDO}
🆔 KELAMIN : {KELAMIN}
💳 KPJ : {KPJ}
🔰 SENSOR: {SENSOR}
📆 IT : {IURAN_T}
🏛️ PT : {PT}
🏆 DPT JMO LASIK ✅"""

# === DB HELPER ANTI-CRASH ===
def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)

def init_db():
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, join_date TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_by INTEGER, added_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, template TEXT, kode_atas TEXT, kode_bawah TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS hasil_format (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, content_raw TEXT, content_formatted TEXT, content_display TEXT, kode TEXT, kab TEXT, kec TEXT, kel TEXT, saldo TEXT, kelamin TEXT, kpj TEXT, sensor TEXT, iuran_t TEXT, pt TEXT, akun TEXT, created_at TEXT, sex_code TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS hasil_akun (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, kode TEXT, akun TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS riwayat (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tipe TEXT, content_raw TEXT, content TEXT, content_formatted TEXT, content_display TEXT, kode TEXT, kab TEXT, kec TEXT, kel TEXT, saldo TEXT, kelamin TEXT, kpj TEXT, sensor TEXT, iuran_t TEXT, pt TEXT, akun TEXT, sex_code TEXT, deleted_at TEXT, original_id INTEGER)""")
        conn.commit()
        conn.close()
        logger.info(f"DB OK at {DB_PATH}")
    except Exception as e:
        logger.error(f"init_db failed: {e}\n{traceback.format_exc()}")

def get_setting(user_id):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT template, kode_atas, kode_bawah FROM settings WHERE user_id=?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {"template": row[0] or DEFAULT_TEMPLATE, "kode_atas": row[1] or "", "kode_bawah": row[2] or ""}
    except Exception as e:
        logger.error(f"get_setting {user_id}: {e}")
    return {"template": DEFAULT_TEMPLATE, "kode_atas": "", "kode_bawah": ""}

def save_setting(user_id, template=None, kode_atas=None, kode_bawah=None):
    try:
        cur = get_setting(user_id)
        if template is None: template = cur["template"]
        if kode_atas is None: kode_atas = cur["kode_atas"]
        if kode_bawah is None: kode_bawah = cur["kode_bawah"]
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (user_id, template, kode_atas, kode_bawah) VALUES (?,?,?,?)", (user_id, template, kode_atas, kode_bawah))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"save_setting: {e}")

def parse_kode_atas(kode_str):
    if not kode_str:
        return "", 0, 3
    s = kode_str.strip()
    m = re.search(r'(\d+)$', s)
    if not m:
        return s + " - " if not s.endswith(" ") else s, 1, 3
    num_str = m.group(1)
    try:
        num = int(num_str)
    except:
        num = 1
    prefix = s[:m.start()]
    return prefix, num, len(num_str)

def get_next_sex_code(user_id):
    max_code = 0
    conn = None
    try:
        conn = get_conn()
        c = conn.cursor()
        for table in ("hasil_format", "riwayat"):
            try:
                c.execute(f"SELECT sex_code FROM {table} WHERE user_id=?", (user_id,))
                rows = c.fetchall()
                for (sc,) in rows:
                    if not sc: continue
                    mm = re.search(r'(\d+)$', str(sc).strip())
                    if mm:
                        try:
                            max_code = max(max_code, int(mm.group(1)))
                        except:
                            pass
            except Exception as e:
                logger.warning(f"get_next_sex_code {table}: {e}")
        conn.close()
        conn = None
    except Exception as e:
        logger.error(f"get_next_sex_code db: {e}")
    finally:
        if conn:
            try: conn.close()
            except: pass
    try:
        setting = get_setting(user_id)
        ka = setting.get('kode_atas','')
        if ka:
            m = re.search(r'(\d+)$', ka.strip())
            if m:
                base = int(m.group(1))
                if base > max_code:
                    max_code = base - 1
    except:
        pass
    return max_code + 1

def build_sex_from_setting(user_id, counter):
    try:
        setting = get_setting(user_id)
        ka = setting.get('kode_atas','').strip()
        if not ka:
            return f"{counter:03d}"
        m = re.search(r'(\d+)$', ka)
        if not m:
            prefix = ka if ka.endswith(" ") or ka.endswith("-") else ka + " - "
            return f"{prefix}{counter:03d}"
        num_width = len(m.group(1))
        prefix_part = ka[:m.start()]
        return f"{prefix_part}{counter:0{num_width}d}"
    except Exception as e:
        logger.error(f"build_sex: {e}")
        return f"{counter:03d}"

def get_all_admins():
    db_admins = []
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        rows = c.fetchall()
        db_admins = [r[0] for r in rows]
        conn.close()
    except Exception as e:
        logger.warning(f"get_all_admins: {e}")
    return list(set(ADMIN_IDS + db_admins))

def is_admin(user_id):
    try:
        return user_id in get_all_admins()
    except:
        return False

def add_admin_db(new_admin_id, added_by):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO admins (user_id, added_by, added_at) VALUES (?,?,?)", (new_admin_id, added_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"add_admin_db: {e}")

def remove_admin_db(admin_id):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id=?", (admin_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"remove_admin_db: {e}")

def add_user(user):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?,?,?,?)", (user.id, user.username, user.first_name or "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"add_user: {e}")

def make_display_text(detail, sex_code="005"):
    try:
        # Format baru sesuai request user
        kode = sex_code.strip() if sex_code else "005"
        s = f"""{kode}
{GARIS}
📍KAB : {detail.get('kab','-').upper() if detail.get('kab') else '-'}
📍KEC : {detail.get('kec','-').upper() if detail.get('kec') else '-'}
📍KEL : {detail.get('kel','-')}
💰 SALDO : {detail.get('saldo','-')}
🆔 KELAMIN : {detail.get('kelamin','-')}
💳 KPJ : {detail.get('kpj','-')}
🔰 SENSOR: {detail.get('sensor','-')}
📆 IT : {detail.get('iuran_t','-')}
🏛️ PT : {detail.get('pt','-').upper() if detail.get('pt') else '-'}
🏆 DPT JMO LASIK ✅"""
        return s
    except Exception as e:
        logger.error(f"make_display_text: {e}")
        return f"{sex_code}\n{GARIS}\n{detail}"

def move_to_riwayat(user_id, tipe, data_row):
    try:
        conn = get_conn()
        c = conn.cursor()
        if tipe == "format":
            c.execute("""INSERT INTO riwayat (user_id, tipe, content_raw, content, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, sex_code, deleted_at, original_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (user_id, tipe, data_row.get('content_raw',''), data_row.get('content',''), data_row.get('content_formatted',''), data_row.get('content_display',''), data_row.get('kode',''), data_row.get('kab',''), data_row.get('kec',''), data_row.get('kel',''), data_row.get('saldo',''), data_row.get('kelamin',''), data_row.get('kpj',''), data_row.get('sensor',''), data_row.get('iuran_t',''), data_row.get('pt',''), data_row.get('akun',''), data_row.get('sex_code','005'), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data_row.get('id',0)))
        else:
            c.execute("""INSERT INTO riwayat (user_id, tipe, content_raw, content, kode, akun, deleted_at, original_id, content_display, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                      (user_id, tipe, data_row.get('content',''), data_row.get('content',''), data_row.get('kode',''), data_row.get('akun',''), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data_row.get('id',0), data_row.get('content',''), "005"))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"move_to_riwayat: {e}")

def parse_jmo_block(text_block, user_id, sex_counter=1):
    try:
        lines = [l.strip() for l in text_block.strip().splitlines()]
        clean = [l for l in lines if l != ""]
        # Auto-skip jika user paste lengkap dengan KODE ATAS + GARIS di awal (contoh: ABH 172 + ━━━)
        # Deteksi garis
        def is_garis(s):
            return "━━" in s or "___" in s or s.count("━")>=5 or s.count("_")>=5 or s.count("-")>=8
        # Hapus leading kode+garis yang mungkin ikut ke-copy
        while len(clean) >= 2 and is_garis(clean[1]):
            # clean[0] = kode seperti ABH 172, clean[1]=garis
            clean = clean[2:]
        # Jika baris pertama masih terlihat seperti kode (misal ABH 172) dan bukan KAB, hapus 1 baris jika sisa >=9
        if len(clean) > 9:
            first = clean[0]
            # Jika first mengandung angka dan panjang pendek (kode) dan baris kedua adalah garis atau KAB? sederhana: jika first tidak mengandung kata KAB/KEC tapi pendek
            if len(first) < 20 and any(c.isdigit() for c in first) and "KAB" not in first.upper():
                # cek apakah setelah ini masih ada 9+ baris
                if len(clean[1:]) >= 9:
                    # jika baris berikutnya adalah garis, sudah di-handle di atas, jadi ini murni kode
                    if not is_garis(first):
                        # hanya hapus jika baris berikutnya bukan KAB tapi kita yakin ini kode
                        # heuristik: jika first mengandung spasi+angka seperti "ABH 172"
                        if re.match(r'^[A-Z]{2,5}\s*\d+', first.upper()):
                            clean = clean[1:]

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
        if isinstance(sex_counter, int):
            sex_code = build_sex_from_setting(user_id, sex_counter)
        else:
            sex_code = build_sex_from_setting(user_id, get_next_sex_code(user_id))
        detail_temp = {"kab": kab, "kec": kec, "kel": kel, "saldo": saldo, "kelamin": kelamin, "kpj": kpj, "sensor": sensor, "iuran_t": iuran_t, "pt": pt}
        display_text = make_display_text(detail_temp, sex_code)
        setting = get_setting(user_id)
        # Template user bisa custom, tapi untuk HASIL FORMAT kita pakai display_text yang sudah pretty (tanpa akun)
        # display_text sudah = kode + garis + body
        formatted_template = display_text
        # Jika user punya template custom, coba format customnya (tanpa akun)
        try:
            custom = setting.get("template","")
            if custom and "{KAB}" in custom:
                # Format custom tanpa akun
                custom_body = custom.format(KAB=kab, KEC=kec, KEL=kel, SALDO=saldo, KELAMIN=kelamin, KPJ=kpj, SENSOR=sensor, IURAN_T=iuran_t, PT=pt, AKUN="", KODE_ATAS=sex_code, KAB_UP=kab.upper(), KEC_UP=kec.upper(), KEL_UP=kel.upper(), PT_UP=pt.upper())
                # Jika custom tidak mengandung kode, kita tambahkan kode + garis di depan
                if sex_code not in custom_body:
                    formatted_template = f"{sex_code}\n{GARIS}\n{custom_body}"
                else:
                    formatted_template = custom_body
        except Exception:
            pass
        parts = []
        kode_bawah = (setting.get("kode_bawah") or "").strip()
        # formatted_template sudah mengandung kode_atas + garis + body (dari make_display_text)
        # Jadi tidak perlu tambahkan kode_atas lagi di sini agar tidak double
        parts.append(formatted_template)
        if kode_bawah:
            # kode bawah: body + garis + kode_bawah
            parts.append(GARIS)
            parts.append(kode_bawah)
        full_formatted = "\n".join(parts)
        detail = {"kab": kab, "kec": kec, "kel": kel, "saldo": saldo,"kelamin": kelamin, "kpj": kpj, "sensor": sensor,"iuran_t": iuran_t, "pt": pt,"akun": raw_akun,"raw_format": raw_format,"raw_akun": raw_akun,"content_formatted": full_formatted,"content_display": display_text,"kode": kode,"sex_code": sex_code}
        return detail, None
    except Exception as e:
        logger.error(f"parse_jmo_block error: {e}\n{traceback.format_exc()}")
        return None, str(e)

def process_blocks(full_text, user_id):
    try:
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
    except Exception as e:
        logger.error(f"process_blocks: {e}")
        return []

# ===== MENU =====
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
        [InlineKeyboardButton("❌ BATAL", callback_data="cancel_batal"), InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
    ])

def four_buttons_format(id_data, display_text=""):
    try:
        # COPY CODE - bisa copy dimana saja pakai CopyTextButton kalau support
        if HAS_COPY and display_text and CopyTextButton:
            try:
                copy_btn = InlineKeyboardButton("📋 COPY CODE", copy_text=CopyTextButton(display_text[:4000]))
            except Exception:
                copy_btn = InlineKeyboardButton("📋 COPY CODE", callback_data=f"copy_format_{id_data}")
        else:
            copy_btn = InlineKeyboardButton("📋 COPY CODE", callback_data=f"copy_format_{id_data}")
        kb = [
            [copy_btn, InlineKeyboardButton("💰 JUAL", callback_data=f"jual_{id_data}")],
            [InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_{id_data}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"hapus_{id_data}")],
        ]
        return InlineKeyboardMarkup(kb)
    except Exception as e:
        logger.error(f"four_buttons_format: {e}")
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]])

def four_buttons_akun(id_data, display_text=""):
    try:
        if HAS_COPY and display_text and CopyTextButton:
            try:
                copy_btn = InlineKeyboardButton("📋 COPY CODE", copy_text=CopyTextButton(display_text[:4000]))
            except:
                copy_btn = InlineKeyboardButton("📋 COPY CODE", callback_data=f"copy_akun_{id_data}")
        else:
            copy_btn = InlineKeyboardButton("📋 COPY CODE", callback_data=f"copy_akun_{id_data}")
        kb = [
            [copy_btn, InlineKeyboardButton("💰 JUAL", callback_data=f"jual_akun_{id_data}")],
            [InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_akun_{id_data}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"hapus_akun_{id_data}")],
        ]
        return InlineKeyboardMarkup(kb)
    except:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]])

def bottom_menu_after_hasil():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 BUAT LAGI", callback_data="bf_manual"), InlineKeyboardButton("⬅️ KEMBALI", callback_data="main")]])

def hasil_format_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 SEMUA HASIL", callback_data="hf_utuh"), InlineKeyboardButton("🔍 CARI", callback_data="hf_cari")],
        [InlineKeyboardButton("📤 EXPORT .xlsx", callback_data="hf_export")],
        [InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
    ])

def hasil_akun_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 SEMUA HASIL", callback_data="ha_utuh"), InlineKeyboardButton("🔍 CARI", callback_data="ha_cari")],
        [InlineKeyboardButton("📤 EXPORT .xlsx", callback_data="ha_export")],
        [InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
    ])

def setting_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 TEMPLAT", callback_data="set_templat"), InlineKeyboardButton("🔢 SET KODE ATAS", callback_data="set_kode_atas")],
        [InlineKeyboardButton("🔢 SET KODE BAWAH", callback_data="set_kode_bawah")],
        [InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
    ])

def setting_templat_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ UBAH TEMPLAT", callback_data="set_templat_ubah")],
        [InlineKeyboardButton("🔙 KEMBALI", callback_data="setting")]
    ])

def setting_kode_atas_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁️ KODE SAYA", callback_data="set_kode_atas_saya"), InlineKeyboardButton("✏️ GANTI KODE", callback_data="set_kode_atas_ganti")],
        [InlineKeyboardButton("🗑️ HAPUS KODE", callback_data="set_kode_atas_hapus"), InlineKeyboardButton("🔙 KEMBALI", callback_data="setting")]
    ])

def setting_kode_bawah_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁️ KODE SAYA", callback_data="set_kode_bawah_saya"), InlineKeyboardButton("✏️ UBAH KODE", callback_data="set_kode_bawah_ganti")],
        [InlineKeyboardButton("🗑️ HAPUS KODE", callback_data="set_kode_bawah_hapus"), InlineKeyboardButton("🔙 KEMBALI", callback_data="setting")]
    ])
            except Exception as e:
                logger.error(f"profil: {e}")
                await query.edit_message_text("Error profil", reply_markup=main_menu())
            return

        if data == "cancel_batal":
            context.user_data["state"]=None
            try:
                await query.edit_message_text("❌ Dibatalkan", reply_markup=main_menu())
            except:
                await query.message.reply_text("❌ Dibatalkan", reply_markup=main_menu())
            return

        if data == "bikin_format":
            await query.edit_message_text("⌨️ BIKIN FORMAT", reply_markup=bikin_format_menu())
            return

        if data == "bf_manual":
            context.user_data["state"]="awaiting_manual"
            txt = '''BUAT FORMAT

Ketik data tanpa perlu menulis KAB/KEC/KEL. Bot otomatis membaca urutannya:

1 KAB
2 KEC
3 KEL
4 SALDO
5 KELAMIN
6 KPJ
7 SENSOR
8 IT
9 PT

Contoh:
DEPOK
CILODONG
KALIBARU
10.000.000
PEREMPUAN 1992
2019
23****
01-07-2022
INDONESIA MERDEKA

/cancel untuk batal'''
            await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ BATAL", callback_data="cancel_batal"), InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
            ]))
            return

        if data == "bf_excel":
            context.user_data["state"]="awaiting_excel"
            await query.edit_message_text("Upload file .xlsx /cancel untuk batal", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ BATAL", callback_data="cancel_batal"), InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
            ]))
            return

        if data == "hasil_format":
            await query.edit_message_text("📄 HASIL FORMAT", reply_markup=hasil_format_menu())
            return

        if data == "hf_utuh":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, content_display, content, kode, sex_code FROM hasil_format WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC, id ASC LIMIT 200", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("📄 HASIL FORMAT kosong", reply_markup=hasil_format_menu())
                    return
                await query.edit_message_text(f"Menampilkan {len(rows)} format urut ID 1,2,3... tiap format ada tombolnya sendiri:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➡️ KEMBALI KE MENU", callback_data="hasil_format")]]))
                no=1
                for fid, display, raw_content, kode, sex in rows:
                    content_show = display if display else raw_content
                    card_text = f"{no}. ID {fid}
```
{content_show}
```"
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("💰 JUAL", callback_data=f"jual_format_{fid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_format_{fid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"hapus_format_{fid}")],
                        [InlineKeyboardButton("🔙 KEMBALI", callback_data="hasil_format")]
                    ])
                    await context.bot.send_message(chat_id=query.message.chat_id, text=card_text, reply_markup=kb, parse_mode="Markdown")
                    no+=1
                await context.bot.send_message(chat_id=query.message.chat_id, text="🔍 MENU LANJUTAN", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 CARI HASIL FORMAT", callback_data="hf_cari")],
                    [InlineKeyboardButton("➡️ KEMBALI KE MENU", callback_data="hasil_format")],
                    [InlineKeyboardButton("🗑️ HAPUS SEMUA HASIL", callback_data="hf_hapus_all")]
                ]))
            except Exception as e:
                logger.error(f"hf_utuh: {e}
{traceback.format_exc()}")
                await query.message.reply_text("❌ Error tampilkan format")
            return

                await query.edit_message_text(f"{len(rows)} HASIL FORMAT UTUH:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("KEMBALI", callback_data="main")]]))
                for rid, display, sex in rows:
                    combined = f"{display}"
                    kb = four_buttons_format(rid, combined)
                    await context.bot.send_message(chat_id=query.message.chat_id, text=combined[:4000], reply_markup=kb)
                await context.bot.send_message(chat_id=query.message.chat_id, text="Selesai HASIL FORMAT UTUH", reply_markup=bottom_menu_after_hasil())
            except Exception as e:
                logger.error(f"hf_utuh: {e}\n{traceback.format_exc()}")
                await query.message.reply_text("❌ Error hf_utuh")
            return

        if data == "hf_kode":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT sex_code FROM hasil_format WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC, id ASC", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("Belum ada kode", reply_markup=hasil_format_menu())
                    return
                kode_list = []
                for (sc,) in rows:
                    if not sc: continue
                    sc_str = str(sc).strip()
                    if not sc_str.upper().startswith("SEX"):
                        kode_list.append(f"SEX {sc_str}")
                    else:
                        kode_list.append(sc_str)
                combined_kode = "\n".join(kode_list)
                await query.edit_message_text(f"{len(kode_list)} KODE (1 KOTAK):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("KEMBALI", callback_data="main")]]))
                if HAS_COPY and CopyTextButton:
                    try:
                        kb_kode = InlineKeyboardMarkup([[InlineKeyboardButton("COPY SEMUA KODE", copy_text=CopyTextButton(combined_kode[:4000]))],[InlineKeyboardButton("KEMBALI", callback_data="main")]])
                    except:
                        kb_kode = InlineKeyboardMarkup([[InlineKeyboardButton("KEMBALI", callback_data="main")]])
                else:
                    kb_kode = InlineKeyboardMarkup([[InlineKeyboardButton("KEMBALI", callback_data="main")]])
                await context.bot.send_message(chat_id=query.message.chat_id, text=combined_kode[:4000], reply_markup=kb_kode)
                await context.bot.send_message(chat_id=query.message.chat_id, text="Selesai", reply_markup=bottom_menu_after_hasil())
            except Exception as e:
                logger.error(f"hf_kode: {e}")
            return

        if data == "ha_utuh":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, content, kode, akun FROM hasil_akun WHERE user_id=? ORDER BY id ASC LIMIT 200", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("💳 HASIL AKUN kosong", reply_markup=hasil_akun_menu())
                    return
                await query.edit_message_text(f"Menampilkan {len(rows)} akun urut ID 1,2,3... tiap akun ada tombolnya sendiri:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➡️ KEMBALI KE MENU", callback_data="hasil_akun")]]))
                no=1
                for fid, cont, kode, akun in rows:
                    full = cont
                    if akun and akun.strip() != "-":
                        full = f"{cont}
{akun}"
                    card_text = f"{no}. ID {fid}
```
{full}
```"
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("💰 JUAL", callback_data=f"jual_akun_{fid}"), InlineKeyboardButton("✏️ EDIT", callback_data=f"edit_akun_{fid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"hapus_akun_{fid}")],
                        [InlineKeyboardButton("🔙 KEMBALI", callback_data="hasil_akun")]
                    ])
                    await context.bot.send_message(chat_id=query.message.chat_id, text=card_text, reply_markup=kb, parse_mode="Markdown")
                    no+=1
                await context.bot.send_message(chat_id=query.message.chat_id, text="🔍 MENU LANJUTAN", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 CARI HASIL AKUN", callback_data="ha_cari")],
                    [InlineKeyboardButton("➡️ KEMBALI KE MENU", callback_data="hasil_akun")],
                    [InlineKeyboardButton("🗑️ HAPUS SEMUA HASIL", callback_data="ha_hapus_all")]
                ]))
            except Exception as e:
                logger.error(f"ha_utuh: {e}
{traceback.format_exc()}")
                await query.message.reply_text("❌ Error tampilkan akun")
            return

                await query.edit_message_text(f"{len(rows)} HASIL AKUN UTUH (FORMAT+AKUN):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("KEMBALI", callback_data="main")]]))
                for rid, display, akun, kode, sex in rows:
                    # display sudah = ABH 172 + garis + body
                    # HASIL AKUN UTUH = display + akun lengkap
                    if akun and akun.strip() != "-" and akun.strip() != "":
                        combined = f"{display}\n{akun}"
                    else:
                        combined = f"{display}"
                    kb = four_buttons_format(rid, combined)
                    await context.bot.send_message(chat_id=query.message.chat_id, text=combined[:4000], reply_markup=kb)
                await context.bot.send_message(chat_id=query.message.chat_id, text="Selesai HASIL AKUN UTUH", reply_markup=bottom_menu_after_akun())
            except Exception as e:
                logger.error(f"ha_utuh: {e}")
            return

        if data == "ha_kode":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, sex_code, akun, kode FROM hasil_format WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC, id ASC LIMIT 100", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("Belum ada akun", reply_markup=hasil_akun_menu())
                    return
                await query.edit_message_text(f"{len(rows)} AKUN KODE:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("KEMBALI", callback_data="main")]]))
                for rid, sex, akun, kode in rows:
                    if not sex:
                        sex = kode or "000"
                    sex_str = str(sex).strip()
                    if not sex_str.upper().startswith("SEX"):
                        sex_str = f"SEX {sex_str}"
                    if akun and akun.strip() != "-" and akun.strip() != "":
                        combined = f"{sex_str}\n---------------\n{akun}"
                    else:
                        combined = f"{sex_str}\n---------------\n{kode or '-'}"
                    kb = four_buttons_akun(rid, combined)
                    await context.bot.send_message(chat_id=query.message.chat_id, text=combined[:4000], reply_markup=kb)
                await context.bot.send_message(chat_id=query.message.chat_id, text="Selesai AKUN KODE", reply_markup=bottom_menu_after_akun())
            except Exception as e:
                logger.error(f"ha_kode: {e}")
            return

        if data == "hf_cari":
            context.user_data["state"]="awaiting_search_format"
            await query.edit_message_text("🔍 CARI FORMAT - kirim kata kunci\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            return
        if data == "hf_hapus_menu":
            context.user_data["state"]="awaiting_delete_format_kode"
            await query.edit_message_text("🗑️ HAPUS - kirim kata kunci kode untuk hapus -> RIWAYAT\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            return
        if data == "hf_salin":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT content_display FROM hasil_format WHERE user_id=? ORDER BY CAST(sex_code AS INTEGER) ASC", (user_id,))
                rows=c.fetchall()
                conn.close()
                txt = "\n\n".join([r[0] for r in rows]) if rows else "Belum ada"
                await query.edit_message_text(f"📋 SALIN SEMUA:\n\n{txt}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            except Exception as e:
                logger.error(f"hf_salin: {e}")
            return
        if data == "hf_export":
            try:
                conn=get_conn()
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
                try: os.remove(path)
                except: pass
            except Exception as e:
                logger.error(f"hf_export: {e}")
                await query.message.reply_text(f"❌ Gagal export: {e}")
            return

        if data == "hasil_akun":
            await query.edit_message_text("💳 HASIL AKUN", reply_markup=hasil_akun_menu())
            return
        if data == "ha_cari":
            context.user_data["state"]="awaiting_search_akun"
            await query.edit_message_text("🔍 CARI AKUN - kata kunci\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            return
        if data == "ha_hapus_menu":
            context.user_data["state"]="awaiting_delete_akun_kode"
            await query.edit_message_text("🗑️ HAPUS AKUN - kata kunci\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            return
        if data == "ha_salin":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT content FROM hasil_akun WHERE user_id=? ORDER BY id ASC", (user_id,))
                rows=c.fetchall()
                conn.close()
                txt = "\n\n".join([r[0] for r in rows]) if rows else "Belum ada"
                await query.edit_message_text(f"📋 SALIN AKUN:\n{txt}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            except Exception as e:
                logger.error(f"ha_salin: {e}")
            return
        if data == "ha_export":
            try:
                conn=get_conn()
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
                try: os.remove(path)
                except: pass
            except Exception as e:
                logger.error(f"ha_export: {e}")
            return

        if data.startswith("copy_format_"):
            try:
                rid = int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                q = "SELECT content_display FROM hasil_format WHERE id=?" if is_admin(user_id) else "SELECT content_display FROM hasil_format WHERE id=? AND user_id=?"
                params = (rid,) if is_admin(user_id) else (rid, user_id)
                c.execute(q, params)
                row=c.fetchone()
                conn.close()
                if row:
                    await context.bot.send_message(chat_id=query.message.chat_id, text=f"📋 COPY ID {rid}:\n\n{row[0]}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            except Exception as e:
                logger.error(f"copy_format: {e}")
            return

        if data.startswith("hapus_"):
            try:
                # handle hapus_123 (format) dan hapus_akun_123
                if data.startswith("hapus_akun_"):
                    rid = int(data.split("_")[-1])
                    conn=get_conn()
                    c=conn.cursor()
                    c.execute("SELECT * FROM hasil_akun WHERE id=?", (rid,))
                    cols=[d[0] for d in c.description]
                    row=c.fetchone()
                    if row:
                        d=dict(zip(cols,row))
                        move_to_riwayat(d['user_id'], "akun", d)
                        c.execute("DELETE FROM hasil_akun WHERE id=?", (rid,))
                        conn.commit()
                        await query.edit_message_text(f"🗑️ Akun {rid} -> RIWAYAT", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                    conn.close()
                else:
                    rid = int(data.split("_")[-1])
                    conn=get_conn()
                    c=conn.cursor()
                    if is_admin(user_id):
                        c.execute("SELECT * FROM hasil_format WHERE id=?", (rid,))
                    else:
                        c.execute("SELECT * FROM hasil_format WHERE id=? AND user_id=?", (rid, user_id))
                    cols=[d[0] for d in c.description] if c.description else []
                    row=c.fetchone()
                    if row:
                        d=dict(zip(cols,row))
                        move_to_riwayat(d['user_id'], "format", d)
                        c.execute("DELETE FROM hasil_format WHERE id=?", (rid,))
                        conn.commit()
                        await query.edit_message_text(f"🗑️ ID {rid} -> RIWAYAT", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                    conn.close()
            except Exception as e:
                logger.error(f"hapus: {e}\n{traceback.format_exc()}")
            return

        # === JUAL HANDLER HASIL FORMAT ===
        if data.startswith("jual_") and not data.startswith("jual_akun_") and not data.startswith("jual_confirm_") and not data.startswith("jual_batal_"):
            try:
                rid = int(data.split("_")[-1])
                # Simpan id untuk konfirmasi
                context.user_data["jual_id"] = rid
                context.user_data["jual_tipe"] = "format"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ YA", callback_data=f"jual_confirm_{rid}"), InlineKeyboardButton("❌ BATAL", callback_data=f"jual_batal_{rid}")],
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
                ])
                await query.edit_message_text("Apakah Anda yakin ingin menjual ini?", reply_markup=kb)
                # Kirim juga detail yang mau dijual biar user cek lagi
                try:
                    conn=get_conn()
                    c=conn.cursor()
                    c.execute("SELECT content_display FROM hasil_format WHERE id=?", (rid,))
                    row=c.fetchone()
                    conn.close()
                    if row:
                        await context.bot.send_message(chat_id=query.message.chat_id, text=f"📦 Yang akan dijual:\n\n{row[0]}"[:4000])
                except:
                    pass
            except Exception as e:
                logger.error(f"jual: {e}")
            return

        if data.startswith("jual_akun_") and not data.startswith("jual_akun_confirm_") and not data.startswith("jual_akun_batal_"):
            try:
                rid = int(data.split("_")[-1])
                context.user_data["jual_id"] = rid
                context.user_data["jual_tipe"] = "akun"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ YA", callback_data=f"jual_akun_confirm_{rid}"), InlineKeyboardButton("❌ BATAL", callback_data=f"jual_akun_batal_{rid}")],
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
                ])
                await query.edit_message_text("Apakah Anda yakin ingin menjual ini?", reply_markup=kb)
                try:
                    conn=get_conn()
                    c=conn.cursor()
                    c.execute("SELECT content FROM hasil_akun WHERE id=?", (rid,))
                    row=c.fetchone()
                    if not row:
                        c.execute("SELECT content_display, akun FROM hasil_format WHERE id=?", (rid,))
                        row2=c.fetchone()
                        if row2:
                            conn.close()
                            await context.bot.send_message(chat_id=query.message.chat_id, text=f"📦 Yang akan dijual:\n\n{row2[0]}\n{row2[1]}"[:4000])
                            return
                    conn.close()
                    if row:
                        await context.bot.send_message(chat_id=query.message.chat_id, text=f"📦 Yang akan dijual:\n\n{row[0]}"[:4000])
                except:
                    pass
            except Exception as e:
                logger.error(f"jual_akun: {e}")
            return

        if data.startswith("jual_confirm_"):
            try:
                rid = int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT * FROM hasil_format WHERE id=?", (rid,))
                cols=[d[0] for d in c.description] if c.description else []
                row=c.fetchone()
                if row:
                    d=dict(zip(cols,row))
                    # Simpan ke riwayat dengan tipe terjual
                    c.execute("""INSERT INTO riwayat (user_id, tipe, content_raw, content, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, sex_code, deleted_at, original_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                              (d.get('user_id', user_id), "terjual", d.get('content_raw',''), d.get('content',''), d.get('content_formatted',''), d.get('content_display',''), d.get('kode',''), d.get('kab',''), d.get('kec',''), d.get('kel',''), d.get('saldo',''), d.get('kelamin',''), d.get('kpj',''), d.get('sensor',''), d.get('iuran_t',''), d.get('pt',''), d.get('akun',''), d.get('sex_code',''), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), d.get('id',0)))
                    c.execute("DELETE FROM hasil_format WHERE id=?", (rid,))
                    conn.commit()
                    await query.edit_message_text(f"✅ Berhasil dijual! ID {rid} sudah masuk RIWAYAT terjual.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                else:
                    await query.edit_message_text("❌ Data tidak ditemukan", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                conn.close()
            except Exception as e:
                logger.error(f"jual_confirm: {e}\n{traceback.format_exc()}")
                await query.edit_message_text("❌ Gagal menjual", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            return

        if data.startswith("jual_akun_confirm_"):
            try:
                rid = int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT * FROM hasil_akun WHERE id=?", (rid,))
                cols=[d[0] for d in c.description] if c.description else []
                row=c.fetchone()
                sold_content = ""
                sold_kode = ""
                sold_waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if row:
                    d=dict(zip(cols,row))
                    sold_content = d.get('content','') or d.get('content_display','')
                    sold_kode = d.get('kode','') or str(d.get('id',''))
                    c.execute("""INSERT INTO riwayat (user_id, tipe, content_raw, content, kode, akun, deleted_at, original_id, content_display, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                              (d.get('user_id', user_id), "terjual_akun", d.get('content',''), d.get('content',''), d.get('kode',''), d.get('akun',''), sold_waktu, d.get('id',0), d.get('content',''), ""))
                    c.execute("DELETE FROM hasil_akun WHERE id=?", (rid,))
                    conn.commit()
                    await query.edit_message_text(f"✅ Akun ID {rid} terjual!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                conn.close()
                # === NOTIF KE SEMUA ADMIN JIKA PENJUAL ADALAH ADMIN ===
                try:
                    if is_admin(user_id):
                        all_admins = get_all_admins()
                        seller_name = query.from_user.first_name or f"ID {user_id}"
                        seller_user = f"@{query.from_user.username}" if query.from_user.username else f"ID {user_id}"
                        notif_text = (
                            f"🔔 NOTIF ADMIN JUAL - HASIL AKUN\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 Admin {seller_name} {seller_user} baru saja menjual data:\n\n"
                            f"🆔 ID: {rid}\n"
                            f"🔢 Kode: {sold_kode}\n"
                            f"🕘 Waktu Jual: {sold_waktu}\n\n"
                            f"📦 HASIL AKUN:\n```\n{sold_content[:3000]}\n```\n\n"
                            f"✅ Data sudah masuk HISTORY."
                        )
                        for admin_id in all_admins:
                            if admin_id == user_id:
                                continue
                            try:
                                await context.bot.send_message(chat_id=admin_id, text=notif_text, parse_mode="Markdown")
                            except Exception as ne:
                                logger.warning(f"Gagal kirim notif ke admin {admin_id}: {ne}")
                except Exception as ne2:
                    logger.error(f"notif admin jual error: {ne2}")
            except Exception as e:
                logger.error(f"jual_akun_confirm: {e}\n{traceback.format_exc()}")
            return

        if data.startswith("jual_batal_") or data.startswith("jual_akun_batal_"):
            try:
                await query.edit_message_text("❌ Dibatalkan", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            except:
                pass
            return

        if data.startswith("edit_") and not data.startswith("edit_akun_"):
            try:
                rid = int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT content_raw, akun FROM hasil_format WHERE id=?", (rid,))
                row=c.fetchone()
                conn.close()
                if not row:
                    await query.edit_message_text("❌ Tidak ditemukan", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                    return
                context.user_data["editing_format_id"]=rid
                context.user_data["state"]="awaiting_edit_format"
                await query.edit_message_text(f"✏️ EDIT ID {rid}\nLama:\n{row[0]}\n{row[1]}\n\nKirim 13 baris baru\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            except Exception as e:
                logger.error(f"edit: {e}")
            return

        if data.startswith("edit_akun_"):
            try:
                rid=int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT content FROM hasil_akun WHERE id=?", (rid,))
                row=c.fetchone()
                conn.close()
                if not row:
                    await query.edit_message_text("❌ Tidak ada", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                    return
                context.user_data["editing_akun_id"]=rid
                context.user_data["state"]="awaiting_edit_akun"
                await query.edit_message_text(f"✏️ EDIT AKUN {rid}\nLama: {row[0]}\nKirim baru", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            except Exception as e:
                logger.error(f"edit_akun: {e}")
            return

        if data == "data_saya":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT COUNT(*) FROM personal_data WHERE user_id=?", (user_id,))
                pd=c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (user_id,))
                f=c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM hasil_akun WHERE user_id=?", (user_id,))
                a=c.fetchone()[0]
                conn.close()
                txt = f"📁 DATA SAYA\n\nPersonal Data: {pd}\nFormat: {f} Akun: {a}"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 MASUKAN DATA", callback_data="ds_masukan"), InlineKeyboardButton("📄 HASIL DATA", callback_data="ds_hasil")],
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
                ])
                await query.edit_message_text(txt, reply_markup=kb)
            except Exception as e:
                logger.error(f"data_saya: {e}\n{traceback.format_exc()}")
                await query.edit_message_text("📁 DATA SAYA", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            return

        if data == "ds_masukan":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT COUNT(*) FROM personal_data WHERE user_id=?", (user_id,))
                cnt=c.fetchone()[0]
                conn.close()
                txt = f"📥 MASUKAN DATA\n\nTotal data kamu: {cnt}\n\nDi sini kamu bisa menyimpan data baru."
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ TAMBAH", callback_data="ds_tambah"), InlineKeyboardButton("🔍 CARI", callback_data="ds_cari")],
                    [InlineKeyboardButton("🗑️ HAPUS", callback_data="ds_hapus_menu"), InlineKeyboardButton("📤 EXPORT .xlsx", callback_data="ds_export")],
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]
                ])
                await query.edit_message_text(txt, reply_markup=kb)
            except Exception as e:
                logger.error(f"ds_masukan: {e}")
                await query.edit_message_text("📥 MASUKAN DATA", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]]))
            return

        if data == "ds_tambah":
            try:
                context.user_data["state"]="awaiting_data_saya"
                await query.edit_message_text("➕ TAMBAH DATA\n\nKirim data baru yang mau disimpan.\nBisa format JMO atau catatan bebas.\n\n/cancel untuk batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ BATAL", callback_data="ds_masukan"), InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]]))
            except:
                pass
            return

        if data == "ds_hapus_menu":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, content FROM personal_data WHERE user_id=? ORDER BY id DESC LIMIT 20", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("🗑️ Tidak ada data untuk dihapus", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="ds_masukan")]]))
                    return
                await query.edit_message_text(f"🗑️ Pilih data yang mau dihapus ({len(rows)} data terbaru):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="ds_masukan")]]))
                for rid, cont in rows:
                    preview = (cont[:50] + "...") if len(cont)>50 else cont
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🗑️ HAPUS", callback_data=f"ds_del_{rid}"), InlineKeyboardButton("🔙 KEMBALI", callback_data="ds_masukan")]
                    ])
                    await context.bot.send_message(chat_id=query.message.chat_id, text=f"ID:{rid}\n{preview}", reply_markup=kb)
            except Exception as e:
                logger.error(f"ds_hapus_menu: {e}")
            return

        if data.startswith("ds_del_"):
            try:
                rid=int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                c.execute("DELETE FROM personal_data WHERE id=? AND user_id=?", (rid, user_id))
                conn.commit()
                conn.close()
                await query.edit_message_text(f"🗑️ Data ID {rid} dihapus", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="ds_masukan")]]))
            except Exception as e:
                logger.error(f"ds_del: {e}")
            return

        if data == "ds_hasil":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, content, created_at FROM personal_data WHERE user_id=? ORDER BY id ASC LIMIT 100", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("📄 HASIL DATA kosong\n\nBelum ada data. Silakan tambah di MASUKAN DATA.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ TAMBAH", callback_data="ds_tambah"), InlineKeyboardButton("🔍 CARI", callback_data="ds_cari")],[InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]]))
                    return
                await query.edit_message_text(f"📄 {len(rows)} HASIL DATA:\n\nPilih aksi:", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 CARI DATA", callback_data="ds_cari"), InlineKeyboardButton("➕ TAMBAH", callback_data="ds_tambah")],
                    [InlineKeyboardButton("📤 EXPORT .xlsx", callback_data="ds_export"), InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]
                ]))
                for rid, cont, created in rows:
                    card = f"{cont[:3500]}\n\nID:{rid} | {created}"
                    # Tombol Edit, Hapus, Jual, Kembali untuk setiap hasil
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✏️ EDIT", callback_data=f"ds_edit_{rid}"), InlineKeyboardButton("🗑️ HAPUS", callback_data=f"ds_del_{rid}")],
                        [InlineKeyboardButton("💰 JUAL", callback_data=f"ds_jual_{rid}"), InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")],
                        [InlineKeyboardButton("📋 COPY CODE", callback_data=f"ds_copy_{rid}")]
                    ])
                    await context.bot.send_message(chat_id=query.message.chat_id, text=card, reply_markup=kb)
            except Exception as e:
                logger.error(f"ds_hasil: {e}\n{traceback.format_exc()}")
                await query.message.reply_text("❌ Error hasil data")
            return

        if data == "ds_cari":
            try:
                context.user_data["state"]="awaiting_data_saya_cari"
                await query.edit_message_text("🔍 CARI DATA\n\nKirim kata kunci yang mau dicari (misal: NIAS, nama, NIK, dll)\n\n/cancel untuk batal", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ BATAL", callback_data="ds_hasil"), InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]
                ]))
            except Exception as e:
                logger.error(f"ds_cari: {e}")
            return

        if data.startswith("ds_edit_"):
            try:
                rid=int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT content FROM personal_data WHERE id=? AND user_id=?", (rid, user_id))
                row=c.fetchone()
                conn.close()
                if row:
                    context.user_data["state"]="awaiting_data_saya_edit"
                    context.user_data["edit_id"]=rid
                    await query.edit_message_text(f"✏️ EDIT DATA ID {rid}\n\nData lama:\n{row[0][:1000]}\n\nKirim data baru untuk mengganti.\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ BATAL", callback_data="ds_hasil"), InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]]))
                else:
                    await query.edit_message_text("❌ Data tidak ditemukan", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="ds_hasil")]]))
            except Exception as e:
                logger.error(f"ds_edit: {e}")
            return

        if data.startswith("ds_copy_"):
            try:
                rid=int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT content FROM personal_data WHERE id=? AND user_id=?", (rid, user_id))
                row=c.fetchone()
                conn.close()
                if row:
                    await query.message.reply_text(f"📋 COPY DATA ID {rid}:\n\n{row[0]}")
            except:
                pass
            return

        if data.startswith("ds_jual_"):
            try:
                rid=int(data.split("_")[-1])
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ YA", callback_data=f"ds_jual_confirm_{rid}"), InlineKeyboardButton("❌ BATAL", callback_data=f"ds_jual_batal_{rid}")],
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="ds_hasil")]
                ])
                await query.edit_message_text("Apakah Anda yakin ingin menjual ini?", reply_markup=kb)
            except:
                pass
            return

        if data.startswith("ds_jual_confirm_"):
            try:
                rid=int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT * FROM personal_data WHERE id=? AND user_id=?", (rid, user_id))
                cols=[d[0] for d in c.description] if c.description else []
                row=c.fetchone()
                if row:
                    d=dict(zip(cols,row))
                    c.execute("INSERT INTO riwayat (user_id, tipe, content, content_display, deleted_at, original_id) VALUES (?,?,?,?,?,?)",
                              (user_id, "terjual_data_saya", d.get('content',''), d.get('content',''), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), d.get('id',0)))
                    c.execute("DELETE FROM personal_data WHERE id=?", (rid,))
                    conn.commit()
                    await query.edit_message_text(f"✅ Data ID {rid} terjual & masuk HISTORY", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]]))
                conn.close()
            except Exception as e:
                logger.error(f"ds_jual_confirm: {e}")
            return

        if data.startswith("ds_jual_batal_"):
            await query.edit_message_text("❌ Batal jual", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="ds_hasil")]]))
            return

        if data == "ds_export":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, content, kode, created_at FROM personal_data WHERE user_id=? ORDER BY id DESC", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("📤 Tidak ada data untuk di-export", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="ds_hasil")]]))
                    return
                # Buat Excel
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "DATA SAYA"
                ws.append(["ID", "KODE", "CONTENT", "CREATED_AT"])
                for rid, cont, kode, created in rows:
                    ws.append([rid, kode or "", cont, created or ""])
                # Auto width
                for col in ws.columns:
                    max_len = 0
                    column = col[0].column_letter
                    for cell in col:
                        try:
                            if cell.value and len(str(cell.value)) > max_len:
                                max_len = len(str(cell.value))
                        except:
                            pass
                    adjusted = min(max_len + 2, 60)
                    ws.column_dimensions[column].width = adjusted
                file_path = f"/tmp/data_saya_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                wb.save(file_path)
                await context.bot.send_document(chat_id=query.message.chat_id, document=open(file_path, 'rb'), filename=f"DATA_SAYA_{len(rows)}_data.xlsx", caption=f"📤 EXPORT DATA SAYA\nTotal: {len(rows)} data")
                await query.edit_message_text(f"✅ Export berhasil {len(rows)} data", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📄 HASIL DATA", callback_data="ds_hasil")],
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]
                ]))
            except Exception as e:
                logger.error(f"ds_export: {e}\n{traceback.format_exc()}")
                await query.edit_message_text("❌ Gagal export", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="data_saya")]]))
            return

        if data == "data_saya_all":
            if not is_admin(user_id):
                await query.edit_message_text("⛔ Hanya admin", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                return
            try:
                conn=get_conn()
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
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
                ]))
            except Exception as e:
                logger.error(f"data_saya_all: {e}")
            return

        if data == "data_saya_all_format":
            if not is_admin(user_id): return
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, content_display, kode FROM hasil_format ORDER BY CAST(sex_code AS INTEGER) ASC LIMIT 20")
                rows=c.fetchall()
                conn.close()
                await query.edit_message_text(f"📋 FORMAT ALL {len(rows)}")
                for rid, display, kode in rows:
                    kb = four_buttons_format(rid, display)
                    await context.bot.send_message(chat_id=query.message.chat_id, text=f"{display}\nID:{rid}"[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"data_saya_all_format: {e}")
            return

        if data == "data_saya_all_akun":
            if not is_admin(user_id): return
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, content, kode FROM hasil_akun ORDER BY id ASC LIMIT 20")
                rows=c.fetchall()
                conn.close()
                await query.edit_message_text(f"💳 AKUN ALL {len(rows)}")
                for rid, content, kode in rows:
                    kb = four_buttons_akun(rid, content)
                    await context.bot.send_message(chat_id=query.message.chat_id, text=f"ID:{rid} {kode}\n{content}"[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"data_saya_all_akun: {e}")
            return

        if data == "riwayat":
            await query.edit_message_text("🕘 RIWAYAT", reply_markup=riwayat_menu())
            return
        if data == "rw_lihat" or data == "rw_history_format":
            try:
                conn=get_conn()
                c=conn.cursor()
                # HISTORY FORMAT = tipe format + terjual, urut ASC biar 001 di atas, tapi waktu tetap tampil
                c.execute("SELECT id, tipe, kode, content_display, content, deleted_at, sex_code FROM riwayat WHERE user_id=? AND tipe IN ('format','terjual') ORDER BY deleted_at ASC, id ASC LIMIT 100", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("📄 HISTORY FORMAT kosong\n\nBelum ada data terjual/dihapus di format.", reply_markup=riwayat_menu())
                    return
                await query.edit_message_text(f"📄 {len(rows)} HISTORY FORMAT (ada waktunya):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="riwayat")]]))
                no=1
                for rid, tipe, kode, display, cont, deleted_at, sex in rows:
                    show = display if display else cont
                    tipe_label = "💰 TERJUAL" if "jual" in tipe.lower() or tipe=="terjual" else "🗑️ DIHAPUS"
                    waktu = deleted_at if deleted_at else "-"
                    # Format dengan waktu jual
                    card = f"{no}. ID {rid} | {tipe_label}\n🕘 Waktu: {waktu}\nKode: {kode or sex or '-'}\n```\n{show}\n```"
                    kb = riwayat_item_menu(rid)
                    await context.bot.send_message(chat_id=query.message.chat_id, text=card, reply_markup=kb, parse_mode="Markdown")
                    no+=1
                await context.bot.send_message(chat_id=query.message.chat_id, text="Selesai HISTORY FORMAT", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="riwayat")]]))
            except Exception as e:
                logger.error(f"rw_history_format: {e}\n{traceback.format_exc()}")
                await query.message.reply_text("❌ Error history format")
            return


        if data == "rw_history_akun":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT id, tipe, kode, content_display, content, deleted_at, sex_code, akun FROM riwayat WHERE user_id=? AND tipe IN ('akun','terjual_akun') ORDER BY deleted_at ASC, id ASC LIMIT 100", (user_id,))
                rows=c.fetchall()
                conn.close()
                if not rows:
                    await query.edit_message_text("💳 HISTORY AKUN kosong\n\nBelum ada data terjual/dihapus di akun.", reply_markup=riwayat_menu())
                    return
                await query.edit_message_text(f"💳 {len(rows)} HISTORY AKUN (ada waktunya):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="riwayat")]]))
                no=1
                for rid, tipe, kode, display, cont, deleted_at, sex, akun in rows:
                    show = display if display else cont
                    if akun and akun.strip() != "-":
                        show = f"{show}\n{akun}"
                    tipe_label = "💰 TERJUAL" if "jual" in tipe.lower() or "terjual" in tipe.lower() else "🗑️ DIHAPUS"
                    waktu = deleted_at if deleted_at else "-"
                    card = f"{no}. ID {rid} | {tipe_label}\n🕘 Waktu: {waktu}\nKode: {kode or sex or '-'}\n```\n{show}\n```"
                    kb = riwayat_item_menu(rid)
                    await context.bot.send_message(chat_id=query.message.chat_id, text=card, reply_markup=kb, parse_mode="Markdown")
                    no+=1
                await context.bot.send_message(chat_id=query.message.chat_id, text="Selesai HISTORY AKUN", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="riwayat")]]))
            except Exception as e:
                logger.error(f"rw_history_akun: {e}\n{traceback.format_exc()}")
                await query.message.reply_text("❌ Error history akun")
            return

                await query.edit_message_text(f"📋 {len(rows)} RIWAYAT:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                for rid, tipe, kode, display, content, deleted_at, sex in rows:
                    txt = display if tipe=="format" else content
                    card = f"{txt}\n\nID:{rid} Dihapus:{deleted_at}"
                    kb = riwayat_item_menu(rid)
                    await context.bot.send_message(chat_id=query.message.chat_id, text=card[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"rw_lihat: {e}")
            return
        if data == "rw_cari":
            context.user_data["state"]="awaiting_search_riwayat"
            await query.edit_message_text("🔍 CARI RIWAYAT - kata kunci", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            return
        if data == "rw_hapus_all":
            await query.edit_message_text("Yakin HAPUS PERMANEN SEMUA RIWAYAT?", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ YA", callback_data="rw_hapus_all_confirm"), InlineKeyboardButton("❌ Batal", callback_data="riwayat")],
                [InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
            ]))
            return
        if data == "rw_hapus_all_confirm":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("DELETE FROM riwayat WHERE user_id=?", (user_id,))
                conn.commit()
                conn.close()
                await query.edit_message_text("✅ Riwayat hapus permanen", reply_markup=riwayat_menu())
            except Exception as e:
                logger.error(f"rw_hapus_all_confirm: {e}")
            return
        if data == "rw_pulihkan_all":
            try:
                conn=get_conn()
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
            except Exception as e:
                logger.error(f"rw_pulihkan_all: {e}")
            return

        if data.startswith("copy_rw_") or data.startswith("del_rw_") or data.startswith("restore_rw_"):
            try:
                rid=int(data.split("_")[-1])
                conn=get_conn()
                c=conn.cursor()
                if data.startswith("copy_rw_"):
                    c.execute("SELECT content_display, content FROM riwayat WHERE id=?", (rid,))
                    row=c.fetchone()
                    conn.close()
                    if row:
                        txt = row[0] or row[1]
                        await context.bot.send_message(chat_id=query.message.chat_id, text=f"📋 COPY RW {rid}:\n{txt}"[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                elif data.startswith("del_rw_"):
                    c.execute("DELETE FROM riwayat WHERE id=?", (rid,))
                    conn.commit()
                    conn.close()
                    await query.edit_message_text(f"🗑️ RW {rid} hapus permanen", reply_markup=riwayat_menu())
                else: # restore
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
            except Exception as e:
                logger.error(f"rw action {data}: {e}")
            return

        if data == "setting":
            await query.edit_message_text("⚙️ SETTING", reply_markup=setting_menu())
            return
        if data == "set_templat":
            try:
                s=get_setting(user_id)
                t=s.get("template","") or "- belum diset -"
                preview = f"📝 TEMPLAT\n\nTemplate aktif:\n{t[:2000]}\n\nGunakan {{KAB}} {{KEC}} {{KEL}} {{SALDO}} {{KELAMIN}} {{KPJ}} {{SENSOR}} {{IT}} {{PT}}"
                await query.edit_message_text(preview, reply_markup=setting_templat_menu())
            except Exception as e:
                logger.error(f"set_templat: {e}")
                await query.edit_message_text("📝 TEMPLAT", reply_markup=setting_templat_menu())
            return

        if data == "set_templat_ubah":
            try:
                s=get_setting(user_id)
                cur = s.get("template","")
                context.user_data["state"]="awaiting_template"
                await query.edit_message_text(
                    f"✏️ UBAH TEMPLAT\n\nTemplate sekarang:\n{cur[:1500]}\n\nKirim template baru. Contoh:\n📍KAB : {{KAB}}\n📍KEC : {{KEC}}\n💰 SALDO : {{SALDO}}\n\n/cancel batal",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ BATAL", callback_data="set_templat"), InlineKeyboardButton("🔙 KEMBALI", callback_data="setting")]])
                )
            except Exception as e:
                logger.error(f"set_templat_ubah: {e}")
            return

        if data == "set_templat_edit":
            context.user_data["state"]="awaiting_template"
            await query.edit_message_text(
                "✏️ UBAH TEMPLATE\n\nKirim template baru kamu.\nGunakan placeholder:\n{KAB} {KEC} {KEL} {SALDO} {KELAMIN} {KPJ} {SENSOR} {IURAN_T} {PT} {KODE_ATAS}\n\nContoh:\n📍KAB  : {KAB}\n📍KEC  : {KEC}\n...\n\n/cancel untuk batal",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ BATAL", callback_data="setting"), InlineKeyboardButton("🔙 KEMBALI", callback_data="set_templat")]])
            )
            return

        if data == "set_kode_hapus":
            try:
                save_setting(user_id, kode_atas="")
                txt = setting_auto_format_text(user_id)
                await query.edit_message_text(f"🗑️ Kode dihapus!\n\n{txt}", reply_markup=setting_auto_format_menu())
            except Exception as e:
                logger.error(f"set_kode_hapus: {e}")
                await query.edit_message_text("✅ Kode dihapus", reply_markup=setting_menu())
            return
        if data == "set_kode_atas":
            try:
                cur_set = get_setting(user_id)
                cur_ka = cur_set.get("kode_atas","") or "- belum diset -"
                txt = f"🔢 SET KODE ATAS\n\nIni adalah FORMAT OTOMATIS yang akan ikut saat BUAT FORMAT.\n\nKode aktif sekarang:\n{cur_ka}\n\nContoh hasil otomatis:\n{cur_ka}\n{GARIS}\n[isi format JMO]\n\nPilih menu:"
                await query.edit_message_text(txt, reply_markup=setting_kode_atas_menu())
            except Exception as e:
                logger.error(f"set_kode_atas menu: {e}")
                await query.edit_message_text("🔢 SET KODE ATAS", reply_markup=setting_kode_atas_menu())
            return

        if data == "set_kode_atas_saya":
            try:
                cur_set = get_setting(user_id)
                cur_ka = cur_set.get("kode_atas","")
                if not cur_ka:
                    await query.edit_message_text("👁️ KODE SAYA - KODE ATAS\n\nBelum ada kode. Silakan GANTI KODE.", reply_markup=setting_kode_atas_menu())
                else:
                    await query.edit_message_text(f"👁️ KODE SAYA - KODE ATAS\n\nKode kamu sekarang:\n{cur_ka}\n{GARIS}\n\nIni akan otomatis muncul di atas setiap HASIL FORMAT.", reply_markup=setting_kode_atas_menu())
            except Exception as e:
                logger.error(f"kode_atas_saya: {e}")
            return

        if data == "set_kode_atas_ganti":
            try:
                context.user_data["state"]="awaiting_kode_atas"
                await query.edit_message_text(f"✏️ GANTI KODE ATAS\n\nKirim kode baru, contoh: MBG 0001 atau ABH 172\n\nNanti otomatis jadi:\nMBG 0001\n{GARIS}\n[isi format]\n\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ BATAL", callback_data="set_kode_atas"), InlineKeyboardButton("🔙 KEMBALI", callback_data="setting")]]))
            except Exception as e:
                logger.error(f"kode_atas_ganti: {e}")
            return

        if data == "set_kode_atas_hapus":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("UPDATE settings SET kode_atas='' WHERE user_id=?", (user_id,))
                conn.commit()
                conn.close()
                await query.edit_message_text("🗑️ KODE ATAS dihapus! Sekarang format otomatis tanpa kode atas.", reply_markup=setting_kode_atas_menu())
            except Exception as e:
                logger.error(f"kode_atas_hapus: {e}")
            return
        if data == "set_kode_bawah":
            try:
                cur_set = get_setting(user_id)
                cur_kb = cur_set.get("kode_bawah","") or "- belum diset -"
                txt = f"🔢 SET KODE BAWAH\n\nIni FORMAT OTOMATIS footer yang ikut saat BUAT FORMAT.\n\nKode aktif sekarang:\n{cur_kb}\n\nContoh hasil otomatis:\n[isi format]\n{GARIS}\n{cur_kb}\n\nPilih menu:"
                await query.edit_message_text(txt, reply_markup=setting_kode_bawah_menu())
            except Exception as e:
                logger.error(f"set_kode_bawah menu: {e}")
                await query.edit_message_text("🔢 SET KODE BAWAH", reply_markup=setting_kode_bawah_menu())
            return

        if data == "set_kode_bawah_saya":
            try:
                cur_set = get_setting(user_id)
                cur_kb = cur_set.get("kode_bawah","")
                if not cur_kb:
                    await query.edit_message_text("👁️ KODE SAYA - KODE BAWAH\n\nBelum ada kode. Silakan UBAH KODE.", reply_markup=setting_kode_bawah_menu())
                else:
                    await query.edit_message_text(f"👁️ KODE SAYA - KODE BAWAH\n\nKode kamu sekarang:\n{cur_kb}\n\nIni akan otomatis muncul di bawah setiap HASIL FORMAT:\n{GARIS}\n{cur_kb}", reply_markup=setting_kode_bawah_menu())
            except Exception as e:
                logger.error(f"kode_bawah_saya: {e}")
            return

        if data == "set_kode_bawah_ganti":
            try:
                context.user_data["state"]="awaiting_kode_bawah"
                await query.edit_message_text(f"✏️ UBAH KODE BAWAH\n\nKirim kode baru, contoh: MBG 0001\n\nNanti otomatis jadi:\n[isi format]\n{GARIS}\nMBG 0001\n\n/cancel batal", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ BATAL", callback_data="set_kode_bawah"), InlineKeyboardButton("🔙 KEMBALI", callback_data="setting")]]))
            except Exception as e:
                logger.error(f"kode_bawah_ganti: {e}")
            return

        if data == "set_kode_bawah_hapus":
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("UPDATE settings SET kode_bawah='' WHERE user_id=?", (user_id,))
                conn.commit()
                conn.close()
                await query.edit_message_text("🗑️ KODE BAWAH dihapus! Format otomatis tanpa footer.", reply_markup=setting_kode_bawah_menu())
            except Exception as e:
                logger.error(f"kode_bawah_hapus: {e}")
            return
        if data == "panel_admin":
            if not is_admin(user_id):
                await query.edit_message_text("⛔ Bukan admin!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
                return
            try:
                conn=get_conn()
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
            except Exception as e:
                logger.error(f"panel_admin: {e}")
            return

        if data == "admin_cek_user":
            if not is_admin(user_id): return
            try:
                conn=get_conn()
                c=conn.cursor()
                c.execute("SELECT user_id, username, first_name FROM users ORDER BY user_id DESC LIMIT 20")
                rows=c.fetchall()
                msg="👥 USER AKTIF:\n"
                for uid, uname, fname in rows:
                    c.execute("SELECT COUNT(*) FROM hasil_format WHERE user_id=?", (uid,))
                    jf=c.fetchone()[0]
                    msg+=f"ID:{uid} @{uname or '-'} F:{jf}\n"
                conn.close()
                await query.edit_message_text(msg[:4000], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="admin_cek_user"), InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            except Exception as e:
                logger.error(f"admin_cek_user: {e}")
            return
        if data in ("admin_hapus_user","admin_tambah_admin","admin_hapus_admin","admin_broadcast","data_cari_all"):
            if not is_admin(user_id): return
            mapping = {
                "admin_hapus_user": "awaiting_admin_hapus_user",
                "admin_tambah_admin": "awaiting_admin_tambah_admin",
                "admin_hapus_admin": "awaiting_admin_hapus_admin",
                "admin_broadcast": "awaiting_admin_broadcast",
                "data_cari_all": "awaiting_search_all_admin"
            }
            context.user_data["state"]=mapping[data]
            prompts = {
                "admin_hapus_user": "🗑️ HAPUS USER - kirim ID\n/cancel batal",
                "admin_tambah_admin": "➕ TAMBAH ADMIN - kirim ID",
                "admin_hapus_admin": "➖ HAPUS ADMIN - kirim ID",
                "admin_broadcast": "📢 BROADCAST - kirim pesan",
                "data_cari_all": "🔍 CARI SEMUA USER - kata kunci"
            }
            await query.edit_message_text(prompts[data], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]]))
            if data == "admin_hapus_admin":
                try:
                    conn=get_conn()
                    c=conn.cursor()
                    c.execute("SELECT user_id FROM admins")
                    rows=c.fetchall()
                    conn.close()
                    txt = "Admin DB:\n" + "\n".join([str(r[0]) for r in rows]) if rows else "Belum ada admin DB"
                    await context.bot.send_message(chat_id=query.message.chat_id, text=txt)
                except: pass
            return

    except Exception as e:
        logger.error(f"button_handler global: {e}\n{traceback.format_exc()}")
        try:
            await update.callback_query.message.reply_text("⚠️ Error, tapi bot tetap jalan. /start lagi", reply_markup=main_menu())
        except: pass

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id=update.effective_user.id
        text=update.message.text or ""
        state=context.user_data.get("state")
        if text=="/cancel":
            context.user_data["state"]=None
            await update.message.reply_text("Dibatalkan", reply_markup=main_menu())
            return
        # === STATE HANDLERS ===
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
            try:
                keyword=text.lower()
                conn=get_conn()
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
                        kb = four_buttons_format(rid, display)
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{display}\nKODE:{kode}"[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"search_format: {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_delete_format_kode":
            try:
                keyword=text.lower()
                conn=get_conn()
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
            except Exception as e:
                logger.error(f"delete_format: {e}")
                await update.message.reply_text(f"❌ Error: {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_search_akun":
            try:
                keyword=text.lower()
                conn=get_conn()
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
                        kb = four_buttons_akun(rid, content)
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"ID:{rid} KODE:{kode}\n{content}"[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"search_akun: {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_delete_akun_kode":
            try:
                keyword=text.lower()
                conn=get_conn()
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
            except Exception as e:
                logger.error(f"delete_akun: {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_search_riwayat":
            try:
                keyword=text.lower()
                conn=get_conn()
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
                            [InlineKeyboardButton("📋 COPY", callback_data=f"copy_rw_{rid}"), InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]
                        ])
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=card[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"search_riwayat: {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_search_all_admin":
            if not is_admin(user_id):
                context.user_data["state"]=None
                return
            try:
                keyword=text.lower()
                conn=get_conn()
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
                        kb = four_buttons_format(rid, display)
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"User:{uid} SEX:{sex} KODE:{kode}\n{display}"[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"search_all: {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_admin_hapus_user":
            if not is_admin(user_id):
                context.user_data["state"]=None
                return
            try:
                target_id = int(text.strip())
                conn=get_conn()
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
            except Exception as e:
                logger.error(f"admin_hapus_user: {e}")
                await update.message.reply_text(f"❌ Error: {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_admin_tambah_admin":
            if not is_admin(user_id):
                context.user_data["state"]=None
                return
            try:
                target_id = int(text.strip())
                add_admin_db(target_id, user_id)
                await update.message.reply_text(f"✅ ID {target_id} jadi ADMIN!", reply_markup=admin_menu())
            except Exception as e:
                await update.message.reply_text(f"❌ ID harus angka! {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_admin_hapus_admin":
            if not is_admin(user_id):
                context.user_data["state"]=None
                return
            try:
                target_id = int(text.strip())
                remove_admin_db(target_id)
                await update.message.reply_text(f"✅ Admin {target_id} dihapus!", reply_markup=admin_menu())
            except:
                await update.message.reply_text("❌ ID harus angka!")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_admin_broadcast":
            if not is_admin(user_id):
                context.user_data["state"]=None
                return
            broadcast_text = text
            try:
                conn=get_conn()
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
            except Exception as e:
                logger.error(f"broadcast: {e}")
            finally:
                context.user_data["state"]=None
            return
        if state=="awaiting_edit_format":
            try:
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
                conn=get_conn()
                c=conn.cursor()
                c.execute("UPDATE hasil_format SET content=?, content_raw=?, content_formatted=?, content_display=?, kode=?, kab=?, kec=?, kel=?, saldo=?, kelamin=?, kpj=?, sensor=?, iuran_t=?, pt=?, akun=? WHERE id=?",
                          (p['raw_format'], p['raw_format'], p['content_formatted'], p['content_display'], p['kode'], p['kab'], p['kec'], p['kel'], p['saldo'], p['kelamin'], p['kpj'], p['sensor'], p['iuran_t'], p['pt'], p['akun'], editing_id))
                conn.commit()
                conn.close()
                context.user_data["state"]=None
                context.user_data["editing_format_id"]=None
                await update.message.reply_text(f"✅ EDIT OK ID {editing_id}", reply_markup=main_menu())
                kb = four_buttons_format(editing_id, p['content_display'])
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{p['content_display']}\nID:{editing_id}"[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"edit_format: {e}\n{traceback.format_exc()}")
                await update.message.reply_text(f"❌ Gagal edit: {e}")
                context.user_data["state"]=None
            return
        if state=="awaiting_edit_akun":
            try:
                editing_id = context.user_data.get("editing_akun_id")
                if not editing_id:
                    context.user_data["state"]=None
                    return
                new_content = text.strip()
                kode=""
                lines=[l.strip() for l in new_content.splitlines() if l.strip()!=""]
                for l in lines:
                    if re.match(r"^\d{16}$", l.replace(" ","")):
                        kode=l; break
                if not kode:
                    kode=lines[0] if lines else ""
                conn=get_conn()
                c=conn.cursor()
                c.execute("UPDATE hasil_akun SET content=?, kode=?, akun=? WHERE id=?", (new_content, kode, new_content, editing_id))
                conn.commit()
                conn.close()
                context.user_data["state"]=None
                context.user_data["editing_akun_id"]=None
                await update.message.reply_text(f"✅ EDIT AKUN OK ID {editing_id}", reply_markup=main_menu())
                kb = four_buttons_akun(editing_id, new_content)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"ID:{editing_id} {kode}\n{new_content}"[:4000], reply_markup=kb)
            except Exception as e:
                logger.error(f"edit_akun: {e}")
                context.user_data["state"]=None
            return
        if state=="awaiting_manual":
            try:
                results=process_blocks(text,user_id)
                if not results:
                    await update.message.reply_text("❌ Format tidak terbaca")
                    return
                conn=get_conn()
                c=conn.cursor()
                success=0
                new_ids=[]
                for p,e in results:
                    if e or not p: continue
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
                conn=get_conn()
                c=conn.cursor()
                for nid in new_ids:
                    c.execute("SELECT content_display, kode FROM hasil_format WHERE id=?", (nid,))
                    row=c.fetchone()
                    if row:
                        display, kode = row
                        kb = four_buttons_format(nid, display)
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{display}\n\nID:{nid} KODE:{kode}"[:4000], reply_markup=kb)
                conn.close()
            except Exception as e:
                logger.error(f"awaiting_manual: {e}\n{traceback.format_exc()}")
                await update.message.reply_text(f"❌ Error: {e}")
                context.user_data["state"]=None
            return
        # DEFAULT: langsung proses
        try:
            results=process_blocks(text,user_id)
            if not results:
                await update.message.reply_text("Pilih menu:", reply_markup=main_menu())
                return
            conn=get_conn()
            c=conn.cursor()
            success=0
            new_ids=[]
            for p,e in results:
                if e or not p: continue
                c.execute("INSERT INTO hasil_format (user_id, content, content_raw, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, created_at, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (user_id, p['raw_format'], p['raw_format'], p['content_formatted'], p['content_display'], p['kode'], p['kab'], p['kec'], p['kel'], p['saldo'], p['kelamin'], p['kpj'], p['sensor'], p['iuran_t'], p['pt'], p['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p['sex_code']))
                new_ids.append(c.lastrowid)
                c.execute("INSERT INTO hasil_akun (user_id, content, kode, akun, created_at) VALUES (?,?,?,?,?)",(user_id, p['raw_akun'], p['kode'], p['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                success+=1
            conn.commit()
            conn.close()
            await update.message.reply_text(f"✅ Berhasil {success} data! Kode urut otomatis.", reply_markup=main_menu())
            conn=get_conn()
            c=conn.cursor()
            for nid in new_ids:
                c.execute("SELECT content_display, kode FROM hasil_format WHERE id=?", (nid,))
                row=c.fetchone()
                if row:
                    display, kode = row
                    kb = four_buttons_format(nid, display)
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{display}\n\nID:{nid} KODE:{kode}"[:4000], reply_markup=kb)
            conn.close()
        except Exception as e:
            logger.error(f"message_handler default: {e}\n{traceback.format_exc()}")
            await update.message.reply_text(f"❌ Gagal: {e}", reply_markup=main_menu())

    except Exception as e:
        logger.error(f"message_handler global: {e}\n{traceback.format_exc()}")
        try:
            await update.message.reply_text("⚠️ Error, tapi bot tetap jalan. Coba /start", reply_markup=main_menu())
        except: pass

async def excel_handler(update, context):
    if context.user_data.get("state")!="awaiting_excel":
        try:
            await update.message.reply_text("Klik BIKIN FORMAT -> Upload .xlsx", reply_markup=main_menu())
        except: pass
        return
    user_id=update.effective_user.id
    path=f"/tmp/temp_{user_id}.xlsx"
    Path("/tmp").mkdir(parents=True, exist_ok=True)
    try:
        file=await update.message.document.get_file()
        await file.download_to_drive(path)
        df=pd.read_excel(path,dtype=str).fillna("")
        conn=get_conn()
        c=conn.cursor()
        success=0
        start_code = get_next_sex_code(user_id)
        new_ids=[]
        for idx,row in df.iterrows():
            try:
                vals=[str(v).strip() for v in row.tolist() if str(v).strip()!=""]
                if len(vals)<9: continue
                block="\n".join(vals)
                p,e=parse_jmo_block(block,user_id, sex_counter=start_code+idx)
                if e or not p: continue
                c.execute("INSERT INTO hasil_format (user_id, content, content_raw, content_formatted, content_display, kode, kab, kec, kel, saldo, kelamin, kpj, sensor, iuran_t, pt, akun, created_at, sex_code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (user_id, p['raw_format'], p['raw_format'], p['content_formatted'], p['content_display'], p['kode'], p['kab'], p['kec'], p['kel'], p['saldo'], p['kelamin'], p['kpj'], p['sensor'], p['iuran_t'], p['pt'], p['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p['sex_code']))
                new_ids.append(c.lastrowid)
                c.execute("INSERT INTO hasil_akun (user_id, content, kode, akun, created_at) VALUES (?,?,?,?,?)",(user_id, p['raw_akun'], p['kode'], p['akun'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                success+=1
            except Exception as e_row:
                logger.warning(f"excel row {idx} skip: {e_row}")
                continue
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ {success} data dari .xlsx (urut kode)", reply_markup=main_menu())
        conn=get_conn()
        c=conn.cursor()
        for nid in new_ids:
            try:
                c.execute("SELECT content_display, kode FROM hasil_format WHERE id=?", (nid,))
                row=c.fetchone()
                if row:
                    display, kode = row
                    kb = four_buttons_format(nid, display)
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{display}\nID:{nid} KODE:{kode}"[:4000], reply_markup=kb)
            except: continue
        conn.close()
    except Exception as e:
        logger.error(f"excel_handler: {e}\n{traceback.format_exc()}")
        try:
            await update.message.reply_text(f"❌ Gagal baca Excel: {e}")
        except: pass
    finally:
        if os.path.exists(path):
            try: os.remove(path)
            except: pass
        context.user_data["state"]=None

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}\n{''.join(traceback.format_exception(None, context.error, context.error.__traceback__))}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        txt = f"""🆘 HELP - SAHABAT JHT BOT

📚 Daftar Perintah:
/start - Menu utama
/profil - Lihat profil kamu
/buat_format - Buat format baru
/hasil_format - Lihat hasil format (tanpa NIK)
/hasil_akun - Lihat hasil akun (full + NIK)
/setting - Setting template & kode
/riwayat - History format & akun yang terjual/dihapus
/help - Bantuan ini

⌨️ CARA PAKAI:
1. Klik BIKIN FORMAT
2. Kirim data 9 baris:
   KAB
   KEC
   KEL
   SALDO
   KELAMIN
   KPJ
   SENSOR
   IT
   PT
   + baris tambahan NIK, KPJ, Nama, TTL (akan masuk ke HASIL AKUN)

3. Hasil otomatis:
   • HASIL FORMAT = ABH 172 + garis + body sampai PT
   • HASIL AKUN = body + NIK dll

⚙️ SETTING:
• TEMPLAT - ubah template (pakai {{KAB}} {{KEC}} {{KEL}} {{SALDO}} {{KELAMIN}} {{KPJ}} {{SENSOR}} {{IT}} {{PT}})
• KODE ATAS - contoh MBG 0001, nanti otomatis jadi header + garis
• KODE BAWAH - footer + garis

💰 JUAL:
Klik JUAL di hasil → konfirmasi YA → masuk HISTORY

📄 HISTORY:
• HISTORY FORMAT & HISTORY AKUN
• Bisa PULIHKAN atau HAPUS PERMANEN

❓ Butuh bantuan? Hubungi admin.
"""
        await update.message.reply_text(txt, reply_markup=main_menu())
    except Exception as e:
        logger.error(f"help_command: {e}")
        await update.message.reply_text("Gunakan /start untuk menu utama", reply_markup=main_menu())


async def profil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        conn=get_conn()
        c=conn.cursor()
        c.execute("SELECT username, first_name FROM users WHERE user_id=?", (user_id,))
        row=c.fetchone()
        conn.close()
        uname = row[0] if row else "-"
        fname = row[1] if row else "-"
        await update.message.reply_text(
            f"👤 PROFIL\nID: {user_id}\nUsername: @{uname}\nNama: {fname}\nAdmin: {'Ya' if is_admin(user_id) else 'Tidak'}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="main")]])
        )
    except Exception as e:
        logger.error(f"profil_command: {e}")
        await update.message.reply_text("👤 PROFIL", reply_markup=main_menu())

async def buat_format_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("⌨️ BIKIN FORMAT", reply_markup=bikin_format_menu())
    except Exception as e:
        logger.error(f"buat_format_command: {e}")
        await update.message.reply_text("⌨️ BIKIN FORMAT", reply_markup=main_menu())

async def hasil_format_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 HASIL FORMAT", reply_markup=hasil_format_menu())

async def hasil_akun_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💳 HASIL AKUN", reply_markup=hasil_akun_menu())

async def setting_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ SETTING", reply_markup=setting_menu())

async def riwayat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🕘 RIWAYAT", reply_markup=riwayat_menu())

def main():
    if not TOKEN or len(TOKEN) < 20:
        logger.critical("BOT_TOKEN kosong! Set di Railway Variables")
        print("ERROR: BOT_TOKEN belum di-set!", file=sys.stderr)
        sys.exit(1)

    init_db()
    print("Bot JMO INLINE 2 baris ready - FINAL KEMBALI FIX + COMMAND")
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("bantuan", help_command))
    app.add_handler(CommandHandler("profil", profil_command))
    app.add_handler(CommandHandler("buat_format", buat_format_command))
    app.add_handler(CommandHandler("buatformat", buat_format_command))
    app.add_handler(CommandHandler("bikin_format", buat_format_command))
    app.add_handler(CommandHandler("hasil_format", hasil_format_command))
    app.add_handler(CommandHandler("hasil_akun", hasil_akun_command))
    app.add_handler(CommandHandler("setting", setting_command))
    app.add_handler(CommandHandler("riwayat", riwayat_command))
    app.add_handler(CommandHandler("history", riwayat_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, excel_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__=="__main__":
    main()
