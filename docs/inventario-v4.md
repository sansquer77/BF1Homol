---
tipo: arquitetura
area: migracao-v4
status: implementado
versao: 0.7
atualizado: 2026-09-08
relacionados:
  - "[[specs/migracao-v4-nextjs-fastapi]]"
  - "[[04_arquitetura]]"
  - "[[03_spec]]"
tags: [arquitetura, "area/migracao-v4", "status/em-revisao"]
aliases: ["Inventário funcional e técnico da versão 4"]
---

# Inventário funcional e técnico da versão 4

> [!info] Status
> **implementado** · área: `migracao-v4` · atualizado em 2026-09-08 · relacionados: [[specs/migracao-v4-nextjs-fastapi]], [[04_arquitetura]], [[03_spec]]

## Objetivo e método

Este documento é a linha de base da migração. O inventário foi obtido do
roteador em `main.py`, da matriz em `services/access_control.py`, das telas em
`ui/`, dos serviços e repositórios, do bootstrap/migrations em `db/` e das specs
focadas. Divergências continuam marcadas para caracterização; este documento
não substitui os contratos executáveis.

## Perfis e jornadas transversais

| Perfil | Escopo atual |
|---|---|
| `master` | Todas as áreas, gestão de regras/usuários, logs de acesso e backup/restauração. |
| `admin` | Operação de provas, pilotos, apostas e resultados, sem usuários, regras, logs de acesso ou backup. |
| `participante` | Aposta, acompanhamento, análises, classificação e conteúdo institucional. |
| `inativo` | Consulta restrita; com histórico acessa temporadas autorizadas, sem histórico recebe o conjunto mínimo definido na RN-001. |

Jornadas transversais a preservar: autenticação e troca obrigatória de senha;
seleção global de temporada; seleção de fuso apenas para apresentação; guardas
de página e autorização da operação; logout e revogação; feedback de sucesso,
validação e falha; paginação/filtros; exportações; invalidação seletiva de cache.

## Telas e áreas de migração

| Área atual | Módulo | Perfis | Responsabilidade principal | Onda sugerida |
|---|---|---|---|---|
| Login | `ui/login.py` | anônimo | Email/senha, rate limit, recuperação e OIDC opcional. | fundação |
| Painel do Participante | `ui/painel.py` | todos autenticados | Próxima prova, aposta e histórico individual. Na V4, a área é exibida como **Telemetria**. | 1 |
| Calendário | `ui/calendario.py` | todos autenticados | Provas e horários convertidos para o fuso de exibição. | 1 |
| Gestão de Usuários | `ui/usuarios.py` | master | Usuários, status, senha e gestão financeira. | 4 |
| Gestão de Pilotos | `ui/gestao_pilotos.py` | admin/master | Cadastro e manutenção de pilotos. | 3 |
| Gestão de Provas | `ui/gestao_provas.py` | admin/master | Calendário, tipo, circuito, status e temporada. | 3 |
| Gestão de Regras | `ui/gestao_regras.py` | master | Regras por temporada/tipo e clonagem. | 4 |
| Gestão de Apostas | `ui/gestao_apostas.py` | admin/master | Consulta/operação administrativa de apostas. | 3 |
| Análise de Apostas | `ui/analysis.py` | autenticados permitidos | Agregações, tabelas e gráficos de apostas. | 2 |
| Atualização de resultados | `ui/gestao_resultados.py` | admin/master | Resultado, abandonos, pontuação e notificações. | 3 |
| Apostas Campeonato | `ui/championship_bets.py` | participante/admin/master | Palpites e deadline do campeonato. | 2 |
| Resultado Campeonato | `ui/championship_results.py` | admin/master | Resultado final e pontuação dos palpites. | 3 |
| Log de Apostas | `ui/log_apostas.py` | autenticados permitidos | Auditoria com restrição do participante aos próprios dados. | 2 |
| Log de Acessos | `ui/log_acessos.py` | master | Auditoria de autenticação/acesso. | 4 |
| Classificação | `ui/classificacao.py` | autenticados permitidos | Totais, descarte, bônus, ranking e exportação. | 2 |
| Hall da Fama | `ui/hall_da_fama.py` | todos autenticados | Histórico consolidado e manutenção master. | 2/4 |
| Dashboard F1 | `ui/dashboard.py` | todos autenticados | Dados e visualizações externas da Fórmula 1. | 2 |
| Backup dos Bancos de Dados | `ui/backup.py` | master | Exportação, reautenticação e restauração. | 5 |
| Regulamento | `ui/regulamento.py` | autenticados permitidos | Conteúdo oficial. | 1 |
| Sobre | `ui/sobre.py` | autenticados permitidos | Metadados e versão do produto. | 1 |

