---
tipo: arquitetura
area: performance
status: implementado
versao: 1.6
atualizado: 2026-09-20
relacionados:
  - "[[04_arquitetura]]"
  - "[[06_modulos_tecnicos]]"
  - "[[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]]"
tags: [arquitetura, "area/performance", "status/implementado"]
aliases: ["Performance e Jornadas Críticas"]
---

# Performance e jornadas críticas

> [!info] Status
> **implementado** · área: `performance` · atualizado em 2026-09-20 · relacionados: [[04_arquitetura]], [[06_modulos_tecnicos]], [[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]]

Metas operacionais:

- P95 dos contratos HTTP de leitura da V4 abaixo de 400 ms; para as jornadas
  completas de interface (`login`, `abertura_painel`, `classificacao`,
  `historico`), p95 abaixo de 1 s.
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
- A Classificação mantém, por temporada e por processo da API, a preparação de
  dados, o resumo e o histórico em caches com TTL fixo de 300 s e limite global
  de entradas definido por `BF1_TTL_CACHE_MAX_ENTRIES`.
- Resumo e histórico possuem contratos HTTP separados. O frontend os solicita
  em paralelo, permitindo que a tabela atual seja apresentada sem aguardar a
  serialização das séries históricas.
- Escritas V4 de apostas, resultados, regras, provas, pilotos, equipes,
  participantes e campeonato invalidam a tag `classificacao`. O processamento
  de resultado aquece o snapshot completo depois da invalidação.
- O cache TTL do FastAPI aplica *single-flight* por chave: em um miss
  concorrente, somente uma requisição executa a leitura/cálculo e as demais
  aguardam o mesmo resultado. A invalidação ocorrida durante o cálculo impede
  que o resultado anterior à escrita seja reinserido no cache.
- O frontend usa `cache: "no-store"` nas chamadas da API. Não há ISR nem cache
  de dados de negócio no Next.js; a autoridade de TTL e invalidação permanece
  no FastAPI.

## Gate de carga da Classificação

Em 2026-09-16, o primeiro ensaio de homologação executou 100 usuários virtuais,
três leituras por usuário e uma sessão Master compartilhada. Foram recebidas 10
respostas dentro do timeout e ocorreram 290 timeouts no cliente; p95 foi 30,527
s e a taxa de erro observada pelo gerador foi 96,67%. A API posteriormente
registrou as 300 chamadas como HTTP 200, evidenciando fila de processamento.

Durante o ensaio, a CPU da API chegou a aproximadamente 70%, enquanto o banco
permaneceu em torno de 20–25%. O cache, a divisão resumo/histórico e o aquecimento
após resultados foram implantados depois desse diagnóstico. Eles são uma
mitigação ainda não validada pelo gate aprovado: a aprovação exige novo ensaio
progressivo em 10, 15 e 25 usuários e atendimento simultâneo das metas de p95 e erro.

Um ensaio intermediário pós-cache com 15 usuários simultâneos e três leituras
por usuário foi executado em 2026-09-16. As 45 requisições responderam HTTP 200,
sem falhas, em 1,128 s de parede e 39,876 requisições/s. O p95 foi 706,568 ms:
atende ao limite de 1 s da jornada de interface, mas ainda excede a meta de 400
ms do contrato HTTP. O artefato está em `load-test-classification-15.json` e
não substitui o gate obrigatório de 25 usuários.

Em 2026-09-19, o ensaio progressivo foi repetido. A primeira passagem, com
caches ainda frios entre as réplicas, preservou erro de 0%, mas excedeu a meta
de latência. Na repetição aquecida, 10, 15 e 25 VUs ficaram respectivamente em
279,362 ms, 347,438 ms e 377,835 ms de p95, sempre com 0% de erro. O patamar de
25 VUs processou 75/75 respostas HTTP 200 e aprovou o gate vigente.

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
9. Cache da Classificação é reutilizado na mesma temporada e invalidado pelas
   escritas V4 dos domínios que alteram seus dados.
10. A mitigação do gargalo só é considerada aprovada após o gate de 25 usuários
    simultâneos; testes unitários de cache não substituem carga em homologação.
11. Requisições concorrentes com a mesma chave em cache frio executam o produtor
    uma única vez por processo; chaves diferentes continuam independentes.
12. Uma invalidação durante o processamento não permite que o resultado
    iniciado antes dela seja armazenado novamente.

## Changelog

- `1.6` — 2026-09-20 — Cache TTL do FastAPI passa a agrupar misses concorrentes por chave e a impedir reinserção obsoleta após invalidação.
- `1.5` — 2026-09-19 — Gate aquecido de 25 VUs aprovado com erro de 0% e p95 de 377,835 ms.

- `1.4` — 2026-09-19 — Gate operacional da Fase 9 calibrado para 25 usuários simultâneos, acima do total atual de participantes.

- `1.3` — 2026-09-16 — Ensaio pós-cache com 15 usuários registrado: zero erros e p95 de 706,568 ms.
- `1.2` — 2026-09-16 — Primeiro gate de carga, diagnóstico de saturação, cache da Classificação e obrigação de novo ensaio documentados.
- `1.1` — 2026-09-06 — Definidas as seis jornadas, métricas, linha de base e barreiras do benchmark seguro da Fase 0.
- `1.0` — 2026-07-31 — Documento incorporado ao padrão SDD com metadados e critérios operacionais.

## Relacionados

- [[04_arquitetura]]
- [[06_modulos_tecnicos]]
- [[adr/0003-nextjs-fastapi-e-compatibilidade-de-dados]]
