---
tipo: arquitetura
area: bf1
status: implementado
versao: 4.19
atualizado: 2026-09-12
relacionados:
  - "[[01_necessidade]]"
  - "[[02_regras_de_negocio]]"
  - "[[03_spec]]"
  - "[[MAPA_MENTAL_MODULOS]]"
tags: [arquitetura, "area/bf1", "status/implementado"]
aliases: ["Arquitetura do Sistema"]
---

# Arquitetura do Sistema — BF1

> [!info] Status
> **implementado** · área: `bf1` · atualizado em 2026-09-12 · relacionados: [[01_necessidade]], [[02_regras_de_negocio]], [[03_spec]], [[MAPA_MENTAL_MODULOS]]

## Visão Geral

O runtime V4 em homologação usa **Next.js/TypeScript** na apresentação e
**FastAPI/Python** na API, conectado ao mesmo **PostgreSQL** gerenciado e
hospedado na **DigitalOcean App Platform**. O monólito Streamlit 3.x permanece
no repositório somente como baseline de comportamento e compatibilidade.

A entrega segue o [[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados|ADR-0003]]:
Next.js na apresentação, FastAPI em `api/`, regras reutilizadas de `services/` e
o mesmo PostgreSQL por meio de `db/`. A Fase 3 estabeleceu `/api/v1`, sessão por
cookie seguro e revogável, autorização opaca por objeto/temporada, contexto
correlacionável por requisição, bootstrap Master e observabilidade estruturada.
A configuração `bf1homol-v4.yaml` separa o deploy em dois componentes: `bf1-api`
(FastAPI/uvicorn) e `bf1-frontend` (Next.js), com `/api` roteado para a API e a
raiz para o frontend. As variáveis Master/DigitalOcean permanecem com os mesmos
nomes; `DATABASE_URL` continua vindo do banco PostgreSQL gerenciado.
O bootstrap sincroniza a conta Master com essas variáveis a cada inicialização;
o PostgreSQL armazena somente o hash bcrypt necessário à autenticação.
A Fase 4 adicionou `frontend/` em Next.js 16/App Router e TypeScript, com saída
standalone para a DigitalOcean, cliente gerado do OpenAPI e um único adaptador
React para ApexCharts. `requirements-api.txt` representa apenas FastAPI e o
domínio Python; Streamlit, `streamlit-calendar` e Plotly não integram o runtime
V4. O `requirements.txt` raiz preserva a homologação V3 somente até o cutover.
O frontend usa o design system Apex Paddock UI, com o ícone oficial BF1,
superfícies grafite, vermelho como ação primária e verde reservado a semântica
positiva. A paleta das equipes fica centralizada no frontend e acompanha o nome
acessível do piloto; ela é apresentação, não dado mestre do PostgreSQL.
O fluxo V4 de continuidade expõe backups SQL e Excel por tabela em `/api/v1/backup`;
ambos exigem Master, e restores usam pré-validação seguida de reautenticação curta
vinculada à sessão. O Excel preserva o contrato V3.x de uma planilha `data` por tabela.

---

## Diagrama legado V3 (baseline de compatibilidade)

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

## Estrutura legada V3

```
BF1/
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
  id, nome_regra, qtd_minima_pilotos,
  quantidade_fichas, fichas_por_piloto, mesma_equipe,
  pontos_11_colocado, penalidade_abandono, pontos_penalidade,
  pontos_dobrada, pontos_posicoes (json), pontos_sprint_posicoes (json),
  pontos_campeao, pontos_vice, pontos_equipe

temporadas_regras
  temporada (PK), regra_id → regras

circuitos_f1
  circuit_id (PK), circuit_name, country, locality,
  latitude, longitude, aliases, atualizado_em
```

> [!warning] Normalização de chaves em `posicoes`
> O campo `posicoes` do resultado pode ter chaves `int` ou `str` dependendo da inserção.
> **Sempre** usar `_parse_posicoes()` de `historico_service.py` (ou equivalente) para normalizar para `int` antes de qualquer lookup de posição (ex.: detecção do 11º colocado).

---

## Decisões Arquiteturais

### 1. Next.js e FastAPI
- **Decisão vigente**: apresentação Next.js/App Router e API FastAPI versionada.
- **Baseline**: Streamlit permanece somente para caracterização da V3.x.

### 2. JWT e sessão HTTP
- **Decisão**: JWT HS256 revogável em cookie `Secure` e `HttpOnly`, com CSRF
  separado, rotação e revalidação no servidor.

### 3. Pool de Conexões PostgreSQL
- **Decisão**: `connection_pool.py` gerencia um pool de conexões com `psycopg` 3 e `psycopg-pool`.
- **Justificativa**: limitar conexões concorrentes e reutilizá-las entre requisições da API.

