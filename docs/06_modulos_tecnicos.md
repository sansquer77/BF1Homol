---
tipo: arquitetura
area: bf1
status: em-implementacao
versao: 5.2
atualizado: 2026-09-16
relacionados: ["[[04_arquitetura]]", "[[05_projeto]]", "[[specs/migracao-v4-nextjs-fastapi]]"]
tags: [arquitetura, "area/bf1", "status/em-implementacao"]
aliases: ["Módulos Técnicos"]
---

# Módulos Técnicos — BF1 V4

> [!info] Status
> **em-implementacao** · área: `bf1` · atualizado em 2026-09-16 · Fases 1–8 concluídas; Fase 9 em validação e Fase 10 pendente.

## Entradas do runtime V4

- `api/main.py`: aplicação FastAPI, bootstrap, middleware e roteadores `/api/v1`.
- `frontend/src/app/`: rotas Next.js App Router.
- `frontend/src/components/`: shell, telas e componentes interativos.
- `frontend/src/lib/api/`: cliente HTTP e tipos derivados do OpenAPI.
- `frontend/src/lib/season/`: contexto global da temporada do bolão.

`main.py`, `ui/`, `.streamlit/` e o `requirements.txt` raiz representam o
runtime V3 de referência. Não são carregados pelos componentes V4.

## Backend

Os roteadores em `api/routes/` cobrem administração, análises, autenticação,
backup, calendário, campeonato, classificação, conteúdo, Dashboard F1, Hall da
Fama, logs, apostas por prova, Telemetria e usuários. Handlers validam e
autorizam; regras permanecem em `services/`; SQL e persistência em `db/`.

O contexto por requisição fornece identidade, temporada autorizada e
`request_id`. Sessão, CSRF, rate limiting, reautenticação e autorização por
objeto são aplicados no servidor, nunca derivados da apresentação.

## Frontend

As rotas cobrem login, Telemetria, apostas, calendário, classificação,
análises, campeonato, Hall da Fama, Dashboard F1, logs, Regulamento, Sobre e as
telas de Administração. ApexCharts é carregado por adaptador compartilhado e
todo gráfico deve possuir representação textual acessível.

O seletor de temporada do bolão usa um contexto global. O seletor histórico do
Dashboard F1 é local e independente por definição de produto.

## Classificação e cache

- `GET /api/v1/classification?season=YYYY` entrega apenas o resumo atual.
- `GET /api/v1/classification/history?season=YYYY` entrega comparativo e séries
  por prova; o frontend inicia essa leitura separadamente em paralelo ao resumo.
- `history=true` no endpoint principal preserva o contrato completo para
  consumidores compatíveis.
- `services/classification_service.py` compartilha a preparação dos DataFrames
  e mantém base, resumo e histórico em cache local por processo durante 300 s.
- Escritas V4 que afetam a classificação invalidam a tag `classificacao`; o
  processamento de resultado aquece novamente o snapshot completo.
- `BF1_TTL_CACHE_MAX_ENTRIES` limita o número de entradas do utilitário. O TTL
  da Classificação não é configurável no código vigente.

## Dados e continuidade

- `db/connection_pool.py`: pool psycopg 3.
- `db/migrations*.py`: evolução incremental e idempotente.
- `db/backup_restore.py`: compatibilidade SQL.
- `db/backup_excel.py`: catálogo, exportação, pré-validação e restore Excel.

O contrato Excel é um `.xlsx` por tabela, planilha `data`. Restore aplica
limites antes do processamento, seleciona tabelas em allowlist e trata FKs e
sequences. O round-trip real foi confirmado funcional em homologação.

## Dependências

- Python V4: `requirements-api.txt`.
- Web V4: `frontend/package.json` e lockfile pnpm.
- Contrato: `api/openapi-v1.json`, verificado contra os tipos do cliente.
- Deploy: `bf1homol-v4.yaml`.

## Lacunas conhecidas

1. Repetir o gate de carga depois do cache da Classificação e confirmar p95 e
   taxa de erro nas metas aprovadas.
2. Concluir acessibilidade e experiência mobile da Fase 9.
3. Executar os gates de cutover, observação e rollback da Fase 10.

## Changelog

- `5.2` — 2026-09-16 — Contratos, cache e invalidação da Classificação documentados; lacunas funcionais já concluídas removidas.
- `5.1` — 2026-09-12 — Gate operacional Excel encerrado e Fase 8 marcada como concluída.
- `5.0` — 2026-09-12 — Referência reescrita para os módulos Next.js/FastAPI e separação explícita do baseline Streamlit V3.
- `4.3` — 2026-07-31 — Limites de camadas do runtime V3 documentados.

## Relacionados

- [[04_arquitetura]]
- [[05_projeto]]
- [[specs/migracao-v4-nextjs-fastapi]]
