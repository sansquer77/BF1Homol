---
tipo: produto
area: releases
status: implementado
versao: 1.0
atualizado: 2026-09-06
relacionados:
  - "[[sdd]]"
  - "[[03_spec]]"
  - "[[07_guia_deploy]]"
tags: [produto, "area/releases", "status/implementado"]
aliases: ["Changelog do produto", "Versões do BF1"]
---

# Changelog do produto BF1

> [!info] Status
> **implementado** · área: `releases` · atualizado em 2026-09-06 · relacionados: [[sdd]], [[03_spec]], [[07_guia_deploy]]

Este documento registra versões do aplicativo. A versão documental deste
arquivo aparece no frontmatter e evolui independentemente do produto.

## Versão vigente

### 3.5.0

- Observabilidade: seis jornadas críticas passam a emitir duração total,
  quantidade e tempo de queries, linhas buscadas/processadas e cache hit/miss.
- Performance: incluído agregador reproduzível de P50/P95 a partir dos logs.
- Benchmark: carga sintética determinística para 5--10 temporadas, com
  `EXPLAIN (ANALYZE, BUFFERS)` exclusivamente em cópia segura e descartável.
- Segurança operacional: o benchmark exige confirmação explícita e recusa a
  identidade do banco configurado para a aplicação.

### 3.0.7

- Correção: exportação PNG da classificação passa a limitar dimensões,
  DPI e orçamento de pixels, reduzindo o pico de memória que podia reiniciar o
  processo Streamlit e devolver o usuário à tela de login.
- Robustez: figuras do Matplotlib são sempre fechadas, inclusive se a gravação
  do PNG falhar.

### 3.0.6

- Segurança: configuração do Streamlit passa a explicitar `enableCORS = true` e
  `enableXsrfProtection = true` em `.streamlit/config.toml`.
- Segurança: validação de identificadores SQL adicionada ao `_get_log_apostas_df`
  (`ui/analysis.py`) antes de interpolar colunas/aliases na query.
- Performance: cache TTL (`utils/ttl_cache.py`) passa a ter limite máximo de
  entradas (`BF1_TTL_CACHE_MAX_ENTRIES`, padrão 1000) com evicção incremental,
  evitando crescimento ilimitado de memória no container.
- Performance: pool PostgreSQL passa a enviar `application_name=bf1_app` e
  `connect_timeout=10` para melhor rastreabilidade e resiliência de conexão.
- Robustez: envio de email SMTP ganha timeout explícito de 15 segundos.
- Documentação: `docs/04_arquitetura.md` e `requirements.txt` atualizados com
  o requisito de Python >= 3.10.

### 3.0.5

- Versão vigente informada pelo mantenedor e centralizada em
  `app_version.py::APP_VERSION`.
- A tela Sobre apresenta essa mesma versão sem manter literais duplicados.
- O histórico anterior não foi reconstruído por falta de registros confiáveis.

## Política de incremento

- Patch: correções compatíveis, segurança e desempenho.
- Minor: capacidade nova e compatível.
- Major: mudança incompatível que exige migração ou ação operacional.
- Alterações sem efeito observável no produto não geram uma nova versão.

## Changelog

- `1.0` — 2026-07-31 — Criado o histórico canônico a partir da versão vigente 3.0.5.

## Relacionados

- [[sdd]]
- [[03_spec]]
- [[07_guia_deploy]]
