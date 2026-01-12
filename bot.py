#!/usr/bin/env python3
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "8398660208:AAGqaBx-_HrExrxNtLWbztkh3hKniWK55sk")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5615921474"))
CHANNEL = os.getenv("CHANNEL", "@rekberinx")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

PROOFS_DIR = "proofs"
os.makedirs(PROOFS_DIR, exist_ok=True)


class TransactionStates(StatesGroup):
    waiting_format = State()
    waiting_payment_proof = State()
    waiting_delivery_confirm = State()


class AdminStates(StatesGroup):
    add_payment = State()
    broadcast = State()
    ban_user = State()
    unban_user = State()
    add_admin = State()
    remove_admin = State()


def gen_tx_code():
    return "RKB" + datetime.utcnow().strftime("%Y%m%d%H%M%S")


async def get_or_create_user(user_id: int, username: str = None, full_name: str = None):
    result = supabase.table("users").select("*").eq("id", user_id).maybe_single().execute()
    if result.data:
        supabase.table("users").update({"last_active": datetime.utcnow().isoformat()}).eq("id", user_id).execute()
        return result.data

    user_data = {
        "id": user_id,
        "username": username,
        "full_name": full_name,
        "is_banned": False,
        "is_admin": user_id == ADMIN_ID
    }
    result = supabase.table("users").insert(user_data).execute()
    return result.data[0] if result.data else None


async def is_user_banned(user_id: int) -> bool:
    result = supabase.table("users").select("is_banned").eq("id", user_id).maybe_single().execute()
    return result.data.get("is_banned", False) if result.data else False


async def is_user_admin(user_id: int) -> bool:
    result = supabase.table("users").select("is_admin").eq("id", user_id).maybe_single().execute()
    return result.data.get("is_admin", False) if result.data else False


async def check_channel_membership(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        return member.status in ("member", "creator", "administrator")
    except Exception:
        return False


def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Buat Transaksi Baru", callback_data="new_transaction")],
        [InlineKeyboardButton(text="📊 Riwayat Transaksi", callback_data="my_transactions")],
        [InlineKeyboardButton(text="💳 Lihat Metode Pembayaran", callback_data="view_payments")],
        [InlineKeyboardButton(text="❓ Bantuan", callback_data="help")]
    ])
    return keyboard


def admin_panel_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Transaksi Pending", callback_data="admin_pending")],
        [InlineKeyboardButton(text="💳 Kelola Payment", callback_data="admin_payments")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 Kelola User", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Statistik", callback_data="admin_stats")],
        [InlineKeyboardButton(text="❌ Tutup", callback_data="close")]
    ])
    return keyboard


