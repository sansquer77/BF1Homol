---
tipo: arquitetura
area: bf1
status: implementado
versao: 4.2
atualizado: 2026-07-20
relacionados:
  - "[[01_necessidade]]"
  - "[[02_regras_de_negocio]]"
  - "[[03_spec]]"
  - "[[04_arquitetura]]"
  - "[[MAPA_MENTAL_MODULOS]]"
tags: [arquitetura, "area/bf1", "status/implementado"]
aliases: ["Referência Técnica de Módulos"]
---

# Referência Técnica de Módulos — BF1

> [!info] Status
> **implementado** · área: `bf1` · atualizado em 2026-07-20 · relacionados: [[01_necessidade]], [[02_regras_de_negocio]], [[03_spec]], [[04_arquitetura]], [[MAPA_MENTAL_MODULOS]]

---

## Ponto de Entrada

| Módulo | Responsabilidade |
|---|---|
| `services/access_control.py` | Contexto revalidado e matrizes de páginas/operações |
| `services/admin_operations.py` | Casos de uso administrativos autorizados |
| `services/deadlines.py` | Regra pura e fail-closed do prazo de campeonato |
| `utils/security_utils.py` | Normalização limitada de identificadores de segurança |
| `utils/dataframe_contracts.py` | Schema mínimo estável para DataFrames vazios de apostas |

### `main.py`

Arquivo principal da aplicação. Responsável por:

- Configurar a página Streamlit (`st.set_page_config`)
- Carregar o CSS do tema Liquid Glass (`load_css`)
- Injetar meta tags PWA e Apple Touch Icon (`load_pwa_meta_tags`)
- Detectar e sincronizar o timezone do browser do cliente via JavaScript (`load_timezone_detector`)
- Executar o bootstrap da aplicação: migrations + criação do usuário master (`bootstrap_app`)
- Definir os menus por perfil: `menu_master`, `menu_admin`, `menu_participante`, `menu_inativo`
- Renderizar o menu lateral agrupado por seção (`sidebar_menu`)
- Implementar o guard de rotas por perfil (`_enforce_route_guard`)
- Rotear para a view correta via dicionário `PAGES`

**Perfis e Menus:**

| Perfil | Seções do Menu |
|---|---|
| `master` | Participante, Operação, Gestão, Monitoramento, Sistema |
| `admin` | Participante, Operação, Gestão, Monitoramento, Sistema |
| `participante` | Participante, Acompanhamento, Sistema |
| `inativo` | Participante, Monitoramento (restrito ao histórico) |

**Variáveis de ambiente obrigatórias:**

```
DATABASE_URL       # Connection string PostgreSQL
JWT_SECRET         # Chave HS256 com no mínimo 32 bytes
MASTER_EMAIL       # Email do usuário master inicial
MASTER_PASSWORD    # Senha do usuário master inicial
MASTER_NOME        # Nome do usuário master inicial
```

---

## Camada UI (`ui/`)

Cada arquivo expõe uma função principal (geralmente `main()` ou nome da view) chamada pelo router em `main.py`. Nenhum arquivo desta camada contém lógica de negócio — apenas renderização Streamlit.

