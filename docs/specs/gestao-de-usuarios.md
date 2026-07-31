---
tipo: spec
area: usuarios
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados: ["[[02_regras_de_negocio]]", "[[specs/autenticacao-e-sessao]]", "[[specs/controle-de-acesso]]"]
tags: [spec, "area/usuarios", "status/implementado"]
aliases: ["Gestão de usuários"]
---

# Gestão de usuários

> [!info] Status
> **implementado** · área: `usuarios` · atualizado em 2026-07-31 · relacionados: [[02_regras_de_negocio]], [[specs/autenticacao-e-sessao]], [[specs/controle-de-acesso]]

## Problema

Permitir que o perfil Master administre contas, credenciais, perfis e participação por temporada sem comprometer sessões ou históricos.

## Usuários

- Master: cadastra e altera usuários, status, perfis e senhas.
- Participante, Administrador e Inativo: são objetos da gestão, sem permissão de escrita nesse módulo.

## Jornada

1. O Master abre a gestão e pesquisa a conta.
2. Cadastra ou altera dados, perfil, status ou senha temporária.
3. O sistema valida unicidade e autorização, registra a mudança e invalida sessões quando necessário.

## Dados

- `usuarios`: nome, email normalizado, senha bcrypt, perfil, status e troca obrigatória de senha.
- `usuarios_status_historico`: vínculo de status do participante com a temporada.
- `auth_sessions`: sessões revogáveis associadas ao usuário.

## Regras

1. Somente Master executa `usuario.write`; a UI não é fonte de autoridade.
2. O email é obrigatório, normalizado e único sem distinção entre maiúsculas e minúsculas.
3. Senhas são armazenadas somente como hash bcrypt e nunca aparecem em logs.
4. Redefinição administrativa pode exigir troca no próximo login e deve revogar sessões abrangidas pela política de autenticação.
5. Perfil e status usam apenas os valores reconhecidos pelo controle de acesso.
6. A ativação ou inativação por temporada preserva dados e histórico existentes.
7. Usuário inativo não ganha acesso de escrita; sua leitura histórica segue [[specs/controle-de-acesso]].

## Interface, serviços e dados

- Tela: Administração → Usuários.
- Serviços: `services/admin_operations.py`, autenticação e controle de acesso.
- Persistência: `db/repo_users.py`, tabelas `usuarios`, `usuarios_status_historico` e `auth_sessions`.
- API externa: não aplicável.

## Critérios de aceite

1. Dado um Master, quando cadastrar email inédito e dados válidos, então a conta é criada com senha protegida.
2. Dado email já existente após normalização, quando cadastrar ou alterar, então a operação é recusada sem duplicidade.
3. Dado perfil sem `usuario.write`, quando invocar uma escrita diretamente no serviço, então a operação é negada.
4. Dada redefinição de senha, quando concluída, então a credencial anterior deixa de autenticar e as sessões previstas são revogadas.
5. Dada mudança de status por temporada, quando salva, então o histórico anterior permanece consultável.
6. Dado usuário inativo, quando acessar o app, então apenas os recursos históricos autorizados ficam disponíveis.
7. Dada falha de validação, quando salvar, então nenhuma alteração parcial é persistida.

## Verificação

- Critérios 1–4 e 6 — testes: `tests/test_access_matrix.py`, `tests/test_permissions_extended.py`, `tests/test_security_utils.py` e `tests/test_performance_optimizations.py`.
- Critérios 5 e 7 — verificação manual: alterar status em duas temporadas e provocar email duplicado, confirmando histórico e ausência de gravação parcial.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Autocadastro público, login social obrigatório e exclusão física do histórico.

## Plano de implementação

- [x] Proteger operações administrativas e persistir usuários. Fecha: critérios 1–3 e 7.
- [x] Integrar credenciais, sessões e status por temporada. Fecha: critérios 4–6.

## Changelog

- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/autenticacao-e-sessao]]
- [[specs/controle-de-acesso]]
- [[02_regras_de_negocio]]