def back_to_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="main_menu")]
    ])


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    await get_or_create_user(user.id, user.username, user.full_name)

    if await is_user_banned(user.id):
        await message.answer("⛔ Anda telah diblokir dari menggunakan bot ini.")
        return

    if not await check_channel_membership(user.id) and not await is_user_admin(user.id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton(text="✅ Sudah Join", callback_data="check_join")]
        ])
        await message.answer(
            f"👋 Selamat datang di <b>Rekber Bot</b>!\n\n"
            f"Untuk menggunakan bot ini, silakan join channel terlebih dahulu:\n"
            f"{CHANNEL}\n\n"
            f"Setelah join, klik tombol 'Sudah Join' di bawah.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    welcome_text = (
        f"👋 Selamat datang <b>{user.full_name}</b>!\n\n"
        f"🛡️ <b>Rekber Bot</b> - Sistem Rekening Bersama yang Aman\n\n"
        f"Silakan pilih menu di bawah:"
    )

    await message.answer(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not await is_user_admin(message.from_user.id):
        await message.answer("⛔ Anda tidak memiliki akses admin.")
        return

    await message.answer(
        "🛠️ <b>Admin Panel</b>\n\nPilih menu admin:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "check_join")
async def check_join_callback(callback: CallbackQuery):
    if await check_channel_membership(callback.from_user.id):
        welcome_text = (
            f"✅ Terima kasih sudah join!\n\n"
            f"👋 Selamat datang <b>{callback.from_user.full_name}</b>!\n\n"
            f"🛡️ <b>Rekber Bot</b> - Sistem Rekening Bersama yang Aman\n\n"
            f"Silakan pilih menu di bawah:"
        )
        await callback.message.edit_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    else:
        await callback.answer("❌ Anda belum join channel!", show_alert=True)


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    welcome_text = (
        f"🏠 <b>Menu Utama</b>\n\n"
        f"Silakan pilih menu di bawah:"
    )
    await callback.message.edit_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "new_transaction")
async def new_transaction_callback(callback: CallbackQuery, state: FSMContext):
    format_text = (
        "📝 <b>BUAT TRANSAKSI BARU</b>\n\n"
        "Silakan isi format berikut:\n\n"
        "<code>Username Seller: @username_seller\n"
        "Username Buyer: @username_buyer\n"
        "Jenis Barang: [deskripsi barang]\n"
        "Harga: [jumlah]\n"
        "Referensi: [no referensi/catatan]</code>\n\n"
        "📌 Copy format di atas dan isi sesuai data transaksi Anda."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Batal", callback_data="main_menu")]
    ])

    await callback.message.edit_text(format_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(TransactionStates.waiting_format)
    await callback.answer()


@router.message(TransactionStates.waiting_format)
async def process_transaction_format(message: Message, state: FSMContext):
    text = message.text

    seller_match = re.search(r"Username Seller\s*:\s*(@?\w+)", text, re.IGNORECASE)
    buyer_match = re.search(r"Username Buyer\s*:\s*(@?\w+)", text, re.IGNORECASE)
    item_match = re.search(r"Jenis Barang\s*:\s*(.+)", text, re.IGNORECASE)
    price_match = re.search(r"Harga\s*:\s*(.+)", text, re.IGNORECASE)
    ref_match = re.search(r"Referensi\s*:\s*(.+)", text, re.IGNORECASE)

    if not (seller_match and buyer_match and item_match and price_match):
        await message.answer(
            "❌ Format tidak lengkap!\n\n"
            "Pastikan semua field diisi dengan benar:\n"
            "- Username Seller\n"
            "- Username Buyer\n"
            "- Jenis Barang\n"
            "- Harga\n"
            "- Referensi"
        )
        return

    seller = seller_match.group(1).strip()
    buyer = buyer_match.group(1).strip()
    item = item_match.group(1).strip()
    price = price_match.group(1).strip()
    reference = ref_match.group(1).strip() if ref_match else "-"

    tx_code = gen_tx_code()

    tx_data = {
        "tx_code": tx_code,
        "buyer_id": message.from_user.id,
        "buyer_username": buyer,
        "seller_username": seller,
        "item_description": item,
        "price": price,
        "reference": reference,
        "status": "pending"
    }

    result = supabase.table("transactions").insert(tx_data).execute()

    supabase.table("transaction_logs").insert({
        "transaction_id": result.data[0]["id"],
        "action": "created",
        "actor_id": message.from_user.id,
        "notes": "Transaction created"
    }).execute()

    admin_text = (
        f"🆕 <b>TRANSAKSI BARU</b>\n\n"
        f"📋 Kode: <code>{tx_code}</code>\n"
        f"👤 Seller: {seller}\n"
        f"👤 Buyer: {buyer}\n"
        f"📦 Barang: {item}\n"
        f"💰 Harga: {price}\n"
        f"📝 Ref: {reference}\n\n"
        f"Status: ⏳ Menunggu Persetujuan"
    )

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Setujui", callback_data=f"approve_{tx_code}"),
            InlineKeyboardButton(text="❌ Tolak", callback_data=f"reject_{tx_code}")
        ]
    ])

    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to send admin notification: {e}")

    await message.answer(
        f"✅ <b>Transaksi Berhasil Dibuat!</b>\n\n"
        f"📋 Kode Transaksi: <code>{tx_code}</code>\n\n"
        f"⏳ Menunggu persetujuan admin...\n"
        f"Anda akan mendapat notifikasi setelah admin menyetujui.",
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


@router.callback_query(F.data.startswith("approve_"))
async def approve_transaction(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    tx_code = callback.data.replace("approve_", "")

    result = supabase.table("transactions").update({
        "status": "approved",
        "updated_at": datetime.utcnow().isoformat()
    }).eq("tx_code", tx_code).execute()

    if not result.data:
        await callback.answer("❌ Transaksi tidak ditemukan", show_alert=True)
        return

    tx = result.data[0]

    supabase.table("transaction_logs").insert({
        "transaction_id": tx["id"],
        "action": "approved",
        "actor_id": callback.from_user.id,
        "notes": "Approved by admin"
    }).execute()

    buyer_text = (
        f"✅ <b>TRANSAKSI DISETUJUI</b>\n\n"
        f"📋 Kode: <code>{tx_code}</code>\n"
        f"💰 Harga: {tx['price']}\n\n"
        f"📌 Langkah selanjutnya:\n"
        f"1. Lihat metode pembayaran\n"
        f"2. Transfer ke rekening yang ditentukan\n"
        f"3. Kirim bukti transfer ke bot ini\n\n"
        f"Klik tombol di bawah untuk melihat metode pembayaran:"
    )

    buyer_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Lihat Metode Pembayaran", callback_data=f"payment_methods_{tx_code}")],
        [InlineKeyboardButton(text="📤 Kirim Bukti Transfer", callback_data=f"send_proof_{tx_code}")]
    ])

    try:
        await bot.send_message(tx["buyer_id"], buyer_text, reply_markup=buyer_keyboard, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to notify buyer: {e}")

    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ <b>DISETUJUI</b> oleh admin",
        parse_mode="HTML"
    )
    await callback.answer("✅ Transaksi disetujui")


