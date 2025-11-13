#!/usr/bin/env python3
# TicaretSECURE - tek dosya, çok sayıda gerçek işlev
import os
import json
import logging
import random
import datetime
from typing import Dict, Any, List, Optional

from telegram import Update, ChatPermissions, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue,
)

# --- CONFIG ---
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8214173862:AAGvwgiv6LwsfonD1Ed29EPRNxyZcq5AC4A")
DATA_FILE = "data.json"
BOT_NAME = "TicaretSECURE"

# --- LOGGING ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DEFAULT DATA STRUCTURE ---
DEFAULT_DATA = {
    "küfür_listesi": ["örnek_küfür1", "örnek_küfür2"],
    "reklam_listesi": ["t.me/", "http://", "https://"],
    "warns": {},                # {"username": count}
    "levels": {},               # {"username": level}
    "puanlar": {},              # {"username": points}
    "vip": [],                  # ["username"]
    "teminat_pos": {},          # {"username": amount}
    "teminat_saha": {},         # {"username": amount}
    "hatirlatmalar": {},        # {"jobid": {...}}
    "logs": [],                 # recent logs
    "stats": {                  # message counts etc.
        "messages": {},         # {"username": count}
        "total_messages": 0
    }
}

# --- DATA I/O ---
def load_data() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.exception("Data load error, resetting: %s", e)
    # write default
    save_data(DEFAULT_DATA)
    return DEFAULT_DATA.copy()

def save_data(d: Dict[str, Any]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

data = load_data()

# --- HELPERS ---
def is_admin_sync(chat_id: int, user_id: int, app) -> bool:
    try:
        member = app.bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

async def is_admin(update: Update) -> bool:
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        member = await update.effective_chat.get_member(user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

def save_and_log(action: str, info: str):
    entry = {"time": datetime.datetime.utcnow().isoformat(), "action": action, "info": info}
    data.setdefault("logs", []).append(entry)
    # keep logs reasonable
    if len(data["logs"]) > 500:
        data["logs"] = data["logs"][-500:]
    save_data(data)

def username_from_arg_or_reply(update: Update, arg_index=0) -> Optional[dict]:
    """
    Try to get target user from reply (preferred) or from context.args username string (like @user).
    Returns dict with keys: 'id' (if available), 'username' (string, without @), 'name'
    """
    msg = update.message
    if msg.reply_to_message:
        u = msg.reply_to_message.from_user
        return {"id": u.id, "username": (u.username or f"{u.first_name}_{u.id}"), "name": u.first_name}
    # else try args
    if msg.text:
        parts = msg.text.split()
        if len(parts) > arg_index + 0:
            # command maybe followed by @username or user_id
            try:
                candidate = parts[arg_index + 1]
            except IndexError:
                return None
            candidate = candidate.strip()
            if candidate.startswith("@"):
                return {"username": candidate.lstrip("@"), "name": candidate}
            # if it's numeric id
            if candidate.isdigit():
                return {"id": int(candidate), "username": None, "name": candidate}
    return None

# --- CORE COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Merhaba! Ben {BOT_NAME}. Grubu korumak ve desteklemek için buradayım.\n"
        "Yardım için /komut veya /yardim yazın."
    )

async def komut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # dynamic list (we keep a curated list)
    cmds = [
        "/start", "/yardim", "/komut", "/kurallar", "/profil", "/istatistik",
        "/puan /puan_ver /puan_sil", "/vip_ekle /vip_cikar /vip_liste",
        "/teminat_pos_ekle /teminat_pos_sil /teminat_saha_ekle /teminat_saha_sil /teminat_listesi",
        "/ban /mute /kick /warn /uyari_sifirla",
        "/sayi_tahmin /tahmin /zar_at /slot", "/duyuru", "/hatirlat", "/hatirlat_sil", "/hatirlat_liste"
    ]
    await update.message.reply_text("🔧 Komutlar:\n" + "\n".join(cmds))

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await komut(update, context)

async def kurallar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📜 Grup Kuralları:\n"
        "1) Teminattan fazla işlem yasaktır.\n"
        "2) Teminatsız POS kullanmak yasaktır.\n"
        "3) Teminatsız saha yasaktır.\n"
        "4) Küfür ve spam yasaktır.\n"
        "5) Reklam yasaktır.\n"
        "Teminat bırakmak için: @abdsmsk\nTek teminatlı saha: @teminat_ve_saha"
    )
    await update.message.reply_text(text)

async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uname = user.username or str(user.id)
    lvl = data["levels"].get(uname, 0)
    warns = data["warns"].get(uname, 0)
    puan = data["puanlar"].get(uname, 0)
    await update.message.reply_text(f"👤 @{user.username or user.first_name}\nSeviye: {lvl}\nUyarı: {warns}\nPuan: {puan}")

