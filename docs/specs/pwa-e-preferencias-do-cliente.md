---
tipo: spec
area: cliente
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados: ["[[specs/autenticacao-e-sessao]]", "[[04_arquitetura]]", "[[07_guia_deploy]]"]
tags: [spec, "area/cliente", "status/implementado"]
aliases: ["PWA e preferências do cliente"]
---

# PWA e preferências do cliente

> [!info] Status
> **implementado** · área: `cliente` · atualizado em 2026-07-31 · relacionados: [[specs/autenticacao-e-sessao]], [[04_arquitetura]], [[07_guia_deploy]]

## Problema

Oferecer experiência instalável e horários compreensíveis por usuário, mantendo um timezone canônico para regras de negócio.

## Usuários

- Qualquer usuário do cliente web: recebe metadados PWA e escolhe timezone de exibição.
- Usuário autenticado: mantém a preferência durante a navegação sem alterar deadlines canônicos.

## Jornada

1. O navegador carrega manifest, ícones e metadados da aplicação.
2. O app detecta um timezone válido ou usa `America/Sao_Paulo` como fallback.
3. O usuário pode escolher manualmente; a preferência é refletida nos query params e reutilizada nos reruns.

## Dados

- `tz`: identificador IANA validado.
- `tz_source`: origem detectada ou `manual`; a escolha manual tem precedência.
- PWA: manifest, nome, cores, ícones e metadados do cliente.

## Regras

1. Deadlines e datas de domínio continuam canônicos em `America/Sao_Paulo`; a preferência altera somente apresentação.
2. Um timezone manual válido prevalece sobre nova detecção automática.
3. Preferência válida é persistida em query params para sobreviver aos reruns e permitir navegação reproduzível.
4. Timezone ausente ou inválido usa fallback seguro sem quebrar a tela.
5. Valores de query params são validados antes de uso e não concedem autenticação ou autorização.
6. Manifest e recursos PWA devem ser servidos por HTTPS em produção e não armazenam segredos.
7. Configurações de segurança do Streamlit preservam proteção XSRF e política de origem definida no deploy.

## Interface, serviços e dados

- Cliente: `main.py`, utilitários de timezone e ativos em `static/`.
- Estado: query params e `session_state`; sem tabela própria no banco.
- Deploy: DigitalOcean App Platform com HTTPS.
- API externa: não aplicável.

## Critérios de aceite

1. Dado navegador com timezone IANA válido e sem escolha, quando abrir, então ele é usado para exibição.
2. Dada escolha manual válida, quando ocorrer rerun, então ela permanece e tem precedência sobre detecção.
3. Dado `tz` inválido ou manipulado, quando carregar, então o app usa fallback e não executa conteúdo arbitrário.
4. Dado horário de prova, quando alternar timezone de exibição, então o instante/deadline canônico não muda.
5. Dado navegador compatível em HTTPS, quando consultar os metadados, então nome, manifest e ícones permitem a experiência instalável.
6. Dado query param de preferência, quando acessado sem login, então ele não autentica nem amplia permissões.
7. Dada configuração de produção, quando iniciar, então XSRF e regras de origem permanecem habilitados conforme o deploy.

## Verificação

- Critérios 1–4 — testes em `tests/test_timezone_preference.py`.
- Critérios 6 e 7 — testes em `tests/test_streamlit_security_config.py` e matriz de autenticação.
- Critério 5 — verificação manual em navegador compatível e HTTPS, incluindo inspeção do manifest e instalação.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Funcionamento offline completo, sincronização em segundo plano e persistência server-side da preferência.

## Plano de implementação

- [x] Implementar detecção, preferência e fallback. Fecha: critérios 1–4 e 6.
- [x] Publicar ativos PWA e preservar configuração segura. Fecha: critérios 5 e 7.

## Changelog

- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/autenticacao-e-sessao]]
- [[04_arquitetura]]
- [[07_guia_deploy]]