@router.callback_query(F.data.startswith("reject_"))
async def reject_transaction(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    tx_code = callback.data.replace("reject_", "")

    result = supabase.table("transactions").update({
        "status": "rejected",
        "updated_at": datetime.utcnow().isoformat()
    }).eq("tx_code", tx_code).execute()

    if not result.data:
        await callback.answer("❌ Transaksi tidak ditemukan", show_alert=True)
        return

    tx = result.data[0]

    supabase.table("transaction_logs").insert({
        "transaction_id": tx["id"],
        "action": "rejected",
        "actor_id": callback.from_user.id,
        "notes": "Rejected by admin"
    }).execute()

    try:
        await bot.send_message(
            tx["buyer_id"],
            f"❌ <b>TRANSAKSI DITOLAK</b>\n\n"
            f"📋 Kode: <code>{tx_code}</code>\n\n"
            f"Transaksi Anda telah ditolak oleh admin.\n"
            f"Silakan hubungi admin untuk informasi lebih lanjut.",
            reply_markup=back_to_menu_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"Failed to notify buyer: {e}")

    await callback.message.edit_text(
        f"{callback.message.text}\n\n❌ <b>DITOLAK</b> oleh admin",
        parse_mode="HTML"
    )
    await callback.answer("❌ Transaksi ditolak")


@router.callback_query(F.data.startswith("payment_methods_"))
async def show_payment_methods(callback: CallbackQuery):
    tx_code = callback.data.replace("payment_methods_", "")

    result = supabase.table("payment_methods").select("*").eq("is_active", True).execute()

    if not result.data:
        await callback.answer("❌ Belum ada metode pembayaran tersedia", show_alert=True)
        return

    banks = [pm for pm in result.data if pm["type"] == "bank"]
    ewallets = [pm for pm in result.data if pm["type"] == "ewallet"]

    text = "💳 <b>METODE PEMBAYARAN</b>\n\n"

    if banks:
        text += "🏦 <b>BANK:</b>\n"
        for bank in banks:
            text += f"• {bank['name']}\n"
            text += f"  {bank['account_number']}\n"
            text += f"  a/n {bank['account_name']}\n\n"

    if ewallets:
        text += "📱 <b>E-WALLET:</b>\n"
        for ew in ewallets:
            text += f"• {ew['name']}\n"
            text += f"  {ew['account_number']}\n"
            text += f"  a/n {ew['account_name']}\n\n"

    text += "⚠️ <b>PENTING:</b>\n"
    text += "Setelah transfer, segera kirim bukti transfer!"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Kirim Bukti Transfer", callback_data=f"send_proof_{tx_code}")],
        [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="main_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("send_proof_"))
async def request_payment_proof(callback: CallbackQuery, state: FSMContext):
    tx_code = callback.data.replace("send_proof_", "")

    await state.update_data(tx_code=tx_code)
    await state.set_state(TransactionStates.waiting_payment_proof)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Batal", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "📤 <b>KIRIM BUKTI TRANSFER</b>\n\n"
        "Silakan kirim foto atau file bukti transfer Anda.\n\n"
        "Format yang diterima: Foto (JPG/PNG) atau PDF",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(TransactionStates.waiting_payment_proof, F.photo | F.document)
async def process_payment_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    tx_code = data.get("tx_code")

    if not tx_code:
        await message.answer("❌ Terjadi kesalahan. Silakan coba lagi.")
        await state.clear()
        return

    file_id = None
    file_ext = "jpg"

    if message.photo:
        file_id = message.photo[-1].file_id
        file_ext = "jpg"
    elif message.document:
        file_id = message.document.file_id
        file_ext = message.document.file_name.split(".")[-1] if "." in message.document.file_name else "pdf"

    if not file_id:
        await message.answer("❌ Format file tidak didukung. Kirim foto atau PDF.")
        return

    file = await bot.get_file(file_id)
    file_path = os.path.join(PROOFS_DIR, f"{tx_code}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{file_ext}")
    await bot.download_file(file.file_path, file_path)

    result = supabase.table("transactions").update({
        "status": "paid",
        "proof_url": file_path,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("tx_code", tx_code).execute()

    if not result.data:
        await message.answer("❌ Transaksi tidak ditemukan.")
        await state.clear()
        return

    tx = result.data[0]

    supabase.table("transaction_logs").insert({
        "transaction_id": tx["id"],
        "action": "paid",
        "actor_id": message.from_user.id,
        "notes": "Payment proof uploaded"
    }).execute()

    admin_text = (
        f"💰 <b>PEMBAYARAN DITERIMA</b>\n\n"
        f"📋 Kode: <code>{tx_code}</code>\n"
        f"👤 Seller: {tx['seller_username']}\n"
        f"👤 Buyer: {tx['buyer_username']}\n"
        f"📦 Barang: {tx['item_description']}\n"
        f"💰 Harga: {tx['price']}\n\n"
        f"✅ Bukti transfer telah diterima.\n"
        f"Dana sudah aman."
    )

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁️ Lihat Bukti", callback_data=f"view_proof_{tx_code}")],
        [InlineKeyboardButton(text="✅ Konfirmasi ke Seller", callback_data=f"notify_seller_{tx_code}")]
    ])

    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
        if os.path.exists(file_path):
            await bot.send_document(ADMIN_ID, FSInputFile(file_path), caption=f"Bukti transfer {tx_code}")
    except Exception as e:
        log.error(f"Failed to notify admin: {e}")

    await message.answer(
        f"✅ <b>BUKTI TRANSFER DITERIMA</b>\n\n"
        f"📋 Kode: <code>{tx_code}</code>\n\n"
        f"Bukti transfer Anda telah diterima dan sedang diverifikasi oleh admin.\n"
        f"Dana Anda sudah aman. Seller akan segera mengirimkan barang.\n\n"
        f"Anda akan mendapat notifikasi selanjutnya.",
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML"
    )

    await state.clear()


@router.callback_query(F.data.startswith("notify_seller_"))
async def notify_seller(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    tx_code = callback.data.replace("notify_seller_", "")

    result = supabase.table("transactions").select("*").eq("tx_code", tx_code).maybe_single().execute()

    if not result.data:
        await callback.answer("❌ Transaksi tidak ditemukan", show_alert=True)
        return

    tx = result.data

    seller_text = (
        f"📦 <b>DANA SUDAH AMAN</b>\n\n"
        f"📋 Kode: <code>{tx_code}</code>\n"
        f"👤 Buyer: {tx['buyer_username']}\n"
        f"📦 Barang: {tx['item_description']}\n"
        f"💰 Harga: {tx['price']}\n\n"
        f"✅ Pembayaran dari buyer telah diterima dan diverifikasi.\n"
        f"Dana sudah aman di rekber.\n\n"
        f"📌 <b>Langkah selanjutnya:</b>\n"
        f"Silakan kirimkan barang/akun kepada buyer.\n"
        f"Setelah buyer konfirmasi, dana akan ditransfer ke Anda.\n\n"
        f"⚠️ <b>PERHATIAN:</b>\n"
        f"Jika dalam 1 jam buyer tidak konfirmasi setelah Anda kirim barang,\n"
        f"dana otomatis dicairkan ke Anda."
    )

    seller_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Barang Sudah Dikirim", callback_data=f"seller_sent_{tx_code}")]
    ])

    seller_username_clean = tx['seller_username'].replace("@", "")

    try:
        result_user = supabase.table("users").select("id").eq("username", seller_username_clean).maybe_single().execute()
        if result_user.data:
            await bot.send_message(result_user.data["id"], seller_text, reply_markup=seller_keyboard, parse_mode="HTML")
            await callback.answer("✅ Seller telah diberitahu")
        else:
            await callback.answer("⚠️ Seller belum terdaftar di bot. Hubungi seller secara manual.", show_alert=True)
    except Exception as e:
        log.error(f"Failed to notify seller: {e}")
        await callback.answer("❌ Gagal menghubungi seller", show_alert=True)


@router.callback_query(F.data.startswith("seller_sent_"))
async def seller_sent_item(callback: CallbackQuery):
    tx_code = callback.data.replace("seller_sent_", "")

    result = supabase.table("transactions").update({
        "status": "delivered",
        "updated_at": datetime.utcnow().isoformat()
    }).eq("tx_code", tx_code).execute()

    if not result.data:
        await callback.answer("❌ Transaksi tidak ditemukan", show_alert=True)
        return

    tx = result.data[0]

    supabase.table("transaction_logs").insert({
        "transaction_id": tx["id"],
        "action": "delivered",
        "actor_id": callback.from_user.id,
        "notes": "Item delivered by seller"
    }).execute()

    buyer_text = (
        f"📦 <b>BARANG TELAH DIKIRIM</b>\n\n"
        f"📋 Kode: <code>{tx_code}</code>\n"
        f"👤 Seller: {tx['seller_username']}\n"
        f"📦 Barang: {tx['item_description']}\n\n"
        f"Seller telah mengirimkan barang kepada Anda.\n"
        f"Silakan cek dan verifikasi barang yang diterima.\n\n"
        f"Jika sudah sesuai, klik tombol konfirmasi di bawah:"
    )

    buyer_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Barang Sesuai - DONE", callback_data=f"buyer_confirm_{tx_code}")],
        [InlineKeyboardButton(text="❌ Ada Masalah", callback_data=f"buyer_complaint_{tx_code}")]
    ])

    try:
        await bot.send_message(tx["buyer_id"], buyer_text, reply_markup=buyer_keyboard, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to notify buyer: {e}")

    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"✅ Konfirmasi diterima. Menunggu buyer konfirmasi...",
        parse_mode="HTML"
    )
    await callback.answer("✅ Buyer telah diberitahu")


