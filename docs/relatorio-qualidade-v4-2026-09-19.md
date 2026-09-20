---
tipo: metodologia
area: migracao-v4
status: implementado
versao: 1.0
atualizado: 2026-09-19
relacionados:
  - "[[specs/migracao-v4-nextjs-fastapi]]"
  - "[[04_arquitetura]]"
  - "[[07_guia_deploy]]"
tags: [qualidade, "area/migracao-v4", "status/implementado"]
aliases: ["Relatório de qualidade V4 2026-09-19"]
---

# Relatório de qualidade e build limpo da V4

> [!info] Status
> **implementado** · área: `migracao-v4` · atualizado em 2026-09-19 · build local aprovado; publicação e observação continuam na Fase 10.

## Escopo

Revisão estática e executável do frontend Next.js/TypeScript e do backend
FastAPI/Python, com remoção de fontes órfãs, busca de duplicações, typecheck,
build de produção e suíte automatizada.

## Resultado do gate local

| Gate | Resultado |
|---|---|
| Compilação Python de `api/`, `services/`, `db/` e `utils/` | Aprovada |
| TypeScript `tsc --noEmit` | Aprovado |
| Next.js `next build` limpo | Aprovado; 26 páginas geradas |
| Testes direcionados da limpeza e documentação | 54 aprovados |
| Suíte integral V4 | Aprovada: 300 testes e 144 subtestes |

A suíte anterior contabilizava 328 testes e 153 subtestes porque ainda incluía
casos que importavam ou inspecionavam a apresentação Streamlit. Esses casos
foram removidos ou migrados para contratos equivalentes da V4; a cobertura de
regras, API, segurança e compatibilidade de backup permanece no gate atual.

A importação isolada da API exige `DATABASE_URL`, por desenho fail-closed. A
suíte fornece configuração exclusivamente de teste antes da coleta; isso não
altera defaults nem permite banco alternativo no runtime.

## Melhorias aplicadas

- Removidos `main.py`, `ui/`, `.streamlit/`, ativos exclusivos da apresentação
  anterior e três cópias numeradas não referenciadas de serviços/componentes.
- Migrados os testes de fronteira, temporada, timezone, cache e frontend para
  contratos Next.js/FastAPI, eliminando inspeções do código Streamlit.
- Centralizada em `utils/json_utils.py` a extração tolerante de objeto JSON
  usada por IA e email, preservando os contratos internos existentes.
- Adicionado teste arquitetural que impede novas cópias numeradas de fontes nas
  camadas de produção.
- Alinhado o teste de versão ao valor canônico `4.0.0` e o teste de resultados
  ao aquecimento de cache incorporado na Fase 9.
- Tornada explícita a configuração isolada exigida pela suíte.

## Avaliação dos padrões

### TypeScript, React e Next.js

Pontos adequados: TypeScript estrito, App Router, páginas finas, componentes
client apenas quando interativos, ApexCharts carregado sob demanda, uso de
`next/image`, saída standalone e ausência de componentes client assíncronos,
imports-barrel amplos e tags nativas de imagem/script nas áreas revisadas.

Oportunidades:

1. Formatar componentes ainda condensados em uma linha e dividir telas grandes,
   começando por `logs-view.tsx`, sem alterar contratos.
2. Adotar ESLint e Prettier em mudança própria, com versões travadas e gate de
   CI; hoje há comentários de ESLint sem uma ferramenta versionada no pacote.
3. Manter o cache de dados no FastAPI: não foi identificado uso de ISR nem
   cache compartilhado do Next que exigisse coordenação entre instâncias.

### Python e FastAPI

Pontos adequados: separação entre rotas, serviços e persistência; schemas
Pydantic; autorização no servidor; tipagem gradual e testes de fronteira. A
interface Python anterior e seus utilitários exclusivos foram removidos.

Oportunidades:

1. Modularizar `db/backup_utils.py` somente após ampliar testes de
   caracterização do restore. A compatibilidade V3.x é regra primária e torna
   uma deduplicação ampla inadequada para uma limpeza mecânica.
2. Dividir `services/bets_write.py` por caso de uso e `api/schemas.py` por
   domínio, preservando os imports públicos durante a transição.
3. Avaliar um helper comum para consultas DataFrame dos repositórios, sem
   esconder limites transacionais ou particularidades de cada query.
4. Introduzir Ruff em entrega separada e corrigir gradualmente os avisos; a
   adoção não deve produzir uma reescrita massiva junto do cutover.
5. Planejar a atualização do adaptador de testes quando Starlette concluir a
   transição de `httpx` para `httpx2`; o uso depreciado de categóricos do pandas
   identificado nesta revisão já foi migrado para `CategoricalDtype`.

## Decisão

As modularizações maiores ficam registradas para depois do cutover, em mudanças
pequenas e caracterizadas. A retirada definitiva do runtime anterior torna a
V4 o único artefato operável. Decisão de versão: **major**, elevando o produto a
`4.0.0`; o contrato PostgreSQL e os backups suportados permanecem compatíveis.

## Changelog

- `1.0` — 2026-09-19 — Gate local, limpeza segura e backlog técnico priorizado.

## Relacionados

- [[specs/migracao-v4-nextjs-fastapi]]
- [[04_arquitetura]]
- [[07_guia_deploy]]
