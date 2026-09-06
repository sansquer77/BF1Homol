---
tipo: adr
area: arquitetura
status: implementado
versao: 1.0
atualizado: 2026-09-06
relacionados:
  - "[[specs/migracao-v4-nextjs-fastapi]]"
  - "[[inventario-v4]]"
  - "[[adr/0001-streamlit-postgresql]]"
tags: [adr, "area/arquitetura", "status/implementado"]
aliases: ["ADR-0003 Next.js, FastAPI e compatibilidade de dados"]
---

# ADR-0003 — Next.js, FastAPI e compatibilidade de dados

> [!info] Status
> **implementado** · área: `arquitetura` · atualizado em 2026-09-06 · relacionados: [[specs/migracao-v4-nextjs-fastapi]], [[inventario-v4]], [[adr/0001-streamlit-postgresql]]

## Contexto

As limitações de responsividade e composição visual atingiram o critério de
revisão do ADR-0001. A aplicação já possui regras Python parcialmente separadas
da UI e precisa preservar o PostgreSQL e a restauração dos backups existentes
como regra primária da versão 4.

## Decisão

- Construir a versão 4 como aplicação limpa com Next.js App Router/TypeScript
  no frontend e FastAPI no backend, sem runtime ou compatibilidade de UI/sessão
  do Streamlit.
- Manter `services/` como núcleo das regras e `db/` como persistência, usando a
  API como adaptador de entrega, conforme os limites do ADR-0002.
- Manter PostgreSQL como única fonte de verdade e tratar o formato de backup
  3.x suportado como contrato de entrada versionado.
- Evoluir o schema por migrations aditivas/idempotentes; colunas legadas ficam
  disponíveis até existir conversor e retirada formalmente aprovados.
- Hospedar frontend e API sob a mesma origem, com o ingresso encaminhando
  `/api/*` ao FastAPI e as demais rotas ao Next.js, simplificando cookies, CORS
  e CSRF.
- Usar sessão em cookie seguro e revogável; autorização por objeto e temporada
  ocorre nos serviços, não no frontend.
- Usar ApexCharts por um componente compartilhado no frontend.
- Registrar aplicação, acesso, segurança e erros em arquivos estruturados com
  rotação e download administrativo protegido; manter auditoria de domínio no PostgreSQL.
- Implementar e validar por área; o rollback operacional usa o último artefato
  estável e o backup compatível, não uma instalação Streamlit paralela.
- Manter autenticação por convite, sem cadastro público, e criar o primeiro
  Master de forma idempotente pelas variáveis seguras da DigitalOcean.

## Alternativas consideradas

- Reescrever também as regras em TypeScript: rejeitada por duplicar o domínio e
  elevar o risco de divergência de pontuação/deadlines.
- Criar um banco novo e importar os dados: rejeitada por violar a regra primária
  e tornar restauração/rollback mais frágeis.
- Conversão imediata das colunas TEXT para tipos nativos: rejeitada; colunas
  paralelas preservam o contrato atual e permitem validação gradual.
- Migração big-bang: rejeitada pela superfície de 20 telas, operações sensíveis
  e criticidade de backup.

## Consequências

- O repositório passa a ter dois runtimes e um contrato HTTP versionado.
- Testes de caracterização tornam-se gate de cada área e do cutover.
- Parte das regras ainda presente em `ui/` terá de migrar para serviços antes de
  receber endpoints.
- Deploy, health checks, logs persistentes e correlação entre runtimes exigem
  configuração operacional adicional.
- Não haverá fallback de interface para Streamlit neste ambiente; a cobertura de
  caracterização e o ensaio de restauração tornam-se gates ainda mais fortes.

## Critérios de revisão

Revisar antes do deploy se a DigitalOcean não suportar persistência/rotação de
arquivos na topologia escolhida. Revisar a retirada de
qualquer coluna/formato legado somente após a janela de compatibilidade e um
conversor de backup aprovado.

## Pendências

- Nenhuma pendência arquitetural bloqueante conhecida.

## Changelog

- `1.0` — 2026-09-06 — Decisão aprovada, incluindo convite, bootstrap Master, política de sessão, logs e compatibilidade integral dos backups V3.x suportados.
- `0.2` — 2026-09-06 — Aprovadas mesma origem com `/api` e V4 pura sem dependência ou convivência com Streamlit.
- `0.1` — 2026-09-06 — Decisão arquitetural proposta para a versão 4.

## Relacionados

- [[specs/migracao-v4-nextjs-fastapi]]
- [[inventario-v4]]
- [[adr/0001-streamlit-postgresql]]
- [[adr/0002-limites-de-camadas]]
