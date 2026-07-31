---
tipo: metodologia
area: meta
status: implementado
versao: 3.1
atualizado: 2026-07-31
relacionados:
  - "[[README]]"
  - "[[templates/spec-template|Template documental]]"
  - "[[03_spec]]"
  - "[[04_arquitetura]]"
tags: [metodologia, "area/meta", "status/implementado"]
aliases: ["SDD", "Spec Driven Development"]
---

# SDD: Spec Driven Development

> [!info] Status
> **implementado** · área: `meta` · atualizado em 2026-07-31 · relacionados: [[README]], [[templates/spec-template|Template documental]], [[03_spec]], [[04_arquitetura]]

O BF1 usa especificações para registrar o comportamento esperado antes da
implementação. A documentação orienta pessoas e agentes de IA, mas não substitui
a verificação do código, dos testes e do comportamento observado.

## Modelo de maturidade: spec-anchored

O projeto é **spec-anchored**, não *spec-as-source*:

- specs ancoram intenção, jornada, regras e critérios de aceite;
- código e testes são a fonte de verdade executável;
- divergências são investigadas antes de alterar qualquer lado;
- depois da decisão, documentação, código e testes voltam a ficar consistentes.

## Tipos de documento

| Tipo | Conteúdo |
|---|---|
| `spec` | Comportamento observável, regras e critérios de aceite |
| `adr` | Decisão técnica, alternativas e consequências |
| `arquitetura` | Estrutura, módulos, dados e fluxos |
| `produto` | Necessidade, escopo e direção do produto |
| `metodologia` | Processo de trabalho, deploy ou operação |
| `glossario` | Vocabulário canônico do domínio |
| `template` | Estrutura obrigatória para novas notas |

## Frontmatter obrigatório

Toda nota em `docs/` deve declarar:

```yaml
---
tipo: spec
area: classificacao
status: rascunho
versao: 0.1
atualizado: AAAA-MM-DD
relacionados:
  - "[[02_regras_de_negocio]]"
tags: [spec, "area/classificacao", "status/rascunho"]
aliases: ["Nome legível"]
---
```

O título é seguido por um callout `> [!info] Status`. Toda nota termina com
`Changelog` e `Relacionados`.

## Fluxo

<!-- sync:fluxo-bf1 -->
1. Localize ou crie a spec usando `docs/templates/spec-template.md`.
2. Elimine pendências que afetem o comportamento antes de codificar.
3. Atualize regras, arquitetura ou ADRs quando o escopo exigir.
4. Implemente a menor mudança que satisfaça os critérios.
5. Crie um teste por critério automatizável; marque verificações manuais.
6. Execute testes direcionados e a suíte completa proporcionalmente ao risco.
7. Atualize status, versão, data, changelog e relacionados da spec.
<!-- /sync:fluxo-bf1 -->

## Ciclo de vida

```text
rascunho → em-implementacao → implementado → em-revisao → implementado
                                      └──→ depreciado
```

- `rascunho`: intenção descrita, com decisões possivelmente abertas.
- `em-implementacao`: alteração autorizada e em andamento.
- `implementado`: comportamento confirmado por código e verificação.
- `em-revisao`: documento ou comportamento precisa ser reconciliado.
- `depreciado`: mantido apenas por histórico e redirecionamento.

## Pendências e autorização

Specs em `rascunho` ou `em-implementacao` possuem seção `Pendências`. Um agente
não implementa comportamento dependente de uma decisão aberta sem confirmação
humana. “Nenhuma pendência conhecida” é uma resposta válida e explícita.

## Critérios de aceite

- Um comportamento observável por critério.
- Formato preferido: dado/quando/então.
- Cobrir sucesso, borda e permissão quando aplicável.
- Critérios automatizáveis apontam para testes.
- Aparência e operação externa podem usar verificação manual explícita.

## Plano de implementação

É obrigatório quando a spec possui mais de seis critérios ou toca mais de um
módulo/camada. Cada passo informa quais critérios fecha. Não é cronograma; é a
ordem segura de mudança.

## Rastreabilidade código ↔ spec

Regras não óbvias podem citar a spec:

```python
# spec: classificacao v1.0 — critério 5
```

Ao incrementar a versão da spec, revise comentários `spec:` correspondentes.

## Versionamento do aplicativo

<!-- sync:versionamento-bf1 -->
O BF1 usa **Versionamento Semântico** (`MAJOR.MINOR.PATCH`). Ao concluir uma
entrega, o agente deve avaliar o impacto acumulado desde a última versão e
registrar uma destas decisões no resumo da entrega: `sem incremento`, `patch`,
`minor` ou `major`, com justificativa breve.

- `PATCH` (`3.0.5` → `3.0.6`): correção compatível, segurança, desempenho ou
  ajuste operacional sem nova capacidade relevante para o usuário.
- `MINOR` (`3.0.5` → `3.1.0`): nova funcionalidade ou capacidade relevante,
  compatível com os fluxos e dados existentes.
- `MAJOR` (`3.0.5` → `4.0.0`): mudança incompatível em fluxo, regra, dados,
  configuração ou operação que exija migração/ação dos usuários ou operadores.
- Mudanças somente em documentação, testes, comentários ou refatorações sem
  efeito observável não incrementam a versão do produto.

Quando houver incremento, atualize na mesma entrega
`app_version.py::APP_VERSION`, `docs/CHANGELOG.md` e a versão exibida em Sobre
(esta última deve consumir a constante, nunca repetir um literal). Mudanças
`minor` ou `major` exigem spec atualizada; `major` também exige ADR e plano de
migração. Não incremente por suposição nem use datas como versão.
<!-- /sync:versionamento-bf1 -->

## Migração da documentação consolidada

A [[03_spec]] permanece válida como inventário funcional. Ao alterar um módulo:

1. crie ou atualize sua spec em `docs/specs/`;
2. mova para ela os critérios observáveis da área;
3. mantenha na spec consolidada um resumo e link;
4. não faça migração mecânica de módulos não revisados.

## Changelog

- `3.1` — 2026-07-31 — Adicionada política SemVer e avaliação obrigatória da versão do produto por entrega.
- `3.0` — 2026-07-31 — Processo robustecido com modelo spec-anchored, pendências, critérios atômicos, plano e rastreabilidade.
- `2.3` — 2026-07-19 — Estrutura numerada inicial alinhada ao BF1.

## Relacionados

- [[README]]
- [[templates/spec-template|Template documental]]
- [[03_spec]]
- [[04_arquitetura]]
