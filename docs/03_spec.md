---
tipo: spec
area: bf1
status: implementado
versao: 4.2
atualizado: 2026-07-20
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[04_arquitetura]]"
  - "[[MAPA_MENTAL_MODULOS]]"
  - "[[05_projeto]]"
tags: [spec, "area/bf1", "status/implementado"]
aliases: ["Especificação Funcional"]
---

# Especificação Funcional — BF1

> [!info] Status
> **implementado** · área: `bf1` · atualizado em 2026-07-20 · relacionados: [[02_regras_de_negocio]], [[04_arquitetura]], [[MAPA_MENTAL_MODULOS]], [[05_projeto]]

---

## 1. Autenticação e Sessão

### 1.1 Login
- **Entrada**: e-mail e senha.
- **Processamento**: normaliza e limita o e-mail antes do rate limiting; valida bcrypt; emite JWT HS256 com `user_id`, perfil, status, `jti`, versão de sessão e expiração de 120 minutos.
- **Transporte atual**: JWT revogável no `session_state`/WebSocket. Ausência de backend server-side para cookie `HttpOnly` não invalida credenciais corretas e não produz cookie com atributos reduzidos; apenas desabilita persistência após recarga completa.
- **Rotação e revogação**: novo login revoga JTIs anteriores; logout revoga o atual; troca/redefinição de senha incrementa a versão e revoga todas as sessões.
- **Saída**: redireciona para "Painel do Participante".
- **Contexto autenticado**: operações sensíveis revalidam o token e carregam do banco usuário, perfil, status e temporadas autorizadas.
- **Autoridade**: `user_id`, perfil ou temporada originados da UI nunca concedem permissão.

### 1.2 Matriz de acesso

- Páginas usam `PAGE_ACCESS`; operações sensíveis usam `OPERATION_ACCESS`.
- O roteador protege a navegação; toda escrita administrativa exige autorização adicional no serviço.
- Usuários inativos são bloqueados em operações sensíveis mesmo com claims antigos no token.

### 1.3 Deadline do campeonato

- A primeira largada válida é o deadline, sem tolerância adicional.
- Antes: permitido. Exatamente no deadline e depois: bloqueado.
- Prova/data/horário ausente ou erro de cálculo: bloqueado e alerta ao administrador.
- **Erro**: mensagem de credenciais inválidas; rate limiting aplicado.

### 1.2 Logout
- Limpa cookies de autenticação e session state do Streamlit.
- Redireciona para tela de login.

### 1.3 Guard de Rotas
- Em cada navegação, o sistema decodifica o JWT, revalida o usuário no banco e verifica o perfil contra `PAGE_ACCESS`.
- Sessão expirada ou usuário não encontrado: redireciona para login com mensagem.

---

## 2. Módulos de Interface (UI)

### 2.1 Painel do Participante (`ui/painel.py`)

Exibe resumo da temporada atual: próxima prova, última aposta, posição na classificação.

**Abas disponíveis:**

| Aba                     | Conteúdo                             | Perfil              |
|-------------------------|--------------------------------------|---------------------|
| Apostas                  | Aposta da temporada selecionada       | Ativos               |
| Apostas - AAAA           | Histórico da temporada selecionada| Todos com histórico |
| **Histórico**           | Consolidado multi-temporada *(v3.6)* | Todos com histórico |
| Minha Conta             | Dados pessoais e senha               | Todos               |

**Aba "Histórico" — detalhamento** *(v3.6)*:
- **Resumo (5 métricas)**: Melhor colocação + Ano · Melhor pontuação + Ano · Média das posições · Média das pontuações · Acertos do 11º.
- **Gráfico**: barras empilhadas — fichas apostadas por piloto, comparando temporadas.
- **Destaque**: piloto mais apostado e total de fichas acumuladas.
- Fonte de dados: `services/historico_service.py` → `calcular_resumo_historico()` e `calcular_dados_grafico()`.
- Regra de exibição: aba visível apenas quando o participante possui ao menos uma aposta cadastrada.

