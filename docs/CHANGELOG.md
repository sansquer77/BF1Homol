---
tipo: produto
area: releases
status: implementado
versao: 1.5
atualizado: 2026-08-16
relacionados:
  - "[[sdd]]"
  - "[[03_spec]]"
  - "[[07_guia_deploy]]"
tags: [produto, "area/releases", "status/implementado"]
aliases: ["Changelog do produto", "Versões do BF1"]
---

# Changelog do produto BF1

> [!info] Status
> **implementado** · área: `releases` · atualizado em 2026-08-16 · relacionados: [[sdd]], [[03_spec]], [[07_guia_deploy]]

Este documento registra versões do aplicativo. A versão documental deste
arquivo aparece no frontmatter e evolui independentemente do produto.

## Versão vigente

### 3.5.0

- Menu lateral com botões por item: o primeiro clique em qualquer item navega
  (inclusive o primeiro de um bloco recém-aberto); item da página atual
  destacado com `▶` (spec `menu-e-navegacao` v1.1, critério 7); radio por
  seção removido.

### 3.4.0

- Validação inline da grade de aposta: aviso imediato de piloto repetido,
  mesma equipe (quando proibida) e 11º também apostado, sem esperar o envio
  (spec `apostas-de-prova` v1.2, critério 10); validações do envio
  inalteradas como gate final.

### 3.3.0

- Formulário de aposta em grade única: seleção de pilotos e distribuição de
  fichas em um só widget (spec `apostas-de-prova` v1.1, critério 9); regras e
  validações inalteradas, pré-preenchimento da aposta existente mantido.

### 3.2.0

- Recuperação de senha em passos guiados na tela de login (spec
  `polimento-de-interface` v1.0).
- Heatmap da classificação por prova com escala suave e contraste legível.
- Botões do painel alinhados sem espaçadores `st.write("")`.
- Seletor de timezone com rótulos amigáveis; valor IANA canônico mantido.
- Cabeçalho de página compacto em todas as telas.
- Saudação pós-login exibida uma única vez.

### 3.1.0

- Menu lateral em coluna única: seções como expansores, seção ativa
  expandida e navegação em um clique (spec `menu-e-navegacao` v1.0).
- Removido o seletor intermediário de seção; itens e permissões por perfil
  permanecem inalterados.

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

- `1.5` — 2026-08-16 — Registrada a versão 3.5.0 (menu com botões por item).
- `1.4` — 2026-08-16 — Registrada a versão 3.4.0 (validação inline da aposta).
- `1.3` — 2026-08-16 — Registrada a versão 3.3.0 (grade única de aposta).
- `1.2` — 2026-08-16 — Registrada a versão 3.2.0 (polimento de interface).
- `1.1` — 2026-08-16 — Registrada a versão 3.1.0 (menu lateral em coluna única).
- `1.0` — 2026-07-31 — Criado o histórico canônico a partir da versão vigente 3.0.5.

## Relacionados

- [[sdd]]
- [[03_spec]]
- [[07_guia_deploy]]