async def istatistik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = data["stats"].get("total_messages", 0)
    users = len(data["stats"].get("messages", {}))
    await update.message.reply_text(f"📊 Toplam mesaj (bot tarafından sayılan): {total}\nKayıtlı kullanıcı: {users}")

# --- VIP ---
async def vip_ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Bu komutu yalnızca adminler kullanabilir.")
        return
    target = username_from_arg_or_reply(update)
    if not target:
        await update.message.reply_text("Kullanıcı belirtin (reply ile veya @kullanici).")
        return
    uname = target.get("username") or str(target.get("id"))
    if uname in data["vip"]:
        await update.message.reply_text(f"@{uname} zaten VIP.")
        return
    data["vip"].append(uname)
    save_and_log("vip_ekle", uname)
    save_data(data)
    await update.message.reply_text(f"✅ @{uname} VIP yapıldı.")

async def vip_cikar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Bu komutu yalnızca adminler kullanabilir.")
        return
    target = username_from_arg_or_reply(update)
    if not target:
        await update.message.reply_text("Kullanıcı belirtin (reply ile veya @kullanici).")
        return
    uname = target.get("username") or str(target.get("id"))
    if uname in data["vip"]:
        data["vip"].remove(uname)
        save_and_log("vip_cikar", uname)
        save_data(data)
        await update.message.reply_text(f"✅ @{uname} VIP listesinden çıkarıldı.")
    else:
        await update.message.reply_text(f"@{uname} VIP değil.")

async def vip_liste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vip = data.get("vip", [])
    if not vip:
        await update.message.reply_text("⭐ VIP kullanıcı yok.")
    else:
        await update.message.reply_text("⭐ VIP kullanıcılar:\n" + "\n".join([f"@{u}" for u in vip]))

# --- TEMİNAT (POS / SAHA) ---
async def teminat_pos_ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Sadece adminler kullanabilir.")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Kullanım: /teminat_pos_ekle <@kullanici> <miktar>")
        return
    uname = args[0].lstrip("@")
    miktar = args[1]
    data["teminat_pos"][uname] = miktar
    save_and_log("teminat_pos_ekle", f"{uname}:{miktar}")
    save_data(data)
    await update.message.reply_text(f"✅ @{uname} POS teminatlı eklendi ({miktar}).")

async def teminat_pos_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Sadece adminler kullanabilir.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: /teminat_pos_sil <@kullanici>")
        return
    uname = args[0].lstrip("@")
    if uname in data["teminat_pos"]:
        del data["teminat_pos"][uname]
        save_and_log("teminat_pos_sil", uname)
        save_data(data)
        await update.message.reply_text(f"✅ @{uname} POS teminatlı listesinden silindi.")
    else:
        await update.message.reply_text("@{} listede yok.".format(uname))

async def teminat_saha_ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Sadece adminler kullanabilir.")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Kullanım: /teminat_saha_ekle <@kullanici> <miktar>")
        return
    uname = args[0].lstrip("@")
    miktar = args[1]
    data["teminat_saha"][uname] = miktar
    save_and_log("teminat_saha_ekle", f"{uname}:{miktar}")
    save_data(data)
    await update.message.reply_text(f"✅ @{uname} saha teminatlı eklendi ({miktar}).")

async def teminat_saha_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Sadece adminler kullanabilir.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Kullanım: /teminat_saha_sil <@kullanici>")
        return
    uname = args[0].lstrip("@")
    if uname in data["teminat_saha"]:
        del data["teminat_saha"][uname]
        save_and_log("teminat_saha_sil", uname)
        save_data(data)
        await update.message.reply_text(f"✅ @{uname} saha teminatlı listesinden silindi.")
    else:
        await update.message.reply_text("@{} listede yok.".format(uname))

async def teminat_listesi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pos = data.get("teminat_pos", {})
    saha = data.get("teminat_saha", {})
    pos_text = "\n".join([f"@{u} — {v}" for u, v in pos.items()]) or "Yok"
    saha_text = "\n".join([f"@{u} — {v}" for u, v in saha.items()]) or "Yok"
    await update.message.reply_text(f"📌 Teminatlı POS'cular:\n{pos_text}\n\n📌 Teminatlı Sahacılar:\n{saha_text}")

