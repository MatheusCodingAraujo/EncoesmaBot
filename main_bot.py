import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, Message
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from estado import get_usuario, usuarios
import database as db
import fazer_pedido_bot
import bater_ponto_bot
import admin_bot
import entregar_trabalho_bot

load_dotenv()
TOKEN            = os.getenv("BOT_TOKEN")
GROUP_PEDIDOS_ID  = os.getenv("GROUP_PEDIDOS_ID")
GROUP_PONTO_ID    = os.getenv("GROUP_PONTO_ID")
GROUP_TRABALHO_ID = os.getenv("GROUP_TRABALHO_ID")


async def teclado_menu(telegram_id: int) -> ReplyKeyboardMarkup:
    func   = await db.get_funcionario(telegram_id)
    botoes = []
    if func and func["fazer_pedido"]:
        botoes.append([KeyboardButton("🛒 Fazer pedido")])
    if func and func["bater_ponto"]:
        botoes.append([KeyboardButton("📍 Bater ponto")])
    if func and func["entregar_trabalho"]:
        botoes.append([KeyboardButton("🔨 Entregar trabalho")])
    if func and func["admin"]:
        botoes.append([KeyboardButton("⚙️ Admin")])
    return ReplyKeyboardMarkup(botoes, resize_keyboard=True)


async def exibir_menu(update_or_message, telegram_id: int):
    msg     = update_or_message if isinstance(update_or_message, Message) else update_or_message.message
    teclado = await teclado_menu(telegram_id)
    if not teclado.keyboard:
        await msg.reply_text("✋ Seu acesso ainda não foi liberado. Aguarde a aprovação do administrador.")
        return
    await msg.reply_text("O que deseja fazer?", reply_markup=teclado)


async def verificar_acesso(update: Update):
    user_id = update.effective_user.id
    func    = await db.get_funcionario(user_id)
    u       = get_usuario(user_id)

    if func:
        return func

    if u["estado"] != "aguardando_nome":
        u["estado"] = "aguardando_nome"
        await update.message.reply_text(
            "👋 Olá! Você ainda não tem acesso.\n\n"
            "Para solicitar, informe seu nome completo:"
        )
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    func    = await db.get_funcionario(user_id)
    u       = get_usuario(user_id)

    if not func:
        u["estado"] = "aguardando_nome"
        await update.message.reply_text(
            "👋 Olá! Para solicitar acesso, informe seu nome completo:",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    usuarios[user_id] = {
        "estado": "menu",
        "produtos": [], "produto_atual": None, "categoria_atual": None,
        "tipo_ponto": None,
    }
    nome = func["nome"] or update.effective_user.first_name or "visitante"
    await update.message.reply_text(f"Olá, {nome}! Seja bem-vindo(a)! 👋", reply_markup=ReplyKeyboardRemove())
    await exibir_menu(update, user_id)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto   = update.message.text.strip()
    u       = get_usuario(user_id)

    # --- SOLICITAÇÃO DE ACESSO ---
    if u["estado"] == "aguardando_nome":
        username = update.effective_user.username
        await db.criar_solicitacao(user_id, texto, username)
        u["estado"] = "aguardando_aprovacao"
        await update.message.reply_text(
            f"✅ Solicitação enviada, *{texto}*!\n\n"
            "Aguarde a aprovação do administrador para acessar o sistema.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    if u["estado"] == "aguardando_aprovacao":
        func = await db.get_funcionario(user_id)
        tem_acesso = func and any(func[p] for p in ["bater_ponto", "fazer_pedido", "entregar_trabalho", "admin"])
        if not tem_acesso:
            await update.message.reply_text("⏳ Sua solicitação ainda está pendente. Aguarde a aprovação.")
            return
        # Acesso liberado — atualiza estado e segue
        u["estado"] = "menu"

    func = await verificar_acesso(update)
    if not func:
        return

    estado = u["estado"]

    # --- MENU ---
    if estado in ("inicial", "menu"):
        if texto == "🛒 Fazer pedido" and func["fazer_pedido"]:
            await fazer_pedido_bot.iniciar(update, context)
        elif texto == "📍 Bater ponto" and func["bater_ponto"]:
            await bater_ponto_bot.iniciar(update, context)
        elif texto == "🔨 Entregar trabalho" and func["entregar_trabalho"]:
            await entregar_trabalho_bot.iniciar(update, context)
        elif texto == "⚙️ Admin" and func["admin"]:
            await admin_bot.iniciar(update, context)
        else:
            await exibir_menu(update, user_id)
        return

    # --- PEDIDO ---
    if estado.startswith("pedido_"):
        await fazer_pedido_bot.handle_message(update, context)
        if u["estado"] == "menu":
            await exibir_menu(update, user_id)
        return

    # --- PONTO ---
    if estado.startswith("ponto_"):
        await bater_ponto_bot.handle_message(update, context)
        if u["estado"] == "menu":
            await exibir_menu(update, user_id)
        return

    # --- ENTREGAR TRABALHO ---
    if estado.startswith("trabalho_"):
        await entregar_trabalho_bot.handle_message(update, context)
        if u["estado"] == "menu":
            await exibir_menu(update, user_id)
        return

    # --- ADMIN ---
    if estado.startswith("admin_"):
        await admin_bot.handle_message(update, context)
        if u["estado"] == "menu":
            await exibir_menu(update, user_id)
        return


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    func    = await db.get_funcionario(user_id)
    if not func:
        return
    u = get_usuario(user_id)
    if u["estado"] == "trabalho_fotos":
        await entregar_trabalho_bot.handle_photo(update, context)


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_usuario(update.effective_user.id)
    if u["estado"] == "ponto_localizacao":
        voltou = await bater_ponto_bot.handle_location(update, context, GROUP_PONTO_ID)
        if voltou:
            await exibir_menu(update, update.effective_user.id)


async def on_startup(app):
    await db.init_db()
    print("Banco inicializado.")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot rodando...")
    app.run_polling()
