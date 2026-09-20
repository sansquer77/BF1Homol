---
tipo: spec
area: autorizacao
status: implementado
versao: 1.1
atualizado: 2026-09-19
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/autenticacao-e-sessao]]"
  - "[[adr/0002-limites-de-camadas]]"
tags: [spec, "area/autorizacao", "status/implementado"]
aliases: ["Controle de Acesso"]
---

# Controle de acesso

> [!info] Status
> **implementado** · área: `autorizacao` · atualizado em 2026-09-19 · relacionados: [[02_regras_de_negocio]], [[specs/autenticacao-e-sessao]], [[adr/0002-limites-de-camadas]]

## Problema

Menus não bastam para proteger operações: perfis, status e temporada precisam
ser revalidados no servidor antes de qualquer escrita sensível.

## Usuários

Os perfis são `master`, `admin`, `participante` e `inativo`.

## Jornada

1. O usuário autentica e recebe o menu permitido ao perfil atual.
2. Ao abrir uma página, o roteador aplica a matriz de páginas.
3. Ao executar escrita sensível, o serviço resolve novamente usuário e escopo.

## Dados

- `perfil`: papel persistido em `usuarios`.
- `status`: estado atual; valor diferente de ativo torna o contexto inativo.
- `temporadas_autorizadas`: histórico de inativos ou temporada atual do participante.
- `PAGE_ACCESS` e `OPERATION_ACCESS`: matrizes centrais.

## Regras

1. Perfil e `user_id` enviados pela UI não concedem autoridade.
2. Toda operação sensível deve existir em `OPERATION_ACCESS`.
3. Operação desconhecida falha de forma fechada.
4. Usuário inativo não executa operações sensíveis, mesmo com claim antigo.
5. Master e admin possuem escopo global somente nas operações permitidas ao papel.
6. Participante fica limitado à temporada atual; inativo, às temporadas históricas autorizadas.
7. Guard de página não substitui autorização dentro do serviço.
8. A especificação OpenAPI operacional exige sessão autenticada; o artefato
   versionado no repositório continua sendo a fonte usada para gerar o cliente.
9. Operações Master permanecem Master mesmo dentro de `/admin`: usuários,
   temporadas, equipes, regras, financeiro, Hall da Fama e backup. Admin só
   recebe as operações explicitamente previstas na matriz vigente.
10. Identificadores de usuário, participante, apostador, prova e temporada são
    validados contra a identidade e o escopo no servidor; parâmetros da URL ou
    do corpo nunca ampliam o escopo da sessão.

## Interface, serviços e dados

- Roteadores: `api/routes/` e dependências em `api/dependencies.py`.
- Política: `services/access_control.py`.
- Operações administrativas: `services/admin_operations.py`.
- Dados: `usuarios`, histórico de status e JWT validado.
- API: `/api/v1`, com contexto autenticado em toda rota protegida.

## Critérios de aceite

1. Dado perfil permitido, quando abre uma página autorizada, então o conteúdo é exibido.
2. Dado perfil não permitido, quando abre a página, então o acesso é negado.
3. Dado usuário inativo, quando tenta escrita sensível, então a operação é negada.
4. Dado perfil adulterado na UI, quando a operação é executada, então o perfil do banco prevalece.
5. Dada temporada fora do escopo, quando uma operação a referencia, então ela é negada.
6. Dada operação sem política, quando requerida, então o sistema falha fechado.
7. Dado usuário removido ou token inválido, quando o contexto é resolvido, então autenticação é exigida novamente.
8. Dado cliente anônimo, quando solicita `/api/v1/openapi.json`, então recebe 401.
9. Dado Admin, quando tenta criar/promover usuário, alterar outro usuário,
   editar financeiro, regras ou backup, então recebe 403 e nenhuma escrita ocorre.
10. Dado participante, quando troca `user_id`, `participant_id` ou `bettor_id`
    por um identificador alheio, então recebe 404 ou permanece estritamente no
    próprio escopo, sem consulta ou retorno do objeto alheio.

## Verificação

- Critérios 1 a 10 — `tests/test_access_matrix.py`, `tests/test_permissions_extended.py`,
  `tests/test_admin_v4_api.py` e `tests/test_v4_api_security.py`.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Delegação granular de permissões por usuário individual.

## Plano de implementação

- [x] Documentar matrizes, status e escopo. Fecha: critérios 1 a 7.
- [x] Vincular aos testes de autorização em profundidade. Fecha: critérios 2 a 7.

## Changelog

- `1.1` — 2026-09-19 — OpenAPI autenticado, matriz Master/Admin e testes IDOR formalizados como controles de não regressão.

- `1.0` — 2026-07-31 — Matriz e autorização em profundidade especificadas.

## Relacionados

- [[02_regras_de_negocio]]
- [[specs/autenticacao-e-sessao]]
- [[adr/0002-limites-de-camadas]]
