---
tipo: spec
area: migracao-v4
status: em-implementacao
versao: 1.1
atualizado: 2026-09-08
relacionados:
  - "[[inventario-v4]]"
  - "[[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]]"
  - "[[04_arquitetura]]"
tags: [spec, "area/migracao-v4", "status/em-implementacao"]
aliases: ["Migração BF1 4.0 para Next.js e FastAPI"]
---

# Migração BF1 4.0 para Next.js e FastAPI

> [!info] Status
> **em-implementacao** · área: `migracao-v4` · atualizado em 2026-09-08 · relacionados: [[inventario-v4]], [[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]], [[04_arquitetura]]

## Problema

O frontend Streamlit limita responsividade, composição visual e evolução da
experiência. A versão 4 separa entrega web e API sem reescrever as regras Python
nem quebrar a restauração dos backups e o banco PostgreSQL existentes.

## Usuários

Todos os perfis atuais (`master`, `admin`, `participante`, `inativo`) e a
operação responsável por deploy, observabilidade e restauração.

## Jornada

1. O usuário acessa o frontend responsivo Next.js.
2. O frontend autentica pela API FastAPI e recebe sessão protegida por cookie.
3. Cada página consulta ou altera recursos por contratos HTTP versionados.
4. FastAPI resolve identidade, autoriza a operação/objeto e chama os serviços Python existentes.
5. Os serviços usam os adaptadores PostgreSQL compatíveis e registram auditoria e observabilidade estruturada.

## Dados

- PostgreSQL atual: fonte de verdade e contrato primário de compatibilidade.
- Backups SQL e Excel atuais: entradas que a versão 4 deve restaurar.
- API: JSON com schemas explícitos, datas ISO 8601 e erros sem detalhes sensíveis.
- Sessão: identificador/token em cookie `Secure`, `HttpOnly`, com rotação e revogação.
- Logs: registros estruturados no PostgreSQL, exportáveis sob demanda em JSON Lines compactado.
- Bootstrap Master: `EMAIL_MASTER`, `SENHA_MASTER` e `USUARIO_MASTER` fornecidos
  como segredos/variáveis do ambiente DigitalOcean.

## Regras

1. Nenhuma etapa pode impedir a restauração de backups 3.x suportados.
2. Regras de domínio permanecem em `services/`; handlers FastAPI apenas validam, autorizam, orquestram e serializam.
3. SQL e persistência permanecem em `db/`/repositórios; o frontend nunca acessa o banco.
4. Next.js usa App Router e TypeScript; componentes client-side ficam restritos à interatividade necessária.
5. Todos os gráficos usam ApexCharts por um adaptador compartilhado e responsivo.
6. Autorização ocorre por rota, operação, objeto e temporada, revalidando o usuário no servidor para impedir IDOR.
7. Login e recuperação mitigam enumeração e força bruta e preservam compatibilidade com bcrypt.
8. Mutações autenticadas por cookie possuem proteção CSRF e validação de origem.
9. Logs operacionais no PostgreSQL não substituem as trilhas de auditoria de domínio existentes.
10. Cada área é implementada isoladamente e só é considerada concluída após paridade automatizada e verificação mobile.
11. A versão 4 é uma aplicação limpa, sem runtime, rota, dependência ou mecanismo de sessão do Streamlit.
12. Datas/deadlines continuam usando `America/Sao_Paulo`; timezone do cliente altera apenas apresentação.
13. Frontend e API são publicados pela mesma origem; o ingresso encaminha `/api/*` ao FastAPI e as demais rotas ao Next.js.
14. Não existe cadastro público: somente o Master autenticado cria e administra usuários convidados.
15. No bootstrap, se ainda não existir usuário Master, o backend cria um usando `EMAIL_MASTER`, `SENHA_MASTER` e `USUARIO_MASTER`; reinícios nunca redefinem a senha de um Master existente e nenhum desses valores é registrado em logs. Os nomes permanecem idênticos aos usados atualmente na DigitalOcean.
16. A sessão usa cookie `Secure`, `HttpOnly`, `SameSite=Lax`, validade de duas horas e rotação durante atividade; há uma sessão ativa por usuário, troca de senha revoga todas as sessões e operações críticas exigem reautenticação.
17. OIDC não integra a primeira entrega da versão 4; a arquitetura não impede inclusão opcional futura, sem substituir o acesso por convite e senha.
18. Aplicação, acesso HTTP, segurança e erros geram registros estruturados no PostgreSQL com retenção inicial de 30 dias; falhas anteriores à conexão ou do próprio banco permanecem em `stdout/stderr`.
19. O Master pode baixar uma exportação de logs gerada sob demanda por endpoint com reautenticação, intervalo e volume limitados; a API nunca aceita caminho arbitrário.
20. A identidade visual preserva a marca BF1; cores, tipografia, densidade e
    composição podem mudar quando houver ganho demonstrável de UX.