Cada onda é implementada somente depois dos testes de caracterização do domínio
correspondente. A versão 4 não carrega módulos ou sessão Streamlit. Gráficos da versão 4 usam ApexCharts por um adaptador React único,
com tabela/resumo textual acessível como alternativa.

“Painel do Participante” permanece como nome histórico da tela V3 e de seu
módulo Python. Na interface V4, a área e a navegação usam **Telemetria**; essa
mudança de rótulo não altera permissões, dados nem regras.

## Serviços Python reutilizáveis

- Autenticação/autorização: `auth_service.py`, `access_control.py`,
  `backup_restore_authorization.py`.
- Apostas: `bets_rules.py`, `bets_write.py`, `bets_scoring.py`, `bets_ai.py`,
  `deadlines.py`.
- Campeonato e resultados: `championship_service.py`, `results_service.py`,
  `result_notification_service.py`.
- Consultas e domínio: fachadas `data_access_*.py`, `rules_service.py`,
  `historico_service.py`, `painel_controller.py`, `hall_da_fama_*`.
- Persistência: `db/repo_*.py`, `db/rules_utils.py`, `db/migrations*.py` e
  `db/backup_*.py`.

Antes de expor um serviço na API, dependências de `app_runtime`/estado Streamlit
devem ser substituídas por contexto de requisição explícito, sem mover regras
para handlers FastAPI.

## Contrato de banco e backup

### Regra primária

Um backup produzido por uma versão 3.x suportada deve poder ser restaurado na
versão 4, e o banco restaurado deve inicializar, autenticar e servir as jornadas
caracterizadas sem edição manual do arquivo. Colunas e formatos legados usados
pelos backups não podem ser removidos nem ter semântica reinterpretada.

O primeiro exemplar oficial recebido foi gerado pela V3.5.0 em 2026-09-06. É
um dump lógico data-only com 20 tabelas e 3.913 instruções `INSERT`. Como contém
dados pessoais, hashes, sessões e logs, o original não é versionado. O manifesto
estrutural e a fixture SQL anonimizada e determinística ficam no Git; IDs, FKs,
tipos e regras esportivas foram preservados.

O exemplar contém dois registros históricos com o mesmo nome de piloto e IDs
distintos. Por isso, `pilotos.id` permanece a identidade canônica e o schema V4
não impõe unicidade global sobre `pilotos.nome`; duplicidade em novos cadastros
é uma validação de serviço contextual, não uma restrição incompatível do banco.

### Restore de caracterização V3.5.0

Validado em PostgreSQL 18.6 local e isolado em 2026-09-06:

- 20 tabelas e 3.913 linhas coincidentes com o manifesto;
- zero órfãos nas FKs verificadas;
- sequences maiores ou iguais aos IDs restaurados;
- hashes bcrypt anonimizados autenticáveis pela senha da fixture;
- colunas nativas de data, arrays e JSON preenchidas após migrations;
- duas execuções consecutivas das migrations sem erro.

O ensaio revelou e corrigiu três incompatibilidades do caminho anterior:
tabelas/colunas criadas apenas sob demanda, booleanos legados como `0/1` e a
unicidade global de nome de piloto incompatível com o histórico real.

### Fontes canônicas do contrato V3.x

Não existe dependência de acesso ao PostgreSQL hospedado na DigitalOcean para
congelar o contrato. A compatibilidade é reconstruída e comprovada pela
combinação destas fontes:

1. código V3.x de criação de schema e migrations, que define a estrutura pretendida;
2. código de restore SQL e Excel, que define tabelas, colunas, conversões,
   reparos legados, limites, ordem e comportamento efetivamente aceitos;