| Arquivo | Função principal | Perfis com acesso | Descrição |
|---|---|---|---|
| `login.py` | `login_view()` | todos | Formulário de login com JWT, recuperação de senha, força bruta mitigada |
| `painel.py` | `participante_view()` | todos autenticados | Painel pessoal: aposta da próxima prova, minha conta, histórico (v3.6) |
| `gestao_apostas.py` | `main()` | admin, master | Visão geral de apostas de todos os participantes por prova |
| `gestao_pilotos.py` | `main()` | admin, master | CRUD de pilotos com status e equipe |
| `gestao_provas.py` | `main()` | admin, master | CRUD de provas com data, horário, tipo e temporada |
| `gestao_regras.py` | `main()` | master | CRUD das regras de pontuação por temporada/tipo |
| `gestao_resultados.py` | `resultados_view()` | admin, master | Lançamento dos resultados de cada prova |
| `usuarios.py` | `main()` | master | CRUD completo de usuários com reset de senha |
| `calendario.py` | `main()` | todos autenticados | Calendário visual de provas do ano corrente com timezone |
| `classificacao.py` | `main()` | todos autenticados | Tabela de classificação com suporte a descarte de provas |
| `analysis.py` | `main()` | todos autenticados | Análise gráfica e tabular das apostas |
| `championship_bets.py` | `main()` | todos autenticados | Apostas no campeão de pilotos e construtores |
| `championship_results.py` | `main()` | admin, master | Lançamento dos resultados do campeonato |
| `log_apostas.py` | `main()` | todos autenticados | Histórico de submissão de apostas |
| `log_acessos.py` | `main()` | master | Log completo de acessos ao sistema |
| `dashboard.py` | `main()` | todos autenticados | Dashboard de estatísticas de F1 com gráficos Plotly |
| `hall_da_fama.py` | `hall_da_fama()` | todos autenticados | Ranking histórico de campeões do bolão |
| `backup.py` | `main()` | master | Interface para geração e download de backups |
| `regulamento.py` | `main()` | todos autenticados | Exibição do regulamento do bolão |
| `sobre.py` | `main()` | todos autenticados | Informações sobre a versão e créditos do sistema |

---

## Camada de Serviços (`services/`)

Concentra a maior parte da lógica de negócio. A separação ainda é parcial: `rules_service.py` usa `st.cache_data`, enquanto serviços como `historico_service.py` permanecem independentes da UI.

### `auth_service.py`
Autenticação e autorização baseadas em JWT.

- `generate_token(user_id, nome, perfil, status)` → `str` — gera JWT HS256 com expiração
- `decode_token(token)` → `dict | None` — decodifica e valida JWT; retorna `None` se inválido/expirado
- `hash_password(senha)` → `str` — bcrypt hash
- `verify_password(senha, hash)` → `bool` — validação bcrypt
- `set_auth_cookies(token)` / `clear_auth_cookies()` — suporte de cookie via `extra-streamlit-components`; a autorização do roteador usa o token da sessão Streamlit
- Rate limiting embutido para mitigar ataques de força bruta no login

### `bets_rules.py`
Validação das regras de composição de uma aposta (RN-003).

- `validate_aposta(pilotos, fichas, piloto_11, regra)` → `list[str]` — lista de erros; vazia se válida
- Verifica: mínimo de pilotos, total de fichas, fichas por piloto, restrição de equipe, unicidade de pilotos

### `bets_scoring.py`
Cálculo de pontuação de apostas (RN-004).

- `calcular_pontos(aposta, resultado, regra)` → `float` — pontuação total de uma aposta
- Aplica tabela de pontos, bônus do 11º colocado, penalidade por abandono, dobrada sprint e penalidade de aposta automática
- Fallback para tabela FIA oficial quando regra não cadastrada

### `bets_write.py`
Persistência de apostas no banco. Módulo mais extenso do serviço (~56 KB).

- `salvar_aposta(usuario_id, prova_id, pilotos, fichas, piloto_11, automatica)` → `bool`
- `gerar_aposta_automatica(usuario_id, prova_id, regra)` → aposta válida automática
- Lógica de reutilização da aposta anterior e fallback para aposta aleatória

### `bets_ai.py`
Análise assistida por IA de apostas e padrões.

- Gera insights e sugestões com base no histórico de apostas do participante
- Identifica padrões de pilotos mais apostados e acertos do 11º colocado

### `championship_service.py`
Lógica de apostas e resultados do campeonato (RN-008).

- `salvar_aposta_campeonato(usuario_id, temporada, dados)` → `bool`
- `calcular_pontos_campeonato(apostas, resultado)` → `dict`
- `get_resultado_campeonato(temporada)` → `dict | None`

### `email_service.py`
Envio de e-mails transacionais (recuperação de senha, notificações).