21. A interface é mobile-first e busca WCAG 2.2 AA, incluindo teclado, foco,
    contraste e alternativas textuais para visualizações.
22. A V4 usa o design system **Apex Paddock UI**: superfícies grafite, vermelho
    de corrida como ação primária, verde apenas para estados positivos/ativos,
    ícone oficial BF1 e tipografia de telemetria. O antigo “Painel do
    Participante” é apresentado como **Telemetria**.
23. Pilotos exibidos em seletores, apostas, resultados e classificações têm
    marcador de equipe ao lado do nome. A cor complementa — e nunca substitui —
    o nome textual/acessível da equipe.

## Metas não funcionais aprovadas

- API: p95 menor que 400 ms em leituras e 700 ms em escritas comuns, com taxa
  de erro inferior a 1% no cenário representativo.
- Carga inicial de homologação: 100 usuários simultâneos.
- Web: LCP menor que 2,5 s e CLS menor que 0,1 nas jornadas prioritárias.
- Compatibilidade: duas versões mais recentes de Chrome, Edge, Firefox e Safari.
- Responsividade: viewport mínimo de 360 px sem rolagem horizontal da página.

## Interface, serviços e dados

- Frontend: `frontend/`, Next.js App Router/TypeScript, layout mobile-first.
- Backend: `api/`, FastAPI, schemas e dependências de autenticação/autorização.
- Domínio: `services/` reutilizado e progressivamente desacoplado de estado de UI.
- Dados: `db/` reutilizado; migrations aditivas e idempotentes.
- API: prefixo `/api/v1`; OpenAPI é contrato de integração e gera/verifica tipos do cliente.

## Critérios de aceite

