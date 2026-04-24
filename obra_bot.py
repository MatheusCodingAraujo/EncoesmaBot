from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from estado import get_usuario
import database as db

CRIAR_NOVA      = "➕ Criar nova obra"
NOVO_STATUS     = "➕ Novo status"
EDITAR_STATUS   = "✏️ Editar status"
EDITAR_DADOS    = "✏️ Editar dados"
EXCLUIR_OBRA    = "🗑️ Excluir obra"
CONCLUIR_OBRA   = "✅ Concluir obra"
PULAR           = "⏭️ Pular"
EDITAR_NOME     = "✏️ Editar nome"
EDITAR_ENDERECO = "✏️ Editar endereço"
EDITAR_TEXTO    = "✏️ Editar texto"
EXCLUIR_STATUS  = "🗑️ Excluir status"
CONFIRMAR       = "✅ Confirmar"
CANCELAR        = "❌ Cancelar"
VOLTAR          = "⬅️ Voltar"
VOLTAR_MENU     = "⬅️ Voltar ao menu"


# ── Teclados ──────────────────────────────────────────────────────────────────

def teclado_obra_menu(obras_map: dict) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(CRIAR_NOVA)]]
    for label in obras_map:
        linhas.append([KeyboardButton(label)])
    linhas.append([KeyboardButton(VOLTAR_MENU)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_obra_detalhe(tem_status: bool) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(NOVO_STATUS)]]
    if tem_status:
        linhas.append([KeyboardButton(EDITAR_STATUS)])
    linhas.append([KeyboardButton(EDITAR_DADOS), KeyboardButton(EXCLUIR_OBRA)])
    linhas.append([KeyboardButton(VOLTAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_editar_dados() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(EDITAR_NOME)],
         [KeyboardButton(EDITAR_ENDERECO)],
         [KeyboardButton(VOLTAR)]],
        resize_keyboard=True
    )


def teclado_status_lista(status_map: dict) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(label)] for label in status_map]
    linhas.append([KeyboardButton(VOLTAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_status_editar() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(EDITAR_TEXTO), KeyboardButton(EXCLUIR_STATUS)],
         [KeyboardButton(VOLTAR)]],
        resize_keyboard=True
    )


def teclado_novo_status() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CONCLUIR_OBRA)],
         [KeyboardButton(VOLTAR)]],
        resize_keyboard=True
    )


def teclado_criar_status() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(PULAR)],
         [KeyboardButton(VOLTAR)]],
        resize_keyboard=True
    )


def teclado_confirmacao() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CONFIRMAR), KeyboardButton(CANCELAR)]],
        resize_keyboard=True
    )


def teclado_digitacao() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(VOLTAR)]], resize_keyboard=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _construir_obras_map(obras: list) -> dict:
    obras_map = {}
    for o in obras:
        label = f"🏗️ {o['nome']}"
        if label in obras_map:
            label = f"🏗️ {o['nome']} (#{o['id']})"
        obras_map[label] = o["id"]
    return obras_map


def _construir_status_map(statuses: list) -> dict:
    status_map = {}
    for s in statuses:
        data  = s["criado_em"].strftime("%d/%m")
        label = f"[{data}] {s['texto']}"
        base  = label
        n     = 1
        while label in status_map:
            n    += 1
            label = f"{base} ({n})"
        status_map[label] = s["id"]
    return status_map


async def _texto_detalhe(obra_id: int) -> str:
    obra     = await db.get_obra(obra_id)
    statuses = await db.listar_status_obra(obra_id)
    texto    = f"🏗️ *{obra['nome']}*\n📍 {obra['endereco'] or 'Endereço não informado'}"
    if statuses:
        texto += "\n\n📋 *Histórico de Status:*"
        for s in statuses:
            data   = s["criado_em"].strftime("%d/%m")
            texto += f"\n• {data} — {s['texto']}"
    return texto


# ── Entry point ───────────────────────────────────────────────────────────────

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_usuario(update.effective_user.id)
    await _exibir_obra_menu(update, u)


