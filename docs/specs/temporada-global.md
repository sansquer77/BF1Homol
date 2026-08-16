---
tipo: spec
area: navegacao
status: implementado
versao: 1.0
atualizado: 2026-08-16
relacionados:
  - "[[04_arquitetura]]"
  - "[[specs/menu-e-navegacao]]"
  - "[[specs/pwa-e-preferencias-do-cliente]]"
tags: [spec, "area/navegacao", "status/implementado"]
aliases: ["Temporada global"]
---

# Temporada global

> [!info] Status
> **implementado** · área: `navegacao` · atualizado em 2026-08-16 · relacionados: [[04_arquitetura]], [[specs/menu-e-navegacao]], [[specs/pwa-e-preferencias-do-cliente]]

## Problema

Cada tela mantinha um seletor de temporada próprio (`classificacao_season`,
`calendario_temporada`, `gestao_apostas_season`, `temporada` no painel, etc.):
trocar temporada em uma tela não refletia nas demais, fragmentando o contexto
do usuário entre telas.

## Usuários

Todos os perfis autenticados (master, admin, participante e inativo) que
consultam ou operam dados por temporada.

## Jornada

1. O usuário troca a temporada no seletor global da sidebar.
2. Todas as telas de consulta e operação passam a usar essa temporada.
3. O seletor global persiste a escolha durante a sessão e se mantém válido
   quando as opções disponíveis mudam (inativo, por exemplo).

## Dados

- `temporada_global` (`session_state`): temporada canônica escolhida na
  sidebar, usada como fonte única por todas as telas de consulta e operação.
- `temporada` (`session_state`): espelho legado que passa a derivar
  exclusivamente do valor global; mantido para compatibilidade interna.

## Regras

1. O seletor global fica na sidebar (`main.py::sidebar_menu`), abaixo do
   menu e acima do seletor de timezone, com as mesmas opções de
   `get_season_options` (que já aplica a restrição de perfil inativo).
2. Telas de consulta e operação não exibem mais seletor próprio: leem
   `temporada_global` e caem para o default da tela apenas se o valor global
   não estiver entre as opções disponíveis naquela tela.
3. Campos de entrada de dados (criar prova em `nova_temporada_prova`, regras,
   dashboard histórico da Ergast e filtros específicos do Hall da Fama)
   permanecem locais, pois representam dados e não contexto de consulta.
4. As opções e o filtro por status de perfil continuam definidos por
   `utils/season_utils.py`; nenhuma regra de negócio muda.
5. `st.session_state["temporada"]` (legado) passa a derivar do global nas
   telas que ainda o escrevem, sem sobrescrever a fonte única.

## Interface, serviços e dados

- Tela: `main.py::sidebar_menu` (seletor global) e telas em `ui/` (consumo).
- Serviços: nenhum — mudança exclusiva de apresentação.
- Tabelas: nenhuma.
- API: não aplicável; entrega Streamlit.

## Critérios de aceite

1. Dado usuário autenticado, quando a sidebar renderiza, então existe um
   seletor global de temporada persistido em `temporada_global`.
2. Dada uma temporada escolhida no seletor global, quando o usuário navega
   entre telas de consulta, então todas exibem dados da mesma temporada sem
   seletor próprio.
3. Dado valor global fora das opções de uma tela, quando a tela renderiza,
   então ela usa o default da própria tela sem erro e sem sobrescrever o
   global.
4. Dados campos de entrada de dados, quando a tela renderiza, então os
   seletores locais de criação/edição permanecem (não são unificados).
5. Dado usuário inativo, quando a sidebar renderiza, então as opções do
   seletor global respeitam o filtro de temporadas permitidas.

## Verificação

- Critérios 1, 2 e 4 — teste automatizado: `tests/test_temporada_global.py`
  (estático).
- Critérios 3 e 5 — verificação manual em navegador (inativo com histórico e
  fallback de tela sem o valor global).

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Unificar campos de entrada de dados (criar prova, criar/editar regras).
- Alterar o dashboard da Ergast (histórico real, não a temporada do bolão).
- Alterar `utils/season_utils.py` ou a restrição por perfil inativo.

## Plano de implementação

- [x] Criar o seletor global na sidebar. Fecha: critério 1.
- [x] Remover seletores locais das telas de consulta e operação. Fecha: critério 2.
- [x] Teste estático do seletor global e das telas. Fecha: critérios 1, 2 e 4.

## Changelog

- `1.0` — 2026-08-16 — Seletor global de temporada na sidebar com fonte
  única `temporada_global`; seletores locais das telas de consulta removidos.

## Relacionados

- [[04_arquitetura]]
- [[specs/menu-e-navegacao]]
- [[specs/pwa-e-preferencias-do-cliente]]