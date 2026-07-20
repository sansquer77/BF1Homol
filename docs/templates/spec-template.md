---
tipo: template
area: meta
status: implementado
versao: 1.2
atualizado: 2026-07-19
relacionados:
  - "[[00_sdd]]"
tags: [template, meta]
---

# Template de Spec

> [!info] Como usar
> Duplique este arquivo para criar qualquer novo documento do vault. Para specs, use um nome descritivo e preencha todas as seções obrigatórias. Para outros tipos, adapte frontmatter, título e seções, mantendo status, changelog e relacionados. Veja o processo completo em [[00_sdd]].

## Frontmatter obrigatório

```yaml
---
tipo: spec                 # spec | adr | design | metodologia | produto | arquitetura | roadmap | glossario | template
area: slug-da-area          # ex.: cartoes, lancamentos, investimentos
status: rascunho            # rascunho | em-implementacao | implementado | em-revisao | depreciado
versao: 0.1
atualizado: AAAA-MM-DD
relacionados: []             # substitua por wikilinks reais quando existirem
tags: [spec, "area/slug-da-area", "status/rascunho"]
aliases: ["Nome bonito da spec"]
---
```

## [Nome da funcionalidade]

> [!info] Status
> **{{status}}** · área: `{{area}}` · atualizado em {{data}} · relacionados: {{links}}

### Problema

Qual dor ou necessidade esta spec resolve? Escreva do ponto de vista do usuário, não da implementação.

### Usuário

Quem usa esta funcionalidade e em qual contexto? Uma ou duas frases bastam.

### Jornada

1. Passo inicial.
2. Ação principal.
3. Resultado esperado observável pelo usuário.

### Dados

- `campo`: descrição, tipo e regra de obrigatoriedade.

### Regras

- Regra de negócio verificável (uma frase, uma regra).

### API e dados

- Rotas afetadas ou criadas (`MÉTODO /api/caminho`).
- Tabelas afetadas ou criadas.

### Critérios de aceite

- Dado um estado inicial, quando uma ação ocorre, então o resultado deve ser observável.

### Fora de escopo *(opcional)*

O que conscientemente não será feito nesta entrega.

### Changelog

- `{{versao}}` — {{data}} — descrição da mudança.

### Relacionados

- Adicione aqui somente documentos existentes e diretamente relacionados.

## Changelog do template

- `1.1` — 2026-07-04 — Uso ampliado: o template passa a ser a base de qualquer novo documento do vault, não apenas specs.
- `1.2` — 2026-07-19 — Links e instrução de destino alinhados à estrutura atual de `docs/`.
- `1.0` — 2026-06-29 — Template inicial para specs.
