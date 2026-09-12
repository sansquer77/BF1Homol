---
tipo: spec
area: financeiro
status: implementado
versao: 1.0
atualizado: 2026-09-12
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/controle-de-acesso]]"
  - "[[specs/migracao-v4-nextjs-fastapi]]"
tags: [spec, "area/financeiro", "status/implementado"]
aliases: ["Gestão financeira da temporada"]
---

# Gestão financeira da temporada

> [!info] Status
> **implementado** · área: `financeiro` · atualizado em 2026-09-12 · relacionados: [[02_regras_de_negocio]], [[specs/controle-de-acesso]], [[specs/migracao-v4-nextjs-fastapi]]

## Problema

O Master precisa controlar a taxa e os pagamentos de cada temporada, conferir o
fundo e a divisão prevista dos prêmios e cobrar participantes pendentes sem
alterar os contratos do banco compatíveis com os backups V3.x.

## Usuários

Somente o perfil `master`. Administradores e participantes não podem ler,
alterar ou disparar cobranças financeiras.

## Jornada

1. O Master escolhe a temporada e informa a taxa individual.
2. O sistema lista quem esteve ativo naquela temporada, exceto perfis Master.
3. O Master marca pagamentos e salva as alterações.
4. A tela apresenta arrecadação, saldo pendente e divisão prevista do fundo.
5. Opcionalmente, o Master filtra devedores e envia um lembrete em CCO.

## Dados

- `financeiro_config_temporada`: taxa por temporada; schema legado preservado.
- `financeiro_participantes`: pagamento por usuário e temporada; schema legado preservado.
- `usuarios_status_historico`: fonte preferencial da participação histórica.
- `usuarios`: identidade, perfil e fallback de status.

## Regras

1. A leitura e toda escrita exigem perfil `master` revalidado no serviço.
2. A lista usa a situação histórica da temporada e exclui usuários Master.
3. Total devido é participantes elegíveis × taxa; arrecadado considera apenas pagos.
4. O fundo previsto divide-se em 40% para campeão, 30% para vice, 20% para terceiro e 10% para administração.
5. O filtro de pendentes é apenas visual e não altera os registros.
6. A cobrança usa somente e-mails válidos de participantes pendentes derivados pelo servidor e os envia em CCO.
7. Falta de destinatários ou falha do provedor de e-mail não produz falso sucesso.

## Interface, serviços e dados

- Tela: `/admin/financeiro` no frontend Next.js.
- API: `GET/PUT /api/v1/admin/financial` e `POST /api/v1/admin/financial/reminder`.
- Serviço: `services/financial_v4_service.py`.
- Nenhuma tabela, coluna ou formato de backup é alterado.

## Critérios de aceite

1. A temporada retorna participantes historicamente ativos, sem o Master.
2. Taxa e pagamentos persistem nas duas tabelas legadas.
3. A resposta calcula contagens, totais monetários e percentuais de premiação.
4. A tela permite filtrar devedores e apresenta todos os resumos.
5. O lembrete envia em CCO somente aos pendentes com e-mail válido.
6. Perfis diferentes de Master recebem acesso negado em todas as operações.

## Verificação

- Critérios 1–3, 5 e 6 — testes em `tests/test_financial_v4_service.py`.
- Critério 4 — contrato de frontend e build Next.js.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Cobrança automática, integração bancária, conciliação ou emissão de recibos.
- Alteração dos percentuais definidos no regulamento vigente.

## Plano de implementação

- [x] Passo 1 — consolidar leitura histórica, cálculos e persistência. Fecha: critérios 1–3.
- [x] Passo 2 — implantar painel responsivo e filtro. Fecha: critério 4.
- [x] Passo 3 — implantar lembrete seguro e testes de autorização. Fecha: critérios 5 e 6.

## Changelog

- `1.0` — 2026-09-12 — Gestão financeira V4 especificada com paridade funcional à V3.

## Relacionados

- [[02_regras_de_negocio]]
- [[specs/controle-de-acesso]]
- [[specs/migracao-v4-nextjs-fastapi]]
