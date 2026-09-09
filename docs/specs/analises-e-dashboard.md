---
tipo: spec
area: analises
status: implementado
versao: 1.3
atualizado: 2026-09-09
relacionados: ["[[specs/apostas-de-prova]]", "[[specs/resultados-de-provas]]", "[[specs/classificacao]]"]
tags: [spec, "area/analises", "status/implementado"]
aliases: ["Análises e dashboard"]
---

# Análises e dashboard

> [!info] Status
> **implementado** · área: `analises` · atualizado em 2026-09-08 · relacionados: [[specs/apostas-de-prova]], [[specs/resultados-de-provas]], [[specs/classificacao]]

## Problema

Transformar apostas, resultados e classificação em visualizações operacionais sem duplicar regras de cálculo nem sobrecarregar cada rerun.

## Usuários

- Perfis autenticados: consultam visualizações permitidas pela matriz de acesso.
- Administrador e Master: usam filtros amplos para monitoramento.

## Jornada

1. O usuário abre Análise de Apostas ou Dashboard F1.
2. Seleciona temporada, prova e filtros disponíveis.
3. O sistema consulta dados sob demanda e renderiza tabelas, métricas e gráficos.

## Dados

- Apostas e resultado oficial da prova selecionada.
- Agregados por posição, piloto, participante, prova e temporada.
- Classificação e métricas derivadas das specs canônicas, sem nova persistência de domínio.

## Regras

1. O módulo é somente leitura e reutiliza cálculos dos serviços de apostas, resultados e classificação.
2. Filtros de temporada/prova limitam consultas antes da geração da visualização.
3. Se resultado ainda não existe, comparações dependentes são omitidas ou identificadas como indisponíveis.
4. DataFrames vazios mantêm colunas mínimas e produzem estado vazio compreensível.
5. Telas pesadas são carregadas apenas quando selecionadas; reruns não selecionados não executam suas consultas.
6. Cache usa namespace/tags do domínio e não mantém resultado obsoleto após escrita relacionada.
7. Visualizações não ampliam o escopo de dados autorizado ao perfil.
8. Admin e Master podem selecionar um participante da temporada; perfis individuais permanecem limitados ao próprio usuário.
9. O Dashboard F1 pagina todos os resultados da temporada pesquisada e mantém seletor histórico independente do contexto global do bolão.

## Interface, serviços e dados

- Telas: Monitoramento → Análise de Apostas, `/analises` na V4 e Dashboard F1.
- Serviços: `services/bets_analysis_service.py`, `services/f1_dashboard_service.py` e fachadas de leitura dos domínios fonte.
- Persistência: somente leitura das tabelas de apostas, resultados, provas, pilotos e usuários.
- API V4: `GET /api/v1/analysis/bets?season=YYYY`, com escopo individual para Participante/Inativo e consolidado para Admin/Master, e `GET /api/v1/f1-dashboard?season=YYYY` autenticado para estatísticas oficiais históricas.

## Critérios de aceite

1. Dada temporada/prova com dados, quando filtrar, então gráficos e tabelas refletem somente o recorte selecionado.
2. Dada prova sem resultado, quando analisar acertos, então a UI informa indisponibilidade sem fabricar valores.
3. Dado conjunto vazio, quando renderizar, então a tela não quebra e preserva contrato tabular.
4. Dada tela não selecionada, quando ocorrer rerun, então suas consultas pesadas não são disparadas.
5. Dado resultado ou aposta alterado, quando reabrir a análise, então o cache apresenta os novos dados.
6. Dado usuário com escopo restrito, quando acessar, então não recebe agregados que revelem dados fora do seu escopo.

## Verificação

- Critérios 3–6 — testes: `tests/test_apostas_dataframe_contract.py`, `tests/test_lazy_screen_loading.py`, `tests/test_performance_cache_namespace.py` e `tests/test_access_matrix.py`.
- Critérios 1 e 2 — verificação visual com uma prova concluída e outra pendente.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- BI externo, previsões estatísticas e edição de dados pelos gráficos.

## Changelog

- `1.3` — 2026-09-09 — Filtro autorizado de participante e paginação integral da progressão histórica do Dashboard F1.
- `1.2` — 2026-09-08 — Dashboard F1 V4 migrado para read model FastAPI, preservando o provedor Jolpica/Ergast da V3, gráficos ApexCharts e estados vazios acessíveis.
- `1.1` — 2026-09-08 — Análise de Apostas V4 migrada para FastAPI e ApexCharts, com escopo por perfil e marcadores de equipe.
- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/apostas-de-prova]]
- [[specs/resultados-de-provas]]
- [[specs/classificacao]]