Acesso: todos os perfis ativos; inativos com histórico.

### 2.2 Calendário (`ui/calendario.py`)
- Lista provas do calendário F1 do ano corrente com status (Pendente, Realizada, Cancelada).
- Destaca a próxima prova com countdown.
- Acesso: todos os perfis.

### 2.3 Gestão de Apostas (`ui/gestao_apostas.py`)
- Permite ao participante selecionar pilotos, distribuir fichas e indicar o 11º colocado.
- Valida em tempo real: total de fichas, limite por piloto, restrição de equipe, piloto_11 fora dos apostados.
- Bloqueia submissão se janela de apostas encerrada.
- Exibe aposta vigente e histórico de edições.
- Acesso: `participante`, `admin`, `master`.

### 2.4 Análise de Apostas (`ui/analysis.py`)
- Visualiza comparativo entre apostas dos participantes e resultado real da prova.
- Gráficos de pontuação por prova e acumulado por temporada.
- Acesso: `participante`, `admin`, `master`, `inativo` (com histórico).

### 2.5 Atualização de Resultados (`ui/gestao_resultados.py`)
- Permite ao `admin`/`master` registrar o resultado (posição dos pilotos 1 a N) de uma prova.
- Após registro, recalcula automaticamente pontuação e classificação de todos os participantes.
- Suporte a registro de pilotos que abandonaram (para penalidade de abandono).

### 2.6 Classificação (`ui/classificacao.py`)
- Tabela com posição geral, pontos totais, pontos com descarte e variação de posição.
- A grade "Pontuação por Prova" mantém participantes nas linhas e provas nas colunas.
- A imagem completa da classificação é preparada sob demanda, sem bloquear a abertura da página.
- Filtro por temporada.
- Acesso: todos.

### 2.7 Hall da Fama (`ui/hall_da_fama.py`)
- Lista campeões de cada temporada com pontuação e foto/avatar.
- Acesso: todos.

### 2.8 Dashboard F1 (`ui/dashboard.py`)
- Estatísticas agregadas: piloto mais apostado, acerto médio, evolução de pontos.
- Gráficos interativos.
- Acesso: todos.

### 2.9 Apostas Campeonato (`ui/championship_bets.py`)
- Formulário para apostar no campeão/vice de pilotos e construtores.
- Deadline configurável.
- Acesso: `participante`, `admin`, `master`.

### 2.10 Resultado Campeonato (`ui/championship_results.py`)
- Registra resultado final do campeonato e calcula pontuação das apostas de campeonato.
- Acesso: `admin`, `master`.

### 2.11 Gestão de Usuários (`ui/usuarios.py`)
- CRUD completo de usuários: criar, editar perfil/status, resetar senha.
- Acesso: `master`.

### 2.12 Gestão de Pilotos (`ui/gestao_pilotos.py`)
- CRUD de pilotos: nome, equipe, número, status (Ativo/Inativo).
- Acesso: `admin`, `master`.

### 2.13 Gestão de Provas (`ui/gestao_provas.py`)
- CRUD de provas: nome, data, horário, tipo (Normal/Sprint), status, temporada.
- Acesso: `admin`, `master`.

### 2.14 Gestão de Regras (`ui/gestao_regras.py`)
- CRUD de regras nomeadas e associação de cada temporada a uma regra.
- Campos: tabelas normal/sprint, bônus 11º e campeonato, penalidades, descarte, fichas e restrição de equipe.
- Acesso: `master`.

### 2.15 Log de Apostas (`ui/log_apostas.py`)
- Histórico auditável de todas as apostas enviadas (manual e automática).
- Filtros por temporada, prova e usuário.
- Acesso: `admin`, `master`.

### 2.16 Log de Acessos (`ui/log_acessos.py`)
- Registro de todos os logins e acessos por usuário.
- Acesso: `master`.

### 2.17 Backup (`ui/backup.py`)
- Geração de backup em Excel e SQL com validação.
- Download imediato pelo browser.
- Acesso: `master`.

