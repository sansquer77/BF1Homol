---
tipo: arquitetura
area: bf1
status: implementado
versao: 4.0
atualizado: 2026-09-19
relacionados:
  - "[[04_arquitetura]]"
  - "[[06_modulos_tecnicos]]"
tags: [arquitetura, "area/bf1", "status/implementado"]
aliases: ["Mapa Mental dos Módulos"]
---

# Mapa dos módulos BF1 V4

> [!info] Status
> **implementado** · área: `bf1` · atualizado em 2026-09-19 · runtime único V4.

```text
frontend/
├─ app/                 rotas, layouts, metadata e páginas
├─ components/          telas, formulários, navegação e ApexCharts
└─ lib/
   ├─ api/              cliente e tipos OpenAPI
   ├─ season-context    temporada global do bolão
   └─ timezone-context  preferência de apresentação
        │ HTTPS /api/v1
api/
├─ main.py              aplicação, lifespan e middleware
├─ routes/              contratos HTTP por domínio
├─ schemas.py           validação e serialização
└─ dependencies.py      sessão e contexto autenticado
        │
services/
├─ access_control       autorização por perfil/objeto/temporada
├─ bets_*               regras, escrita, pontuação e análises
├─ classification_*     classificação, histórico, cache e PNG
├─ *_v4_service         casos de uso das jornadas V4
└─ auth/email/weather   capacidades transversais de domínio
        │
db/
├─ connection_pool      pool psycopg 3
├─ repo_*               consultas e escritas
├─ migrations*          evolução idempotente
└─ backup_*             SQL/Excel, validação e restore
        │
PostgreSQL 18
```

## Regras de dependência

1. O frontend acessa somente `/api/v1`.
2. Rotas não executam SQL nem recalculam regras de domínio.
3. Serviços não dependem do frontend.
4. Repositórios não autorizam usuários; recebem operações já autorizadas.
5. Utilitários não acessam o banco.

## Changelog

- `4.0` — 2026-09-19 — Mapa refeito para o runtime exclusivo Next.js/FastAPI.

## Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
- [[adr/0002-limites-de-camadas]]
