---
tipo: spec
area: cliente
status: implementado
versao: 2.0
atualizado: 2026-09-19
relacionados: ["[[specs/autenticacao-e-sessao]]", "[[04_arquitetura]]", "[[07_guia_deploy]]"]
tags: [spec, "area/cliente", "status/implementado"]
aliases: ["PWA e preferências do cliente"]
---

# PWA e preferências do cliente

> [!info] Status
> **implementado** · área: `cliente` · atualizado em 2026-08-16 · relacionados: [[specs/autenticacao-e-sessao]], [[04_arquitetura]], [[07_guia_deploy]]

## Problema

Oferecer experiência instalável e horários compreensíveis por usuário, mantendo um timezone canônico para regras de negócio.

## Usuários

- Qualquer usuário do cliente web: recebe metadados PWA e escolhe timezone de exibição.
- Usuário autenticado: mantém a preferência durante a navegação sem alterar deadlines canônicos.

## Jornada

1. O navegador carrega manifest, ícones e metadados da aplicação.
2. O app detecta um timezone válido ou usa `America/Sao_Paulo` como fallback.
3. O usuário pode escolher manualmente; a preferência é persistida pela API na conta.

## Dados

- `tz`: identificador IANA validado.
- `timezone`: preferência IANA persistida no usuário autenticado.
- PWA: manifest, nome, cores, ícones e metadados do cliente.

## Regras

1. Deadlines e datas de domínio continuam canônicos em `America/Sao_Paulo`; a preferência altera somente apresentação.
2. Um timezone manual válido prevalece sobre nova detecção automática.
3. Preferência válida é persistida pelo endpoint autenticado da conta.
4. Timezone ausente ou inválido usa fallback seguro sem quebrar a tela.
5. O valor enviado à API é validado antes de persistir e não amplia autorização.
6. Manifest e recursos PWA devem ser servidos por HTTPS em produção e não armazenam segredos.
7. Mutações usam cookie seguro, origem permitida e CSRF.

## Interface, serviços e dados

- Cliente: `frontend/src/lib/timezone-context.tsx` e metadados do App Router.
- API: `PUT /api/v1/auth/account/timezone`.
- Estado: campo de preferência do usuário autenticado.
- Deploy: DigitalOcean App Platform com HTTPS.

## Critérios de aceite

1. Dado navegador com timezone IANA válido e sem escolha, quando abrir, então ele é usado para exibição.
2. Dada escolha manual válida, quando navegar ou autenticar novamente, então ela permanece.
3. Dado timezone inválido ou manipulado, quando persistir, então a API rejeita sem alterar a preferência.
4. Dado horário de prova, quando alternar timezone de exibição, então o instante/deadline canônico não muda.
5. Dado navegador compatível em HTTPS, quando consultar os metadados, então nome, manifest e ícones permitem a experiência instalável.
6. Dada requisição sem sessão, quando tenta persistir timezone, então recebe 401.
7. Dada mutação sem origem/CSRF válidos, quando enviada, então é rejeitada.
8. Dado fuso selecionado, quando o Calendário renderiza, então eventos usam esse fuso sem alterar o instante canônico.

## Verificação

- Critérios 1–4 e 8 — `tests/test_v4_pure_runtime.py` e contratos do frontend.
- Critérios 6 e 7 — `tests/test_v4_api_security.py`.
- Critério 5 — verificação manual em navegador compatível e HTTPS, incluindo inspeção do manifest e instalação.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Funcionamento offline completo, sincronização em segundo plano e persistência server-side da preferência.

## Plano de implementação

- [x] Implementar detecção, preferência e fallback. Fecha: critérios 1–4 e 6.
- [x] Publicar ativos PWA e preservar configuração segura. Fecha: critérios 5 e 7.
- [x] Exibir a Agenda no fuso selecionado (timezone do componente). Fecha: critério 8.

## Changelog

- `1.1` — 2026-08-16 — Agenda passa a exibir eventos no fuso de exibição selecionado (critério 8).
- `2.0` — 2026-09-19 — Preferência e segurança consolidadas no frontend/API V4.
- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/autenticacao-e-sessao]]
- [[04_arquitetura]]
- [[07_guia_deploy]]