# ── Handler principal ─────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto   = update.message.text.strip()
    u       = get_usuario(user_id)

    # --- MENU DE OBRAS ---
    if u["estado"] == "admin_obra_menu":
        if texto == CRIAR_NOVA:
            u["estado"] = "admin_obra_criar_nome"
            await update.message.reply_text(
                "🏗️ *Nova Obra*\n\nDigite o nome da obra:",
                parse_mode="Markdown",
                reply_markup=teclado_digitacao()
            )
        elif texto == VOLTAR_MENU:
            u["estado"] = "menu"
        else:
            obras_map = u.get("admin_obra_map", {})
            if texto in obras_map:
                u["admin_obra_id"] = obras_map[texto]
                await _exibir_detalhe(update, u)
            else:
                await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_obra_menu(obras_map))
        return

    # --- CRIAR OBRA: NOME ---
    if u["estado"] == "admin_obra_criar_nome":
        if texto == VOLTAR:
            await _exibir_obra_menu(update, u)
        else:
            u["admin_obra_nome_temp"] = texto
            u["estado"]               = "admin_obra_criar_endereco"
            await update.message.reply_text(
                f"📍 Digite o endereço de *{texto}*:",
                parse_mode="Markdown",
                reply_markup=teclado_digitacao()
            )
        return

    # --- CRIAR OBRA: ENDEREÇO ---
    if u["estado"] == "admin_obra_criar_endereco":
        if texto == VOLTAR:
            u["estado"] = "admin_obra_criar_nome"
            await update.message.reply_text("🏗️ Digite o nome da obra:", reply_markup=teclado_digitacao())
        else:
            u["admin_obra_endereco_temp"] = texto
            u["estado"]                   = "admin_obra_criar_status"
            await update.message.reply_text(
                "📋 Digite o status inicial ou pule:",
                reply_markup=teclado_criar_status()
            )
        return

    # --- CRIAR OBRA: STATUS INICIAL ---
    if u["estado"] == "admin_obra_criar_status":
        if texto == VOLTAR:
            u["estado"] = "admin_obra_criar_endereco"
            await update.message.reply_text("📍 Digite o endereço da obra:", reply_markup=teclado_digitacao())
            return

        nome     = u.pop("admin_obra_nome_temp", "")
        endereco = u.pop("admin_obra_endereco_temp", "")
        obra_id  = await db.criar_obra(nome, endereco)
        u["admin_obra_id"] = obra_id

        if texto != PULAR:
            await db.criar_status_obra(obra_id, texto)

        await update.message.reply_text(f'✅ Obra *"{nome}"* criada com sucesso!', parse_mode="Markdown")
        await _exibir_detalhe(update, u)
        return

    # --- DETALHE DA OBRA ---
    if u["estado"] == "admin_obra_detalhe":
        obra_id  = u.get("admin_obra_id")
        statuses = await db.listar_status_obra(obra_id)

        if texto == NOVO_STATUS:
            u["estado"] = "admin_obra_novo_status"
            await update.message.reply_text(
                "✍️ Digite o novo status ou conclua a obra:",
                reply_markup=teclado_novo_status()
            )
        elif texto == EDITAR_STATUS:
            await _exibir_status_lista(update, u, obra_id)
        elif texto == EDITAR_DADOS:
            u["estado"] = "admin_obra_editar_dados"
            await update.message.reply_text("✏️ O que deseja editar?", reply_markup=teclado_editar_dados())
        elif texto == EXCLUIR_OBRA:
            u["estado"] = "admin_obra_confirmar_excluir"
            obra        = await db.get_obra(obra_id)
            await update.message.reply_text(
                f"⚠️ Confirmar exclusão de *{obra['nome']}*?\nTodos os status serão removidos.",
                parse_mode="Markdown",
                reply_markup=teclado_confirmacao()
            )
        elif texto == VOLTAR:
            await _exibir_obra_menu(update, u)
        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_obra_detalhe(bool(statuses)))
        return

    # --- NOVO STATUS ---
    if u["estado"] == "admin_obra_novo_status":
        obra_id = u.get("admin_obra_id")

        if texto == VOLTAR:
            await _exibir_detalhe(update, u)
        elif texto == CONCLUIR_OBRA:
            await db.criar_status_obra(obra_id, "✅ Concluído", concluir=True)
            obra = await db.get_obra(obra_id)
            await update.message.reply_text(f'✅ Obra *"{obra["nome"]}"* concluída!', parse_mode="Markdown")
            await _exibir_obra_menu(update, u)
        else:
            await db.criar_status_obra(obra_id, texto)
            await update.message.reply_text(f'✅ Status *"{texto}"* adicionado.', parse_mode="Markdown")
            await _exibir_detalhe(update, u)
        return

    # --- EDITAR DADOS ---
    if u["estado"] == "admin_obra_editar_dados":
        if texto == EDITAR_NOME:
            u["estado"] = "admin_obra_editar_nome"
            await update.message.reply_text("✏️ Digite o novo nome:", reply_markup=teclado_digitacao())
        elif texto == EDITAR_ENDERECO:
            u["estado"] = "admin_obra_editar_endereco"
            await update.message.reply_text("📍 Digite o novo endereço:", reply_markup=teclado_digitacao())
        elif texto == VOLTAR:
            await _exibir_detalhe(update, u)
        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_editar_dados())
        return

    # --- EDITAR NOME ---
    if u["estado"] == "admin_obra_editar_nome":
        if texto == VOLTAR:
            u["estado"] = "admin_obra_editar_dados"
            await update.message.reply_text("✏️ O que deseja editar?", reply_markup=teclado_editar_dados())
        else:
            await db.editar_obra_nome(u["admin_obra_id"], texto)
            await update.message.reply_text(f'✅ Nome atualizado para *"{texto}"*.', parse_mode="Markdown")
            await _exibir_detalhe(update, u)
        return

    # --- EDITAR ENDEREÇO ---
    if u["estado"] == "admin_obra_editar_endereco":
        if texto == VOLTAR:
            u["estado"] = "admin_obra_editar_dados"
            await update.message.reply_text("✏️ O que deseja editar?", reply_markup=teclado_editar_dados())
        else:
            await db.editar_obra_endereco(u["admin_obra_id"], texto)
            await update.message.reply_text(f'✅ Endereço atualizado para *"{texto}"*.', parse_mode="Markdown")
            await _exibir_detalhe(update, u)
        return

    # --- CONFIRMAR EXCLUSÃO DA OBRA ---
    if u["estado"] == "admin_obra_confirmar_excluir":
        obra_id = u.get("admin_obra_id")
        if texto == CONFIRMAR:
            obra = await db.get_obra(obra_id)
            await db.excluir_obra(obra_id)
            u["admin_obra_id"] = None
            await update.message.reply_text(f'🗑️ Obra *"{obra["nome"]}"* excluída.', parse_mode="Markdown")
            await _exibir_obra_menu(update, u)
        elif texto == CANCELAR:
            await _exibir_detalhe(update, u)
        return

    # --- LISTA DE STATUS (para editar) ---
    if u["estado"] == "admin_obra_status_lista":
        if texto == VOLTAR:
            await _exibir_detalhe(update, u)
        else:
            status_map = u.get("admin_obra_status_map", {})
            if texto in status_map:
                status_id                 = status_map[texto]
                u["admin_obra_status_id"] = status_id
                u["estado"]               = "admin_obra_status_editar"
                status                    = await db.get_status_obra(status_id)
                await update.message.reply_text(
                    f"📋 *{status['texto']}*\n\nO que deseja fazer?",
                    parse_mode="Markdown",
                    reply_markup=teclado_status_editar()
                )
            else:
                await update.message.reply_text("Selecione um status da lista.", reply_markup=teclado_status_lista(status_map))
        return

    # --- EDITAR UM STATUS ---
    if u["estado"] == "admin_obra_status_editar":
        status_id = u.get("admin_obra_status_id")

        if texto == EDITAR_TEXTO:
            u["estado"] = "admin_obra_status_renomear"
            await update.message.reply_text("✏️ Digite o novo texto:", reply_markup=teclado_digitacao())
        elif texto == EXCLUIR_STATUS:
            u["estado"] = "admin_obra_status_confirmar_excluir"
            status      = await db.get_status_obra(status_id)
            await update.message.reply_text(
                f"⚠️ Confirmar exclusão do status *\"{status['texto']}\"*?",
                parse_mode="Markdown",
                reply_markup=teclado_confirmacao()
            )
        elif texto == VOLTAR:
            await _exibir_status_lista(update, u, u["admin_obra_id"])
        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_status_editar())
        return

    # --- RENOMEAR STATUS ---
    if u["estado"] == "admin_obra_status_renomear":
        if texto == VOLTAR:
            await _exibir_status_lista(update, u, u["admin_obra_id"])
        else:
            await db.editar_status_obra(u["admin_obra_status_id"], texto)
            await update.message.reply_text(f'✅ Status atualizado para *"{texto}"*.', parse_mode="Markdown")
            await _exibir_detalhe(update, u)
        return

    # --- CONFIRMAR EXCLUSÃO DE STATUS ---
    if u["estado"] == "admin_obra_status_confirmar_excluir":
        status_id = u.get("admin_obra_status_id")
        if texto == CONFIRMAR:
            status = await db.get_status_obra(status_id)
            await db.excluir_status_obra(status_id)
            u["admin_obra_status_id"] = None
            await update.message.reply_text(f'🗑️ Status *"{status["texto"]}"* excluído.', parse_mode="Markdown")
            await _exibir_detalhe(update, u)
        elif texto == CANCELAR:
            u["estado"] = "admin_obra_status_editar"
            status      = await db.get_status_obra(status_id)
            await update.message.reply_text(
                f"📋 *{status['texto']}*\n\nO que deseja fazer?",
                parse_mode="Markdown",
                reply_markup=teclado_status_editar()
            )
        return


