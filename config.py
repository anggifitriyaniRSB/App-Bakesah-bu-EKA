"""Konfigurasi terpisah: development (default) dan production."""
import os, secrets
BASE = os.path.dirname(os.path.abspath(__file__))
ENV = os.environ.get("BAKESAH_ENV", "development")

class Dev:
    ENV = "development"
    DB_PATH = os.environ.get("BAKESAH_DB_PATH", os.path.join(BASE, "instance", "bakesah_dev.sqlite3"))
    SECRET_KEY = os.environ.get("BAKESAH_SECRET_KEY", "dev-only-key-ganti-di-produksi")
    COOKIE_SECURE = False
    SHOW_DEMO_ACCOUNTS = True   # hanya di development

class Prod:
    ENV = "production"
    DB_PATH = os.environ.get("BAKESAH_DB_PATH")
    SECRET_KEY = os.environ.get("BAKESAH_SECRET_KEY")
    COOKIE_SECURE = True
    SHOW_DEMO_ACCOUNTS = False

def load():
    c = Prod if ENV == "production" else Dev
    if c is Prod and not (c.DB_PATH and c.SECRET_KEY):
        raise RuntimeError("Produksi wajib mengatur BAKESAH_DB_PATH dan BAKESAH_SECRET_KEY")
    return c
