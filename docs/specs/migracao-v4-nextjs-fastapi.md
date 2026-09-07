---
tipo: spec
area: migracao-v4
status: em-implementacao
versao: 0.4
atualizado: 2026-09-06
relacionados:
  - "[[inventario-v4]]"
  - "[[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]]"
  - "[[04_arquitetura]]"
tags: [spec, "area/migracao-v4", "status/em-implementacao"]
aliases: ["Migração BF1 4.0 para Next.js e FastAPI"]
---

# Migração BF1 4.0 para Next.js e FastAPI

> [!info] Status
> **em-implementacao** · área: `migracao-v4` · atualizado em 2026-09-06 · relacionados: [[inventario-v4]], [[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]], [[04_arquitetura]]

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
5. Os serviços usam os adaptadores PostgreSQL compatíveis e registram auditoria; a infraestrutura registra logs, métricas e erros em arquivos.

## Dados

- PostgreSQL atual: fonte de verdade e contrato primário de compatibilidade.
- Backups SQL e Excel atuais: entradas que a versão 4 deve restaurar.
- API: JSON com schemas explícitos, datas ISO 8601 e erros sem detalhes sensíveis.
- Sessão: identificador/token em cookie `Secure`, `HttpOnly`, com rotação e revogação.
- Logs: JSON Lines em arquivos persistentes com rotação e retenção.
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
9. Logs e métricas em arquivo não substituem logs de auditoria do domínio no PostgreSQL.
10. Cada área é implementada isoladamente e só é considerada concluída após paridade automatizada e verificação mobile.
11. A versão 4 é uma aplicação limpa, sem runtime, rota, dependência ou mecanismo de sessão do Streamlit.
12. Datas/deadlines continuam usando `America/Sao_Paulo`; timezone do cliente altera apenas apresentação.
13. Frontend e API são publicados pela mesma origem; o ingresso encaminha `/api/*` ao FastAPI e as demais rotas ao Next.js.
14. Não existe cadastro público: somente o Master autenticado cria e administra usuários convidados.
15. No bootstrap, se ainda não existir usuário Master, o backend cria um usando `EMAIL_MASTER`, `SENHA_MASTER` e `USUARIO_MASTER`; reinícios nunca redefinem a senha de um Master existente e nenhum desses valores é registrado em logs. Os nomes permanecem idênticos aos usados atualmente na DigitalOcean.
16. A sessão usa cookie `Secure`, `HttpOnly`, `SameSite=Lax`, validade de duas horas e rotação durante atividade; há uma sessão ativa por usuário, troca de senha revoga todas as sessões e operações críticas exigem reautenticação.
17. OIDC não integra a primeira entrega da versão 4; a arquitetura não impede inclusão opcional futura, sem substituir o acesso por convite e senha.
18. Arquivos de aplicação, acesso, segurança e erro usam JSON Lines em volume persistente, rotação diária ou a 100 MB e retenção de 30 dias.
19. O Master pode baixar arquivos de log por endpoint com reautenticação, allowlist de arquivos e limites; a API nunca aceita caminho arbitrário.
20. A identidade visual preserva a marca BF1; cores, tipografia, densidade e
    composição podem mudar quando houver ganho demonstrável de UX.
21. A interface é mobile-first e busca WCAG 2.2 AA, incluindo teclado, foco,
    contraste e alternativas textuais para visualizações.

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
14. Dada falha não tratada, quando ocorre, então o cliente recebe erro opaco com `request_id` e o servidor registra stack trace no arquivo de erros.
15. Dada a meta de carga definida antes do cutover, quando o cenário representativo é executado, então latência, erros e saturação ficam dentro dos limites aprovados.
16. Dado o artefato da versão 4, quando dependências e imports são inspecionados, então não existe dependência de Streamlit nem código de compatibilidade com sua sessão/UI.
17. Dado o primeiro bootstrap sem Master, quando as três variáveis obrigatórias estão válidas, então exatamente um Master é criado; em reinícios, suas credenciais persistidas não são alteradas.
18. Dado usuário não Master, quando tenta listar ou baixar logs por chamada direta, então recebe acesso negado sem metadados do arquivo.
19. Dado Master reautenticado, quando baixa um log permitido, então recebe somente o arquivo solicitado, com nome seguro e auditoria da operação.
20. Dada a tela pública de login, quando acessada, então não existe fluxo de criação de conta e respostas de login/recuperação não enumeram convidados.

## Verificação

- Critérios 1–3 — suíte de compatibilidade em PostgreSQL efêmero com fixtures versionadas.
- Critérios 4–10 — testes unitários/de integração da API e regressão dos serviços.
- Critérios 11–12 — testes E2E em viewports mobile/tablet/desktop e auditoria de acessibilidade.
- Critérios 13–15 — testes de redaction, falha, carga e inspeção dos artefatos operacionais.
- Critério 16 — teste arquitetural de dependências/imports e build limpo dos dois runtimes.
- Critério 17 — integração do bootstrap em banco vazio e reinicializado.
- Critérios 18–19 — testes de autorização, path traversal, reautenticação, limites e auditoria do download.
- Critério 20 — teste E2E da tela pública e testes de respostas indistinguíveis.

## Pendências

> [!question] Pendências
> As decisões de produto e arquitetura necessárias ao scaffold foram aprovadas.

- Nenhuma pendência bloqueante conhecida.
- Detalhes físicos do volume/coleta de logs serão verificados contra a infraestrutura DigitalOcean durante a preparação do deploy, sem alterar o contrato funcional acima.

## Fora de escopo

- Mudança das regras do bolão durante a migração técnica.
- Substituição do PostgreSQL ou alteração destrutiva do formato legado.
- Tornar OIDC obrigatório.
- Aplicativo móvel nativo.
- Cadastro público de usuários e OIDC na primeira entrega.

## Plano de implementação

- [ ] Fase 1 — congelar inventário, snapshot do schema e fixtures de backup. Fixture SQL V3.5.0 anonimizada e restore real em PostgreSQL 18.6 concluídos; snapshot versionado e fixture Excel ainda pendentes. Fecha: critérios 1–3.
- [ ] Fase 2 — ampliar testes de caracterização de serviços e jornadas. Fecha: critérios 4 e 10.
- [ ] Fase 3 — criar FastAPI, contratos `/api/v1`, contexto por requisição, auth, bootstrap Master e observabilidade. Fecha: critérios 5–9, 13, 14 e 17–20.
- [ ] Fase 4 — criar Next.js responsivo, design system, cliente tipado e adaptador ApexCharts. Fecha: critérios 11 e 12.
- [ ] Fase 5 — migrar conteúdo e consultas simples (Sobre, Regulamento, Calendário e Painel). Fecha parte dos critérios 4, 10–12.
- [ ] Fase 6 — migrar acompanhamento e gráficos (Análise, Logs, Classificação, Hall, Dashboard e Campeonato). Fecha critérios 4, 10 e 12.
- [ ] Fase 7 — migrar operações administrativas e autorização por objeto. Fecha critérios 4 e 5.
- [ ] Fase 8 — validar backup/restauração e recuperação a partir do último artefato estável. Fecha critérios 1–3.
- [ ] Fase 9 — executar segurança, carga, acessibilidade e experiência mobile. Fecha critérios 5–9, 11–15 e 18–20.
- [ ] Fase 10 — validar builds puros, publicar a V4 e observar a operação. Fecha critério 16.

## Changelog

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
