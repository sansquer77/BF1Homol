---
tipo: arquitetura
area: performance
status: implementado
versao: 1.1
atualizado: 2026-09-06
relacionados:
  - "[[04_arquitetura]]"
  - "[[06_modulos_tecnicos]]"
  - "[[adr/0001-streamlit-postgresql]]"
tags: [arquitetura, "area/performance", "status/implementado"]
aliases: ["Performance e Jornadas Críticas"]
---

# Performance e jornadas críticas

> [!info] Status
> **implementado** · área: `performance` · atualizado em 2026-09-06 · relacionados: [[04_arquitetura]], [[06_modulos_tecnicos]], [[adr/0001-streamlit-postgresql]]

Metas operacionais:

- P95 das jornadas de leitura (`login`, `abertura_painel`, `classificacao`, `historico`) abaixo de 1 s.
- Downloads com renderização pesada, como a imagem da classificação, são gerados somente após ação explícita do usuário.
- Cada função de leitura possui namespace próprio no cache; resultados de provas, participantes, apostas e posições nunca compartilham entradas mesmo quando recebem a mesma temporada.
- P95 de `envio_aposta` abaixo de 1,5 s.
- P95 de `lancamento_resultado` abaixo de 1,5 s como meta operacional inicial.
- Quantidade de queries constante em relação ao número de temporadas.
- Logs sempre filtrados e paginados (máximo de 500 linhas por página); dados
  brutos do histórico são filtrados por usuário e limitados a 5.000 linhas.

Cada jornada gera um evento JSON no logger `bf1.performance` com duração total,
quantidade e tempo de queries, linhas buscadas no banco (`rows_fetched`), linhas
entregues ao processamento (`rows_processed`), cache hit/miss e fingerprints
sem parâmetros das consultas. Em cache miss, as linhas são contadas no cursor;
em cache hit, são contadas na entrega do valor armazenado. O agregador de logs
calcula P50 e P95 por campo `journey`.

As seis jornadas críticas têm estes limites:

| Jornada | Início e fim da medição |
|---|---|
| `login` | envio do formulário até autenticação, erro ou redirecionamento |
| `abertura_painel` | início do rerun até concluir a seção inicial do Painel |
| `classificacao` | início do rerun até concluir a tela de classificação |
| `envio_aposta` | envio confirmado até persistência, invalidação de cache e resposta |
| `lancamento_resultado` | envio confirmado até persistência, recálculo, invalidação e resposta |
| `historico` | início do rerun até concluir o Histórico consolidado do Painel |

A abertura das telas de login e resultados pode aparecer separadamente como
`abertura_login` e `abertura_resultados`; só a submissão promove o evento para a
jornada crítica correspondente. `PERFORMANCE_METRICS_ENABLED=0` desativa a
emissão sem remover a instrumentação.

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
  python scripts/performance_benchmark.py --confirm-safe-copy \
  --seasons 10 --iterations 30 > benchmark.json
```

O benchmark gera dados determinísticos equivalentes a 5--10 temporadas, mede
login, painel, classificação, histórico, envio de aposta e lançamento de
resultado, e inclui `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` das leituras. Ele
cria um schema isolado e o remove ao terminar. A confirmação explícita é
obrigatória e a execução é recusada quando host, porta, usuário e nome do banco
coincidem com `DATABASE_URL`, mesmo que senha ou opções da URL sejam diferentes.
Nunca execute o benchmark, carga sintética ou `EXPLAIN ANALYZE` em produção.

Para consolidar uma linha de base reproduzível a partir dos logs:

```bash
python scripts/performance_report.py caminho/do/runtime.log > baseline.json
```

O artefato de baseline deve registrar versão do app, parâmetros do benchmark,
data, quantidade de amostras e resultado por jornada. Compare `query_count`
entre 5 e 10 temporadas: ele não pode crescer com o número de temporadas.

## Critérios de aceite operacional

1. As seis jornadas críticas emitem duração, queries, tempo de banco, linhas
   buscadas/processadas, cache hit/miss e sucesso, sem dados sensíveis.
2. Consultas de logs limitam a página a no máximo 500 registros.
3. Consultas do histórico bruto limitam a leitura a 5.000 registros por usuário.
4. Benchmark exige confirmação de cópia segura e nunca executa contra a mesma
   identidade de banco configurada para a aplicação.
5. O benchmark aceita somente 5--10 temporadas, produz P50/P95 e inclui planos
   com `ANALYZE` e `BUFFERS` para as leituras frequentes.
6. `query_count` das páginas permanece constante ao comparar 5 e 10 temporadas.
7. O relatório agregado permite verificar P95 de leitura abaixo de 1 s e de
   envio de aposta abaixo de 1,5 s.
8. Geração de imagens pesadas só ocorre após ação explícita.

## Changelog

- `1.1` — 2026-09-06 — Definidas as seis jornadas, métricas, linha de base e barreiras do benchmark seguro da Fase 0.
- `1.0` — 2026-07-31 — Documento incorporado ao padrão SDD com metadados e critérios operacionais.

## Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
- [[adr/0001-streamlit-postgresql]]
