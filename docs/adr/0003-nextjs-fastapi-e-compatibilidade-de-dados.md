---
tipo: adr
area: arquitetura
status: implementado
versao: 2.0
atualizado: 2026-09-19
relacionados:
  - "[[specs/migracao-v4-nextjs-fastapi]]"
  - "[[inventario-v4]]"
  - "[[adr/0002-limites-de-camadas]]"
tags: [adr, "area/arquitetura", "status/implementado"]
aliases: ["ADR-0003 Next.js, FastAPI e compatibilidade de dados"]
---

# ADR-0003 — Next.js, FastAPI e compatibilidade de dados

> [!info] Status
> **implementado** · área: `arquitetura` · atualizado em 2026-09-19 · runtime V4 exclusivo.

## Contexto

O BF1 precisa de uma interface responsiva, contratos HTTP explícitos e
continuidade integral do PostgreSQL e dos backups já suportados.

## Decisão

- Next.js App Router/TypeScript é o único frontend.
- FastAPI é o único backend HTTP, sob `/api/v1`.
- `services/` preserva o domínio Python e `db/` a persistência PostgreSQL.
- Frontend e API operam na mesma origem.
- PostgreSQL permanece como única fonte de verdade.
- Backups SQL e Excel suportados continuam como contrato de entrada versionado.
- Migrations são aditivas e idempotentes.
- Sessão usa cookie seguro e revogável; autorização por objeto e temporada
  ocorre no servidor.
- ApexCharts é o adaptador compartilhado para gráficos.
- O rollback usa o último artefato V4 estável e backup compatível.

## Alternativas rejeitadas

- Reescrever regras em TypeScript: duplicaria o domínio.
- Criar outro banco: quebraria a regra primária de compatibilidade.
- Executar uploads SQL arbitrários: incompatível com a política fail-closed.
- Manter duas interfaces: ampliaria superfície de ataque, dependências e testes.

## Consequências

O repositório possui um único runtime web. A compatibilidade histórica é
garantida por dados, testes e fixtures, não por código de apresentação antigo.
O cutover exige build, health checks, restore e rollback do artefato V4.

## Changelog

- `2.0` — 2026-09-19 — Retirada da apresentação antiga e consolidação do runtime V4 exclusivo.
- `1.0` — 2026-09-06 — Arquitetura V4 aprovada.

## Relacionados

- [[specs/migracao-v4-nextjs-fastapi]]
- [[inventario-v4]]
- [[adr/0002-limites-de-camadas]]
