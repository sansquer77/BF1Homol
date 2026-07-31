---
tipo: adr
area: arquitetura
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados:
  - "[[04_arquitetura]]"
  - "[[05_projeto]]"
  - "[[07_guia_deploy]]"
tags: [adr, "area/arquitetura", "status/implementado"]
aliases: ["ADR-0001 Streamlit e PostgreSQL"]
---

# ADR-0001 — Streamlit e PostgreSQL gerenciado

> [!info] Status
> **implementado** · área: `arquitetura` · atualizado em 2026-07-31 · relacionados: [[04_arquitetura]], [[05_projeto]], [[07_guia_deploy]]

## Contexto

O BF1 atende um grupo fechado, possui regras intensivas em Python/pandas e
precisa de deploy simples, dados compartilhados e histórico multi-temporada.

## Decisão

- Manter Streamlit como camada web full-stack.
- Usar PostgreSQL gerenciado como fonte de verdade.
- Usar `psycopg` 3 e pool de conexões.
- Hospedar o serviço na DigitalOcean App Platform.

## Alternativas consideradas

- Frontend JavaScript + API FastAPI: maior flexibilidade, porém exige duas
  camadas de entrega, contrato HTTP e migração ampla das telas.
- SQLite local: inadequado ao acesso concorrente e ao deploy gerenciado atual.

## Consequências

- Reruns e consultas precisam ser controlados com cache e carregamento tardio.
- Regras devem permanecer desacopladas do Streamlit para permitir testes e uma
  API futura sem reescrever o domínio.
- PostgreSQL e variáveis de ambiente fazem parte do ambiente obrigatório.

## Critérios de revisão

Reavaliar quando limitações de UX, concorrência ou integração externa
justificarem uma API e frontend separados.

## Changelog

- `1.0` — 2026-07-31 — Decisão arquitetural vigente formalizada.

## Relacionados

- [[04_arquitetura]]
- [[05_projeto]]
- [[07_guia_deploy]]

