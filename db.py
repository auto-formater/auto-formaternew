import os
import sqlite3

USE_POSTGRES = False
DATABASE_URL = os.getenv("DATABASE_URL", "")
# Supabase Postgres connection string format: postgresql://postgres.xxx:password@aws-0-ap-...pooler.supabase.com:6543/postgres

conn_postgres = None
try:
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        import psycopg2
        import psycopg2.extras
        USE_POSTGRES = True
        print(f"✅ Using Postgres (Supabase) mode")
    else:
        print(f"✅ Using SQLite mode")
except Exception as e:
    print(f"Fallback to SQLite: {e}")
    USE_POSTGRES = False

DB_PATH = os.getenv("DB_PATH", "bot_data.db")

def get_conn():
    if USE_POSTGRES:
        import psycopg2
        # Use connection pooling via new connection each time (simple)
        return psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(DB_PATH)
        return conn

def execute(query, params=(), fetch=False, fetchone=False, commit=True):
    """Universal execute that handles ? vs %s placeholder"""
    if USE_POSTGRES:
        # convert ? to %s for postgres
        pg_query = query.replace("?", "%s")
        # Handle sqlite specific syntax differences
        pg_query = pg_query.replace("INSERT OR IGNORE", "INSERT")
        pg_query = pg_query.replace("INSERT OR REPLACE", "INSERT")
        # For INSERT OR REPLACE we need ON CONFLICT
        # Simplification: try insert, on conflict do update for settings/admins
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(pg_query, params)
            result = None
            if fetch:
                result = cur.fetchall()
            elif fetchone:
                result = cur.fetchone()
            if commit:
                conn.commit()
            return result
        except Exception as e:
            # Try ON CONFLICT handling for settings/admins
            if "settings" in query.lower() and "INSERT" in query:
                try:
                    cur.execute("ROLLBACK")
                    # upsert for settings
                    cur.execute("""
                        INSERT INTO settings (user_id, template, kode_atas, kode_bawah)
                        VALUES (%s,%s,%s,%s)
                        ON CONFLICT (user_id) DO UPDATE SET template=EXCLUDED.template, kode_atas=EXCLUDED.kode_atas, kode_bawah=EXCLUDED.kode_bawah
                    """, params)
                    conn.commit()
                except Exception as e2:
                    print(f"DB error fallback: {e2}")
                    conn.rollback()
            elif "admins" in query.lower() and "INSERT" in query:
                try:
                    cur.execute("ROLLBACK")
                    cur.execute("""
                        INSERT INTO admins (user_id, added_by, added_at) VALUES (%s,%s,%s)
                        ON CONFLICT (user_id) DO NOTHING
                    """, params)
                    conn.commit()
                except:
                    conn.rollback()
            else:
                print(f"DB Error: {e} | Query: {pg_query} | Params: {params}")
                conn.rollback()
            return None
        finally:
            cur.close()
            conn.close()
    else:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, params)
        result = None
        if fetch:
            result = cur.fetchall()
        elif fetchone:
            result = cur.fetchone()
        if commit:
            conn.commit()
        cur.close()
        conn.close()
        return result

def init_db():
    if USE_POSTGRES:
        # Tables already created via supabase_schema.sql, but ensure
        conn = get_conn()
        cur = conn.cursor()
        # Just test connection
        cur.execute("SELECT 1")
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Postgres tables ready (run supabase_schema.sql if not exists)")
    else:
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