- Usa SMTP configurado via variáveis de ambiente
- Templates HTML embutidos para e-mails de redefinição de senha

### `result_notification_service.py`
Envio de e-mails de notificação com o resumo do resultado da corrida para todos os participantes que registraram aposta.

- `enviar_emails_resultado_prova(prova_id, temporada)` → `ResultadoEmailStats` — envia e-mails detalhados de resultado para os participantes

### `historico_service.py` *(v3.6)*
Consolida histórico multi-temporada do participante.

- `calcular_resumo_historico(usuario_id)` → `ResumoHistorico`
- `calcular_dados_grafico(usuario_id)` → `DadosGrafico`
- **Sem dependência de Streamlit** — testável de forma isolada
- Normaliza chaves do dict `posicoes` para `int` via `_parse_posicoes()`

### `hall_da_fama_service.py` / `hall_da_fama_controller.py`
Calculam e recuperam o ranking histórico de campeões do bolão.

- `get_hall_da_fama()` → lista de campeões por temporada com pontuação

### `results_service.py`
Processamento dos resultados de corrida.

- `salvar_resultado(prova_id, posicoes, abandonos)` → `bool`
- Recalcula pontuações de todos os participantes após salvar resultado

### `rules_service.py`
CRUD das regras de pontuação (RN-006).

- `get_regra(temporada, tipo_prova)` → `dict | None`
- `upsert_regra(dados)` → `bool`

### `painel_controller.py`
Lógica do painel do participante.

- `get_dados_painel(usuario_id, temporada)` → agregado com próxima prova, aposta atual, pontuação

### `data_access_*.py` (Camada de Acesso a Dados)
Adaptadores finos entre os serviços e os repositórios da camada `db/`.

| Arquivo | Responsabilidade |
|---|---|
| `data_access_apostas.py` | Leitura de apostas para os serviços |
| `data_access_auth.py` | Consulta de usuários para autenticação |
| `data_access_backup.py` | Consulta de tabelas para backup |
| `data_access_core.py` | Funções utilitárias de acesso genérico |
| `data_access_provas.py` | Consulta de provas |
| `data_access_regras.py` | Consulta de regras por temporada |

---

## Camada de Banco de Dados (`db/`)

### `connection_pool.py`
Gerencia pool de conexões PostgreSQL usando `psycopg-pool`.

- Expõe `get_connection()` como context manager
- Reconexão automática em caso de falha
- Configurado via `DATABASE_URL`

### `db_config.py`
Lê e expõe configurações do banco a partir das variáveis de ambiente.

### `db_schema.py`
Define as constantes de schema (nomes de tabelas, colunas).

### `migrations.py`
Executa DDL incremental e idempotente no bootstrap (`run_migrations()`).

- Verifica existência de colunas/tabelas antes de aplicar
- Não requer ferramenta externa (Alembic, Flyway)

### `migrations_native_types.py`
Migrations específicas para normalização de tipos nativos no banco.

### `master_user_manager.py`
Cria o usuário master inicial se não existir (`MasterUserManager.create_master_user()`).

### `repo_users.py`
Repositório de usuários.

- `get_user_by_id(user_id)` → `dict | None`
- `get_user_by_email(email)` → `dict | None`
- `get_usuario_temporadas_ativas(usuario_id)` → `list[str]`
- CRUD completo de usuários

### `repo_bets.py`
Repositório de apostas.

- `get_aposta(usuario_id, prova_id)` → `dict | None`
- `list_apostas_prova(prova_id)` → `list[dict]`

### `repo_races.py`
Repositório de provas e resultados.

- `get_provas_temporada(temporada)` → `list[dict]`
- `get_resultado(prova_id)` → `dict | None`

### `repo_logs.py`
Repositório de logs de acesso e apostas.

- `registrar_acesso(usuario_id, ip)` → `None`
- `registrar_aposta(usuario_id, prova_id, tipo)` → `None`

### `rules_utils.py`
Funções utilitárias relacionadas à leitura e parsing das regras do bolão.

