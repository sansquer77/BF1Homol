---
tipo: produto
area: bf1
status: em-implementacao
versao: 5.4
atualizado: 2026-09-19
relacionados: ["[[01_necessidade]]", "[[02_regras_de_negocio]]", "[[03_spec]]", "[[04_arquitetura]]", "[[specs/migracao-v4-nextjs-fastapi]]"]
tags: [produto, "area/bf1", "status/em-implementacao"]
aliases: ["Documento de Projeto"]
---

# Documento de Projeto — BF1

> [!info] Status
> **em-implementacao** · área: `bf1` · atualizado em 2026-09-19 · relacionados: [[04_arquitetura]], [[specs/migracao-v4-nextjs-fastapi]]

## Estado do produto

O BF1 é um bolão privado de Fórmula 1. A produção 3.x continua sendo o baseline
de compatibilidade; a homologação executa a V4, com frontend Next.js e API
FastAPI. PostgreSQL e os backups SQL/Excel da V3.x são contratos primários e
não podem ser quebrados.

- Versão de produto vigente no código: `app_version.py::APP_VERSION`.
- Versão-alvo da migração: `4.0.0`.
- Deploy: DigitalOcean App Platform, mesma origem pública e dois componentes.
- Acesso: somente por convite; Master cria e administra usuários.

## Escopo funcional

Estão implementados na V4: autenticação e recuperação de senha, Telemetria,
apostas, calendário, classificação, análises, campeonato, Hall da Fama,
Dashboard F1, logs, conteúdo institucional e operações administrativas de
usuários, pilotos, equipes, provas, resultados, Hall, financeiro, regras e
backup/restore. Backup e restore SQL/Excel foram confirmados funcionais em
homologação.

A Classificação usa cache em memória por temporada com TTL de cinco minutos,
resumo e histórico em contratos separados e aquecimento após o processamento
de resultados. O gate aquecido de 25 usuários simultâneos foi aprovado com
erro de 0% e p95 de 377,835 ms, encerrando a Fase 9.

## Stack vigente da V4

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 16, React 19 e TypeScript, App Router |
| Gráficos | ApexCharts por adaptador compartilhado |
| Backend | FastAPI e Uvicorn em `/api/v1` |
| Domínio | Python em `services/` |
| Dados | PostgreSQL, psycopg 3 e pool gerenciado |
| Autenticação | bcrypt, JWT revogável, cookies HttpOnly e CSRF |
| Arquivos | pandas e openpyxl para compatibilidade Excel |
| Deploy | DigitalOcean App Platform |

`requirements-api.txt` define o runtime Python V4 e `frontend/package.json`
define o runtime web. `requirements.txt`, `main.py` e `ui/` documentam e
suportam o baseline V3, mas não fazem parte do runtime V4.

## Qualidade e gates

- Regras canônicas permanecem em [[02_regras_de_negocio]].
- Specs focadas definem os critérios; testes são a fonte executável.
- Migrations são incrementais e idempotentes.
- Nenhum segredo, senha, JWT ou conteúdo integral de backup é registrado.
- Metas da V4: API p95 abaixo de 400 ms em leitura e 700 ms em escrita comum;
  25 usuários simultâneos; LCP abaixo de 2,5 s; CLS abaixo de 0,1; WCAG 2.2 AA.

## Próximas entregas

1. Validar builds limpos, rollback, cutover e observação da operação na Fase 10.

## Changelog

- `5.4` — 2026-09-19 — Fase 9 concluída com gate de 25 VUs, acessibilidade e responsividade aprovados.

- `5.3` — 2026-09-19 — Gate da Fase 9 calibrado para 25 usuários simultâneos.

- `5.2` — 2026-09-16 — Escopo funcional reconciliado; cache da Classificação e pendência de novo gate de carga registrados.
- `5.1` — 2026-09-12 — Fase 8 atualizada como concluída após confirmação do backup/restore Excel.
- `5.0` — 2026-09-12 — Documento reconciliado com a arquitetura V4 Next.js/FastAPI, status real dos módulos e pendências de homologação.
- `4.1` — 2026-07-31 — Governança SDD e stack PostgreSQL/psycopg 3 documentadas para o baseline V3.

## Relacionados

- [[01_necessidade]]
- [[02_regras_de_negocio]]
- [[03_spec]]
- [[04_arquitetura]]
- [[specs/migracao-v4-nextjs-fastapi]]
