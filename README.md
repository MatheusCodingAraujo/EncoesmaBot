# BOT Gestão

Bot Telegram interno para gestão de funcionários, pedidos, ponto e obras.

## Funcionalidades

| Módulo | Permissão necessária | Descrição |
|---|---|---|
| Fazer Pedido | `fazer_pedido` | Fluxo categoria → produto → quantidade → revisão. Suporta item livre "🔤 Outros" |
| Bater Ponto | `bater_ponto` | Registro de entrada/saída com localização GPS |
| Entregar Trabalho | `entregar_trabalho` | Seleciona obra → envia fotos → álbum enviado ao grupo |
| Painel Admin | `admin` | Gerencia funcionários, obras e visualiza relatórios de ponto |

O menu principal é dinâmico: cada funcionário vê apenas os botões para os quais tem permissão. Novos usuários ficam em `aguardando_aprovacao` até um admin liberar acesso.

## Configuração

### 1. Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
BOT_TOKEN=seu_token_do_botfather

DATABASE_URL=postgresql://usuario:senha@host:porta/banco

GROUP_PEDIDOS_ID=-100xxxxxxxxxx
GROUP_PONTO_ID=-100xxxxxxxxxx
GROUP_TRABALHO_ID=-100xxxxxxxxxx
```

- **`BOT_TOKEN`** — obtido via [@BotFather](https://t.me/BotFather)
- **`DATABASE_URL`** — string de conexão PostgreSQL (Supabase ou outro)
- **`GROUP_PEDIDOS_ID`** — grupo que recebe novos pedidos finalizados
- **`GROUP_PONTO_ID`** — grupo que recebe os registros de ponto
- **`GROUP_TRABALHO_ID`** — grupo que recebe os álbuns de fotos de obra

### 2. Dependências

```bash
pip install -r requirements.txt
```

Pacotes: `python-telegram-bot==22.7`, `asyncpg==0.31.0`, `python-dotenv==1.0.1`

### 3. Executar

```bash
python main_bot.py
```

As tabelas são criadas automaticamente no banco ao iniciar, se não existirem.

## Estrutura

```
main_bot.py               # Entry point; roteador de estados e handlers
admin_bot.py              # Painel admin: funcionários, obras, relatórios
obra_bot.py               # CRUD de obras e histórico de status
relatorio_ponto_bot.py    # Relatório de ponto por funcionário e período
fazer_pedido_bot.py       # Fluxo de pedidos
bater_ponto_bot.py        # Registro de ponto com GPS
entregar_trabalho_bot.py  # Entrega de fotos por obra
database.py               # Todas as funções de banco (asyncpg)
estado.py                 # Estado em memória por usuário
```

### Roteamento de estados

```
handle_text()
├── "menu"              → roteia pelo botão pressionado
├── "pedido_*"          → fazer_pedido_bot
├── "ponto_*"           → bater_ponto_bot
├── "trabalho_*"        → entregar_trabalho_bot
└── "admin_*"           → admin_bot
      ├── "admin_obra_*"      → obra_bot
      └── "admin_relatorio_*" → relatorio_ponto_bot

handle_photo()          → entregar_trabalho_bot
handle_location()       → bater_ponto_bot
```

## Banco de dados

PostgreSQL via Supabase. Tabelas principais:

| Tabela | Descrição |
|---|---|
| `funcionarios` | Telegram ID, nome, flags de permissão |
| `categorias` / `produtos` | Catálogo de pedidos |
| `pedidos` / `itens_pedido` | Pedidos com suporte a item livre (`item_especial`) |
| `pontos` | Batidas de ponto com horário e coordenadas GPS |
| `obras` / `status_obras` | Obras com histórico de status; `concluida=TRUE` oculta da listagem |
| `fotos_trabalho` | `file_id` do Telegram associado à obra e ao funcionário |

## Build (executável Windows)

O projeto inclui `BOT_Gestao.spec` para gerar um `.exe` com PyInstaller:

```bat
build.bat
```

O executável gerado fica em `dist/`.
