---
tipo: arquitetura
area: performance
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados:
  - "[[04_arquitetura]]"
  - "[[06_modulos_tecnicos]]"
  - "[[adr/0001-streamlit-postgresql]]"
tags: [arquitetura, "area/performance", "status/implementado"]
aliases: ["Performance e Jornadas Críticas"]
---

# Performance e jornadas críticas

> [!info] Status
> **implementado** · área: `performance` · atualizado em 2026-07-31 · relacionados: [[04_arquitetura]], [[06_modulos_tecnicos]], [[adr/0001-streamlit-postgresql]]

Metas operacionais:

- P95 das jornadas de leitura (`login`, `abertura_painel`, `classificacao`, `historico`) abaixo de 1 s.
- Downloads com renderização pesada, como a imagem da classificação, são gerados somente após ação explícita do usuário.
- Cada função de leitura possui namespace próprio no cache; resultados de provas, participantes, apostas e posições nunca compartilham entradas mesmo quando recebem a mesma temporada.
- `envio_aposta` abaixo de 1,5 s.
- Quantidade de queries constante em relação ao número de temporadas.
- Logs sempre filtrados e paginados (máximo de 500 linhas por página); dados
  brutos do histórico são filtrados por usuário e limitados a 5.000 linhas.

Cada jornada gera um evento JSON no logger `bf1.performance` com duração total,
quantidade e tempo de queries, linhas processadas, cache hit/miss e fingerprints
das consultas. O agregador de logs deve calcular P95 por campo `journey`.

## Otimizações implementadas

- Logs de acesso e apostas usam contagem e filtros no PostgreSQL antes de
  `LIMIT/OFFSET`; os totais representam todo o resultado e a página é ajustada
  automaticamente quando o conjunto diminui.

- Metadados estáveis de schema (`table_exists` e `get_table_columns`) são mantidos
  em memória e invalidados depois das migrations.
- Caches de leitura possuem tags por domínio (`apostas`, `provas`, `resultados`,
  `posicoes`, `usuarios`, `regras`, `championship`); escritas críticas invalidam
  somente os domínios afetados.
- Resultado e apostas de campeonato usados pela classificação possuem cache de
  leitura com TTL de 60 segundos.
- A seleção de participantes por temporada evita a consulta separada de
  contagem do histórico no caminho normal.
- O envio manual de aposta não força um segundo rerun; o cache afetado é
  invalidado e a confirmação é exibida no mesmo ciclo.
- As views são importadas sob demanda pelo roteador; módulos pesados de telas
  não aumentam o tempo de startup de rotas que não os utilizam.
- O Painel renderiza somente a seção ativa e, no histórico anual, calcula
  somente a prova selecionada em vez de executar todas as antigas abas.
- Matplotlib é importado somente durante a geração explícita de imagens da
  classificação.

## Benchmark e EXPLAIN

Use exclusivamente uma cópia descartável ou anonimizada do PostgreSQL:

```bash
BENCHMARK_DATABASE_URL=postgresql://usuario:senha@host/copia \
  python scripts/performance_benchmark.py --seasons 10 --iterations 30 > benchmark.json
```

O benchmark gera dados equivalentes a 5--10 temporadas, mede painel,
classificação, histórico e envio de aposta, e inclui `EXPLAIN (ANALYZE, BUFFERS,
FORMAT JSON)` das leituras. Ele cria um schema isolado e o remove ao terminar.
Por padrão recusa executar quando `BENCHMARK_DATABASE_URL` é igual a
`DATABASE_URL`.

## Critérios de aceite operacional

1. Jornadas instrumentadas emitem duração, queries, linhas e estado de cache.
2. Consultas de logs limitam a página a no máximo 500 registros.
3. Benchmark nunca executa contra a mesma URL configurada como produção.
4. Geração de imagens pesadas só ocorre após ação explícita.

## Changelog

- `1.0` — 2026-07-31 — Documento incorporado ao padrão SDD com metadados e critérios operacionais.

## Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
- [[adr/0001-streamlit-postgresql]]
