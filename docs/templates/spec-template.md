---
tipo: template
area: meta
status: implementado
versao: 1.3
atualizado: 2026-07-31
relacionados:
  - "[[sdd]]"
  - "[[README]]"
tags: [template, "area/meta", "status/implementado"]
aliases: ["Template de Spec"]
---

# Template documental

> [!info] Status
> **implementado** · área: `meta` · atualizado em 2026-07-31 · relacionados: [[sdd]], [[README]]

> [!info] Como usar
> Duplique este arquivo para qualquer documento novo. Specs ficam em `specs/`,
> ADRs em `adr/`. Para outros tipos, adapte as seções, mas preserve frontmatter,
> callout de status, changelog e relacionados. Consulte [[sdd]].

## Frontmatter obrigatório

```yaml
---
tipo: spec                 # spec | adr | arquitetura | produto | metodologia | glossario | template
area: slug-da-area         # ex.: apostas, classificacao, autenticacao
status: rascunho           # rascunho | em-implementacao | implementado | em-revisao | depreciado
versao: 0.1
atualizado: AAAA-MM-DD
relacionados:
  - "[[02_regras_de_negocio]]"
tags: [spec, "area/slug-da-area", "status/rascunho"]
aliases: ["Nome legível"]
---
```

# [Nome da funcionalidade]

> [!info] Status
> **{{status}}** · área: `{{area}}` · atualizado em {{data}} · relacionados: {{links}}

## Problema

Qual necessidade do usuário esta entrega resolve?

## Usuários

Quem usa a funcionalidade, com qual perfil e em qual contexto?

## Jornada

1. Estado inicial observável.
2. Ação do usuário ou evento do sistema.
3. Resultado esperado.

## Dados

- `campo`: tipo, origem, obrigatoriedade e regra relevante.

## Regras

1. Uma regra verificável por item.

## Interface, serviços e dados

- Tela ou fluxo afetado.
- Serviço/caso de uso responsável.
- Tabelas consultadas ou alteradas.
- API: “não aplicável” enquanto o BF1 não expuser API externa.

## Critérios de aceite

> Cada critério cobre um resultado observável. Inclua sucesso, borda e
> permissão/segurança quando aplicável.

1. Dado [estado], quando [ação], então [resultado único].
2. Dado [borda], quando [ação], então [resultado de borda].
3. Dado [perfil sem acesso], quando [ação], então [proteção esperada].

## Verificação

- Critério 1 — teste automatizado: `tests/test_exemplo.py::teste`.
- Critério 2 — verificação manual: passos e resultado esperado.

## Pendências

> [!question] Pendências
> Obrigatória para `rascunho` e `em-implementacao`. Nenhum agente implementa
> comportamento dependente de uma decisão aberta sem confirmação humana.

- Nenhuma pendência conhecida.

## Fora de escopo

- Comportamento conscientemente não incluído.

## Plano de implementação

> Obrigatório com mais de seis critérios ou quando mais de um módulo/camada for
> alterado. Cada passo referencia os critérios que fecha.

- [ ] Passo 1 — mudança e módulo. Fecha: critérios 1 e 2.
- [ ] Passo 2 — testes e documentação. Fecha: critério 3.

## Changelog

- `{{versao}}` — {{data}} — descrição da mudança.

## Relacionados

- [[02_regras_de_negocio]]

## Changelog do template

- `1.3` — 2026-07-31 — Adicionados critérios atômicos, verificação, pendências e plano rastreável.
- `1.2` — 2026-07-19 — Links alinhados à estrutura documental do BF1.
- `1.1` — 2026-07-04 — Template ampliado para todos os tipos documentais.
- `1.0` — 2026-06-29 — Template inicial.