@router.callback_query(F.data.startswith("buyer_confirm_"))
async def buyer_confirm_received(callback: CallbackQuery):
    tx_code = callback.data.replace("buyer_confirm_", "")

    result = supabase.table("transactions").update({
        "status": "completed",
        "updated_at": datetime.utcnow().isoformat()
    }).eq("tx_code", tx_code).execute()

    if not result.data:
        await callback.answer("❌ Transaksi tidak ditemukan", show_alert=True)
        return

    tx = result.data[0]

    supabase.table("transaction_logs").insert({
        "transaction_id": tx["id"],
        "action": "completed",
        "actor_id": callback.from_user.id,
        "notes": "Confirmed by buyer"
    }).execute()

    admin_text = (
        f"✅ <b>TRANSAKSI SELESAI</b>\n\n"
        f"📋 Kode: <code>{tx_code}</code>\n"
        f"👤 Seller: {tx['seller_username']}\n"
        f"👤 Buyer: {tx['buyer_username']}\n"
        f"💰 Harga: {tx['price']}\n\n"
        f"Buyer telah konfirmasi barang diterima dengan baik.\n"
        f"Silakan cairkan dana ke seller."
    )

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Cairkan Dana", callback_data=f"release_funds_{tx_code}")]
    ])

    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to notify admin: {e}")

    await callback.message.edit_text(
        f"✅ <b>KONFIRMASI DITERIMA</b>\n\n"
        f"Terima kasih! Transaksi Anda telah selesai.\n"
        f"Admin sedang memproses pencairan dana ke seller.\n\n"
        f"🎉 Selamat bertransaksi!",
        parse_mode="HTML"
    )
    await callback.answer("✅ Terima kasih atas konfirmasinya!")


