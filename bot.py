import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Telegram Token (Render'da Environment Variable olarak TELEGRAM_TOKEN eklenecek)
TOKEN = os.environ.get("TELEGRAM_TOKEN")
BOT_NAME = "TicaretSECURE"

# Log ayarları
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

küfür_listesi = ["küfür1", "küfür2"]
reklam_listesi = ["t.me/", "http://", "https://"]
warns = {}
kullanici_seviyeleri = {}
vip_kullanicilar = []

# --- Komutlar ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Merhaba! Ben {BOT_NAME}, bu grubu korumak ve destek olmak için buradayım.\n"
        "Yardım için /yardim yazabilirsiniz."
    )

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    komutlar = """
/start - Botu başlat
/yardim - Komutları gör
/kurallar - Grup kurallarını göster
/profil - Kullanıcı istatistiklerini göster
"""
    await update.message.reply_text(komutlar)

async def kurallar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kurallar_metni = """
📜 Grup Kuralları:
1️⃣ Teminattan fazla işlem yasaktır.
2️⃣ Teminatsız POS kullanmak yasaktır.
3️⃣ Teminatsız saha yasaktır.
4️⃣ Küfür ve spam yasaktır.
5️⃣ Reklam yasaktır.
6️⃣ Yetkililere uyun.

💰 Teminat bırakmak için: @abdsmsk
🧾 Tek teminatlı saha: @teminat_ve_saha
"""
    await update.message.reply_text(kurallar_metni)

async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.username or update.message.from_user.first_name
    seviye = kullanici_seviyeleri.get(user, 0)
    uyarilar = warns.get(user, 0)
    await update.message.reply_text(f"👤 {user}\nSeviye: {seviye}\nUyarılar: {uyarilar}")

# --- Mesaj filtreleme ---
async def mesaj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user = update.message.from_user.username or update.message.from_user.first_name
    vip = user in vip_kullanicilar

    # Teminat / POS / saha kuralları bilgilendirmesi
    if any(k in text for k in ["teminat", "pos", "saha"]):
        await update.message.reply_text(
            f"{user}, grup kurallarına dikkat edin! ❗\n"
            "1. Teminattan fazla işlem yasak\n"
            "2. Teminatsız POS kullanmak yasak\n"
            "3. Teminatsız saha yasak\n"
            "Teminat bırakmak için: @abdsmsk\n"
            "Şu anda tek teminatlı saha: @teminat_ve_saha"
        )
        return

    # Küfür filtresi
    for k in küfür_listesi:
        if k in text:
            warns[user] = warns.get(user, 0) + 1
            await update.message.reply_text(f"{user}, küfür yasak! Uyarı sayısı: {warns[user]}")
            return

    # Reklam filtresi
    for link in reklam_listesi:
        if link in text:
            warns[user] = warns.get(user, 0) + 1
            await update.message.reply_text(f"{user}, reklam yasak! Uyarı sayısı: {warns[user]}")
            return

    # Otomatik selamlama
    if "merhaba" in text:
        await update.message.reply_text(f"Merhaba {user}! 👋")

    # Kullanıcı seviye puanı
    kullanici_seviyeleri[user] = kullanici_seviyeleri.get(user, 0) + 1

# --- Ana çalıştırıcı ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yardim", yardim))
    app.add_handler(CommandHandler("kurallar", kurallar))
    app.add_handler(CommandHandler("profil", profil))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj))

    print("✅ TicaretSECURE Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