1. Dado um backup SQL 3.x válido, quando restaurado em banco vazio da versão 4, então todas as verificações de schema, integridade e jornadas de fumaça passam sem edição manual.
2. Dado um backup Excel suportado, quando restaurado, então dados, FKs e sequences permanecem consistentes.
3. Dado o banco atual antes de uma migration, quando a migration roda duas vezes, então não há perda, duplicação nem falha na segunda execução.
4. Dado qualquer perfil, quando navega pela versão 4, então vê somente as áreas previstas na matriz vigente.
5. Dado um ID pertencente a outro usuário ou temporada, quando um cliente tenta leitura ou mutação direta, então a API nega sem revelar o recurso.
6. Dado email inexistente ou senha inválida, quando ocorre login/recuperação, então a resposta pública não permite enumerar contas.
7. Dadas tentativas excedentes por IP ou identificador, quando novo login ocorre, então o limite é aplicado no servidor e auditado sem senha/token.
8. Dada sessão revogada, expirada ou com versão antiga, quando uma rota protegida é chamada, então a API rejeita e o frontend volta ao login.
9. Dada uma mutação sem CSRF/origem válida, quando enviada com cookie, então a API a rejeita.
10. Dada uma regra de aposta, pontuação, descarte ou deadline já caracterizada, quando executada pela API, então o resultado é idêntico ao baseline 3.x.
11. Dado viewport de 360 px, quando uma jornada prioritária é usada, então não há rolagem horizontal da página e alvos interativos permanecem utilizáveis.
12. Dado um gráfico, quando o contêiner muda de tamanho, então ApexCharts se ajusta sem perder legenda/dados e existe alternativa textual acessível.
13. Dada uma requisição, quando termina, então logs correlacionáveis registram status e duração sem conteúdo sensível.
14. Dada falha não tratada, quando ocorre, então o cliente recebe erro opaco com `request_id` e o servidor registra o erro sanitizado, usando `stdout/stderr` como contingência se o banco estiver indisponível.
15. Dada a meta de carga definida antes do cutover, quando o cenário representativo é executado, então latência, erros e saturação ficam dentro dos limites aprovados.
16. Dado o artefato da versão 4, quando dependências e imports são inspecionados, então não existe dependência de Streamlit nem código de compatibilidade com sua sessão/UI.
17. Dado o primeiro bootstrap sem Master, quando as três variáveis obrigatórias estão válidas, então exatamente um Master é criado; em reinícios, suas credenciais persistidas não são alteradas.
18. Dado usuário não Master, quando tenta listar ou baixar logs por chamada direta, então recebe acesso negado sem metadados do arquivo.
19. Dado Master reautenticado, quando baixa um log permitido, então recebe somente o arquivo solicitado, com nome seguro e auditoria da operação.
20. Dada a tela pública de login, quando acessada, então não existe fluxo de criação de conta e respostas de login/recuperação não enumeram convidados.
21. Dada uma tela V4 de participante, quando renderizada, então usa o ícone
    oficial, a navegação “Telemetria” e a hierarquia visual Apex Paddock sem
    verde como ação primária.
22. Dado um piloto associado a uma equipe, quando seu nome é apresentado em
    contexto esportivo, então existe marcador com a paleta da equipe e seu nome
    continua disponível em texto ou nome acessível.

## Verificação

- Critérios 1–3 — suíte de compatibilidade em PostgreSQL efêmero com fixtures versionadas.
- Critérios 4–10 — testes unitários/de integração da API e regressão dos serviços.
- Critérios 11–12 — testes E2E em viewports mobile/tablet/desktop e auditoria de acessibilidade.
- Critérios 13–15 — testes de redaction, falha, carga e inspeção dos artefatos operacionais.
- Critério 16 — teste arquitetural de dependências/imports e build limpo dos dois runtimes.
- Critério 17 — integração do bootstrap em banco vazio e reinicializado.
- Critérios 18–19 — testes de autorização, path traversal, reautenticação, limites e auditoria do download.
- Critério 20 — teste E2E da tela pública e testes de respostas indistinguíveis.
- Critérios 21–22 — testes de contrato visual e E2E com inspeção acessível em
  viewports mobile e desktop.

## Pendências

> [!question] Pendências
> As decisões de produto e arquitetura necessárias ao scaffold foram aprovadas.

- Fase 5: substituir os dados demonstrativos do shell por conteúdo e consultas
  reais de Sobre, Regulamento, Calendário e Telemetria.
- A retenção poderá ser ajustada após observar o volume real, sem reduzir os controles de acesso, sanitização e exportação.

## Fora de escopo

- Mudança das regras do bolão durante a migração técnica.
- Substituição do PostgreSQL ou alteração destrutiva do formato legado.
- Tornar OIDC obrigatório.
- Aplicativo móvel nativo.
- Cadastro público de usuários e OIDC na primeira entrega.

## Plano de implementação

