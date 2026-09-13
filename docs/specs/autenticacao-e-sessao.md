---
tipo: spec
area: autenticacao
status: implementado
versao: 1.4
atualizado: 2026-09-13
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[03_spec]]"
  - "[[specs/controle-de-acesso]]"
  - "[[07_guia_deploy]]"
tags: [spec, "area/autenticacao", "status/implementado"]
aliases: ["Autenticação e Sessão"]
---

# Autenticação e sessão

> [!info] Status
> **implementado** · área: `autenticacao` · atualizado em 2026-09-12 · relacionados: [[02_regras_de_negocio]], [[03_spec]], [[specs/controle-de-acesso]], [[07_guia_deploy]]

## Problema

O BF1 precisa identificar cada usuário, proteger credenciais e encerrar sessões
comprometidas sem tornar um cookie client-side a autoridade de acesso.

## Usuários

Todos os usuários cadastrados usam email e senha. Master administra contas;
usuários sem acesso à senha usam o fluxo de recuperação por email.

## Jornada

1. O usuário informa email e senha.
2. O sistema aplica limitação de tentativas, normaliza o email e valida bcrypt.
3. Credenciais válidas geram JWT revogável e direcionam ao Painel.
4. Logout, troca ou redefinição de senha revogam as sessões previstas.

## Dados

- `email`: identificador normalizado, limitado a 254 caracteres.
- `senha_hash`: hash bcrypt; senha em texto não é persistida.
- `jti`: identificador único do JWT persistido em `auth_sessions`.
- `session_version`: versão que invalida sessões anteriores.
- `exp`: expiração do JWT, atualmente 120 minutos.

## Regras

1. `JWT_SECRET` é obrigatório e possui no mínimo 32 bytes recomendados.
2. Novo login revoga JTIs ativos anteriores do usuário.
3. JWT só é aceito quando JTI, usuário, versão e expiração permanecem válidos.
4. Logout revoga o token atual e remove os cookies de sessão e CSRF da V4.
5. Troca ou redefinição de senha revoga todas as sessões do usuário.
6. Falhas de autenticação alimentam rate limiting por email e IP.
7. O login tradicional funciona sem OIDC; OIDC permanece opcional e desabilitado.
8. Na API V4, sessão e CSRF usam cookies separados; a sessão é `HttpOnly`, e
   toda mutação autenticada exige origem permitida e token CSRF coincidente.
9. `POST /api/v1/auth/refresh` rotaciona o JTI durante atividade e mantém apenas
   uma sessão ativa por usuário.
10. No bootstrap, `USUARIO_MASTER`, `EMAIL_MASTER` e `SENHA_MASTER` são a fonte
    autoritativa da conta Master; nome, email, status e hash bcrypt são
    sincronizados sem persistir a senha em texto.
11. Alteração autenticada de email ou senha exige a senha atual; a conta Master
    não altera email nem senha pela interface porque `EMAIL_MASTER` e
    `SENHA_MASTER` permanecem autoritativos.

## Interface, serviços e dados

- Tela V4: `frontend/src/app/login`; o fluxo Streamlit permanece apenas como baseline V3.
- Serviços: `services/auth_service.py` e `services/access_control.py`.
- Repositórios/tabelas: `usuarios`, `auth_sessions`, `login_attempts`, `password_reset_tokens`.
- API V4: `/api/v1/auth/login`, `/logout`, `/me`, `/refresh`,
  `/password-reset`, `/password-reset/confirm`, `/account/email` e
  `/account/password`.

## Critérios de aceite

1. Dadas credenciais válidas, quando o usuário entra, então recebe uma sessão JWT revogável.
2. Dada senha inválida, quando o usuário entra, então nenhuma sessão é criada.
3. Dado JWT revogado ou expirado, quando uma rota protegida é acessada, então o usuário retorna ao login.
4. Dado novo login do mesmo usuário, quando o novo JWT é emitido, então JTIs ativos anteriores são revogados.
5. Dado logout, quando confirmado, então o JWT atual deixa de ser aceito.
6. Dada troca ou redefinição de senha, quando concluída, então sessões anteriores deixam de ser aceitas.
7. Dado OIDC desabilitado, quando a tela abre, então email e senha continuam sendo o fluxo operacional.
8. Dada senha atual válida, quando um usuário não Master altera email ou senha,
   então a alteração é aplicada; a troca de senha revoga as sessões existentes.
9. Dada conta Master, quando tentar alterar credenciais pela interface, então a
   operação falha sem sobrescrever as variáveis autoritativas do ambiente.

## Verificação

- Critérios 2, 3 e 6 — testes de segurança, permissões e recuperação na suíte `tests/`.
- Critérios 1, 4, 5 e 7 — verificação de integração do login e inspeção de `auth_sessions`.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Tornar OIDC obrigatório ou substituir o login por senha.

## Plano de implementação

- [x] Registrar o contrato de login e sessão. Fecha: critérios 1 a 7.
- [x] Mapear segurança, persistência e verificações existentes. Fecha: critérios 2 a 6.
- [x] Expor recuperação e confirmação de senha na tela de login V4. Fecha: critério 6.
- [x] Expor Minha conta com reautenticação para email e senha. Fecha: critérios 8 e 9.

## Changelog

- `1.4` — 2026-09-13 — Minha conta V4 permite alterar email e senha mediante confirmação da credencial atual.
- `1.3` — 2026-09-12 — Interface e logout alinhados ao runtime Next.js/FastAPI; Streamlit identificado apenas como baseline V3.
- `1.2` — 2026-09-09 — Recuperação segura de senha disponibilizada na tela de login V4.
- `1.1` — 2026-09-08 — Documentados os contratos V4 de cookie, CSRF e rotação da sessão ativa.
- `1.0` — 2026-07-31 — Comportamento atual de autenticação e sessão especificado.

## Relacionados

- [[02_regras_de_negocio]]
- [[specs/controle-de-acesso]]
- [[07_guia_deploy]]