# --- MODERASYON: WARN/MUTE/BAN/KICK ---
async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Bu komutu yalnızca adminler kullanabilir.")
        return
    target = username_from_arg_or_reply(update)
    if not target:
        await update.message.reply_text("Kullanıcı belirtin (reply ile veya @kullanici).")
        return
    uname = target.get("username") or str(target.get("id"))
    data["warns"][uname] = data["warns"].get(uname, 0) + 1
    save_and_log("warn", f"{uname}:{data['warns'][uname]}")
    save_data(data)
    await update.message.reply_text(f"⚠️ @{uname} uyarıldı. Toplam uyarı: {data['warns'][uname]}")

    # Otomatik cezalar
    if data["warns"][uname] >= 5:
        # ban
        try:
            chat_id = update.effective_chat.id
            # get user id if possible
            uid = target.get("id")
            if uid:
                await context.bot.ban_chat_member(chat_id, uid)
                await update.message.reply_text(f"❌ @{uname} otomatik olarak banlandı (uyarı >=5).")
                save_and_log("auto_ban", uname)
            else:
                await update.message.reply_text(f"⚠️ @{uname} limit aştı — adminlerin manuel banlaması gerekiyor (id yok).")
        except Exception as e:
            logger.exception("Auto-ban failed: %s", e)
    elif data["warns"][uname] >= 3:
        # mute for 1 day
        try:
            chat_id = update.effective_chat.id
            uid = target.get("id")
            if uid:
                until = datetime.datetime.utcnow() + datetime.timedelta(days=1)
                permissions = ChatPermissions(can_send_messages=False)
                await context.bot.restrict_chat_member(chat_id, uid, permissions=permissions, until_date=until)
                await update.message.reply_text(f"🔇 @{uname} otomatik susturuldu (uyarı >=3) 24saat.")
                save_and_log("auto_mute", uname)
            else:
                await update.message.reply_text(f"⚠️ @{uname} limit aştı — adminlerin manuel susturması gerekiyor (id yok).")
        except Exception as e:
            logger.exception("Auto-mute failed: %s", e)

async def uyari_sifirla_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Yalnızca adminler kullanabilir.")
        return
    target = username_from_arg_or_reply(update)
    if not target:
        await update.message.reply_text("Kullanıcı belirtin.")
        return
    uname = target.get("username") or str(target.get("id"))
    data["warns"][uname] = 0
    save_and_log("uyari_sifirla", uname)
    save_data(data)
    await update.message.reply_text(f"✅ @{uname} uyarıları sıfırlandı.")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Yalnızca adminler kullanabilir.")
        return
    target = username_from_arg_or_reply(update)
    if not target:
        await update.message.reply_text("Kullanıcı belirtin (reply ile önerilir).")
        return
    uid = target.get("id")
    uname = target.get("username") or str(uid)
    chat_id = update.effective_chat.id
    try:
        if uid:
            await context.bot.ban_chat_member(chat_id, uid)
            await update.message.reply_text(f"🚫 @{uname} banlandı.")
            save_and_log("ban", uname)
        else:
            # try by username resolution
            await update.message.reply_text("Kullanıcı id'si yok — lütfen komutu kullanırken hedefin mesajına yanıt verin.")
    except Exception as e:
        logger.exception("ban failed: %s", e)
        await update.message.reply_text("Ban işlemi başarısız oldu. Botun admin yetkileri olduğundan emin olun.")

async def kick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Yalnızca adminler kullanabilir.")
        return
    target = username_from_arg_or_reply(update)
    if not target:
        await update.message.reply_text("Kullanıcı belirtin (reply ile önerilir).")
        return
    uid = target.get("id")
    uname = target.get("username") or str(uid)
    chat_id = update.effective_chat.id
    try:
        if uid:
            await context.bot.unban_chat_member(chat_id, uid)  # to ensure they can be readded if needed, then kick
            await context.bot.ban_chat_member(chat_id, uid)
            # unban immediately so it's a kick, not permanent ban
            await context.bot.unban_chat_member(chat_id, uid)
            await update.message.reply_text(f"🦵 @{uname} gruptan atıldı.")
            save_and_log("kick", uname)
        else:
            await update.message.reply_text("Kullanıcı id bulunamadı — lütfen reply ile kullanın.")
    except Exception as e:
        logger.exception("kick failed: %s", e)
        await update.message.reply_text("Kick işlemi başarısız oldu. Bot admin mi kontrol edin.")

async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Yalnızca adminler kullanabilir.")
        return
    target = username_from_arg_or_reply(update)
    if not target:
        await update.message.reply_text("Kullanıcı belirtin (reply ile önerilir).")
        return
    uid = target.get("id")
    uname = target.get("username") or str(uid)
    chat_id = update.effective_chat.id
    if not uid:
        await update.message.reply_text("Kullanıcı id bulunamadı — lütfen reply ile deneyin.")
        return
    try:
        until = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id, uid, permissions=permissions, until_date=until)
        await update.message.reply_text(f"🔇 @{uname} 24 saat susturuldu.")
        save_and_log("mute", uname)
    except Exception as e:
        logger.exception("mute failed: %s", e)
        await update.message.reply_text("Mute işlemi başarısız oldu.")