### 4. Migrations Incrementais e Idempotentes
- **Decisão**: `migrations.py` executa DDL incremental no bootstrap da aplicação.
- **Justificativa**: simplifica deploy — não requer ferramenta externa (Alembic, Flyway).
- **Risco mitigado**: todas as migrations verificam a existência da coluna/tabela antes de aplicar.

### 5. Separação em Camadas
- `frontend/` → apresentação e estado de interface, sem acesso direto ao banco.
- `api/` → validação, autorização, orquestração e serialização HTTP.
- `services/` → toda lógica de negócio e scoring.
- `db/` → acesso a dados, sem lógica de negócio.
- `utils/` → funções puras e transversais (sem dependência de DB ou UI).

### 6. Fuso Horário São Paulo como Padrão
- Todas as comparações de data/hora usam `America/Sao_Paulo` via `zoneinfo`.
- `now_sao_paulo()` é a função canônica para obter o tempo atual.

### 7. Camadas internas independentes da entrega
- **Decisão**: `services/`, `db/` e `utils/` não importam Streamlit nem componentes Streamlit.
- **Implementação V4**: FastAPI vincula identidade e metadados ao contexto de
  requisição; caches usam `utils/ttl_cache.py` e a API chama os serviços existentes.
- **Backup**: widgets são fornecidos pela camada chamadora por injeção, enquanto validação, geração e restauração continuam nas camadas internas.
- **Justificativa**: permite testar o domínio sem navegador ou protocolo de entrega.

### 8. Previsão meteorológica da Telemetria
- A sincronização Jolpica persiste coordenadas opcionais em `circuitos_f1`; as
  colunas são incrementais e backups V3.x sem esses campos continuam restauráveis.
- `services/weather_service.py` consulta Open-Meteo somente no backend, com
  timeout de 6 segundos, cache em memória de 30 minutos e janela máxima de 16 dias.
- Falhas do provedor produzem um estado indisponível no contrato e nunca
  impedem a renderização da Telemetria.

---

## Infraestrutura (DigitalOcean)

| Componente            | Serviço DO | Observações |
|-----------------------|---------------------------------|------------------------------------------|
| Frontend              | App Platform (`bf1-frontend`)   | Next.js standalone, porta 3000           |
| API                   | App Platform (`bf1-api`)        | FastAPI/Uvicorn, porta 8000              |
| Banco de Dados        | Managed PostgreSQL              | Backups automáticos, SSL obrigatório     |
| Variáveis de Ambiente | App Platform Env Vars           | `DATABASE_URL`, `JWT_SECRET` e variáveis Master existentes |
| CI/CD                 | Auto-deploy no push para `main` | Sem pipeline adicional necessário        |
| Runtime Python        | >= 3.10 (preferencialmente 3.13)| ParamSpec, tomllib e dict_row do psycopg 3 são utilizados |

O ingresso encaminha `/api/*` à API preservando o prefixo e as demais rotas ao
frontend. A configuração versionada está em `bf1homol-v4.yaml`.

### Variáveis de Ambiente Obrigatórias

```
DATABASE_URL        # Connection string PostgreSQL
JWT_SECRET          # Chave HS256 (mínimo 32 bytes)
EMAIL_MASTER        # Email do usuário master inicial
SENHA_MASTER        # Senha do usuário master inicial
USUARIO_MASTER      # Nome do usuário master inicial
```

---

## Segurança

- Todo valor dinâmico inserido em HTML usa `escape_html_text` ou `escape_html_attr`, conforme o contexto.
- Valores inseridos em JavaScript são produzidos exclusivamente por `serialize_js_value`.
- `render_trusted_html` é o único sink permitido para HTML/JavaScript; chamadas diretas com `unsafe_allow_html` ou `unsafe_allow_javascript` são bloqueadas por teste estático.
- Elementos interativos do frontend devem preservar semântica, teclado, foco e contraste.
- Restaurações SQL e importações Excel ficam bloqueadas por padrão. A liberação exige que o master confirme novamente sua senha atual; a autorização é curta, vinculada ao `user_id` e ao `jti` da sessão revalidada e expira em 10 minutos por padrão (`BACKUP_REAUTH_TTL_SECONDS`, limitado entre 60 e 1800 segundos).
- A reautenticação na UI não substitui a autorização em profundidade: cada caminho de escrita revalida a operação `backup.write` e a autorização temporária na camada de serviço/banco.
- Uploads de backup possuem limites globais e específicos de bytes; Excel também limita tamanho descompactado, membros ZIP, linhas, colunas e células antes de qualquer mutação.

