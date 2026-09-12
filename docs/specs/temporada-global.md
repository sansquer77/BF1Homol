---
tipo: spec
area: navegacao
status: implementado
versao: 1.2
atualizado: 2026-09-09
relacionados:
  - "[[04_arquitetura]]"
  - "[[specs/menu-e-navegacao]]"
  - "[[specs/pwa-e-preferencias-do-cliente]]"
tags: [spec, "area/navegacao", "status/implementado"]
aliases: ["Temporada global"]
---

# Temporada global

> [!info] Status
> **implementado** · área: `navegacao` · atualizado em 2026-09-12 · relacionados: [[04_arquitetura]], [[specs/menu-e-navegacao]], [[specs/pwa-e-preferencias-do-cliente]]

## Problema

Cada tela mantinha um seletor de temporada próprio (`classificacao_season`,
`calendario_temporada`, `gestao_apostas_season`, `temporada` no painel, etc.):
trocar temporada em uma tela não refletia nas demais, fragmentando o contexto
do usuário entre telas.

## Usuários

Todos os perfis autenticados (master, admin, participante e inativo) que
consultam ou operam dados por temporada.

## Jornada

1. O usuário troca a temporada no seletor global do shell V4.
2. Todas as telas de consulta e operação passam a usar essa temporada.
3. O seletor global persiste a escolha durante a sessão e se mantém válido
   quando as opções disponíveis mudam (inativo, por exemplo).

## Dados

- `SeasonProvider`/`useSeason`: contexto canônico do frontend V4, persistido no
  cliente e usado pelas consultas do bolão.
- Parâmetro `season` da API: sempre validado e autorizado no backend.
- `temporada_global`/`temporada` em `session_state`: implementação legada V3.

## Regras

1. O seletor global fica no shell V4 e publica a escolha pelo contexto de temporada.
2. Telas de consulta e operação não exibem mais seletor próprio: leem
   `temporada_global` e caem para o default da tela apenas se o valor global
   não estiver entre as opções disponíveis naquela tela.
3. Campos de entrada de dados (criar prova em `nova_temporada_prova`, regras,
   dashboard histórico da Ergast e filtros específicos do Hall da Fama)
   permanecem locais, pois representam dados e não contexto de consulta.
4. As opções e o filtro por status de perfil continuam definidos por
   `utils/season_utils.py`; nenhuma regra de negócio muda.
5. O Dashboard F1 mantém seletor local independente, pois pesquisa a história
   da Fórmula 1 e não o recorte anual do bolão.

## Interface, serviços e dados

- Frontend: contexto em `frontend/src/lib/season/` e consumo pelas páginas V4.
- Backend: endpoints recebem `season` e revalidam o escopo permitido.
- Tabelas: nenhuma.
- API: contratos `/api/v1` dos módulos filtrados por temporada.

## Critérios de aceite

1. Dado usuário autenticado, quando a sidebar renderiza, então existe um
  seletor global de temporada provido pelo contexto V4.
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

- Critérios 1, 2 e 4 — testes de temporada V3 e contratos/frontend V4 na suíte.
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

- `1.2` — 2026-09-12 — Contrato atualizado para `SeasonProvider` da V4 e APIs por temporada; estado Streamlit rotulado como legado.
- `1.1` — 2026-09-09 — Contexto global V4 aplicado às consultas do bolão; Dashboard F1 histórico permanece independente.
- `1.0` — 2026-08-16 — Seletor global de temporada na sidebar com fonte
  única `temporada_global`; seletores locais das telas de consulta removidos.

## Relacionados

- [[04_arquitetura]]
- [[specs/menu-e-navegacao]]
- [[specs/pwa-e-preferencias-do-cliente]]
