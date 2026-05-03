---
tags: [bf1, sdd, arquitetura]
status: produção
versao: 3.6
data_revisao: 2026-05-03
---

# Arquitetura do Sistema — BF1

> [!info] Navegação SDD
> - Visão geral: [[01_necessidade]]
> - Regras: [[02_regras_de_negocio]]
> - Especificação: [[03_spec]]
> - Módulos: [[MAPA_MENTAL_MODULOS]]

## Visão Geral

O BF1 é uma aplicação web **monolítica stateless** construída com **Streamlit**, conectada a um banco **PostgreSQL** gerenciado, e hospedada na **DigitalOcean App Platform**. A arquitetura é baseada em camadas com separação clara de responsabilidades.

---

## Diagrama de Camadas

```
┌─────────────────────────────────────────────────────────┐
│                  BROWSER / PWA (Cliente)                │
│           Streamlit Frontend + CSS Liquid Glass         │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTPS
┌───────────────────────▼─────────────────────────────────┐
│          DigitalOcean App Platform (Container)          │
│  ┌──────────────────────────────────────────────────┐   │
│  │                  main.py                         │   │
│  │  Router + Session Manager + Auth Guard + Menu    │   │
│  ├──────────────┬───────────────────────────────────┤   │
│  │   UI Layer   │         Services Layer            │   │
│  │  (ui/*.py)   │        (services/*.py)            │   │
│  │              │                                   │   │
│  │  - Views     │  - Auth (JWT/bcrypt)              │   │
│  │  - Forms     │  - Bets Rules & Scoring           │   │
│  │  - Charts    │  - Bets AI (auto)                 │   │
│  │  - Tables    │  - Championship                   │   │
│  │              │  - Results                        │   │
│  │              │  - historico_service (v3.6)       │   │
│  │              │  - Email                          │   │
│  ├──────────────┴───────────────────────────────────┤   │
│  │              Data Access Layer                   │   │
│  │         (services/data_access_*.py)              │   │
│  ├──────────────────────────────────────────────────┤   │
│  │              Database Layer                      │   │
│  │  (db/*.py) — Pool, Repos, Migrations, Backup     │   │
│  └──────────────────────────┬───────────────────────┘   │
│                             │                           │
└─────────────────────────────┼───────────────────────────┘
                              │ PostgreSQL Protocol
┌─────────────────────────────▼───────────────────────────┐
│         DigitalOcean Managed PostgreSQL                 │
│  Tables: usuarios, pilotos, provas, apostas,            │
│          resultados, posicoes_participantes,            │
│          regras, logs, championship_*                   │
└─────────────────────────────────────────────────────────┘
```

---

## Estrutura de Diretórios

```
3.6/
├── main.py                    # Entry point: router, menu, auth guard
├── requirements.txt           # Dependências Python
├── assets/
│   └── styles.css             # Tema Liquid Glass (CSS customizado)
├── static/
│   ├── favicon.ico
│   ├── apple-touch-icon.png
│   ├── icon-192.png
│   ├── icon-512.png
│   └── manifest.json          # Configuração PWA
├── ui/                        # Camada de interface (views Streamlit)
│   ├── login.py
│   ├── painel.py              # Inclui aba "Histórico" (v3.6)
│   ├── gestao_apostas.py
│   ├── classificacao.py
│   └── ... (19 módulos)
├── services/                  # Camada de negócio e acesso a dados
│   ├── auth_service.py
│   ├── bets_rules.py
│   ├── bets_scoring.py
│   ├── bets_ai.py
│   ├── historico_service.py   # Histórico consolidado (v3.6)
│   ├── data_access_*.py
│   └── ... (18 módulos)
├── db/                        # Camada de banco de dados
│   ├── connection_pool.py
│   ├── db_config.py
│   ├── db_schema.py
│   ├── migrations.py
│   ├── repo_*.py
│   └── backup_*.py
├── utils/                     # Utilitários transversais
│   ├── datetime_utils.py
│   ├── validators.py
│   └── ...
└── docs/                      # Documentação SDD (este diretório)
    ├── 01_necessidade.md
    ├── 02_regras_de_negocio.md
    ├── 03_spec.md
    ├── 04_arquitetura.md      # Este arquivo
    ├── 05_projeto.md
    └── MAPA_MENTAL_MODULOS.md
```

---

## Modelo de Dados

