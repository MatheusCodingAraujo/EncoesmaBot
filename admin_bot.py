from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes
from estado import get_usuario
import database as db

PERMISSOES = {
    "bater_ponto":       "Bater Ponto",
    "fazer_pedido":      "Fazer Pedido",
    "entregar_trabalho": "Entregar Trabalho",
    "admin":             "Admin",
}

REMOVER           = "🗑️ Remover funcionário"
VOLTAR            = "⬅️ Voltar à lista"
VOLTAR_MENU       = "⬅️ Voltar ao menu"
CONFIRMAR_REMOCAO = "✅ Confirmar remoção"
CANCELAR_REMOCAO  = "❌ Cancelar"

RELATORIO_PONTO    = "📋 Relatório de Ponto"

CRIAR_NOVA_CAT     = "➕ Criar uma nova"
RENOMEAR           = "✏️ Renomear"
EXCLUIR_CAT        = "🗑️ Excluir categoria"
EXCLUIR_PROD       = "🗑️ Excluir produto"
ADICIONAR_PROD     = "➕ Adicionar produto"
VOLTAR_REGISTRAR   = "⬅️ Voltar"
VOLTAR_CATS        = "⬅️ Voltar às categorias"
VOLTAR_PRODS       = "⬅️ Voltar aos produtos"
CONFIRMAR_EXCLUSAO = "✅ Confirmar exclusão"
CANCELAR_EXCLUSAO  = "❌ Cancelar"


# ── Teclados ──────────────────────────────────────────────────────────────────

def teclado_admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("👥 Funcionários"), KeyboardButton("📦 Registrar/Editar")],
         [KeyboardButton("🏗️ Obras"),        KeyboardButton(RELATORIO_PONTO)],
         [KeyboardButton(VOLTAR_MENU)]],
        resize_keyboard=True
    )


def teclado_lista(func_map: dict) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(label)] for label in func_map]
    linhas.append([KeyboardButton(VOLTAR_MENU)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


async def teclado_funcionario(telegram_id: int) -> ReplyKeyboardMarkup:
    func = await db.get_funcionario(telegram_id)
    def btn(campo, label):
        icone = "✅" if func[campo] else "❌"
        return KeyboardButton(f"{icone} {label}")

    return ReplyKeyboardMarkup([
        [btn("bater_ponto", "Bater Ponto"),       btn("fazer_pedido", "Fazer Pedido")],
        [btn("entregar_trabalho", "Entregar Trabalho"), btn("admin", "Admin")],
        [KeyboardButton(REMOVER)],
        [KeyboardButton(VOLTAR)],
    ], resize_keyboard=True)


def teclado_confirmar_remocao() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CONFIRMAR_REMOCAO), KeyboardButton(CANCELAR_REMOCAO)]],
        resize_keyboard=True
    )


def teclado_registrar_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📂 Categorias"), KeyboardButton("🛍️ Produtos")],
         [KeyboardButton(VOLTAR_MENU)]],
        resize_keyboard=True
    )


def teclado_cat_lista(categorias: list) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(CRIAR_NOVA_CAT)]]
    for cat in categorias:
        linhas.append([KeyboardButton(f"✏️ Editar {cat}")])
    linhas.append([KeyboardButton(VOLTAR_REGISTRAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_cat_editar() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(RENOMEAR), KeyboardButton(EXCLUIR_CAT)],
         [KeyboardButton(VOLTAR_CATS)]],
        resize_keyboard=True
    )


def teclado_confirmar_exclusao() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CONFIRMAR_EXCLUSAO), KeyboardButton(CANCELAR_EXCLUSAO)]],
        resize_keyboard=True
    )