3. backup SQL real V3.5.0, que comprova o formato produzido em operação;
4. exportações Excel reais, que comprovam o contrato de arquivo por tabela.

Em divergências, backups reais e comportamento comprovado do restore orientam
os testes de caracterização; código e documentação são então corrigidos para
representar esse contrato. Um PostgreSQL temporário e isolado pode ser usado
para prova de restore, sem credenciais ou acesso ao banco da DigitalOcean.

Em 2026-09-07 foram recebidas 21 exportações Excel V3.x, todas com uma aba
`data`: `access_logs`, `apostas`, `auth_sessions`, `championship_bets`,
`championship_bets_log`, `championship_results`, `circuitos_f1`,
`financeiro_config_temporada`, `financeiro_participantes`, `hall_da_fama`,
`log_apostas`, `login_attempts`, `pilotos`, `posicoes_participantes`, `provas`,
`regras`, `resultados`, `temporadas`, `temporadas_regras`, `usuarios` e
`usuarios_status_historico`. Os arquivos originais contêm dados sensíveis e
não são versionados. As fixtures determinísticas anonimizadas preservam abas,
cabeçalhos, tipos lógicos, IDs, relacionamentos e casos de tabela vazia.

### Restore de caracterização Excel V3.x

Validado em PostgreSQL 18.6 local e isolado em 2026-09-07:

- 21 arquivos/tabelas e 3.904 linhas coincidentes com o manifesto;
- aba `data`, cabeçalhos e casos vazios preservados;
- FKs pré-validadas pelo caminho real de importação;
- IDs e sequences preservados/ressincronizados;
- hashes bcrypt substituídos por hash conhecido exclusivo da fixture;
- schema reconstruído contendo todas as colunas exportadas;
- duas execuções adicionais das migrations sem alteração do snapshot.

O ensaio revelou e corrigiu duas incompatibilidades adicionais: booleanos do
Excel representados como `0/1` diante de colunas PostgreSQL `BOOLEAN`, e cache
de metadados não invalidado entre preparações consecutivas do restore.

### Estruturas encontradas

| Grupo | Tabelas/estruturas |
|---|---|
| Domínio principal | `usuarios`, `pilotos`, `provas`, `apostas`, `resultados`, `posicoes_participantes`, `regras`, `temporadas_regras`, `temporadas` |
| Campeonato/histórico | `championship_bets`, `championship_results`, `championship_bets_log`, `hall_da_fama`, `usuarios_status_historico` |
| Segurança/auditoria | `auth_sessions`, `login_attempts`, `password_reset_tokens`, `access_logs`, `log_apostas` |
| Apoio operacional | `circuitos_f1`, `financeiro_participantes`, `financeiro_config_temporada` |

O contrato reconstruído de colunas, tipos, nulabilidade, defaults, chaves,
índices, sequences e ordem de restauração será congelado em artefato
automatizado e versionado. Ele não será apresentado como snapshot do banco de
produção inacessível. O código já contém colunas nativas paralelas (`*_date`, `*_ts`,
`*_arr`, `*_jsonb`); elas são uma estratégia válida porque preservam as colunas
TEXT originais.

### Política de evolução compatível

1. Migrações são incrementais, idempotentes e executadas antes de servir tráfego.
2. Otimizações preferem índices e novas colunas/tabelas; não renomeiam nem removem contratos legados durante a janela de compatibilidade.
3. Escritas que possuam representação legada e moderna mantêm sincronização verificável.
4. O restore aceita SQL e Excel atualmente suportados, valida limites e FKs e ressincroniza sequences.
5. Toda restauração ocorre primeiro em banco isolado, com transação ou estratégia de troca documentada; falha não deixa produção parcialmente alterada.
6. Uma migration destrutiva futura exige versão própria de formato de backup, conversor testado, ADR e plano de rollback.

## Contratos de segurança da API

- O identificador do usuário e o perfil vêm da sessão validada, nunca do corpo,
  query string ou claim não revalidada no banco.
- Todo recurso com ID aplica autorização por objeto e temporada no serviço;
  ocultar botões não é controle de acesso.