# ── Auxiliares ────────────────────────────────────────────────────────────────

async def _exibir_obra_menu(update: Update, u: dict):
    obras     = await db.listar_obras_ativas()
    obras_map = _construir_obras_map(obras)
    u["admin_obra_map"] = obras_map
    u["estado"]         = "admin_obra_menu"
    msg = "🏗️ *Registro de Obras*\n\nSelecione uma obra ou crie uma nova:" if obras else \
          "🏗️ *Registro de Obras*\n\nNenhuma obra ativa. Crie uma nova:"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=teclado_obra_menu(obras_map))


async def _exibir_detalhe(update: Update, u: dict):
    obra_id  = u["admin_obra_id"]
    statuses = await db.listar_status_obra(obra_id)
    u["estado"] = "admin_obra_detalhe"
    await update.message.reply_text(
        await _texto_detalhe(obra_id),
        parse_mode="Markdown",
        reply_markup=teclado_obra_detalhe(bool(statuses))
    )


async def _exibir_status_lista(update: Update, u: dict, obra_id: int):
    statuses   = await db.listar_status_obra(obra_id)
    status_map = _construir_status_map(statuses)
    u["admin_obra_status_map"] = status_map
    u["estado"]                = "admin_obra_status_lista"
    await update.message.reply_text(
        "📋 Selecione o status para editar:",
        reply_markup=teclado_status_lista(status_map)
    )
