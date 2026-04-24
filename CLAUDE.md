# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Executar o bot

```bash
cd /mnt/c/Users/mathe/OneDrive/Documentos/estudos/BOT
python main_bot.py
```

Requer o `.env` com `BOT_TOKEN`, `DATABASE_URL`, `GROUP_PEDIDOS_ID`, `GROUP_PONTO_ID` e `GROUP_TRABALHO_ID`.

## Arquitetura

Bot Telegram assíncrono com máquina de estados por usuário. O estado de cada usuário é mantido em memória (`estado.py`) e roteado em `main_bot.py` por prefixo de string.

### Roteamento de estados (`main_bot.py`)

```
handle_text()
├── "menu"         → roteia pelo texto do botão pressionado
├── "pedido_*"     → fazer_pedido_bot.handle_message()
├── "ponto_*"      → bater_ponto_bot.handle_message()
├── "trabalho_*"   → entregar_trabalho_bot.handle_message()
└── "admin_*"      → admin_bot.handle_message()
                        └── "admin_obra_*" → obra_bot.handle_message()

handle_photo()     → entregar_trabalho_bot.handle_photo()
handle_location()  → bater_ponto_bot.handle_location()
```

Cada sub-bot sinaliza retorno ao menu principal setando `u["estado"] = "menu"`. O `main_bot` detecta isso e chama `exibir_menu()`.

### Sub-bots

| Arquivo | Estados | Responsabilidade |
|---|---|---|
| `fazer_pedido_bot.py` | `pedido_*` | Fluxo de pedido: categoria → produto → quantidade → revisão. Suporta "🔤 Outros" (item especial com ⚠️ no grupo) |
| `bater_ponto_bot.py` | `ponto_*` | Registro de ponto com localização GPS. Edita mensagem existente no grupo |
| `entregar_trabalho_bot.py` | `trabalho_*` | Seleciona obra → recebe múltiplas fotos → envia álbum ao grupo com nome e horário |
| `admin_bot.py` | `admin_*` | Gerencia funcionários e permissões; delega `admin_obra_*` para `obra_bot` |
| `obra_bot.py` | `admin_obra_*` | CRUD de obras e histórico de status. "✅ Concluir obra" marca `concluida=TRUE` e some da lista |

### Banco de dados (`database.py`)

PostgreSQL via Supabase. Todas as funções são `async` com `asyncpg`. As tabelas são criadas em `_criar_tabelas()` no startup.

Tabelas principais:
- `funcionarios` — permissões por flag booleana (`admin`, `fazer_pedido`, `bater_ponto`, `entregar_trabalho`)
- `categorias` / `produtos` — catálogo. Produto tem `UNIQUE(categoria_id, nome)`
- `itens_pedido` — tem coluna `item_especial TEXT` para pedidos livres ("Outros")
- `obras` / `status_obras` — obras com histórico de status. `concluida=TRUE` remove da listagem
- `fotos_trabalho` — `file_id` do Telegram + `obra_id` + `funcionario_id` + `enviado_em`
- `pontos` — `UNIQUE(funcionario_id, data, categoria)` — uma batida por tipo por dia

### Grupos de notificação

| Variável | Uso |
|---|---|
| `GROUP_PEDIDOS_ID` | Novos pedidos finalizados |
| `GROUP_PONTO_ID` | Registro de ponto (mensagem editável) |
| `GROUP_TRABALHO_ID` | Álbum de fotos ao concluir entrega de trabalho |

### Padrão de teclados

Cada estado tem sua função `teclado_*()` que retorna `ReplyKeyboardMarkup`. Botões de ação usam constantes de string definidas no topo de cada arquivo para facilitar comparação no handler.

### Permissões de acesso

O menu principal (`teclado_menu()`) é dinâmico: só exibe botões para permissões `TRUE` do funcionário. Novos usuários ficam em `aguardando_aprovacao` até um admin liberar permissões via toggle.
