# Performance e jornadas críticas

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