- [x] Fase 1 — inventário congelado; fixtures SQL e 21 Excel anonimizadas e versionadas; restores reais aprovados no PostgreSQL 18.6; contrato reconstruído de schema versionado e estável após migrations repetidas. Fecha: critérios 1–3.
- [x] Fase 2 — baseline de 126 testes e 139 subtestes aprovada e congelada por domínio em `tests/characterization_v4.json`. Fecha: critérios 4 e 10 no comportamento legado; autorização HTTP será ampliada na Fase 3.
- [x] Fase 3 — FastAPI e contratos `/api/v1` implementados com contexto correlacionável por requisição, autenticação por cookie revogável, rotação ativa, proteção de origem/CSRF, mitigação de enumeração e força bruta, autorização opaca por usuário/temporada, bootstrap Master transacional e observabilidade PostgreSQL exportável com reautenticação. Gates de integração aprovados. Fecha: critérios 5–9, 13, 14 e 17–20.
- [x] Fase 4 — frontend Next.js 16/App Router e TypeScript criado com design system Apex Paddock UI mobile-first, ícone oficial BF1, login exclusivo para convidados, shell responsivo, cliente regenerável pelo OpenAPI versionado e adaptador ApexCharts carregado sob demanda com tabela acessível. O Painel do Participante passa a se chamar Telemetria e pilotos recebem marcadores acessíveis de equipe. Build de produção aprovado; dashboard, login, menu e ausência de overflow validados manualmente em 360 px. Fecha: critérios 11, 12, 21 e 22 na fundação visual.
- [ ] Fase 5 — migrar conteúdo e consultas simples (Sobre, Regulamento, Calendário e Telemetria). Fecha parte dos critérios 4, 10–12.
- [ ] Fase 6 — migrar acompanhamento e gráficos (Análise, Logs, Classificação, Hall, Dashboard e Campeonato). Fecha critérios 4, 10 e 12.
- [ ] Fase 7 — migrar operações administrativas e autorização por objeto. Fecha critérios 4 e 5.
- [ ] Fase 8 — validar backup/restauração e recuperação a partir do último artefato estável. Fecha critérios 1–3.
- [ ] Fase 9 — executar segurança, carga, acessibilidade e experiência mobile. Fecha critérios 5–9, 11–15 e 18–20.
- [ ] Fase 10 — validar builds puros, publicar a V4 e observar a operação. Fecha critério 16.

## Changelog

- `1.1` — 2026-09-08 — Design system Apex Paddock UI adotado com ícone oficial, paleta grafite/vermelha, tipografia própria, novo nome Telemetria e marcadores de equipe acessíveis.
- `1.0` — 2026-09-08 — Fase 4 concluída: Next.js responsivo, design system, login, cliente OpenAPI tipado e adaptador ApexCharts acessível aprovados em build e viewport de 360 px.
- `0.9` — 2026-09-08 — Fase 3 concluída: gates de IDOR, sessão, força bruta, CSRF, bootstrap Master, correlação/erro opaco e exportação administrativa de logs aprovados.
- `0.8` — 2026-09-07 — Fase 1 concluída: 21 fixtures Excel/3.904 linhas restauradas, contrato de schema reconstruído congelado e duas incompatibilidades do restore corrigidas.
- `0.7` — 2026-09-07 — Status consolidado: inventário implementado, 21 exportações Excel recebidas, Fase 1 em validação final e Fase 3 em implementação.
- `0.6` — 2026-09-06 — Observabilidade movida para o PostgreSQL por decisão explícita de custo, com exportação sob demanda e contingência em stdout/stderr.
- `0.5` — 2026-09-06 — Baseline de caracterização congelada por domínio com 126 testes e 139 subtestes aprovados.
- `0.4` — 2026-09-06 — Restore da fixture V3.5.0 validado em PostgreSQL 18.6, incluindo contagens, FKs, sequences, bcrypt, tipos nativos e idempotência das migrations.
- `0.3` — 2026-09-06 — Fechadas compatibilidade V3.x, sessão, acesso somente por convite, logs baixáveis pelo Master, metas de qualidade, direção visual e bootstrap Master por ambiente.
- `0.2` — 2026-09-06 — Aprovadas mesma origem com `/api` e implementação V4 sem convivência ou dependência de Streamlit.
- `0.1` — 2026-09-06 — Visão, contratos, critérios e fases iniciais da migração 4.0.

## Relacionados

- [[inventario-v4]]
- [[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]]
- [[specs/autenticacao-e-sessao]]
- [[specs/backup-e-restauracao]]
- [[04_arquitetura]]