### 2.18 Regulamento (`ui/regulamento.py`)
- Exibe o regulamento do bolão em formato rich text.
- Acesso: todos.

### 2.19 Sobre (`ui/sobre.py`)
- Informações sobre a versão do sistema e créditos.
- Acesso: todos.

---

## 3. Serviços (Services)

| Arquivo                           | Responsabilidade                                                    |
|-----------------------------------|---------------------------------------------------------------------|
| `auth_service.py`                 | Emissão, decodificação e validação de JWT; gerenciamento de cookies |
| `bets_rules.py`                   | Validação da composição de apostas e ajuste automático para regras  |
| `bets_scoring.py`                 | Cálculo de pontuação e salvamento de classificação por prova        |
| `bets_write.py`                   | Persistência de apostas no banco                                    |
| `bets_ai.py`                      | Geração de apostas automáticas para participantes ausentes          |
| `gemini_service.py`               | Cliente centralizado da API Gemini via SDK oficial Google Gen AI    |
| `championship_service.py`         | Lógica de apostas e resultado de campeonato                         |
| `rules_service.py`                | Recuperação das regras aplicáveis por temporada/tipo                |
| `results_service.py`              | Registro de resultados e disparo de recálculo                       |
| `email_service.py`                | Envio de notificações por e-mail                                    |
| `result_notification_service.py`  | Envio de notificações de resultado da prova por e-mail              |
| `hall_da_fama_service.py`         | Consolidação do histórico de campeões                               |
| `hall_da_fama_controller.py`      | Lógica de apresentação do ranking do Hall da Fama                   |
| `painel_controller.py`            | Dados do painel do participante                                     |
| `historico_service.py`            | Consolidação do histórico multi-temporada do participante *(v3.6)*  |
| `data_access_*.py`                | Camada de acesso a dados (queries SQL por domínio)                  |

> [!tip] `historico_service.py` — contrato público
> - `calcular_resumo_historico(usuario_id: int) -> ResumoHistorico`
> - `calcular_dados_grafico(usuario_id: int) -> DadosGrafico`
> Ambas retornam `@dataclass` tipados, sem dependência de Streamlit.

---

## 4. Banco de Dados (DB)

| Arquivo                  | Responsabilidade                                  |
|--------------------------|---------------------------------------------------|
| `connection_pool.py`     | Pool de conexões PostgreSQL                       |
| `db_config.py`           | Leitura de variáveis de ambiente de conexão       |
| `db_schema.py`           | DDL inicial e helpers de schema                   |
| `migrations.py`          | Migrations incrementais idempotentes              |
| `repo_users.py`          | Repositório de usuários                           |
| `repo_bets.py`           | Repositório de apostas                            |
| `repo_races.py`          | Repositório de provas e pilotos                   |
| `repo_logs.py`           | Repositório de logs                               |
| `master_user_manager.py` | Criação/garantia do usuário master no bootstrap   |
| `backup_*.py`            | Módulos de backup (Excel, SQL, validação, repair) |

---

## 5. Utilitários (Utils)

| Arquivo             | Responsabilidade                                   |
|---------------------|----------------------------------------------------|
| `datetime_utils.py` | Fuso horário SP, parse de datas, `now_sao_paulo()` |
| `validators.py`     | Validações genéricas de entrada                    |
| `input_models.py`   | Modelos de dados de entrada                        |
| `helpers.py`        | Funções auxiliares diversas                        |
| `logging_utils.py`  | Configuração de logging                            |
| `request_utils.py`  | Utilitários de request/cookie                      |
| `season_utils.py`   | Funções de manipulação de temporada                |
| `data_utils.py`     | Utilitários de manipulação de dados/DataFrames     |

---

## 6. Fluxos Principais

### Fluxo: Submissão de Aposta
```
Participante seleciona pilotos e fichas
  → UI valida composição em tempo real (bets_rules)
  → Verifica janela de apostas (pode_fazer_aposta)
  → Se válido: persiste via bets_write → registra no log
  → Se inválido: exibe mensagem de erro inline
```