```
usuarios
  id, nome, email, senha_hash, perfil, status,
  must_change_password, faltas, criado_em

pilotos
  id, nome, equipe, status, numero

provas
  id, nome, data, horario_prova, tipo, status, temporada

apostas
  id, usuario_id → usuarios, prova_id → provas,
  data_envio, pilotos (csv), fichas (csv),
  piloto_11, nome_prova, automatica, temporada

resultados
  prova_id → provas,
  posicoes (json — chaves SEMPRE normalizadas para int ao ler),
  abandono_pilotos

posicoes_participantes
  id, prova_id → provas, usuario_id → usuarios,
  posicao, pontos, temporada

regras
  id, temporada, tipo_prova, qtd_minima_pilotos,
  quantidade_fichas, fichas_por_piloto, mesma_equipe,
  pontos_11_colocado, penalidade_abandono, pontos_penalidade,
  pontos_dobrada, pontos_posicoes (json), pontos_sprint_posicoes (json)
  UNIQUE(temporada, tipo_prova)
```

> [!warning] Normalização de chaves em `posicoes`
> O campo `posicoes` do resultado pode ter chaves `int` ou `str` dependendo da inserção.
> **Sempre** usar `_parse_posicoes()` de `historico_service.py` (ou equivalente) para normalizar para `int` antes de qualquer lookup de posição (ex.: detecção do 11º colocado).

---

## Decisões Arquiteturais

### 1. Streamlit como Framework Full-Stack
- **Decisão**: usar Streamlit em vez de Flask/FastAPI + frontend separado.
- **Justificativa**: equipe pequena, ciclo de desenvolvimento rápido, interface adequada para dashboards e formulários.
- **Trade-off**: limitações de UX avançado são contornadas com CSS customizado (Liquid Glass) e injeção de JavaScript via `st.markdown(unsafe_allow_html=True)`.

### 2. Stateless com JWT + Cookies
- **Decisão**: autenticação via JWT persistido em cookie HttpOnly.
- **Justificativa**: a App Platform da DigitalOcean pode escalar horizontalmente (múltiplas instâncias); sessão não pode depender de estado em memória.
- **Implementação**: `session_state` do Streamlit é rehidratado a partir do cookie a cada rerun.

### 3. Pool de Conexões PostgreSQL
- **Decisão**: `connection_pool.py` gerencia um pool de conexões com `psycopg2`.
- **Justificativa**: Streamlit rerenderiza o script inteiro a cada interação; sem pool, cada interação abriria uma nova conexão ao banco.

### 4. Migrations Incrementais e Idempotentes
- **Decisão**: `migrations.py` executa DDL incremental no bootstrap da aplicação.
- **Justificativa**: simplifica deploy — não requer ferramenta externa (Alembic, Flyway).
- **Risco mitigado**: todas as migrations verificam a existência da coluna/tabela antes de aplicar.

### 5. Separação em Camadas
- `ui/` → apenas renderização Streamlit, sem lógica de negócio.
- `services/` → toda lógica de negócio e scoring.
- `db/` → acesso a dados, sem lógica de negócio.
- `utils/` → funções puras e transversais (sem dependência de DB ou UI).

### 6. Fuso Horário São Paulo como Padrão
- Todas as comparações de data/hora usam `America/Sao_Paulo` via `zoneinfo`.
- `now_sao_paulo()` é a função canônica para obter o tempo atual.

### 7. Serviços sem Dependência de UI *(v3.6)*
- **Decisão**: `historico_service.py` retorna `@dataclass` tipados, sem importar Streamlit.
- **Justificativa**: garante testabilidade isolada da lógica de negócio do histórico, independente do ciclo de rerun do Streamlit.

---

## Infraestrutura (DigitalOcean)

| Componente            | Serviço DO | Observações |
|-----------------------|---------------------------------|------------------------------------------|
| Aplicação             | App Platform (Web Service)      | Container gerenciado, deploy via GitHub  |
| Banco de Dados        | Managed PostgreSQL              | Backups automáticos, SSL obrigatório     |
| Variáveis de Ambiente | App Platform Env Vars           | `DATABASE_URL`, `SECRET_KEY`, `MASTER_*` |
| CI/CD                 | Auto-deploy no push para `main` | Sem pipeline adicional necessário        |

### Variáveis de Ambiente Obrigatórias

```
DATABASE_URL        # Connection string PostgreSQL
SECRET_KEY          # Chave de assinatura JWT
MASTER_EMAIL        # Email do usuário master inicial
MASTER_PASSWORD     # Senha do usuário master inicial
MASTER_NOME         # Nome do usuário master inicial
```

---

## Segurança

- **Senhas**: bcrypt com salt automático (nunca texto claro).
- **Tokens**: JWT HS256 com expiração configurável.
- **Guard de rotas**: verificação de perfil em todas as rotas protegidas.
- **Rate limiting**: aplicado na autenticação para mitigar força bruta.
- **Credenciais**: nunca no código — sempre via variáveis de ambiente.
- **HTTPS**: garantido pela App Platform da DigitalOcean.
