---
tipo: spec
area: autenticacao
status: implementado
versao: 1.8
atualizado: 2026-09-16
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
> **implementado** · área: `autenticacao` · atualizado em 2026-09-16 · relacionados: [[02_regras_de_negocio]], [[03_spec]], [[specs/controle-de-acesso]], [[07_guia_deploy]]

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
- `timezone`: fuso horário de exibição do usuário (padrão `America/Sao_Paulo`).
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
12. O timezone do usuário é persistido em `usuarios.timezone`, carregado na
    autenticação e usado para exibir horários e prazos na interface V4.
13. O usuário pode alterar seu timezone através de seletor global; a escolha
    persiste entre sessões e não exige reautenticação.
14. Confirmações de senha para operações administrativas críticas compartilham
    um limite persistido por conta e IP; sessão renovada ou troca de endpoint
    não reinicia a janela, e indisponibilidade do limitador falha fechada.
15. A interface de conta rejeita o Master antes de verificar a senha, pois suas
    credenciais são autoritativas nas variáveis de ambiente e não podem servir
    como oráculo alternativo de validação.
16. Quando `must_change_password` estiver ativo, o servidor só permite consultar
    a identidade, encerrar a sessão ou concluir a troca de senha; as demais
    rotas protegidas são recusadas independentemente da UI.
16. O fluxo de recuperação de senha retorna a mesma mensagem genérica para
    emails cadastrados e não cadastrados.
17. O envio do email de recuperação é executado em background, de modo que a
    latência do SMTP não influencie o tempo de resposta da API.
18. Quando o email não está cadastrado, o servidor executa trabalho
    computacionalmente similar ao caminho existente para equalizar o tempo de
    resposta e dificultar enumeração por timing attack.
19. Quando `must_change_password` está ativa, a sessão emitida é restrita: o
    backend permite apenas identidade, troca de senha, logout e refresh; todas
    as demais rotas autenticadas retornam 403 até que a senha seja trocada.
20. A troca de senha própria limpa `must_change_password`, incrementa
    `session_version` e revoga as sessões anteriores.

## Interface, serviços e dados

- Tela V4: `frontend/src/app/login`; o fluxo Streamlit permanece apenas como baseline V3.
- Serviços: `services/auth_service.py` e `services/access_control.py`.
- Repositórios/tabelas: `usuarios`, `auth_sessions`, `login_attempts`, `password_reset_tokens`.
- API V4: `/api/v1/auth/login`, `/logout`, `/me`, `/refresh`,
  `/password-reset`, `/password-reset/confirm`, `/account/email`,
  `/account/password` e `/account/timezone`.

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
10. Dado usuário autenticado, quando acessar a interface V4, então seu timezone
    persistido é carregado e aplicado aos horários exibidos.
11. Dado usuário autenticado, quando alterar o timezone no seletor global, então
    o novo valor é persistido e refletido imediatamente na interface.
12. Dado o limite de reautenticação crítica atingido por conta ou IP, quando
    houver nova tentativa em restauração ou exportação de logs, então bcrypt
    não é executado e nenhuma autorização ou exportação é concedida.
13. Dada conta Master, quando tentar alterar email ou senha com qualquer
    candidato, então a operação é rejeitada antes de comparar o hash.
14. Dado usuário com `must_change_password`, quando acessar uma rota protegida
    que não seja troca de senha, identidade ou logout, então o servidor recusa
    a operação.
14. Dado email cadastrado, quando solicitada recuperação de senha, então a
    resposta é genérica e o email é enviado em background.
15. Dado email não cadastrado, quando solicitada recuperação de senha, então a
    resposta é idêntica à do email cadastrado e nenhum email é enviado.
16. Dado usuário com `must_change_password` ativa, quando acessar qualquer rota
    autenticada fora da whitelist, então recebe 403.
17. Dado usuário com `must_change_password` ativa, quando acessar `/auth/me`,
    `/auth/account/password`, `/auth/logout` ou `/auth/refresh`, então a
    operação é permitida.
18. Dado usuário com `must_change_password` ativa, quando troca a senha com
    sucesso, então a flag é limpa, as sessões anteriores são revogadas e o
    próximo login funciona normalmente.

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
- [x] Limitar reautenticação crítica e fechar oráculos alternativos do Master. Fecha: critérios 12 e 13.
- [x] Aplicar `must_change_password` no servidor e redirecionar a interface para Minha conta. Fecha: critério 14.
- [x] Mitigar information disclosure por timing no reset de senha. Fecha: critérios 14 e 15.
- [x] Restringir sessão enquanto `must_change_password` estiver ativa e garantir limpeza da flag na troca. Fecha: critérios 16 a 18.

## Changelog

- `1.8` — 2026-09-16 — Troca obrigatória de senha agora restringe a sessão no servidor (apenas identidade, troca de senha, logout e refresh) e a troca de senha própria limpa a flag e revoga sessões anteriores.
- `1.7` — 2026-09-16 — Recuperação de senha envia email em background e equaliza tempo de processamento para emails não cadastrados, dificultando enumeração por timing.
- `1.6` — 2026-09-16 — Reautenticação crítica passa a ter bucket compartilhado por conta/IP e a conta Master é recusada antes de bcrypt na interface de conta.
- `1.5` — 2026-09-14 — Adicionado timezone do usuário persistido, seletor global e API `/account/timezone`.
- `1.4` — 2026-09-13 — Minha conta V4 permite alterar email e senha mediante confirmação da credencial atual.
- `1.3` — 2026-09-12 — Interface e logout alinhados ao runtime Next.js/FastAPI; Streamlit identificado apenas como baseline V3.
- `1.2` — 2026-09-09 — Recuperação segura de senha disponibilizada na tela de login V4.
- `1.1` — 2026-09-08 — Documentados os contratos V4 de cookie, CSRF e rotação da sessão ativa.
- `1.0` — 2026-07-31 — Comportamento atual de autenticação e sessão especificado.

## Relacionados

- [[02_regras_de_negocio]]
- [[specs/controle-de-acesso]]
- [[07_guia_deploy]]
