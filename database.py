import os
import asyncpg
from datetime import date, time

pool: asyncpg.Pool = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), ssl="require")
    await _criar_tabelas()


async def _criar_tabelas():
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS funcionarios (
                id                SERIAL PRIMARY KEY,
                telegram_id       BIGINT UNIQUE NOT NULL,
                nome              TEXT,
                username          TEXT,
                admin             BOOLEAN DEFAULT FALSE,
                fazer_pedido      BOOLEAN DEFAULT FALSE,
                bater_ponto       BOOLEAN DEFAULT FALSE,
                entregar_trabalho BOOLEAN DEFAULT FALSE,
                criado_em         TIMESTAMP DEFAULT NOW()
            );

            ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS admin             BOOLEAN DEFAULT FALSE;
            ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS fazer_pedido      BOOLEAN DEFAULT FALSE;
            ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS bater_ponto       BOOLEAN DEFAULT FALSE;
            ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS entregar_trabalho BOOLEAN DEFAULT FALSE;

            CREATE TABLE IF NOT EXISTS categorias (
                id   SERIAL PRIMARY KEY,
                nome TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS produtos (
                id           SERIAL PRIMARY KEY,
                categoria_id INT REFERENCES categorias(id),
                nome         TEXT NOT NULL,
                UNIQUE(categoria_id, nome)
            );

            CREATE TABLE IF NOT EXISTS fotos_trabalho (
                id             SERIAL PRIMARY KEY,
                funcionario_id INT REFERENCES funcionarios(id),
                obra_id        INT REFERENCES obras(id) ON DELETE SET NULL,
                file_id        TEXT NOT NULL,
                enviado_em     TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS obras (
                id        SERIAL PRIMARY KEY,
                nome      TEXT NOT NULL,
                endereco  TEXT,
                concluida BOOLEAN DEFAULT FALSE,
                criado_em TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS status_obras (
                id        SERIAL PRIMARY KEY,
                obra_id   INT REFERENCES obras(id) ON DELETE CASCADE,
                texto     TEXT NOT NULL,
                criado_em TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS pedidos (
                id             SERIAL PRIMARY KEY,
                funcionario_id INT REFERENCES funcionarios(id),
                criado_em      TIMESTAMP DEFAULT NOW(),
                status         TEXT DEFAULT 'confirmado'
            );

            CREATE TABLE IF NOT EXISTS itens_pedido (
                id           SERIAL PRIMARY KEY,
                pedido_id    INT REFERENCES pedidos(id),
                produto      TEXT NOT NULL,
                quantidade   INT NOT NULL,
                item_especial TEXT
            );

            ALTER TABLE itens_pedido ADD COLUMN IF NOT EXISTS item_especial TEXT;

        """)
        # Recria pontos com estrutura de uma linha por batida
        await conn.execute("""
            DROP TABLE IF EXISTS pontos;
            CREATE TABLE IF NOT EXISTS pontos (
                id               SERIAL PRIMARY KEY,
                funcionario_id   INT REFERENCES funcionarios(id),
                data             DATE NOT NULL,
                categoria        TEXT NOT NULL,
                horario          TIME NOT NULL,
                lat              FLOAT,
                lon              FLOAT,
                group_message_id BIGINT,
                UNIQUE(funcionario_id, data, categoria)
            );
        """)


# ── Funcionários ──────────────────────────────────────────────────────────────

async def get_funcionario(telegram_id: int) -> asyncpg.Record | None:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM funcionarios WHERE telegram_id=$1", telegram_id
        )


async def criar_solicitacao(telegram_id: int, nome: str, username: str | None):
    """Cria registro com todas as permissões falsas — aguarda aprovação do admin."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO funcionarios (telegram_id, nome, username)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO NOTHING
        """, telegram_id, nome, username)


async def upsert_funcionario(telegram_id: int, nome: str, username: str | None):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO funcionarios (telegram_id, nome, username)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO UPDATE SET nome=$2, username=$3
        """, telegram_id, nome, username)


async def get_funcionario_id(telegram_id: int) -> int | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM funcionarios WHERE telegram_id=$1", telegram_id
        )
        return row["id"] if row else None


# ── Admin ─────────────────────────────────────────────────────────────────────

CAMPOS_PERMISSAO = ("bater_ponto", "fazer_pedido", "entregar_trabalho", "admin")


async def listar_funcionarios() -> list:
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM funcionarios ORDER BY nome")


async def toggle_permissao(telegram_id: int, campo: str):
    if campo not in CAMPOS_PERMISSAO:
        return
    async with pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE funcionarios SET {campo} = NOT {campo} WHERE telegram_id=$1
        """, telegram_id)


async def remover_funcionario(telegram_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM funcionarios WHERE telegram_id=$1", telegram_id)


# ── Catálogo ──────────────────────────────────────────────────────────────────

async def listar_categorias() -> list[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT nome FROM categorias ORDER BY nome")
        return [r["nome"] for r in rows]


async def listar_produtos_por_categoria(categoria: str) -> list[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.nome FROM produtos p
            JOIN categorias c ON c.id = p.categoria_id
            WHERE c.nome = $1
            ORDER BY p.nome
        """, categoria)
        return [r["nome"] for r in rows]


async def criar_categoria(nome: str) -> bool:
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT id FROM categorias WHERE nome=$1", nome)
        if existing:
            return False
        await conn.execute("INSERT INTO categorias (nome) VALUES ($1)", nome)
        return True


async def renomear_categoria(nome_antigo: str, nome_novo: str) -> bool:
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT id FROM categorias WHERE nome=$1", nome_novo)
        if existing:
            return False
        await conn.execute("UPDATE categorias SET nome=$1 WHERE nome=$2", nome_novo, nome_antigo)
        return True


async def remover_categoria(nome: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM produtos WHERE categoria_id=(SELECT id FROM categorias WHERE nome=$1)
        """, nome)
        await conn.execute("DELETE FROM categorias WHERE nome=$1", nome)


async def criar_produto(categoria: str, nome: str) -> bool:
    async with pool.acquire() as conn:
        cat_id = await conn.fetchval("SELECT id FROM categorias WHERE nome=$1", categoria)
        if not cat_id:
            return False
        existing = await conn.fetchval(
            "SELECT id FROM produtos WHERE categoria_id=$1 AND nome=$2", cat_id, nome
        )
        if existing:
            return False
        await conn.execute("INSERT INTO produtos (categoria_id, nome) VALUES ($1, $2)", cat_id, nome)
        return True


async def renomear_produto(categoria: str, nome_antigo: str, nome_novo: str) -> bool:
    async with pool.acquire() as conn:
        cat_id = await conn.fetchval("SELECT id FROM categorias WHERE nome=$1", categoria)
        existing = await conn.fetchval(
            "SELECT id FROM produtos WHERE categoria_id=$1 AND nome=$2", cat_id, nome_novo
        )
        if existing:
            return False
        await conn.execute(
            "UPDATE produtos SET nome=$1 WHERE categoria_id=$2 AND nome=$3", nome_novo, cat_id, nome_antigo
        )
        return True


async def remover_produto(categoria: str, nome: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM produtos WHERE nome=$1 AND categoria_id=(SELECT id FROM categorias WHERE nome=$2)
        """, nome, categoria)


async def sincronizar_produtos(dados: list[tuple[str, str]]):
    async with pool.acquire() as conn:
        for categoria, produto in dados:
            cat_id = await conn.fetchval("""
                INSERT INTO categorias (nome) VALUES ($1)
                ON CONFLICT (nome) DO UPDATE SET nome=$1
                RETURNING id
            """, categoria)
            await conn.execute("""
                INSERT INTO produtos (categoria_id, nome) VALUES ($1, $2)
                ON CONFLICT (categoria_id, nome) DO NOTHING
            """, cat_id, produto)


# ── Fotos de Trabalho ─────────────────────────────────────────────────────────

async def salvar_foto_trabalho(funcionario_id: int, obra_id: int, file_id: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO fotos_trabalho (funcionario_id, obra_id, file_id) VALUES ($1, $2, $3)
        """, funcionario_id, obra_id, file_id)


# ── Obras ─────────────────────────────────────────────────────────────────────

async def listar_obras_ativas() -> list:
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM obras WHERE concluida = FALSE ORDER BY nome")


async def get_obra(obra_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM obras WHERE id = $1", obra_id)


async def criar_obra(nome: str, endereco: str) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO obras (nome, endereco) VALUES ($1, $2) RETURNING id",
            nome, endereco
        )


async def editar_obra_nome(obra_id: int, nome: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE obras SET nome = $1 WHERE id = $2", nome, obra_id)


async def editar_obra_endereco(obra_id: int, endereco: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE obras SET endereco = $1 WHERE id = $2", endereco, obra_id)


async def excluir_obra(obra_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM obras WHERE id = $1", obra_id)


async def listar_status_obra(obra_id: int) -> list:
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM status_obras WHERE obra_id = $1 ORDER BY criado_em",
            obra_id
        )


async def get_status_obra(status_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM status_obras WHERE id = $1", status_id)


async def criar_status_obra(obra_id: int, texto: str, concluir: bool = False) -> int:
    async with pool.acquire() as conn:
        status_id = await conn.fetchval(
            "INSERT INTO status_obras (obra_id, texto) VALUES ($1, $2) RETURNING id",
            obra_id, texto
        )
        if concluir:
            await conn.execute("UPDATE obras SET concluida = TRUE WHERE id = $1", obra_id)
        return status_id


async def editar_status_obra(status_id: int, texto: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE status_obras SET texto = $1 WHERE id = $2", texto, status_id)


async def excluir_status_obra(status_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM status_obras WHERE id = $1", status_id)


# ── Pedidos ───────────────────────────────────────────────────────────────────

async def salvar_pedido(funcionario_id: int, itens: list[dict]) -> int:
    async with pool.acquire() as conn:
        pedido_id = await conn.fetchval("""
            INSERT INTO pedidos (funcionario_id) VALUES ($1) RETURNING id
        """, funcionario_id)
        await conn.executemany("""
            INSERT INTO itens_pedido (pedido_id, produto, quantidade, item_especial) VALUES ($1, $2, $3, $4)
        """, [(pedido_id, item["nome"], item["quantidade"], item.get("especial")) for item in itens])
        return pedido_id


# ── Ponto ─────────────────────────────────────────────────────────────────────

CATEGORIAS_PONTO = ("entrada", "saida_almoco", "volta_almoco", "fim_expediente")


async def get_pontos_hoje(funcionario_id: int) -> dict:
    """Retorna dict {categoria: record} com as batidas de hoje."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM pontos WHERE funcionario_id=$1 AND data=$2",
            funcionario_id, date.today()
        )
        return {r["categoria"]: r for r in rows}


async def registrar_ponto(funcionario_id: int, categoria: str, horario: time, lat: float, lon: float):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO pontos (funcionario_id, data, categoria, horario, lat, lon)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (funcionario_id, data, categoria)
            DO UPDATE SET horario=$4, lat=$5, lon=$6
        """, funcionario_id, date.today(), categoria, horario, lat, lon)


async def get_group_message_id(funcionario_id: int) -> int | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT group_message_id FROM pontos
            WHERE funcionario_id=$1 AND data=$2 AND group_message_id IS NOT NULL
            LIMIT 1
        """, funcionario_id, date.today())
        return row["group_message_id"] if row else None


async def salvar_group_message_id(funcionario_id: int, message_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE pontos SET group_message_id=$3
            WHERE funcionario_id=$1 AND data=$2 AND categoria='entrada'
        """, funcionario_id, date.today(), message_id)
