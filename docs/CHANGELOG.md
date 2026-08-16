---
tipo: produto
area: releases
status: implementado
versao: 2.7
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

### 3.10.5

- O "retângulo" do menu era o grupo (expansor), não os botões: o cabeçalho
  da seção (`stBaseButton-headerNoPadding`) e o contêiner colapsável
  (`stExpanderDetails`) agora ficam sem borda nem fundo — o grupo vira apenas
  o texto da seção, com hover transparente (spec `menu-e-navegacao` v1.5,
  critério 8).

### 3.10.4

- Estilo do menu aplicado por JavaScript injetado pelo sink central
  (`render_dom_styles`): os estilos vão como atributos inline diretamente no
  DOM renderizado (prioridade máxima, imune a especificidade do tema e a
  sanitização), com `MutationObserver` reaplicando a cada rerun/mutação —
  bordas/fundo do Liquid Glass deixam de se sobrepor; rolagem da sidebar no
  celular também via inline (spec `menu-e-navegacao` v1.4, critério 8).

### 3.10.3

- Estilo do menu reforçado: injeção de CSS pelo padrão clássico de markdown
  (sink `render_global_css`), com `!important` para vencer o tema — os itens
  ficam em texto sem bordas/fundo; rolagem explícita do conteúdo da sidebar
  no celular (`overflow-y: auto`) para navegar o menu completo (spec
  `menu-e-navegacao` v1.3, critério 8).

### 3.10.2

- Correção do estilo do menu: o seletor de borda/fundo usava `kind="secondary"`,
  que não existe no DOM do Streamlit 1.35+; agora usa
  `data-testid="stBaseButton-secondary"` (mantendo o antigo como fallback) —
  os itens aparecem como texto sem bordas (spec `menu-e-navegacao` v1.3,
  critério 8).

### 3.10.1

- Itens do menu lateral sem borda e sem fundo (aparência de texto), com
  espaçamento mínimo e densidade maior no celular preservando a altura de
  toque (spec `menu-e-navegacao` v1.3, critério 8); mudança exclusivamente
  visual.

### 3.10.0

- Gestão de Apostas com tabela-resumo e detalhe colapsável por item: na aba
  "Por Participante" cada prova vira linha da tabela + expander, e na aba
  "Por Prova" cada participante idem — a geração de aposta automática mantém
  a mesma ação sem dezenas de blocos e botões soltos (spec
  `apostas-automaticas` v1.1, critério 8).

### 3.9.0

- Tela de classificação dividida em cinco abas — Classificação, Pontuação
  por Prova, Imagem por Prova, Evolução Acumulada e Posições por Prova —
  eliminando a rolagem longa única (spec `classificacao` v1.2, critério 9);
  dados compartilhados calculados uma vez por renderização.

### 3.8.0

- Classificação com colunas numéricas ordenáveis: totais, descarte e
  diferença deixam de ser pré-formatados como texto e passam a
  `NumberColumn` (`%.2f`) — o usuário pode ordenar pela coluna
  (spec `classificacao` v1.1, critério 8); primeira linha da Diferença
  permanece vazia ("—") e o CSV sai com valores numéricos.

### 3.7.2

- Botões do menu lateral compactos (fonte e espaçamento reduzidos) e
  densidade maior em telas estreitas, preservando altura mínima de toque
  (spec `menu-e-navegacao` v1.2, critério 8); mudança exclusivamente visual.

### 3.7.1

- Agenda do calendário passa a exibir os eventos no fuso de exibição
  selecionado na sidebar (spec `pwa-e-preferencias-do-cliente` v1.1,
  critério 8): o componente streamlit-calendar recebia o fuso `local` do
  navegador e ignorava a escolha quando ela diferia do navegador; a aba
  "Horário limite" e a legenda da tela já respeitavam a escolha.

### 3.7.0

- Seletor global de temporada na sidebar (`temporada_global`): todas as telas
  de consulta e operação (classificação, calendário, análises, gestão de
  apostas/provas/resultados, logs, painel e campeonato) passam a usar a
  mesma temporada; seletores locais removidos (spec `temporada-global` v1.0);
  campos de entrada de dados (criar prova, regras, Ergast, Hall da Fama)
  permanecem locais.

### 3.6.0

- Indicador de progresso da Etapa 2 por validações concluídas (fração real +
  lista explícita de 6 validações), substituindo o progresso fixo 0.67/1.0
  (spec `apostas-de-prova` v1.3, critério 11); regras do envio inalteradas.

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

- `1.7` — 2026-08-16 — Registrada a versão 3.7.0 (temporada global na sidebar).
- `1.6` — 2026-08-16 — Registrada a versão 3.6.0 (progresso honesto da aposta).
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
