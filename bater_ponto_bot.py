from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes
from estado import get_usuario
import database as db

TIPOS = {
    "entrada":        {"label": "🟢 Entrada",          "emoji": "🟢", "nome": "Entrada"},
    "saida_almoco":   {"label": "🍽️ Saída almoço",     "emoji": "🍽️", "nome": "Saída almoço"},
    "volta_almoco":   {"label": "🔄 Volta almoço",      "emoji": "🔄", "nome": "Volta almoço"},
    "fim_expediente": {"label": "🔴 Fim de expediente", "emoji": "🔴", "nome": "Fim de expediente"},
}

LABEL_PARA_TIPO = {v["label"]: k for k, v in TIPOS.items()}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _opcoes_disponiveis(pontos: dict) -> list[str]:
    if "entrada" not in pontos:
        return ["entrada"]
    disponiveis = []
    if "saida_almoco" not in pontos:
        disponiveis.append("saida_almoco")
    if "saida_almoco" in pontos and "volta_almoco" not in pontos:
        disponiveis.append("volta_almoco")
    if "fim_expediente" not in pontos:
        disponiveis.append("fim_expediente")
    return disponiveis


def _status_hoje(pontos: dict) -> str:
    linhas = ["📋 Seu registro de hoje:"]
    for cat, info in TIPOS.items():
        if cat in pontos:
            horario = str(pontos[cat]["horario"])[:5]
            linhas.append(f"  {info['emoji']} {info['nome']}: {horario}")
        else:
            linhas.append(f"  {info['emoji']} {info['nome']}: —")
    return "\n".join(linhas)


def _montar_texto_grupo(identificacao: str, hoje: str, pontos: dict) -> str:
    linhas = [f"🕐 *Registro de Ponto*\n\n👤 {identificacao}\n📅 {hoje}\n"]
    for cat, info in TIPOS.items():
        if cat in pontos:
            horario = str(pontos[cat]["horario"])[:5]
            lat     = pontos[cat]["lat"]
            lon     = pontos[cat]["lon"]
            url     = f"https://maps.google.com/?q={lat},{lon}"
            linhas.append(f"{info['emoji']} {info['nome']}: {horario} [loc]({url})")
        else:
            linhas.append(f"{info['emoji']} {info['nome']}: ——")
    return "\n".join(linhas)


# ── Teclados ──────────────────────────────────────────────────────────────────

def teclado_tipo_ponto(pontos: dict) -> ReplyKeyboardMarkup:
    disponiveis = _opcoes_disponiveis(pontos)
    linhas = [[KeyboardButton(TIPOS[t]["label"])] for t in disponiveis]
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True, one_time_keyboard=True)


def teclado_localizacao() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Enviar minha localização", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# ── Handlers ──────────────────────────────────────────────────────────────────

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id        = update.effective_user.id
    u              = get_usuario(user_id)
    funcionario_id = await db.get_funcionario_id(user_id)
    pontos         = await db.get_pontos_hoje(funcionario_id) if funcionario_id else {}
    disponiveis    = _opcoes_disponiveis(pontos)

    if not disponiveis:
        await update.message.reply_text(
            f"{_status_hoje(pontos)}\n\n✅ Todos os registros do dia já foram realizados!"
        )
        return

    u["estado"] = "ponto_tipo"
    await update.message.reply_text(
        f"{_status_hoje(pontos)}\n\nO que deseja registrar?",
        reply_markup=teclado_tipo_ponto(pontos)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto   = update.message.text.strip()
    u       = get_usuario(user_id)

    # Texto recebido quando localização era esperada
    if u["estado"] == "ponto_localizacao":
        tipo_nome = TIPOS[u["tipo_ponto"]]["nome"]
        await update.message.reply_text(
            f"❌ Não foi possível registrar *{tipo_nome}*.\n\n"
            "Para bater o ponto é necessário enviar sua localização. "
            "Use o botão abaixo 👇",
            parse_mode="Markdown",
            reply_markup=teclado_localizacao()
        )
        return

    if u["estado"] != "ponto_tipo":
        return

    tipo = LABEL_PARA_TIPO.get(texto)
    funcionario_id = await db.get_funcionario_id(user_id)
    pontos         = await db.get_pontos_hoje(funcionario_id) if funcionario_id else {}

    if not tipo or tipo not in _opcoes_disponiveis(pontos):
        await update.message.reply_text("Use os botões para escolher.", reply_markup=teclado_tipo_ponto(pontos))
        return

    u["tipo_ponto"] = tipo
    u["estado"]     = "ponto_localizacao"
    await update.message.reply_text(
        f"📍 Compartilhe sua localização para registrar *{TIPOS[tipo]['nome']}*.",
        parse_mode="Markdown",
        reply_markup=teclado_localizacao()
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE, group_ponto_id: str):
    user_id = update.effective_user.id
    u       = get_usuario(user_id)

    if u["estado"] != "ponto_localizacao":
        return

    location      = update.message.location
    agora         = datetime.now()
    horario_time  = agora.time().replace(second=0, microsecond=0)
    hoje_str      = agora.strftime("%d/%m/%Y")
    tipo          = u["tipo_ponto"]

    nome          = update.effective_user.first_name or "usuário"
    username      = update.effective_user.username
    identificacao = f"@{username}" if username else nome

    funcionario_id = await db.get_funcionario_id(user_id)
    await db.registrar_ponto(funcionario_id, tipo, horario_time, location.latitude, location.longitude)
    pontos         = await db.get_pontos_hoje(funcionario_id)
    group_msg_id   = await db.get_group_message_id(funcionario_id)
    texto_grupo    = _montar_texto_grupo(identificacao, hoje_str, pontos)

    await update.message.reply_text(
        f"✅ *{TIPOS[tipo]['nome']}* registrada!",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    if group_ponto_id:
        if group_msg_id:
            await context.bot.edit_message_text(
                chat_id=group_ponto_id,
                message_id=group_msg_id,
                text=texto_grupo,
                parse_mode="Markdown"
            )
        else:
            msg = await context.bot.send_message(
                chat_id=group_ponto_id,
                text=texto_grupo,
                parse_mode="Markdown"
            )
            await db.salvar_group_message_id(funcionario_id, msg.message_id)

    u["estado"]     = "menu"
    u["tipo_ponto"] = None
    return True
