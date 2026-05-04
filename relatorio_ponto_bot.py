from datetime import datetime, date, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes
from estado import get_usuario
import database as db

CANCELAR = "❌ Cancelar"

PERIODOS = {
    "📅 7 dias":  7,
    "📅 15 dias": 15,
    "📅 30 dias": 30,
}

TIPOS_PONTO = {
    "entrada":        "🟢",
    "saida_almoco":   "🍽️",
    "volta_almoco":   "🔄",
    "fim_expediente": "🔴",
}

DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


# ── Teclados ──────────────────────────────────────────────────────────────────

def teclado_funcionarios(func_map: dict) -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(nome)] for nome in func_map]
    linhas.append([KeyboardButton(CANCELAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


def teclado_periodos() -> ReplyKeyboardMarkup:
    linhas = [[KeyboardButton(p)] for p in PERIODOS]
    linhas.append([KeyboardButton(CANCELAR)])
    return ReplyKeyboardMarkup(linhas, resize_keyboard=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _construir_func_map(funcionarios: list) -> dict:
    func_map = {}
    for f in funcionarios:
        label = f["nome"] or f"ID {f['id']}"
        if label in func_map:
            label = f"{f['nome']} (#{f['id']})"
        func_map[label] = f["id"]
    return func_map


def _cancelar(u: dict):
    u["estado"]              = "menu"
    u["relatorio_func_id"]   = None
    u["relatorio_func_nome"] = None
    u["relatorio_dias"]      = None


def _gerar_relatorio(nome: str, data_inicio: date, data_fim: date, pontos: list, dias: int) -> str:
    pontos_por_dia: dict[date, dict] = {}
    for p in pontos:
        d = p["data"]
        if d not in pontos_por_dia:
            pontos_por_dia[d] = {}
        pontos_por_dia[d][p["categoria"]] = p

    linhas = [
        f"📋 *Relatório de Ponto*",
        f"👤 {nome}",
        f"📅 {data_inicio.strftime('%d/%m/%Y')} → {data_fim.strftime('%d/%m/%Y')} ({dias} dias)\n",
    ]

    dias_com_registro = 0
    d = data_inicio
    while d <= data_fim:
        dia_semana = DIAS_SEMANA[d.weekday()]
        dia_pontos = pontos_por_dia.get(d, {})
        data_label = f"{d.strftime('%d/%m')} {dia_semana}"

        if dia_pontos:
            dias_com_registro += 1
            partes = []
            for cat, emoji in TIPOS_PONTO.items():
                if cat in dia_pontos:
                    p       = dia_pontos[cat]
                    horario = str(p["horario"])[:5]
                    lat     = p["lat"]
                    lon     = p["lon"]
                    if lat and lon:
                        url    = f"https://maps.google.com/?q={lat},{lon}"
                        partes.append(f"{emoji}[{horario}]({url})")
                    else:
                        partes.append(f"{emoji}{horario}")
            linhas.append(f"`{data_label}:` {' '.join(partes)}")
        else:
            linhas.append(f"`{data_label}:` — sem registro")

        d += timedelta(days=1)

    linhas.append(f"\n✅ Dias com registro: *{dias_com_registro}/{dias}*")
    return "\n".join(linhas)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u            = get_usuario(update.effective_user.id)
    funcionarios = await db.listar_funcionarios()

    if not funcionarios:
        await update.message.reply_text(
            "⚠️ Nenhum funcionário cadastrado.",
            reply_markup=ReplyKeyboardRemove()
        )
        u["estado"] = "menu"
        return

    func_map                = _construir_func_map(funcionarios)
    u["relatorio_func_map"] = func_map
    u["estado"]             = "admin_relatorio_func"

    await update.message.reply_text(
        "📋 *Relatório de Pontos*\n\nSelecione o funcionário:",
        parse_mode="Markdown",
        reply_markup=teclado_funcionarios(func_map)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto   = update.message.text.strip()
    u       = get_usuario(user_id)
    estado  = u["estado"]

    if texto == CANCELAR:
        _cancelar(u)
        await update.message.reply_text("Operação cancelada.", reply_markup=ReplyKeyboardRemove())
        return

    # ── Seleção de funcionário ──
    if estado == "admin_relatorio_func":
        func_map = u.get("relatorio_func_map", {})
        if texto not in func_map:
            await update.message.reply_text(
                "Selecione um funcionário da lista.",
                reply_markup=teclado_funcionarios(func_map)
            )
            return

        u["relatorio_func_id"]   = func_map[texto]
        u["relatorio_func_nome"] = texto
        u["estado"]              = "admin_relatorio_periodo"

        await update.message.reply_text(
            f"👤 *{texto}*\n\nSelecione o período do relatório:",
            parse_mode="Markdown",
            reply_markup=teclado_periodos()
        )
        return

    # ── Seleção de período ──
    if estado == "admin_relatorio_periodo":
        if texto not in PERIODOS:
            await update.message.reply_text(
                "Selecione um período da lista.",
                reply_markup=teclado_periodos()
            )
            return

        u["relatorio_dias"] = PERIODOS[texto]
        u["estado"]         = "admin_relatorio_data"

        await update.message.reply_text(
            "📅 Informe a *data de início* no formato DD/MM/AAAA:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # ── Data de início ──
    if estado == "admin_relatorio_data":
        try:
            data_inicio = datetime.strptime(texto, "%d/%m/%Y").date()
        except ValueError:
            await update.message.reply_text("❌ Data inválida. Use o formato DD/MM/AAAA:")
            return

        dias      = u.get("relatorio_dias", 7)
        data_fim  = data_inicio + timedelta(days=dias - 1)
        func_id   = u.get("relatorio_func_id")
        func_nome = u.get("relatorio_func_nome", "")

        pontos    = await db.get_pontos_por_periodo(func_id, data_inicio, data_fim)
        relatorio = _gerar_relatorio(func_nome, data_inicio, data_fim, pontos, dias)

        await update.message.reply_text(relatorio, parse_mode="Markdown")
        _cancelar(u)
