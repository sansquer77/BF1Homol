---
tipo: produto
area: meta
status: implementado
versao: 1.12
atualizado: 2026-09-12
relacionados:
  - "[[sdd]]"
  - "[[01_necessidade]]"
  - "[[03_spec]]"
  - "[[04_arquitetura]]"
tags: [produto, "area/meta", "status/implementado"]
aliases: ["Documentação BF1", "Map of Content"]
---

# Documentação BF1

> [!info] Status
> **implementado** · área: `meta` · atualizado em 2026-09-12 · relacionados: [[sdd]], [[01_necessidade]], [[03_spec]], [[04_arquitetura]]

Este é o ponto de entrada da documentação do BF1. O vault é compatível com
Obsidian e permanece legível no GitHub, IDEs e ferramentas de IA.

## Estado atual da migração V4

- Fases 1–8 concluídas; backup/restore SQL e Excel confirmados em homologação.
- Jornadas funcionais V4 concluídas, incluindo equipes e processamento de resultados.
- Fases 9 e 10 pendentes: segurança/carga/acessibilidade/mobile e cutover/observação.

## Comece aqui

| Documento | Finalidade |
|---|---|
| [[sdd]] | Processo de especificação, implementação e revisão |
| [[01_necessidade]] | Problema, público, escopo e valor do produto |
| [[02_regras_de_negocio]] | Regras canônicas e verificáveis do bolão |
| [[03_spec]] | Especificação funcional consolidada legada |
| [[04_arquitetura]] | Arquitetura, camadas, dados e decisões vigentes |
| [[05_projeto]] | Visão executiva, stack e qualidade |
| [[06_modulos_tecnicos]] | Referência dos módulos implementados |
| [[07_guia_deploy]] | Deploy e operação na DigitalOcean |
| [[PERFORMANCE]] | Metas, instrumentação e benchmark |
| [[MAPA_MENTAL_MODULOS]] | Relações entre componentes |
| [[glossario]] | Vocabulário de domínio |
| [[CHANGELOG]] | Versão vigente e histórico de releases do produto |
| [[inventario-v4]] | Inventário de telas, jornadas, serviços e contratos para a versão 4 |

## Especificações focadas

- [[specs/autenticacao-e-sessao|Autenticação e sessão]]
- [[specs/controle-de-acesso|Controle de acesso]]
- [[specs/apostas-de-prova|Apostas de prova]]
- [[specs/deadline-de-apostas|Deadline de apostas]]
- [[specs/pontuacao-de-provas|Pontuação de provas]]
- [[specs/resultados-de-provas|Resultados de provas]]
- [[specs/apostas-automaticas|Apostas automáticas]]
- [[specs/apostas-de-campeonato|Apostas de campeonato]]
- [[specs/classificacao|Classificação]]
- [[specs/gestao-de-usuarios|Gestão de usuários]]
- [[specs/gestao-de-temporadas-e-regras|Gestão de temporadas e regras]]
- [[specs/calendario-provas-e-pilotos|Calendário, provas e pilotos]]
- [[specs/historico-do-participante|Histórico do participante]]
- [[specs/logs-e-auditoria|Logs e auditoria]]
- [[specs/backup-e-restauracao|Backup e restauração]]
- [[specs/notificacoes-por-email|Notificações por email]]
- [[specs/analises-e-dashboard|Análises e dashboard]]
- [[specs/hall-da-fama|Hall da Fama]]
- [[specs/pwa-e-preferencias-do-cliente|PWA e preferências do cliente]]
- [[specs/temporada-global|Temporada global]]
- [[specs/migracao-v4-nextjs-fastapi|Migração BF1 4.0 para Next.js e FastAPI]]
- [[specs/conteudo-institucional-v4|Regulamento e Sobre da versão 4]]
- [[specs/telemetria-v4|Telemetria da versão 4]]
- [[specs/financeiro-da-temporada|Gestão financeira da temporada]]

Novas funcionalidades devem ganhar uma spec focada em `docs/specs/`. A
[[03_spec|spec consolidada]] continua como referência de compatibilidade até a
migração gradual de cada módulo.

## Decisões arquiteturais

- [[adr/0001-streamlit-postgresql|ADR-0001 — Streamlit e PostgreSQL gerenciado]]
- [[adr/0002-limites-de-camadas|ADR-0002 — Limites entre UI, serviços e banco]]
- [[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados|ADR-0003 — Next.js, FastAPI e compatibilidade de dados]]

## Governança

- Todo documento novo usa [[templates/spec-template|o template]].
- Frontmatter, callout de status, changelog e relacionados são obrigatórios.
- `app_version.py::APP_VERSION` define a versão do produto exibida em Sobre;
  `versao` no frontmatter controla somente a versão do respectivo documento.
- `AGENTS.md` resume as regras para agentes, mas `docs/` é canônico.
- Código e testes são a fonte executável; specs ancoram intenção e aceite.

## Changelog

- `1.12` — 2026-09-12 — Pendências funcionais de equipes e resultados encerradas; migração segue para validação não funcional.
- `1.11` — 2026-09-12 — Adicionada a spec da gestão financeira da temporada.
- `1.10` — 2026-09-12 — Fase 8 marcada como concluída após confirmação operacional do fluxo Excel.
- `1.9` — 2026-09-12 — Adicionado status consolidado da migração V4 e gate operacional do restore Excel.
- `1.8` — 2026-09-08 — Adicionada a spec da Telemetria V4 ao mapa canônico.
- `1.7` — 2026-09-06 — Aprovada a arquitetura V4 e registrada a primeira fonte de backup V3.5.0.
- `1.6` — 2026-09-06 — Adicionados inventário, spec e ADR proposto da migração 4.0.
- `1.5` — 2026-08-16 — Adicionada a spec de temporada global ao índice.
- `1.4` — 2026-07-31 — Adicionados política SemVer e changelog próprio do produto.
- `1.3` — 2026-07-31 — Documentada a separação entre versão do produto e versão dos documentos.
- `1.2` — 2026-07-31 — Dez módulos operacionais e de suporte adicionados ao índice.
- `1.1` — 2026-07-31 — Oito domínios críticos adicionados ao índice de specs focadas.
- `1.0` — 2026-07-31 — Criado o mapa de conteúdo e a navegação por specs e ADRs.

## Relacionados

- [[sdd]]
- [[templates/spec-template|Template documental]]
- [[glossario]]
