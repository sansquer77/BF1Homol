---
tipo: spec
area: autenticacao
status: implementado
versao: 1.0
atualizado: 2026-07-31
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
> **implementado** · área: `autenticacao` · atualizado em 2026-07-31 · relacionados: [[02_regras_de_negocio]], [[03_spec]], [[specs/controle-de-acesso]], [[07_guia_deploy]]

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
4. Logout revoga o token atual e limpa o estado Streamlit.
5. Troca ou redefinição de senha revoga todas as sessões do usuário.
6. Falhas de autenticação alimentam rate limiting por email e IP.
7. O login tradicional funciona sem OIDC; OIDC permanece opcional e desabilitado.

## Interface, serviços e dados

- Tela: `ui/login.py`; roteamento e logout em `main.py`.
- Serviços: `services/auth_service.py` e `services/access_control.py`.
- Repositórios/tabelas: `usuarios`, `auth_sessions`, `login_attempts`, `password_reset_tokens`.
- API: não aplicável; entrega Streamlit.

## Critérios de aceite

1. Dadas credenciais válidas, quando o usuário entra, então recebe uma sessão JWT revogável.
2. Dada senha inválida, quando o usuário entra, então nenhuma sessão é criada.
3. Dado JWT revogado ou expirado, quando uma rota protegida é acessada, então o usuário retorna ao login.
4. Dado novo login do mesmo usuário, quando o novo JWT é emitido, então JTIs ativos anteriores são revogados.
5. Dado logout, quando confirmado, então o JWT atual deixa de ser aceito.
6. Dada troca ou redefinição de senha, quando concluída, então sessões anteriores deixam de ser aceitas.
7. Dado OIDC desabilitado, quando a tela abre, então email e senha continuam sendo o fluxo operacional.

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

## Changelog

- `1.0` — 2026-07-31 — Comportamento atual de autenticação e sessão especificado.

## Relacionados

- [[02_regras_de_negocio]]
- [[specs/controle-de-acesso]]
- [[07_guia_deploy]]