### `circuitos_utils.py`
Mapeamento e utilitários de circuitos de F1 (nomes, países, emojis de bandeira).

### `backup_*.py` (Módulos de Backup)

| Arquivo | Função |
|---|---|
| `backup_excel.py` | Exporta todas as tabelas para `.xlsx` multi-aba |
| `backup_sql.py` | Gera dump SQL completo |
| `backup_utils.py` | Orquestra o processo de backup (~48 KB) |
| `backup_repair.py` | Tenta reparar backups corrompidos |
| `backup_validate.py` | Valida integridade do backup antes do download |

---

## Camada de Utilitários (`utils/`)

Funções puras, sem dependência de banco ou UI.

| Arquivo | Principais funções |
|---|---|
| `datetime_utils.py` | `now_sao_paulo()` — datetime atual em America/Sao_Paulo |
| `timezone_utils.py` | Conversão de datetimes entre timezones, formatação localizada |
| `data_utils.py` | Parsing e transformação de DataFrames, limpeza de dados (~22 KB) |
| `helpers.py` | Funções auxiliares genéricas (formatação, strings) |
| `input_models.py` | Modelos Pydantic para validação de entrada do usuário |
| `validators.py` | Validações de formato (email, senha, etc.) |
| `logging_utils.py` | Configuração do logger padrão do projeto |
| `request_utils.py` | Funções para leitura de headers e IP do cliente |
| `season_utils.py` | Helpers para determinar a temporada ativa e listas de temporadas |
| `cache_utils.py` | `clear_data_cache()` — Limpa caches de leitura do Streamlit após escritas |

---

## Infraestrutura e Configuração

### `.streamlit/`
Configurações do Streamlit (tema, server).

### `assets/styles.css`
CSS customizado do tema **Liquid Glass** — visual responsivo para mobile e desktop.

### `static/`
Arquivos estáticos servidos diretamente:
- `favicon.ico` — ícone do browser
- `apple-touch-icon.png` / `apple-touch-icon-180.png` — ícones iOS
- `icon-192.png`, `icon-512.png` — ícones PWA
- `manifest.json` — configuração PWA (Web App Manifest)

---

## Dependências Principais (`requirements.txt`)

| Biblioteca | Versão mínima | Uso |
|---|---|---|
| `streamlit` | 1.55.0 | Framework principal |
| `extra-streamlit-components` | 0.1.56 | Gerenciamento de cookies |
| `streamlit-calendar` | 1.4.0 | Componente de calendário |
| `psycopg[binary]` | 3.2.0 | Driver PostgreSQL |
| `psycopg-pool` | 3.2.0 | Pool de conexões |
| `bcrypt` | 4.1.0 | Hash de senhas |
| `PyJWT` | 2.8.0 | Tokens JWT |
| `pandas` | 2.2.0 | Manipulação de dados |
| `numpy` | 1.26.0 | Computação numérica |
| `openpyxl` | 3.1.0 | Exportação Excel |
| `pydantic` | 2.9.0 | Validação de modelos |
| `plotly` | 5.18.0 | Gráficos interativos |
| `matplotlib` | 3.8.0 | Gráficos estáticos |
| `httpx` | 0.25.0 | Requisições HTTP assíncronas |

### Changelog

- `4.2` — 2026-07-20 — `jti`, revogação de sessão, cookie obrigatório, normalização de e-mail e contrato estável para DataFrames vazios.
- `4.1` — 2026-07-20 — Contexto autenticado, operações administrativas e deadline puro.
- `4.0` — 2026-07-19 — Variáveis, contratos do histórico e limites reais entre camadas corrigidos.
- `3.6` — 2026-05-12 — Adicionados os módulos `result_notification_service.py` e `cache_utils.py` na documentação.
- `3.5` — — Versão base.

### Relacionados

- [[01_necessidade]]
- [[02_regras_de_negocio]]
- [[03_spec]]
- [[04_arquitetura]]
- [[MAPA_MENTAL_MODULOS]]