### Fluxo: Registro de Resultado
```
Admin registra posições dos pilotos
  → results_service salva na tabela `resultados`
  → bets_scoring.atualizar_classificacoes_todas_as_provas() é chamado
  → Pontuação de cada participante é calculada e salva em posicoes_participantes
  → Classificação é atualizada automaticamente
```

### Fluxo: Aposta Automática
```
Horário limite da prova é atingido
  → bets_ai verifica participantes sem aposta
  → Tenta reutilizar última aposta válida do participante
  → Ajusta para regras vigentes (ajustar_aposta_para_regras)
  → Persiste com flag automatica >= 1
```

### Fluxo: Histórico Consolidado *(v3.6)*
```
Participante acessa aba "Histórico" no Painel
  → ui/painel.py chama historico_service.calcular_resumo_historico(usuario_id)
  → historico_service consulta posicoes_participantes + apostas (todas as temporadas)
  → _parse_posicoes() normaliza chaves para int
  → Retorna ResumoHistorico (dataclass) → exibido como st.metric
  → ui/painel.py chama historico_service.calcular_dados_grafico(usuario_id)
  → Retorna DadosGrafico (dataclass) → gráfico Plotly + destaque do piloto
```

### Changelog

- `4.2` — 2026-07-20 — Sessão revogável, recuperação resistente a timing e retenção automática.
- `4.1` — 2026-07-20 — Contexto autenticado, matrizes de acesso e deadline fail-closed.
- `4.0` — 2026-07-19 — Contratos de autenticação, abas e regras atualizados conforme a implementação.
- `3.6` — 2026-05-03 — Adicionado fluxo do Histórico Consolidado e `historico_service.py`.
- `3.5` — — Versão base.

### Relacionados

- [[02_regras_de_negocio]]
- [[04_arquitetura]]
- [[MAPA_MENTAL_MODULOS]]
- [[05_projeto]]
> Toda fachada tabular deve aplicar o contrato central correspondente (`APOSTAS_COLUMNS`, `PILOTOS_COLUMNS`, `PROVAS_COLUMNS`, `RESULTADOS_COLUMNS`, `USUARIOS_COLUMNS`, `POSICOES_COLUMNS`, `CHAMPIONSHIP_BETS_COLUMNS` ou `CHAMPIONSHIP_RESULTS_COLUMNS`). Ausência de linhas ou cache legado não altera o schema tabular.
> DataFrames intermediários criados pelas telas, inclusive após `st.rerun()`, também devem preservar o contrato do domínio; fallbacks não podem retornar `pd.DataFrame()` sem colunas.
> Após escrita de aposta, a função cacheada de leitura de apostas deve ser invalidada explicitamente antes do `st.rerun()`; mensagens de confirmação devem sobreviver ao rerun via `session_state`.
> O fluxo “Sem ideias” somente informa sucesso após reler a linha diretamente do banco, sem cache, e transporta os valores confirmados pelo `session_state` para preencher o formulário após o rerun.
> A Gestão de Apostas normaliza apostas, provas e participantes na entrada da página; a ordenação de provas converte datas com `errors="coerce"`, mantendo registros inválidos ao final sem quebrar a tela.
> A Atualização de Resultados normaliza provas, pilotos e resultados em toda leitura, inclusive após salvar/rerun; datas ausentes ou inválidas são exibidas sem interromper a página.
> Painel, Classificação, Calendário, Usuários, Hall da Fama e apostas/resultados de campeonato reaplicam seus contratos na fronteira da UI para tolerar valores de cache produzidos por versões anteriores.
> A Gestão de Provas aplica `PROVAS_COLUMNS` antes da tabela e dos formulários; registros sem ID são descartados, enquanto data ausente usa um valor seguro no editor.
> O Diagnóstico Regras/Provas da Análise Detalhada aplica os contratos completos de provas, resultados e apostas antes de normalizar IDs ou consultar `prova_id`.
> A Classificação converte IDs com `errors="coerce"`, descarta linhas sem identificadores válidos antes de `int()` e substitui pontuações não numéricas por zero.
