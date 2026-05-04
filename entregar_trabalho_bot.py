from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, InputMediaPhoto
from telegram.ext import ContextTypes
from datetime import datetime
from estado import get_usuario
import database as db

CONCLUIR = "✅ Concluir envio"
CANCELAR = "❌ Cancelar"


# ── Teclados ──────────────────────────────────────────────────────────────────

def teclado_obras(obras_map: dict) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(label)] for label in obras_map]
    linhas.append([KeyboardButton(CANCELAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_fotos() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CONCLUIR)],
         [KeyboardButton(CANCELAR)]],
        resize_keyboard=True
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _construir_obras_map(obras: list) -> dict:
    obras_map = {}
    for o in obras:
        label = o["nome"]
        if label in obras_map:
            label = f"{o['nome']} (#{o['id']})"
        obras_map[label] = o["id"]
    return obras_map


def _cancelar(u: dict):
    u["estado"]               = "menu"
    u["trabalho_obra_id"]     = None
    u["trabalho_obra_nome"]   = None
    u["trabalho_fotos_count"] = 0
    u["trabalho_file_ids"]    = []


async def _enviar_grupo(context: ContextTypes.DEFAULT_TYPE, identificacao: str, obra_nome: str, file_ids: list):
    from main_bot import GROUP_TRABALHO_ID
    if not GROUP_TRABALHO_ID:
        return

    agora   = datetime.now().strftime("%d/%m/%Y às %H:%M")
    caption = (
        f"📸 *Entrega de Trabalho*\n\n"
        f"👤 {identificacao}\n"
        f"🏗️ Obra: {obra_nome}\n"
        f"🕐 {agora}"
    )

    # Envia em lotes de 10 (limite do Telegram)
    for i in range(0, len(file_ids), 10):
        lote   = file_ids[i:i + 10]
        midias = [
            InputMediaPhoto(
                media=fid,
                caption=caption if idx == 0 and i == 0 else None,
                parse_mode="Markdown" if idx == 0 and i == 0 else None
            )
            for idx, fid in enumerate(lote)
        ]
        if len(midias) == 1:
            # yoopa
            await context.bot.send_photo(
                chat_id=GROUP_TRABALHO_ID,
                photo=midias[0].media,
                caption=midias[0].caption,
                parse_mode="Markdown" if midias[0].caption else None
            )
        else:
            await context.bot.send_media_group(chat_id=GROUP_TRABALHO_ID, media=midias)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u     = get_usuario(update.effective_user.id)
    obras = await db.listar_obras_ativas()

    if not obras:
        await update.message.reply_text(
            "⚠️ Nenhuma obra ativa no momento.",
            reply_markup=ReplyKeyboardRemove()
        )
        u["estado"] = "menu"
        return

    obras_map                 = _construir_obras_map(obras)
    u["trabalho_obras_map"]   = obras_map
    u["trabalho_fotos_count"] = 0
    u["trabalho_file_ids"]    = []
    u["estado"]               = "trabalho_obra"

    await update.message.reply_text(
        "🔨 *Entregar Trabalho*\n\nQual obra você está trabalhando?",
        parse_mode="Markdown",
        reply_markup=teclado_obras(obras_map)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto   = update.message.text.strip()
    u       = get_usuario(user_id)

    # --- SELEÇÃO DE OBRA ---
    if u["estado"] == "trabalho_obra":
        if texto == CANCELAR:
            _cancelar(u)
            await update.message.reply_text("Operação cancelada.", reply_markup=ReplyKeyboardRemove())
            return

        obras_map = u.get("trabalho_obras_map", {})
        if texto not in obras_map:
            await update.message.reply_text("Selecione uma obra da lista.", reply_markup=teclado_obras(obras_map))
            return

        u["trabalho_obra_id"]   = obras_map[texto]
        u["trabalho_obra_nome"] = texto
        u["estado"]             = "trabalho_fotos"

        await update.message.reply_text(
            f"📸 *{texto}*\n\nEncaminhe as fotos do seu trabalho.\n"
            "Você pode enviar várias. Quando terminar, clique em *✅ Concluir envio*.",
            parse_mode="Markdown",
            reply_markup=teclado_fotos()
        )
        return

    # --- RECEBENDO FOTOS ---
    if u["estado"] == "trabalho_fotos":
        if texto == CANCELAR:
            _cancelar(u)
            await update.message.reply_text("Envio cancelado.", reply_markup=ReplyKeyboardRemove())
            return

        if texto == CONCLUIR:
            count = u.get("trabalho_fotos_count", 0)
            if count == 0:
                await update.message.reply_text(
                    "📸 Envie ao menos uma foto antes de concluir.",
                    reply_markup=teclado_fotos()
                )
                return

            obra_nome     = u.get("trabalho_obra_nome", "")
            file_ids      = u.get("trabalho_file_ids", [])
            nome          = update.effective_user.first_name or "Funcionário"
            username      = update.effective_user.username
            identificacao = f"@{username}" if username else nome

            await update.message.reply_text(
                f'✅ *{count} foto(s)* registrada(s) para *"{obra_nome}"*!',
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove()
            )

            await _enviar_grupo(context, identificacao, obra_nome, file_ids)
            _cancelar(u)
            return

        await update.message.reply_text(
            "📸 Envie as fotos ou clique em *✅ Concluir envio*.",
            parse_mode="Markdown",
            reply_markup=teclado_fotos()
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u       = get_usuario(user_id)

    if u["estado"] != "trabalho_fotos":
        return

    file_id        = update.message.photo[-1].file_id
    obra_id        = u.get("trabalho_obra_id")
    funcionario_id = await db.get_funcionario_id(user_id)

    await db.salvar_foto_trabalho(funcionario_id, obra_id, file_id)

    if "trabalho_file_ids" not in u:
        u["trabalho_file_ids"] = []
    u["trabalho_file_ids"].append(file_id)
    u["trabalho_fotos_count"] = len(u["trabalho_file_ids"])
    count = u["trabalho_fotos_count"]

    await update.message.reply_text(
        f"📸 Foto {count} recebida! Pode enviar mais ou clique em *✅ Concluir envio*.",
        parse_mode="Markdown",
        reply_markup=teclado_fotos()
    )