@router.callback_query(F.data.startswith("release_funds_"))
async def release_funds(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    tx_code = callback.data.replace("release_funds_", "")

    result = supabase.table("transactions").select("*").eq("tx_code", tx_code).maybe_single().execute()

    if not result.data:
        await callback.answer("❌ Transaksi tidak ditemukan", show_alert=True)
        return

    tx = result.data

    seller_text = (
        f"💸 <b>DANA TELAH DICAIRKAN</b>\n\n"
        f"📋 Kode: <code>{tx_code}</code>\n"
        f"💰 Jumlah: {tx['price']}\n\n"
        f"✅ Dana telah ditransfer ke rekening Anda.\n"
        f"Silakan cek mutasi rekening/e-wallet Anda.\n\n"
        f"🎉 Terima kasih telah menggunakan layanan rekber kami!\n"
        f"Selamat bertransaksi kembali! 🔥"
    )

    seller_username_clean = tx['seller_username'].replace("@", "")

    try:
        result_user = supabase.table("users").select("id").eq("username", seller_username_clean).maybe_single().execute()
        if result_user.data:
            await bot.send_message(result_user.data["id"], seller_text, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to notify seller: {e}")

    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"💸 <b>DANA DICAIRKAN</b>\n"
        f"Seller telah diberitahu.",
        parse_mode="HTML"
    )
    await callback.answer("✅ Dana telah dicairkan")


@router.callback_query(F.data == "my_transactions")
async def my_transactions_callback(callback: CallbackQuery):
    user_id = callback.from_user.id

    result = supabase.table("transactions").select("*").or_(f"buyer_id.eq.{user_id},seller_id.eq.{user_id}").order("created_at", desc=True).limit(10).execute()

    if not result.data:
        await callback.message.edit_text(
            "📊 <b>RIWAYAT TRANSAKSI</b>\n\n"
            "Anda belum memiliki transaksi.",
            reply_markup=back_to_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    text = "📊 <b>RIWAYAT TRANSAKSI</b>\n\n"

    for tx in result.data[:5]:
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "paid": "💰",
            "delivered": "📦",
            "completed": "🎉",
            "rejected": "❌",
            "cancelled": "🚫"
        }

        text += f"{status_emoji.get(tx['status'], '•')} <code>{tx['tx_code']}</code>\n"
        text += f"   {tx['item_description'][:30]}...\n"
        text += f"   {tx['price']} - {tx['status']}\n\n"

    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "view_payments")