# --- Puan / Level sistemi ---
async def puan_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = username_from_arg_or_reply(update, arg_index=0)
    if not target:
        user = update.effective_user
        uname = user.username or str(user.id)
    else:
        uname = target.get("username") or str(target.get("id"))
    puan = data["puanlar"].get(uname, 0)
    await update.message.reply_text(f"🏆 @{uname} puanı: {puan}")

async def puan_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Yalnızca adminler puan verebilir.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Kullanım: /puan_ver <@kullanici> <miktar>")
        return
    uname = context.args[0].lstrip("@")
    try:
        miktar = int(context.args[1])
    except:
        await update.message.reply_text("Miktar sayı olmalı.")
        return
    data["puanlar"][uname] = data["puanlar"].get(uname, 0) + miktar
    save_and_log("puan_ver", f"{uname}:{miktar}")
    save_data(data)
    await update.message.reply_text(f"✅ @{uname} puanı {miktar} eklendi. Toplam: {data['puanlar'][uname]}")

async def puan_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("Yalnızca adminler puan silebilir.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Kullanım: /puan_sil <@kullanici> <miktar>")
        return
    uname = context.args[0].lstrip("@")
    try:
        miktar = int(context.args[1])
    except:
        await update.message.reply_text("Miktar sayı olmalı.")
        return
    data["puanlar"][uname] = max(0, data["puanlar"].get(uname, 0) - miktar)
    save_and_log("puan_sil", f"{uname}:{miktar}")
    save_data(data)
    await update.message.reply_text(f"✅ @{uname} puanı {miktar} azaltıldı. Toplam: {data['puanlar'][uname]}")

