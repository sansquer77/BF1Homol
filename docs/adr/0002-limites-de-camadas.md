---
tipo: adr
area: arquitetura
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados:
  - "[[04_arquitetura]]"
  - "[[06_modulos_tecnicos]]"
  - "[[specs/classificacao]]"
tags: [adr, "area/arquitetura", "status/implementado"]
aliases: ["ADR-0002 Limites de Camadas"]
---

# ADR-0002 — Limites entre UI, serviços e banco

> [!info] Status
> **implementado** · área: `arquitetura` · atualizado em 2026-07-31 · relacionados: [[04_arquitetura]], [[06_modulos_tecnicos]], [[specs/classificacao]]

## Contexto

O código legado concentrou renderização, regras e SQL em algumas telas. Isso
dificulta testes, cache seletivo e uma possível camada de API futura.

## Decisão

- `ui/`: widgets, apresentação e orquestração da jornada.
- `services/`: regras, autorização e casos de uso sem Streamlit.
- `db/`: conexões, migrations e repositórios PostgreSQL.
- `utils/`: funções puras e transversais, sem banco ou UI.
- `app_runtime.py`: ponte explícita para contexto de sessão e requisição.

## Alternativas consideradas

- Manter SQL nas telas: menor esforço imediato, mas amplia acoplamento.
- Fazer serviços dependerem de Streamlit: simplifica cache no curto prazo, mas
  impede testes e novos adaptadores de entrega.

## Consequências

- Novas regras são testáveis sem simular reruns.
- Cache interno usa abstração neutra e invalidação por domínio.
- Código legado que viola a fronteira deve ser migrado gradualmente, sem
  reescrita ampla não relacionada à entrega corrente.

## Critérios de revisão

Uma futura API pode adicionar outro adaptador de entrega, sem mover regras para
FastAPI nem transformar a API na fonte do domínio.

## Changelog

- `1.0` — 2026-07-31 — Fronteiras já adotadas pelo projeto formalizadas.

## Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
- [[specs/classificacao]]