def teclado_prod_cat(categorias: list) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(cat)] for cat in categorias]
    linhas.append([KeyboardButton(VOLTAR_REGISTRAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_prod_lista(produtos: list) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(ADICIONAR_PROD)]]
    for prod in produtos:
        linhas.append([KeyboardButton(f"📦 {prod}")])
    linhas.append([KeyboardButton(VOLTAR_CATS)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_prod_editar() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(RENOMEAR), KeyboardButton(EXCLUIR_PROD)],
         [KeyboardButton(VOLTAR_PRODS)]],
        resize_keyboard=True
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _construir_func_map(funcionarios: list) -> dict:
    func_map = {}
    for f in funcionarios:
        label = f"👤 {f['nome']}"
        if label in func_map:
            label = f"👤 {f['nome']} (@{f['username']})" if f["username"] else f"👤 {f['nome']} #{f['telegram_id']}"
        func_map[label] = f["telegram_id"]
    return func_map


# ── Handlers ──────────────────────────────────────────────────────────────────

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_usuario(update.effective_user.id)
    u["estado"] = "admin_menu"
    await update.message.reply_text(
        "⚙️ *Painel Admin*\n\nEscolha uma opção:",
        parse_mode="Markdown",
        reply_markup=teclado_admin_menu()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto   = update.message.text.strip()
    u       = get_usuario(user_id)

    # Delega estados de obras para obra_bot
    if u["estado"].startswith("admin_obra_"):
        import obra_bot
        await obra_bot.handle_message(update, context)
        return

    # Delega estados de relatório de ponto
    if u["estado"].startswith("admin_relatorio_"):
        import relatorio_ponto_bot
        await relatorio_ponto_bot.handle_message(update, context)
        return

    # --- MENU ADMIN ---
    if u["estado"] == "admin_menu":
        if texto == "👥 Funcionários":
            await _exibir_lista(update, u)
        elif texto == "🏗️ Obras":
            import obra_bot
            await obra_bot.iniciar(update, context)
        elif texto == RELATORIO_PONTO:
            import relatorio_ponto_bot
            await relatorio_ponto_bot.iniciar(update, context)
        elif texto == "📦 Registrar/Editar":
            u["estado"] = "admin_registrar_menu"
            await update.message.reply_text(
                "📦 *Registrar/Editar*\n\nO que deseja gerenciar?",
                parse_mode="Markdown",
                reply_markup=teclado_registrar_menu()
            )
        elif texto == VOLTAR_MENU:
            u["estado"] = "menu"
        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_admin_menu())
        return

    # --- LISTA DE FUNCIONÁRIOS ---
    if u["estado"] == "admin_funcionarios":
        if texto == VOLTAR_MENU:
            u["estado"] = "menu"
            return

        func_map = u.get("admin_func_map", {})
        if texto in func_map:
            telegram_id        = func_map[texto]
            func               = await db.get_funcionario(telegram_id)
            u["admin_func_id"] = telegram_id
            u["estado"]        = "admin_funcionario"
            username           = f" (@{func['username']})" if func["username"] else ""
            await update.message.reply_text(
                f"👤 *{func['nome']}*{username}",
                parse_mode="Markdown",
                reply_markup=await teclado_funcionario(telegram_id)
            )
        else:
            await update.message.reply_text("Selecione um funcionário da lista.", reply_markup=teclado_lista(func_map))
        return

    # --- DETALHE DO FUNCIONÁRIO ---
    if u["estado"] == "admin_funcionario":
        telegram_id = u.get("admin_func_id")

        if texto == VOLTAR:
            await _exibir_lista(update, u)
            return

        if texto == REMOVER:
            func = await db.get_funcionario(telegram_id)
            u["estado"] = "admin_confirmar_remocao"
            await update.message.reply_text(
                f"⚠️ Tem certeza que deseja remover *{func['nome']}*?",
                parse_mode="Markdown",
                reply_markup=teclado_confirmar_remocao()
            )
            return

        campo = _identificar_campo(texto)
        if campo:
            await db.toggle_permissao(telegram_id, campo)
            func     = await db.get_funcionario(telegram_id)
            username = f" (@{func['username']})" if func["username"] else ""
            await update.message.reply_text(
                f"👤 *{func['nome']}*{username}",
                parse_mode="Markdown",
                reply_markup=await teclado_funcionario(telegram_id)
            )
        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=await teclado_funcionario(telegram_id))
        return

    # --- CONFIRMAR REMOÇÃO ---
    if u["estado"] == "admin_confirmar_remocao":
        telegram_id = u.get("admin_func_id")

        if texto == CONFIRMAR_REMOCAO:
            func = await db.get_funcionario(telegram_id)
            nome = func["nome"] if func else "Funcionário"
            await db.remover_funcionario(telegram_id)
            u["admin_func_id"] = None
            await update.message.reply_text(f'🗑️ "{nome}" removido com sucesso.')
            await _exibir_lista(update, u)

        elif texto == CANCELAR_REMOCAO:
            u["estado"] = "admin_funcionario"
            func        = await db.get_funcionario(telegram_id)
            username    = f" (@{func['username']})" if func["username"] else ""
            await update.message.reply_text(
                f"👤 *{func['nome']}*{username}",
                parse_mode="Markdown",
                reply_markup=await teclado_funcionario(telegram_id)
            )
        return

    # --- REGISTRAR/EDITAR MENU ---
    if u["estado"] == "admin_registrar_menu":
        if texto == "📂 Categorias":
            await _exibir_cat_lista(update, u)
        elif texto == "🛍️ Produtos":
            await _exibir_prod_cat(update, u)
        elif texto == VOLTAR_MENU:
            u["estado"] = "menu"
        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_registrar_menu())
        return

    # --- LISTA DE CATEGORIAS ---
    if u["estado"] == "admin_cat_lista":
        if texto == CRIAR_NOVA_CAT:
            u["estado"] = "admin_cat_nova_nome"
            await update.message.reply_text(
                "📝 Digite o nome da nova categoria:",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(VOLTAR_REGISTRAR)]], resize_keyboard=True)
            )
        elif texto == VOLTAR_REGISTRAR:
            u["estado"] = "admin_registrar_menu"
            await update.message.reply_text(
                "📦 *Registrar/Editar*\n\nO que deseja gerenciar?",
                parse_mode="Markdown",
                reply_markup=teclado_registrar_menu()
            )
        elif texto.startswith("✏️ Editar "):
            nome_cat             = texto[len("✏️ Editar "):]
            u["admin_cat_atual"] = nome_cat
            u["estado"]          = "admin_cat_editar"
            await update.message.reply_text(
                f"✏️ *{nome_cat}*\n\nO que deseja fazer?",
                parse_mode="Markdown",
                reply_markup=teclado_cat_editar()
            )
        else:
            cats = await db.listar_categorias()
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_cat_lista(cats))
        return

    # --- CRIAR NOVA CATEGORIA ---
    if u["estado"] == "admin_cat_nova_nome":
        if texto == VOLTAR_REGISTRAR:
            await _exibir_cat_lista(update, u)
        else:
            sucesso = await db.criar_categoria(texto)
            if sucesso:
                await update.message.reply_text(f'✅ Categoria *"{texto}"* criada com sucesso!', parse_mode="Markdown")
            else:
                await update.message.reply_text(f'⚠️ Já existe uma categoria com o nome *"{texto}"*.', parse_mode="Markdown")
            await _exibir_cat_lista(update, u)
        return

    # --- EDITAR CATEGORIA ---
    if u["estado"] == "admin_cat_editar":
        nome_cat = u.get("admin_cat_atual")

        if texto == RENOMEAR:
            u["estado"] = "admin_cat_renomear"
            await update.message.reply_text(
                f"✏️ Digite o novo nome para *{nome_cat}*:",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(VOLTAR_CATS)]], resize_keyboard=True)
            )
        elif texto == EXCLUIR_CAT:
            u["estado"] = "admin_cat_confirmar_excluir"
            await update.message.reply_text(
                f"⚠️ Tem certeza que deseja excluir *{nome_cat}* e todos os seus produtos?",
                parse_mode="Markdown",
                reply_markup=teclado_confirmar_exclusao()
            )
        elif texto == VOLTAR_CATS:
            await _exibir_cat_lista(update, u)
        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_cat_editar())
        return

    # --- RENOMEAR CATEGORIA ---
    if u["estado"] == "admin_cat_renomear":
        nome_cat = u.get("admin_cat_atual")

        if texto == VOLTAR_CATS:
            await _exibir_cat_lista(update, u)
        else:
            sucesso = await db.renomear_categoria(nome_cat, texto)
            if sucesso:
                u["admin_cat_atual"] = texto
                await update.message.reply_text(f'✅ Categoria renomeada para *"{texto}"* com sucesso!', parse_mode="Markdown")
            else:
                await update.message.reply_text(f'⚠️ Já existe uma categoria com o nome *"{texto}"*.', parse_mode="Markdown")
            await _exibir_cat_lista(update, u)
        return

    # --- CONFIRMAR EXCLUSÃO DE CATEGORIA ---
    if u["estado"] == "admin_cat_confirmar_excluir":
        nome_cat = u.get("admin_cat_atual")

        if texto == CONFIRMAR_EXCLUSAO:
            await db.remover_categoria(nome_cat)
            u["admin_cat_atual"] = None
            await update.message.reply_text(f'🗑️ Categoria *"{nome_cat}"* excluída com sucesso.', parse_mode="Markdown")
            await _exibir_cat_lista(update, u)
        elif texto == CANCELAR_EXCLUSAO:
            u["estado"] = "admin_cat_editar"
            await update.message.reply_text(
                f"✏️ *{nome_cat}*\n\nO que deseja fazer?",
                parse_mode="Markdown",
                reply_markup=teclado_cat_editar()
            )
        return

    # --- SELECIONAR CATEGORIA P/ PRODUTOS ---
    if u["estado"] == "admin_prod_cat":
        cats = await db.listar_categorias()

        if texto == VOLTAR_REGISTRAR:
            u["estado"] = "admin_registrar_menu"
            await update.message.reply_text(
                "📦 *Registrar/Editar*\n\nO que deseja gerenciar?",
                parse_mode="Markdown",
                reply_markup=teclado_registrar_menu()
            )
        elif texto in cats:
            u["admin_cat_atual"] = texto
            await _exibir_prod_lista(update, u)
        else:
            await update.message.reply_text("Selecione uma categoria.", reply_markup=teclado_prod_cat(cats))
        return

    # --- LISTA DE PRODUTOS ---
    if u["estado"] == "admin_prod_lista":
        nome_cat = u.get("admin_cat_atual")

        if texto == ADICIONAR_PROD:
            u["estado"] = "admin_prod_novo_nome"
            await update.message.reply_text(
                f"📝 Digite o nome do novo produto para *{nome_cat}*:",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(VOLTAR_PRODS)]], resize_keyboard=True)
            )
        elif texto == VOLTAR_CATS:
            await _exibir_prod_cat(update, u)
        elif texto.startswith("📦 "):
            nome_prod             = texto[len("📦 "):]
            u["admin_prod_atual"] = nome_prod
            u["estado"]           = "admin_prod_editar"
            await update.message.reply_text(
                f"📦 *{nome_prod}*\n\nO que deseja fazer?",
                parse_mode="Markdown",
                reply_markup=teclado_prod_editar()
            )
        else:
            produtos = await db.listar_produtos_por_categoria(nome_cat)
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_prod_lista(produtos))
        return

    # --- ADICIONAR PRODUTO ---
    if u["estado"] == "admin_prod_novo_nome":
        nome_cat = u.get("admin_cat_atual")

        if texto == VOLTAR_PRODS:
            await _exibir_prod_lista(update, u)
        else:
            sucesso = await db.criar_produto(nome_cat, texto)
            if sucesso:
                await update.message.reply_text(f'✅ Produto *"{texto}"* adicionado com sucesso!', parse_mode="Markdown")
            else:
                await update.message.reply_text(f'⚠️ Já existe um produto *"{texto}"* nessa categoria.', parse_mode="Markdown")
            await _exibir_prod_lista(update, u)
        return

    # --- EDITAR PRODUTO ---
    if u["estado"] == "admin_prod_editar":
        nome_prod = u.get("admin_prod_atual")

        if texto == RENOMEAR:
            u["estado"] = "admin_prod_renomear"
            await update.message.reply_text(
                f"✏️ Digite o novo nome para *{nome_prod}*:",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(VOLTAR_PRODS)]], resize_keyboard=True)
            )
        elif texto == EXCLUIR_PROD:
            u["estado"] = "admin_prod_confirmar_excluir"
            await update.message.reply_text(
                f"⚠️ Tem certeza que deseja excluir o produto *{nome_prod}*?",
                parse_mode="Markdown",
                reply_markup=teclado_confirmar_exclusao()
            )
        elif texto == VOLTAR_PRODS:
            await _exibir_prod_lista(update, u)
        else:
            await update.message.reply_text("Use os botões abaixo.", reply_markup=teclado_prod_editar())
        return

    # --- RENOMEAR PRODUTO ---
    if u["estado"] == "admin_prod_renomear":
        nome_cat  = u.get("admin_cat_atual")
        nome_prod = u.get("admin_prod_atual")

        if texto == VOLTAR_PRODS:
            await _exibir_prod_lista(update, u)
        else:
            sucesso = await db.renomear_produto(nome_cat, nome_prod, texto)
            if sucesso:
                u["admin_prod_atual"] = texto
                await update.message.reply_text(f'✅ Produto renomeado para *"{texto}"* com sucesso!', parse_mode="Markdown")
            else:
                await update.message.reply_text(f'⚠️ Já existe um produto *"{texto}"* nessa categoria.', parse_mode="Markdown")
            await _exibir_prod_lista(update, u)
        return

    # --- CONFIRMAR EXCLUSÃO DE PRODUTO ---
    if u["estado"] == "admin_prod_confirmar_excluir":
        nome_cat  = u.get("admin_cat_atual")
        nome_prod = u.get("admin_prod_atual")

        if texto == CONFIRMAR_EXCLUSAO:
            await db.remover_produto(nome_cat, nome_prod)
            u["admin_prod_atual"] = None
            await update.message.reply_text(f'🗑️ Produto *"{nome_prod}"* excluído com sucesso.', parse_mode="Markdown")
            await _exibir_prod_lista(update, u)
        elif texto == CANCELAR_EXCLUSAO:
            u["estado"] = "admin_prod_editar"
            await update.message.reply_text(
                f"📦 *{nome_prod}*\n\nO que deseja fazer?",
                parse_mode="Markdown",
                reply_markup=teclado_prod_editar()
            )
        return


