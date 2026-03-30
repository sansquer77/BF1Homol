# BF1 — Bolão de Fórmula 1

Aplicativo web de gerenciamento de bolão da Fórmula 1, construído com **Streamlit** e **PostgreSQL**.

> **Repositório de Homologação** — branch principal espelha a versão de produção, mas está apontando para banco/infra de staging.

---

## Funcionalidades

- Apostas por prova (pilotos, fichas, piloto 11º)
- Aposta de campeonato (campeão, vice, equipe)
- Cálculo automático de pontos e penalidades
- Hall da Fama por temporada
- Painel administrativo (gestores e master)
- Gestão de pilotos, provas, circuitos e regras
- Autenticação JWT com bcrypt, rate limiting e recuperação de senha
- Logs de acesso e auditoria de apostas

---

## Arquitetura

```
bf1/
├── main.py                 # Entrypoint Streamlit, roteamento e guards de perfil
├── ui/                     # Views Streamlit (uma por página/feature)
├── services/               # Lógica de negócio desacoplada da UI
│   ├── auth_service.py     # Autenticação, JWT, cookies
│   ├── bets_service.py     # Apostas de prova
│   ├── championship_service.py
│   ├── email_service.py
│   └── rules_service.py
├── db/
│   ├── connection_pool.py  # Pool psycopg + adaptador de cursor compatível sqlite3
│   ├── db_utils.py         # CRUD genérico, hash, helpers de schema
│   ├── migrations.py       # Migrations idempotentes (ADD COLUMN IF NOT EXISTS)
│   ├── db_config.py        # Constantes, índices, TTLs de cache
│   └── rules_utils.py
├── utils/                  # Helpers genéricos (data, validação, input models)
├── assets/                 # Imagens e recursos estáticos
├── requirements.txt
└── .env.example
```

**Fluxo de dados:** `UI → Service → db_utils/db_connect → ConnectionPool → PostgreSQL`

O `ConnectionPool` usa `psycopg_pool.ConnectionPool` cacheado via `@st.cache_resource`.

---

## Pré-requisitos

- Python 3.11+
- PostgreSQL 14+ (ou managed database no Digital Ocean)
- `pip install -r requirements.txt`

---

## Configuração

Copie `.env.example` para `.env` e preencha os valores:

```bash
cp .env.example .env
```

### Variáveis de ambiente obrigatórias

| Variável | Descrição | Exemplo |
|---|---|---|
| `DATABASE_URL` | URL completa do PostgreSQL com SSL | `postgresql://user:pass@host:5432/db?sslmode=require` |
| `JWT_SECRET` | Segredo HS256 (mín. 32 bytes) — **nunca** commitado | `openssl rand -hex 32` |
| `USUARIO_MASTER` | Nome do usuário master inicial | `Admin` |
| `EMAIL_MASTER` | Email do usuário master inicial | `admin@dominio.com` |
| `SENHA_MASTER` | Senha inicial do master | (forte, min 12 chars) |

### Variáveis opcionais de tuning

| Variável | Padrão | Descrição |
|---|---|---|
| `DB_POOL_SIZE` | `5` | Tamanho do pool de conexões |
| `DB_MIN_CONN` | `1` | Conexões mínimas no pool |
| `DB_MAX_CONN` | `10` | Conexões máximas no pool |
| `DB_TIMEOUT` | `30` | Timeout para obter conexão (segundos) |
| `DB_CONN_MAX_LIFETIME` | `1800` | Tempo máximo de vida de uma conexão (segundos) |
| `BCRYPT_ROUNDS` | `12` | Rounds do bcrypt para hash de senha |
| `MAX_LOGIN_ATTEMPTS` | `5` | Tentativas antes do lockout |
| `LOCKOUT_DURATION` | `900` | Duração do lockout em segundos (15min) |
| `PRODUCTION` | `false` | Seta modo produção (obriga JWT_SECRET válido) |

---

## Executando localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Exportar variáveis (ou usar arquivo .env com python-dotenv)
export DATABASE_URL="postgresql://..."
export JWT_SECRET="seu-segredo-aqui"

# Iniciar a aplicação
streamlit run main.py
```

O banco é inicializado automaticamente na primeira execução via `bootstrap_app()` em `main.py`.

---

## Perfis de usuário

| Perfil | Permissões |
|---|---|
| `master` | Acesso total, cria admins, configura sistema |
| `admin` | Gerencia provas, pilotos, resultados, regras |
| `participante` | Realiza apostas, visualiza resultados e ranking |

---

## Deployment (Digital Ocean App Platform)

1. Conecte o repositório ao App Platform
2. Configure as variáveis de ambiente obrigatórias em **App Settings > Environment Variables**
3. O `run command` deve ser: `streamlit run main.py --server.port $PORT --server.address 0.0.0.0`
4. Use um **Managed PostgreSQL** do Digital Ocean como banco de dados

---

## Segurança

- Senhas hasheadas com **bcrypt** (12 rounds)
- Autenticação stateless via **JWT HS256** (expira em 120 min)
- Rate limiting: 5 tentativas de login antes do lockout de 15 minutos
- Tokens de reset armazenados como **hash SHA-256** (nunca em plaintext)
- Cookies com `secure=True`, `httponly=True`, `samesite=Lax`
- Guards de rota por perfil em `main.py` (`ROLE_GUARDS`)
- `JWT_SECRET` ausente causa `RuntimeError` imediato no startup
