---
tipo: spec
area: financeiro
status: implementado
versao: 1.2
atualizado: 2026-09-16
relacionados:
  - "[[02_regras_de_negocio]]"
  - "[[specs/controle-de-acesso]]"
  - "[[specs/migracao-v4-nextjs-fastapi]]"
tags: [spec, "area/financeiro", "status/implementado"]
aliases: ["Gestão financeira da temporada"]
---

# Gestão financeira da temporada

> [!info] Status
> **implementado** · área: `financeiro` · atualizado em 2026-09-16 · relacionados: [[02_regras_de_negocio]], [[specs/controle-de-acesso]], [[specs/migracao-v4-nextjs-fastapi]]

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
8. A alteração do status de pagamento de um participante atualiza imediatamente os cards de resumo no frontend, sem exigir salvamento prévio.
9. O formulário só permite salvar quando a taxa informada é um número válido maior ou igual a zero; mensagens de erro da API são apresentadas ao usuário.

## Interface, serviços e dados

- Tela: `/admin/financeiro` no frontend Next.js.
- API: `GET/PUT /api/v1/admin/financial` e `POST /api/v1/admin/financial/reminder`.
- Serviço: `services/financial_v4_service.py`.
- Nenhuma tabela, coluna ou formato de backup é alterado.

## Critérios de aceite

1. A temporada retorna participantes historicamente ativos, sem o Master.
2. Taxa e pagamentos persistem nas duas tabelas legadas; `pago` é gravado
   explicitamente como inteiro `0/1`, conforme o schema dos backups V3.5.
3. A resposta calcula contagens, totais monetários e percentuais de premiação.
4. A tela permite filtrar devedores e apresenta todos os resumos.
5. O lembrete envia em CCO somente aos pendentes com e-mail válido.
6. Perfis diferentes de Master recebem acesso negado em todas as operações.
7. Dado que o Master altera um pagamento na tabela, quando a ação ocorre, então os cards de resumo e a distribuição de prêmios recalculam instantaneamente.
8. Dado uma taxa inválida ou vazia, quando o Master tenta salvar, então a ação é bloqueada no frontend com mensagem clara.

## Verificação

- Critérios 1–3, 5 e 6 — testes em `tests/test_financial_v4_service.py`.
- Critério 4 — contrato de frontend e build Next.js.
- Critérios 7 e 8 — teste em `tests/test_v4_frontend_foundation.py`.

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

- `1.2` — 2026-09-16 — Escrita de `pago` corrigida para o contrato legado `INTEGER` (`0/1`).
- `1.1` — 2026-09-16 — Recálculo imediato dos cards de resumo ao alternar status de pagamento; validação de taxa e exibição de erro da API no frontend.
- `1.0` — 2026-09-12 — Gestão financeira V4 especificada com paridade funcional à V3.

## Relacionados

- [[02_regras_de_negocio]]
- [[specs/controle-de-acesso]]
- [[specs/migracao-v4-nextjs-fastapi]]
