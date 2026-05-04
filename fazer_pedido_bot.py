from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes
from estado import get_usuario
import database as db

FINALIZAR      = "✅ Finalizar pedido"
VOLTAR         = "⬅️ Voltar"
ADICIONAR_MAIS = "➕ Adicionar mais"
REMOVER_ITEM   = "🗑️ Remover item"
CONCLUIR       = "✅ Concluir pedido"
CANCELAR       = "❌ Cancelar pedido"
OUTROS         = "🔤 Outros"


# ── Teclados ──────────────────────────────────────────────────────────────────

async def teclado_categorias() -> ReplyKeyboardMarkup:
    categorias = await db.listar_categorias()
    linhas = [[KeyboardButton(c)] for c in categorias]
    linhas.append([KeyboardButton(OUTROS)])
    linhas.append([KeyboardButton(FINALIZAR)])
    linhas.append([KeyboardButton(CANCELAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


async def teclado_produtos(categoria: str) -> ReplyKeyboardMarkup:
    produtos = await db.listar_produtos_por_categoria(categoria)
    linhas = []
    for i in range(0, len(produtos), 2):
        linha = [KeyboardButton(produtos[i])]
        if i + 1 < len(produtos):
            linha.append(KeyboardButton(produtos[i + 1]))
        linhas.append(linha)
    linhas.append([KeyboardButton(VOLTAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_quantidade() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("1"), KeyboardButton("2"), KeyboardButton("3")],
         [KeyboardButton("5"), KeyboardButton("10"), KeyboardButton("20")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def teclado_revisao() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(ADICIONAR_MAIS), KeyboardButton(REMOVER_ITEM)],
         [KeyboardButton(CONCLUIR),       KeyboardButton(CANCELAR)]],
        resize_keyboard=True
    )


def _label_remover(p: dict) -> str:
    if p.get("especial"):
        return f"🗑️ Outros: {p['especial']} (qtd: {p['quantidade']})"
    return f"🗑️ {p['nome']} (qtd: {p['quantidade']})"


def teclado_remover(produtos: list) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(_label_remover(p))] for p in produtos]
    linhas.append([KeyboardButton(VOLTAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def montar_resumo(produtos: list) -> str:
    linhas = []
    for p in produtos:
        if p.get("especial"):
            linhas.append(f"• ⚠️ Outros: {p['especial']} — qtd: {p['quantidade']}")
        else:
            linhas.append(f"• {p['nome']} — qtd: {p['quantidade']}")
    return "\n".join(linhas)


def _texto_revisao(produtos: list) -> str:
    return f"📋 *Seu pedido atual:*\n\n{montar_resumo(produtos)}"


def adicionar_produto(u: dict, nome: str, quantidade: int, especial: str = None):
    if not especial:
        for p in u["produtos"]:
            if p["nome"] == nome and not p.get("especial"):
                p["quantidade"] += quantidade
                return
    u["produtos"].append({"nome": nome, "quantidade": quantidade, "especial": especial})


def _cancelar(u: dict):
    u["estado"]          = "menu"
    u["produtos"]        = []
    u["produto_atual"]   = None
    u["categoria_atual"] = None
    u["especial_atual"]  = None


# ── Handlers ──────────────────────────────────────────────────────────────────

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_usuario(update.effective_user.id)
    u["estado"]         = "pedido_categoria"
    u["produtos"]       = []
    u["especial_atual"] = None
    await update.message.reply_text("🛒 Certo! Selecione uma categoria:", reply_markup=await teclado_categorias())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto   = update.message.text.strip()
    u       = get_usuario(user_id)

    # --- CATEGORIA ---
    if u["estado"] == "pedido_categoria":
        if texto == CANCELAR:
            _cancelar(u)
            await update.message.reply_text("Pedido cancelado.", reply_markup=ReplyKeyboardRemove())
            return

        if texto == FINALIZAR:
            if not u["produtos"]:
                await update.message.reply_text("Adicione ao menos um produto antes de finalizar.", reply_markup=await teclado_categorias())
                return
            await _exibir_revisao(update, u)
            return

        if texto == OUTROS:
            u["estado"] = "pedido_outros"
            await update.message.reply_text(
                "✍️ Descreva o item especial que deseja:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(VOLTAR)]], resize_keyboard=True)
            )
            return

        categorias = await db.listar_categorias()
        if texto not in categorias:
            await update.message.reply_text("Selecione uma categoria válida.", reply_markup=await teclado_categorias())
            return

        u["categoria_atual"] = texto
        u["estado"]          = "pedido_produto"
        await update.message.reply_text(
            f"📦 *{texto}* — selecione o produto:",
            parse_mode="Markdown",
            reply_markup=await teclado_produtos(texto)
        )
        return

    # --- PRODUTO ---
    if u["estado"] == "pedido_produto":
        if texto == VOLTAR:
            u["categoria_atual"] = None
            u["estado"]          = "pedido_categoria"
            await update.message.reply_text("📂 Selecione uma categoria:", reply_markup=await teclado_categorias())
            return

        produtos = await db.listar_produtos_por_categoria(u["categoria_atual"])
        if texto not in produtos:
            await update.message.reply_text("Selecione um produto válido.", reply_markup=await teclado_produtos(u["categoria_atual"]))
            return

        u["produto_atual"] = texto
        u["estado"]        = "pedido_quantidade"
        await update.message.reply_text(
            f"Qual a quantidade de *{texto}*?",
            parse_mode="Markdown",
            reply_markup=teclado_quantidade()
        )
        return

    # --- ITEM ESPECIAL (OUTROS) ---
    if u["estado"] == "pedido_outros":
        if texto == VOLTAR:
            u["estado"] = "pedido_categoria"
            await update.message.reply_text("📂 Selecione uma categoria:", reply_markup=await teclado_categorias())
            return

        u["especial_atual"] = texto
        u["produto_atual"]  = "Outros"
        u["estado"]         = "pedido_quantidade"
        await update.message.reply_text(
            "Qual a quantidade?",
            reply_markup=teclado_quantidade()
        )
        return

    # --- QUANTIDADE ---
    if u["estado"] == "pedido_quantidade":
        if not texto.isdigit() or int(texto) < 1:
            await update.message.reply_text("Informe uma quantidade válida.", reply_markup=teclado_quantidade())
            return

        adicionar_produto(u, u["produto_atual"], int(texto), especial=u.get("especial_atual"))
        u["produto_atual"]  = None
        u["especial_atual"] = None
        u["estado"]         = "pedido_revisao"

        await update.message.reply_text(
            _texto_revisao(u["produtos"]),
            parse_mode="Markdown",
            reply_markup=teclado_revisao()
        )
        return

    # --- REVISÃO ---
    if u["estado"] == "pedido_revisao":
        if texto == ADICIONAR_MAIS:
            u["estado"] = "pedido_categoria"
            await update.message.reply_text("📂 Selecione uma categoria:", reply_markup=await teclado_categorias())

        elif texto == REMOVER_ITEM:
            u["estado"] = "pedido_remover"
            await update.message.reply_text(
                f"{_texto_revisao(u['produtos'])}\n\nSelecione o item para remover:",
                parse_mode="Markdown",
                reply_markup=teclado_remover(u["produtos"])
            )

        elif texto == CONCLUIR:
            await _concluir(update, context, u)

        elif texto == CANCELAR:
            _cancelar(u)
            await update.message.reply_text("Pedido cancelado.", reply_markup=ReplyKeyboardRemove())

        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_revisao())
        return

    # --- REMOVER ITEM ---
    if u["estado"] == "pedido_remover":
        if texto == VOLTAR:
            u["estado"] = "pedido_revisao"
            await update.message.reply_text(
                _texto_revisao(u["produtos"]),
                parse_mode="Markdown",
                reply_markup=teclado_revisao()
            )
            return

        removido = None
        for i, p in enumerate(u["produtos"]):
            if texto == _label_remover(p):
                removido = u["produtos"].pop(i)
                break

        if not removido:
            await update.message.reply_text("Selecione um item da lista.", reply_markup=teclado_remover(u["produtos"]))
            return

        if not u["produtos"]:
            u["estado"] = "pedido_categoria"
            nome_exibido = f'Outros: {removido["especial"]}' if removido.get("especial") else removido["nome"]
            await update.message.reply_text(
                f'🗑️ "{nome_exibido}" removido. Nenhum produto restante.\n\nSelecione uma categoria para continuar:',
                reply_markup=await teclado_categorias()
            )
            return

        u["estado"] = "pedido_revisao"
        nome_exibido = f'Outros: {removido["especial"]}' if removido.get("especial") else removido["nome"]
        await update.message.reply_text(
            f'🗑️ "{nome_exibido}" removido.\n\n{_texto_revisao(u["produtos"])}',
            parse_mode="Markdown",
            reply_markup=teclado_revisao()
        )
        return


async def _exibir_revisao(update: Update, u: dict):
    u["estado"] = "pedido_revisao"
    await update.message.reply_text(
        _texto_revisao(u["produtos"]),
        parse_mode="Markdown",
        reply_markup=teclado_revisao()
    )


async def _concluir(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    user_id       = update.effective_user.id
    nome          = update.effective_user.first_name or "usuário"
    username      = update.effective_user.username
    identificacao = f"@{username}" if username else nome
    resumo        = montar_resumo(u["produtos"])

    from main_bot import GROUP_PEDIDOS_ID
    funcionario_id = await db.get_funcionario_id(user_id)
    await db.salvar_pedido(funcionario_id, u["produtos"])

    await update.message.reply_text("✅ Pedido encaminhado com sucesso!", reply_markup=ReplyKeyboardRemove())

    if GROUP_PEDIDOS_ID:
        await context.bot.send_message(
            chat_id=GROUP_PEDIDOS_ID,
            text=f"🛒 *Novo pedido recebido!*\n\n👤 Cliente: {identificacao}\n\n📦 Produtos:\n{resumo}",
            parse_mode="Markdown"
        )

    u["estado"]         = "menu"
    u["produtos"]       = []
    u["especial_atual"] = None