- **Senhas**: bcrypt com salt automático (nunca texto claro).
- **Tokens**: JWT HS256 com expiração fixa de 120 minutos no código atual.
- **Sessões**: `auth_sessions` registra `jti`, usuário, versão, emissão, expiração e revogação.
- **Cookie**: sessão `HttpOnly`, `Secure` em produção e `SameSite=Lax`; CSRF em cookie separado e validação de origem nas mutações.
- **Proxy**: headers de IP só são confiados com `TRUSTED_PROXY_MODE` e topologia explícita; o padrão `direct` ignora headers.
- **Retenção**: o bootstrap remove tentativas, logs, tokens expirados e sessões antigas conforme configuração.
- **Autorização em profundidade**: `access_control.py` revalida o usuário e centraliza matrizes de páginas/operações.
- **Guard de rotas**: restringe navegação, mas não substitui autorização no serviço.
- **Mutações administrativas**: a UI coleta dados; `admin_operations.py` autoriza e escreve.
- **Fail-closed**: deadline incompleto ou erro de cálculo bloqueia apostas de campeonato.
- **Rate limiting**: aplicado na autenticação para mitigar força bruta.
- **Credenciais**: nunca no código — sempre via variáveis de ambiente.
- **HTTPS**: garantido pela App Platform da DigitalOcean.

### Changelog

- `4.19` — 2026-09-12 — Coordenadas opcionais de circuitos e previsão Open-Meteo isolada no backend da Telemetria.
- `4.18` — 2026-09-12 — Visão, decisões, infraestrutura e segurança reconciliadas com o runtime V4; Streamlit rotulado como baseline V3.
- `4.17` — 2026-09-12 — Backup/restore Excel V4 exposto por tabela com limites, pré-validação e autorização curta vinculada à sessão Master.
- `4.16` — 2026-09-08 — Gestão Master do Hall da Fama adicionada à API V4, com CRUD, lote idempotente e invalidação de caches; catálogo administrativo V4 cobre usuários, pilotos, provas e financeiro.
- `4.14` — 2026-09-08 — Módulo de Campeonato V4 adicionado com leitura/escrita autenticada, deadline fail-closed e preservação das tabelas `championship_bets`, `championship_bets_log` e `championship_results`.
- `4.13` — 2026-09-08 — Dashboard F1 V4 adicionado como read model autenticado, reutilizando `utils.data_utils` e o provedor histórico da V3 sem persistência nova.
- `4.12` — 2026-09-08 — Logs V4 expostos por read models paginados: apostas respeitam o escopo da identidade autenticada e acessos permanecem exclusivos do Master.
- `4.11` — 2026-09-08 — Hall da Fama V4 adicionado como read model autenticado, preferindo `hall_da_fama` e preservando fallback legado determinístico.
- `4.10` — 2026-09-08 — Análise de Apostas V4 isolada em serviço de agregação autorizado e exportação PNG da Classificação movida para backend headless.
- `4.9` — 2026-09-08 — Classificação V4 separada em serviço canônico, contrato FastAPI e tabela Next.js responsiva.
- `4.8` — 2026-09-08 — Adicionado snapshot autenticado da Telemetria V4, agregado sobre tabelas compatíveis do V3 e consumido pelo dashboard Next.js.
- `4.7` — 2026-09-08 — Adicionadas rotas institucionais V4, contrato autenticado de versão e embed Tenor isolado no Regulamento.
- `4.6` — 2026-09-08 — Registrados o Apex Paddock UI, o ícone oficial, a nomenclatura Telemetria e a paleta centralizada de equipes.
- `4.5` — 2026-09-08 — Adicionados o runtime Next.js standalone, contrato OpenAPI gerado, ApexCharts compartilhado e manifesto Python exclusivo da V4.
- `4.4` — 2026-09-08 — Registrada a fundação FastAPI V4 concluída, incluindo contratos HTTP, segurança, bootstrap e observabilidade PostgreSQL.
- `4.3` — 2026-07-31 — Driver PostgreSQL corrigido e decisões vigentes formalizadas em ADRs.
- `4.2` — 2026-07-20 — Sessões revogáveis, cookie fail-closed, proxy explícito e retenção automática.
- `4.1` — 2026-07-20 — Autorização em profundidade, serviços administrativos e deadline fail-closed.
- `4.0` — 2026-07-19 — Modelo de regras, autenticação, diretórios e variáveis atualizados.
- `3.6` — 2026-05-03 — Integração do `historico_service.py` na arquitetura e documentação de normalização.
- `3.5` — — Versão base.

### Relacionados

- [[01_necessidade]]
- [[02_regras_de_negocio]]
- [[03_spec]]
- [[MAPA_MENTAL_MODULOS]]
- [[adr/0001-streamlit-postgresql]]
- [[adr/0002-limites-de-camadas]]