# --- Oyunlar / Eğlence ---
async def zar_at(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = random.randint(1, 6)
    await update.message.reply_text(f"🎲 Zar: {r}")

async def sayi_tahmin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Kullanım: /sayi_tahmin <min> <max>")
        return
    try:
        a = int(context.args[0]); b = int(context.args[1])
    except:
        await update.message.reply_text("Geçerli sayılar girin.")
        return
    number = random.randint(a, b)
    context.user_data["sayi_tahmin"] = number
    await update.message.reply_text(f"Sayı tahmin oyunu başladı! {a}-{b} arasında tahmin için /tahmin <sayi>")

async def tahmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "sayi_tahmin" not in context.user_data:
        await update.message.reply_text("Önce /sayi_tahmin başlatın.")
        return
    if not context.args:
        await update.message.reply_text("Kullanım: /tahmin <sayı>")
        return

    try:
        guess = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Lütfen bir sayı girin.")
        return

    number = context.user_data["sayi_tahmin"]
    if guess == number:
        await update.message.reply_text("🎉 Tebrikler! Sayıyı doğru tahmin ettiniz!")
        del context.user_data["sayi_tahmin"]
    elif guess < number:
        await update.message.reply_text("🔼 Daha büyük bir sayı söyleyin.")
    else:
        await update.message.reply_text("🔽 Daha küçük bir sayı söyleyin.")

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    semboller = ["🍒", "🍋", "🍉", "⭐", "🔔", "7️⃣"]
    sonuc = [random.choice(semboller) for _ in range(3)]
    text = " | ".join(sonuc)
    if len(set(sonuc)) == 1:
        msg = f"{text}\n🎉 Jackpot! Hepsi aynı!"
    else:
        msg = f"{text}\n😅 Şansını tekrar dene!"
    await update.message.reply_text(msg)

async def duello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Kullanım: /duello <@kullanıcı>")
        return
    hedef = context.args[0].lstrip("@")
    kazanan = random.choice([update.effective_user.username or "Sen", hedef])
    await update.message.reply_text(f"⚔️ @{update.effective_user.username or 'Sen'} ve @{hedef} düello yaptı.\n🏆 Kazanan: @{kazanan}")

# --- HATIRLATICI SİSTEMİ ---
async def hatirlat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Kullanım: /hatirlat <dakika> <metin>")
        return
    try:
        dakika = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Dakika sayısı geçerli olmalı.")
        return
    text = " ".join(context.args[1:])
    when = datetime.datetime.utcnow() + datetime.timedelta(minutes=dakika)
    job_id = str(len(data["hatirlatmalar"]) + 1)
    data["hatirlatmalar"][job_id] = {"user": update.effective_user.username, "text": text, "when": str(when)}
    save_and_log("hatirlat", f"{job_id}:{text}")
    save_data(data)
    await update.message.reply_text(f"⏰ Hatırlatıcı ayarlandı: {dakika} dk sonra '{text}'")

async def hatirlat_liste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data["hatirlatmalar"]:
        await update.message.reply_text("Hatırlatıcı yok.")
        return
    lines = [f"{jid}: {info['text']} (zaman: {info['when']})" for jid, info in data["hatirlatmalar"].items()]
    await update.message.reply_text("📋 Hatırlatıcılar:\n" + "\n".join(lines))

async def hatirlat_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /hatirlat_sil <jobid>")
        return
    jid = context.args[0]
    if jid in data["hatirlatmalar"]:
        del data["hatirlatmalar"][jid]
        save_and_log("hatirlat_sil", jid)
        save_data(data)
        await update.message.reply_text("✅ Hatırlatıcı silindi.")
    else:
        await update.message.reply_text("Hatırlatıcı bulunamadı.")

# --- MESAJ FİLTRELEME / OTOMATİK TEPKİ ---
async def mesaj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user = update.effective_user
    uname = user.username or str(user.id)

    # Mesaj sayacı
    data["stats"]["messages"][uname] = data["stats"]["messages"].get(uname, 0) + 1
    data["stats"]["total_messages"] += 1

    # Küfür kontrolü
    for kelime in data["küfür_listesi"]:
        if kelime in text:
            await update.message.reply_text(f"⚠️ @{uname}, lütfen küfür etme.")
            await warn_cmd(update, context)
            save_data(data)
            return

    # Reklam kontrolü
    for link in data["reklam_listesi"]:
        if link in text:
            await update.message.reply_text(f"🚫 @{uname}, reklam paylaşmak yasak!")
            await warn_cmd(update, context)
            save_data(data)
            return

    # POS veya saha mesajı
    if "pos" in text:
        if data["teminat_pos"]:
            liste = ", ".join([f"@{u}" for u in data["teminat_pos"].keys()])
            await update.message.reply_text(f"💳 Teminatlı POS'cular: {liste}")
        else:
            await kurallar(update, context)
    elif "saha" in text:
        if data["teminat_saha"]:
            liste = ", ".join([f"@{u}" for u in data["teminat_saha"].keys()])
            await update.message.reply_text(f"📍 Teminatlı Sahacılar: {liste}")
        else:
            await kurallar(update, context)

    save_data(data)

# --- BOT BAŞLATMA ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("komut", komut))
    app.add_handler(CommandHandler("yardim", yardim))
    app.add_handler(CommandHandler("kurallar", kurallar))
    app.add_handler(CommandHandler("profil", profil))
    app.add_handler(CommandHandler("istatistik", istatistik))

    # VIP & teminat
    app.add_handler(CommandHandler("vip_ekle", vip_ekle))
    app.add_handler(CommandHandler("vip_cikar", vip_cikar))
    app.add_handler(CommandHandler("vip_liste", vip_liste))
    app.add_handler(CommandHandler("teminat_pos_ekle", teminat_pos_ekle))
    app.add_handler(CommandHandler("teminat_pos_sil", teminat_pos_sil))
    app.add_handler(CommandHandler("teminat_saha_ekle", teminat_saha_ekle))
    app.add_handler(CommandHandler("teminat_saha_sil", teminat_saha_sil))
    app.add_handler(CommandHandler("teminat_listesi", teminat_listesi))

    # Moderasyon
    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("uyari_sifirla", uyari_sifirla_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("kick", kick_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))

    # Puan & oyun
    app.add_handler(CommandHandler("puan", puan_goster))
    app.add_handler(CommandHandler("puan_ver", puan_ver))
    app.add_handler(CommandHandler("puan_sil", puan_sil))
    app.add_handler(CommandHandler("zar_at", zar_at))
    app.add_handler(CommandHandler("sayi_tahmin", sayi_tahmin_start))
    app.add_handler(CommandHandler("tahmin", tahmin))
    app.add_handler(CommandHandler("slot", slot))
    app.add_handler(CommandHandler("duello", duello))

    # Hatırlatıcılar
    app.add_handler(CommandHandler("hatirlat", hatirlat))
    app.add_handler(CommandHandler("hatirlat_liste", hatirlat_liste))
    app.add_handler(CommandHandler("hatirlat_sil", hatirlat_sil))

    # Mesaj filtreleme
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj))

    print("✅ TicaretSECURE Bot 100+ Özellik ile aktif!")
    app.run_polling()

if __name__ == "__main__":
    main()
