---
tipo: adr
area: arquitetura
status: implementado
versao: 2.0
atualizado: 2026-09-19
relacionados:
  - "[[04_arquitetura]]"
  - "[[06_modulos_tecnicos]]"
tags: [adr, "area/arquitetura", "status/implementado"]
aliases: ["ADR-0002 Limites de Camadas"]
---

# ADR-0002 — Limites entre frontend, API, serviços e banco

> [!info] Status
> **implementado** · área: `arquitetura` · atualizado em 2026-09-19 · relacionados: [[04_arquitetura]], [[06_modulos_tecnicos]]

## Contexto

A aplicação precisa manter regras testáveis, autorização server-side e um
contrato PostgreSQL estável sem acoplar apresentação e persistência.

## Decisão

- `frontend/`: apresentação, interação e estado efêmero do cliente.
- `api/`: transporte HTTP, schemas, autenticação, autorização inicial e
  serialização; handlers não contêm SQL nem regras de pontuação.
- `services/`: regras, autorização por objeto e casos de uso.
- `db/`: conexões, migrations e repositórios PostgreSQL.
- `utils/`: funções puras ou transversais, sem persistência.
- `app_runtime.py`: contexto por requisição para compatibilidade entre serviços.

Escritas administrativas sempre passam pela autorização do serviço. Perfil,
usuário e temporada enviados pelo cliente nunca são fonte de autoridade.

## Consequências

- O frontend pode evoluir sem duplicar domínio.
- Serviços podem ser testados sem navegador.
- SQL fica auditável e centralizado.
- Caches são independentes do framework web e invalidados por domínio.

## Changelog

- `2.0` — 2026-09-19 — Fronteiras atualizadas para o runtime único Next.js/FastAPI.
- `1.0` — 2026-07-31 — Fronteiras iniciais formalizadas.

## Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
- [[specs/migracao-v4-nextjs-fastapi]]
