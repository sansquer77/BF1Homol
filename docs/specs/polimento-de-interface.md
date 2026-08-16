---
tipo: spec
area: apresentacao
status: implementado
versao: 1.0
atualizado: 2026-08-16
relacionados:
  - "[[04_arquitetura]]"
  - "[[specs/autenticacao-e-sessao]]"
  - "[[specs/classificacao]]"
  - "[[specs/apostas-de-prova]]"
  - "[[specs/pwa-e-preferencias-do-cliente]]"
  - "[[specs/historico-do-participante]]"
tags: [spec, "area/apresentacao", "status/implementado"]
aliases: ["Polimento de interface"]
---

# Polimento de interface

> [!info] Status
> **implementado** · área: `apresentacao` · atualizado em 2026-08-16 · relacionados: [[04_arquitetura]], [[specs/autenticacao-e-sessao]], [[specs/classificacao]], [[specs/apostas-de-prova]], [[specs/pwa-e-preferencias-do-cliente]], [[specs/historico-do-participante]]

## Problema

O BF1 acumula pequenas fricções de apresentação que não alteram regras, mas
comprometem clareza e consistência: fluxo de recuperação de senha em dois
formulários soltos, heatmap com contraste ruim no tom intermediário, botões
alinhados com `st.write("")`, seletor de timezone técnico, cabeçalho de página
grande e saudação duplicada após login.

## Usuários

Todos os perfis: participantes, inativos, administradores e master usam o
painel, a classificação e o login; qualquer visitante usa o seletor de
timezone e a recuperação de senha.

## Jornada

1. O visitante abre o login; para recuperar acesso, escolhe a etapa adequada
   (solicitar token ou redefinir senha) em passos guiados.
2. O usuário autentica e é recebido uma única vez; as páginas abrem com
   cabeçalho compacto e seletor de timezone com rótulos compreensíveis.
3. Na classificação, a grade por prova mantém a semântica vermelho/verde com
   contraste legível em todas as intensidades.

## Dados

- Nenhum dado novo; as mudanças são exclusivamente de apresentação.
- O valor do timezone permanece o identificador IANA canônico
  (`client_timezone`); apenas o rótulo exibido muda.

## Regras

1. A recuperação de senha mantém a funcionalidade atual: token único por
   email, rate limiting, resposta genérica e validações existentes.
2. O heatmap da grade por prova mantém a semântica de desempenho (vermelho =
   pior, verde = melhor) com fundos suaves e texto legível em qualquer
   intensidade.
3. Nenhum layout depende de `st.write("")` como espaçador; o alinhamento usa
   recursos nativos do Streamlit.
4. O seletor manual de timezone exibe rótulos amigáveis, mas grava e valida o
   identificador IANA de sempre.
5. O cabeçalho de página (`render_page_header`) permanece padronizado e mais
   compacto em todas as telas que o utilizam.
6. A saudação pós-login aparece uma única vez, na tela de destino.

## Interface, serviços e dados

- Telas: `ui/login.py`, `ui/painel.py`, `ui/classificacao.py`, `main.py` e
  `utils/helpers.py`.
- Serviços: nenhum — mudança exclusiva de apresentação.
- Tabelas: nenhuma.
- API: não aplicável; entrega Streamlit.

## Critérios de aceite

1. Dado visitante na tela de login, quando abre “Esqueci a senha”, então as
   etapas “solicitar token” e “redefinir senha” são apresentadas como passos
   guiados separados, com a mesma validação e resposta genérica de antes.
2. Dada grade de pontuação por prova com resultado, quando a célula é
   colorida, então o fundo usa escala suave e o texto permanece legível em
   todas as intensidades.
3. Dado o seletor de prova do painel, quando a página renderiza, então os
   botões “Ver regras” e “Sem ideias” ficam alinhados ao campo sem
   `st.write("")`.
4. Dado o seletor manual de timezone, quando a sidebar renderiza, então os
   valores aparecem com rótulos amigáveis e o valor persistido permanece o
   identificador IANA.
5. Dada qualquer página que usa `render_page_header`, quando renderiza, então
   o cabeçalho é mais compacto (título menor) mantendo logo e avisos.
6. Dado login com sucesso, quando a tela de destino carrega, então a saudação
   é exibida uma única vez.

## Verificação

- Critérios 1 a 6 — testes estáticos em `tests/test_ui_polish.py`.
- Criterios 2, 3, 4 e 5 — verificação manual em navegador (contraste do
  heatmap, alinhamento dos botões, rótulos do timezone e cabeçalho das telas).

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Alterar regras de negócio, fluxos de segurança ou o formato dos dados.
- Redesenho completo de identidade visual.

## Plano de implementação

- [x] Passos guiados de recuperação de senha. Fecha: critério 1.
- [x] Escala suave do heatmap. Fecha: critério 2.
- [x] Alinhamento nativo dos botões do painel. Fecha: critério 3.
- [x] Rótulos amigáveis do seletor de timezone. Fecha: critério 4.
- [x] Cabeçalho de página compacto. Fecha: critério 5.
- [x] Saudação única pós-login. Fecha: critério 6.
- [x] Testes estáticos e registro de versão minor. Fecha: critérios 1 a 6.

## Changelog

- `1.0` — 2026-08-16 — Polimento aplicado: recuperação de senha em passos,
  heatmap com escala suave, alinhamento nativo de botões, rótulos amigáveis
  de timezone, cabeçalho compacto e saudação única.

## Relacionados

- [[04_arquitetura]]
- [[specs/autenticacao-e-sessao]]
- [[specs/classificacao]]
- [[specs/apostas-de-prova]]
- [[specs/pwa-e-preferencias-do-cliente]]
- [[specs/historico-do-participante]]