- Login e recuperação respondem de forma indistinguível para conta inexistente
  e credencial inválida, têm limite por IP e identificador normalizado, atraso
  progressivo e observabilidade sem registrar segredo.
- Cookies de sessão são `Secure`, `HttpOnly`, com `SameSite` definido, rotação,
  expiração curta e proteção CSRF nas mutações. Tokens não ficam em
  `localStorage`.
- Hashes bcrypt restaurados continuam válidos. Uma evolução de hash só pode
  rehashar após login válido e deve manter leitura dos hashes antigos.
- CORS usa allowlist explícita; documentação da API e endpoints operacionais
  não ficam públicos em produção por padrão.

## Observabilidade no PostgreSQL

O backend persiste eventos estruturados de aplicação, acesso HTTP, segurança e
erro em tabela própria no PostgreSQL. Os registros têm UTC,
`request_id`, rota, status, duração e identidade pseudonimizada quando
necessária; nunca incluem senha, JWT, token de reset, conteúdo de backup ou
payload sensível. A retenção e os limites seguem a spec V4. O download pelo
Master gera JSON Lines compactado sob demanda, com reautenticação e auditoria;
nenhum caminho de arquivo é recebido do cliente. `stdout/stderr` cobre falhas
que não possam ser gravadas no próprio banco.

## Bootstrap do usuário Master

O FastAPI preserva a mecânica atual: no bootstrap de banco vazio, cria o Master
com `EMAIL_MASTER`, `SENHA_MASTER` e `USUARIO_MASTER` do ambiente DigitalOcean.
As variáveis são obrigatórias na primeira inicialização, tratadas como segredo e
nunca registradas. Se um Master já existir, reiniciar ou alterar a variável não
redefine a credencial persistida.

## Testes de caracterização necessários

1. Snapshot do schema e restauração de fixtures SQL/Excel representativas.
2. Golden tests das fórmulas, deadlines e timezone `America/Sao_Paulo`.
3. Matriz página/operação/perfil e autorização por objeto/temporada.
4. Login, rotação/revogação, troca/reset de senha e limites de tentativa.
5. Schemas mínimos dos DataFrames e equivalentes JSON vazios/não vazios.
6. Jornada de aposta manual/automática e atualização de resultados.
7. Classificação, descarte, bônus, desempate e exportações.
8. Falhas de backup sem mutação parcial, sequences e round-trip 3.x → 4.x.

## Riscos e lacunas encontradas

- Existem regras/cálculos ainda em módulos `ui/` (notadamente classificação e
  análise); precisam ganhar serviços antes de virarem endpoints.
- A gestão financeira cria schema a partir do serviço e ainda possui helpers na
  UI; a fronteira deve ser consolidada antes da migração dessa área.
- O log operacional em banco deve coexistir com `access_logs` e `log_apostas`;
  nenhum deles substitui a auditoria de domínio do outro.
- A mesma origem, a ausência de Streamlit e logs no PostgreSQL estão aprovados;
  ainda é preciso fechar a política de rollback por artefato/backup.

## Changelog

- `0.7` — 2026-09-08 — Painel do Participante mapeado para Telemetria na V4 e identidade de equipes incorporada ao contrato visual.
- `0.6` — 2026-09-07 — Restore das 21 fixtures Excel aprovado no PostgreSQL 18.6 e contrato reconstruído de schema congelado.
- `0.5` — 2026-09-07 — Inventário congelado com quatro fontes canônicas do contrato V3.x e 21 exportações Excel reais recebidas.
- `0.4` — 2026-09-06 — Restore V3.5.0 validado em PostgreSQL 18.6 e incompatibilidades encontradas documentadas.
- `0.3` — 2026-09-06 — Adicionados exemplar V3.5.0, política de logs e bootstrap Master por ambiente.
- `0.2` — 2026-09-06 — Registradas topologia de mesma origem e V4 pura sem Streamlit.
- `0.1` — 2026-09-06 — Inventário inicial de telas, jornadas, serviços, segurança e compatibilidade do banco/backup.

## Relacionados

- [[specs/migracao-v4-nextjs-fastapi]]
- [[04_arquitetura]]
- [[03_spec]]
- [[specs/backup-e-restauracao]]
- [[specs/autenticacao-e-sessao]]