def _identificar_campo(texto: str) -> str | None:
    for campo, label in PERMISSOES.items():
        if label in texto:
            return campo
    return None


async def _exibir_lista(update: Update, u: dict):
    funcionarios        = await db.listar_funcionarios()
    func_map            = await _construir_func_map(funcionarios)
    u["admin_func_map"] = func_map
    u["estado"]         = "admin_funcionarios"

    if not funcionarios:
        await update.message.reply_text("Nenhum funcionário cadastrado.", reply_markup=teclado_admin_menu())
        return

    await update.message.reply_text(
        "👥 *Funcionários cadastrados:*\nSelecione para gerenciar.",
        parse_mode="Markdown",
        reply_markup=teclado_lista(func_map)
    )


async def _exibir_cat_lista(update: Update, u: dict):
    cats        = await db.listar_categorias()
    u["estado"] = "admin_cat_lista"
    await update.message.reply_text(
        "📂 *Categorias*\n\nSelecione para editar ou crie uma nova:",
        parse_mode="Markdown",
        reply_markup=teclado_cat_lista(cats)
    )


async def _exibir_prod_cat(update: Update, u: dict):
    cats = await db.listar_categorias()
    if not cats:
        u["estado"] = "admin_registrar_menu"
        await update.message.reply_text(
            "⚠️ Nenhuma categoria cadastrada. Crie uma categoria primeiro.",
            reply_markup=teclado_registrar_menu()
        )
        return
    u["estado"] = "admin_prod_cat"
    await update.message.reply_text(
        "🛍️ *Produtos*\n\nSelecione a categoria:",
        parse_mode="Markdown",
        reply_markup=teclado_prod_cat(cats)
    )


async def _exibir_prod_lista(update: Update, u: dict):
    nome_cat    = u.get("admin_cat_atual")
    produtos    = await db.listar_produtos_por_categoria(nome_cat)
    u["estado"] = "admin_prod_lista"
    await update.message.reply_text(
        f"🛍️ *Produtos em {nome_cat}*\n\nSelecione para editar ou adicione um novo:",
        parse_mode="Markdown",
        reply_markup=teclado_prod_lista(produtos)
    )
