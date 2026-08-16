---
tipo: spec
area: navegacao
status: implementado
versao: 1.3
atualizado: 2026-08-16
relacionados:
  - "[[04_arquitetura]]"
  - "[[specs/controle-de-acesso]]"
  - "[[specs/autenticacao-e-sessao]]"
  - "[[06_modulos_tecnicos]]"
tags: [spec, "area/navegacao", "status/implementado"]
aliases: ["Menu e navegação lateral"]
---

# Menu e navegação lateral

> [!info] Status
> **implementado** · área: `navegacao` · atualizado em 2026-08-16 · relacionados: [[04_arquitetura]], [[specs/controle-de-acesso]], [[specs/autenticacao-e-sessao]], [[06_modulos_tecnicos]]

## Problema

A sidebar exige dois passos para navegar (seletor de seção + menu), o que
aumenta cliques e esconde as páginas do perfil. Para o master são 19 itens em
5 seções.

## Usuários

Todos os perfis autenticados (master, admin, participante e inativo) e o
visitante anônimo na tela de login.

## Jornada

1. O usuário autentica e a sidebar renderiza as seções do perfil.
2. A seção da página atual inicia expandida, com o item ativo destacado.
3. O usuário expande outra seção e clica no item desejado — o primeiro
   clique em qualquer item navega.
4. A nova seção passa a ser a expandida e o item escolhido fica destacado.

## Dados

- `pagina` (`session_state`): página ativa, usada pelo roteador e guard.
- `menu_secao_last_<perfil>` (`session_state`): última seção escolhida, usada
  para decidir qual expansor inicia aberto.
- `menu_btn_<perfil>_<seção>_<item>` (`session_state`): estado transitório do
  botão de cada item (navegação em um clique).

## Regras

1. Itens e agrupamentos por perfil permanecem os definidos por
   `menu_*()`/`grouped_menu_*()` em `main.py`; a matriz de acesso
   (`services/access_control.py`) não muda.
2. A seção expandida é a da página atual ou a última seção escolhida pelo
   usuário; as demais iniciam colapsadas.
3. Cada item navega com um único clique, sem seletor intermediário de seção.
4. O item da página atual fica destacado na respectiva seção; não há seleção
   implícita de outro item (o radio por seção foi removido).
5. `Logout` permanece um item da seção Participante e dispara o fluxo de
   logout existente em `main.py`.
6. O guard de rotas e os redirecionamentos por permissão permanecem
   responsáveis pela navegação segura; o menu é apenas apresentação.
7. O seletor de timezone da sidebar permanece inalterado abaixo do menu.
8. Os itens do menu são botões sem borda e sem fundo (aparência de texto,
   alinhados à esquerda), com espaçamento mínimo; em telas estreitas
   (`max-width: 768px`) a densidade aumenta sem reduzir a altura mínima de
   toque. Mudança exclusivamente de apresentação via CSS.

## Interface, serviços e dados

- Tela: `main.py::sidebar_menu` (renderização do menu).
- Serviços: nenhum — mudança exclusiva de apresentação.
- Tabelas: nenhuma.
- API: não aplicável; entrega Streamlit.

## Critérios de aceite

1. Dado usuário autenticado, quando a sidebar renderiza, então as seções do
   perfil aparecem como expansores e a seção da página atual está expandida.
2. Dado usuário em qualquer seção, quando escolhe um item de outra seção,
   então a página troca e a nova seção passa a ser a expandida.
3. Dados perfis master, admin, participante e inativo, quando a sidebar
   renderiza, então os itens exibidos são exatamente os do agrupamento do
   perfil vigente.
4. Dado usuário na página atual, quando a sidebar renderiza, então o item
   correspondente aparece destacado na seção ativa.
5. Dado clique em `Logout`, quando o fluxo existente executa, então a sessão
   é encerrada e a sidebar volta ao estado anônimo.
6. Dada página fora do menu do perfil, quando o guard redireciona, então a
   navegação permanece consistente sem erro.
7. Dado bloco recém-expandido, quando o usuário clica no primeiro item (já
   destacado), então a navegação ocorre no primeiro clique — sem exigir
   selecionar outro item antes.
8. Dado o menu renderizado, quando a tela é estreita (celular), então os
   itens aparecem como texto sem borda nem fundo, com altura mínima de toque
   preservada; a navegação e o destaque do item ativo permanecem idênticos.

## Verificação

- Critérios 3, 7 e 8 — teste automatizado: `tests/test_menu_navigation.py`.
- Critérios 1, 2, 4, 5 e 6 — verificação manual em navegador com cada perfil
  (expansores por seção, item ativo destacado, primeiro clique navegando e
  logout funcional).
- Critério 8 — verificação visual em janela estreita e em dispositivo móvel
  (botões compactos e tocáveis).

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Alterar a matriz de acesso ou os itens por perfil.
- Alterar o fluxo de logout ou o seletor de timezone.
- Migração de frontend para JavaScript.

## Plano de implementação

- [x] Substituir o seletor de seção + radio por expansores por seção em
      `main.py::sidebar_menu`. Fecha: critérios 1, 2, 4 e 5.
- [x] Criar teste estático de estrutura do menu. Fecha: critério 3.
- [x] Registrar versão minor e changelog. Fecha: critério 6 (verificação).
- [x] Trocar o radio por botões por item (primeiro clique sempre navega) e
      destacar o item ativo. Fecha: critérios 4 e 7.
- [x] Compactar os botões do menu e aumentar a densidade em telas estreitas
      via CSS. Fecha: critério 8.
- [x] Remover bordas e fundo dos itens (menu em texto), mantendo o toque
      mínimo no celular. Fecha: critério 8.

## Changelog

- `1.3` — 2026-08-16 — Itens do menu sem borda nem fundo (texto), densidade
  maior no celular (critério 8).
- `1.2` — 2026-08-16 — Botões do menu compactos, com densidade maior em
  telas estreitas preservando altura mínima de toque (critério 8).
- `1.1` — 2026-08-16 — Itens do menu como botões: primeiro clique navega em
  qualquer item, item ativo destacado; radio por seção removido (critério 7).
- `1.0` — 2026-08-16 — Menu lateral em coluna única: seções como expansores,
  seção ativa expandida e navegação em um clique; seletor de seção removido.

## Relacionados

- [[04_arquitetura]]
- [[specs/controle-de-acesso]]
- [[specs/autenticacao-e-sessao]]
- [[06_modulos_tecnicos]]