async def view_payments_callback(callback: CallbackQuery):
    result = supabase.table("payment_methods").select("*").eq("is_active", True).execute()

    if not result.data:
        await callback.message.edit_text(
            "💳 <b>METODE PEMBAYARAN</b>\n\n"
            "Belum ada metode pembayaran tersedia.",
            reply_markup=back_to_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    banks = [pm for pm in result.data if pm["type"] == "bank"]
    ewallets = [pm for pm in result.data if pm["type"] == "ewallet"]

    text = "💳 <b>METODE PEMBAYARAN</b>\n\n"

    if banks:
        text += "🏦 <b>BANK:</b>\n"
        for bank in banks:
            text += f"• {bank['name']}\n"
            text += f"  {bank['account_number']}\n"
            text += f"  a/n {bank['account_name']}\n\n"

    if ewallets:
        text += "📱 <b>E-WALLET:</b>\n"
        for ew in ewallets:
            text += f"• {ew['name']}\n"
            text += f"  {ew['account_number']}\n"
            text += f"  a/n {ew['account_name']}\n\n"

    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    help_text = (
        "❓ <b>BANTUAN</b>\n\n"
        "<b>Cara Menggunakan Rekber Bot:</b>\n\n"
        "<b>Untuk Buyer:</b>\n"
        "1. Klik 'Buat Transaksi Baru'\n"
        "2. Isi format transaksi\n"
        "3. Tunggu persetujuan admin\n"
        "4. Transfer ke rekening yang ditentukan\n"
        "5. Kirim bukti transfer\n"
        "6. Tunggu seller mengirim barang\n"
        "7. Konfirmasi jika barang sudah diterima\n\n"
        "<b>Untuk Seller:</b>\n"
        "1. Tunggu notifikasi dana masuk\n"
        "2. Kirim barang ke buyer\n"
        "3. Konfirmasi pengiriman\n"
        "4. Tunggu dana dicairkan\n\n"
        "<b>Keamanan:</b>\n"
        "✅ Dana buyer aman di rekber\n"
        "✅ Seller dapat barang baru kirim dana\n"
        "✅ Dispute handling by admin"
    )

    await callback.message.edit_text(help_text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_pending")
async def admin_pending_transactions(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    result = supabase.table("transactions").select("*").in_("status", ["pending", "approved", "paid", "delivered"]).order("created_at", desc=True).execute()

    if not result.data:
        await callback.message.edit_text(
            "📋 <b>TRANSAKSI AKTIF</b>\n\n"
            "Tidak ada transaksi aktif.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_panel")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    text = "📋 <b>TRANSAKSI AKTIF</b>\n\n"

    for tx in result.data[:10]:
        text += f"• <code>{tx['tx_code']}</code>\n"
        text += f"  Status: {tx['status']}\n"
        text += f"  {tx['price']}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_panel")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_payments")
async def admin_payments_menu(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    result = supabase.table("payment_methods").select("*").execute()

    text = "💳 <b>KELOLA METODE PEMBAYARAN</b>\n\n"

    if result.data:
        for pm in result.data:
            status = "✅" if pm["is_active"] else "❌"
            text += f"{status} {pm['type']}: {pm['name']} - {pm['account_number']}\n"
    else:
        text += "Belum ada metode pembayaran.\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tambah Bank", callback_data="admin_add_bank")],
        [InlineKeyboardButton(text="➕ Tambah E-Wallet", callback_data="admin_add_ewallet")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_add_bank")
async def admin_add_bank_request(callback: CallbackQuery, state: FSMContext):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    await state.update_data(payment_type="bank")
    await state.set_state(AdminStates.add_payment)

    await callback.message.edit_text(
        "➕ <b>TAMBAH BANK</b>\n\n"
        "Kirim dengan format:\n"
        "<code>BCA\n1234567890\nJohn Doe</code>\n\n"
        "Format: Nama Bank | Nomor Rekening | Nama Pemilik\n"
        "(Pisahkan dengan enter/baris baru)",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_ewallet")
async def admin_add_ewallet_request(callback: CallbackQuery, state: FSMContext):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    await state.update_data(payment_type="ewallet")
    await state.set_state(AdminStates.add_payment)

    await callback.message.edit_text(
        "➕ <b>TAMBAH E-WALLET</b>\n\n"
        "Kirim dengan format:\n"
        "<code>Dana\n08123456789\nJohn Doe</code>\n\n"
        "Format: Nama E-Wallet | Nomor | Nama Pemilik\n"
        "(Pisahkan dengan enter/baris baru)",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.add_payment)
async def process_add_payment(message: Message, state: FSMContext):
    if not await is_user_admin(message.from_user.id):
        return

    data = await state.get_data()
    payment_type = data.get("payment_type")

    lines = message.text.strip().split("\n")

    if len(lines) < 3:
        await message.answer("❌ Format tidak lengkap. Harus 3 baris: Nama | Nomor | Pemilik")
        return

    name = lines[0].strip()
    account_number = lines[1].strip()
    account_name = lines[2].strip()

    pm_data = {
        "type": payment_type,
        "name": name,
        "account_number": account_number,
        "account_name": account_name,
        "is_active": True
    }

    supabase.table("payment_methods").insert(pm_data).execute()

    await message.answer(
        f"✅ Metode pembayaran berhasil ditambahkan!\n\n"
        f"Type: {payment_type}\n"
        f"Nama: {name}\n"
        f"Nomor: {account_number}\n"
        f"a/n: {account_name}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Admin Panel", callback_data="admin_panel")]
        ])
    )

    await state.clear()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_request(callback: CallbackQuery, state: FSMContext):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    await state.set_state(AdminStates.broadcast)

    await callback.message.edit_text(
        "📢 <b>BROADCAST</b>\n\n"
        "Kirim pesan yang ingin di-broadcast ke semua user.\n"
        "Bisa berupa teks, foto, atau dokumen.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if not await is_user_admin(message.from_user.id):
        return

    result = supabase.table("users").select("id").execute()
    user_ids = [u["id"] for u in result.data] if result.data else []

    success = 0
    failed = 0

    for user_id in user_ids:
        try:
            if message.photo:
                await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
            elif message.document:
                await bot.send_document(user_id, message.document.file_id, caption=message.caption)
            else:
                await bot.send_message(user_id, message.text or message.caption)
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await message.answer(
        f"✅ Broadcast selesai!\n\n"
        f"Berhasil: {success}\n"
        f"Gagal: {failed}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Admin Panel", callback_data="admin_panel")]
        ])
    )

    await state.clear()


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    users_result = supabase.table("users").select("id", count="exact").execute()
    tx_result = supabase.table("transactions").select("status", count="exact").execute()

    total_users = users_result.count if users_result.count else 0
    total_tx = tx_result.count if tx_result.count else 0

    completed = len([t for t in tx_result.data if t["status"] == "completed"]) if tx_result.data else 0
    pending = len([t for t in tx_result.data if t["status"] == "pending"]) if tx_result.data else 0

    text = (
        f"📊 <b>STATISTIK</b>\n\n"
        f"👥 Total User: {total_users}\n"
        f"📋 Total Transaksi: {total_tx}\n"
        f"✅ Selesai: {completed}\n"
        f"⏳ Pending: {pending}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_panel")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def admin_users_menu(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(
        "👥 <b>KELOLA USER</b>\n\nPilih aksi:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("⛔ Akses ditolak", show_alert=True)
        return

    await callback.message.edit_text(
        "🛠️ <b>Admin Panel</b>\n\nPilih menu admin:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "close")
async def close_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


async def main():
    dp.include_router(router)

    result = supabase.table("users").update({"is_admin": True}).eq("id", ADMIN_ID).execute()
    if not result.data:
        await get_or_create_user(ADMIN_ID)
        supabase.table("users").update({"is_admin": True}).eq("id", ADMIN_ID).execute()

    log.info("🤖 Bot started successfully!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
