---
tipo: spec
area: gestao-administrativa-de-apostas
status: implementado
versao: 1.1
atualizado: 2026-09-16
relacionados:
  - "[[specs/apostas-de-prova]]"
  - "[[specs/apostas-automaticas]]"
  - "[[specs/notificacoes-por-email]]"
tags: [spec, "area/gestao-administrativa-de-apostas", "status/implementado"]
aliases: ["Gestão Administrativa de Apostas"]
---

# Gestão administrativa de apostas

> [!info] Status
> **implementado** · área: `gestao-administrativa-de-apostas` · atualizado em 2026-09-16 · relacionados: [[specs/apostas-de-prova]], [[specs/apostas-automaticas]], [[specs/notificacoes-por-email]]

## Problema

Admin e Master precisam acompanhar as apostas da temporada, lembrar participantes
pendentes e gerar apostas por ausência na Administração V4.

## Usuários

Somente usuários ativos com perfil `admin` ou `master`.

## Jornada

1. O operador acessa Administração > Gestão de apostas e usa a temporada global.
2. Em Por prova, seleciona uma prova, consulta todos os participantes, envia
   lembrete em CCO aos pendentes e pode gerar a aposta automática individual.
3. Em Por usuário, seleciona participante e prova, consulta todo o ano, envia
   lembrete somente à pessoa selecionada e pode gerar sua aposta automática.
4. Em Relatórios, compara por participante as provas manuais, automáticas e sem registro e pode baixar essa análise como imagem institucional.

## Dados

- `usuarios`: participantes ativos na temporada, exceto o Master.
- `provas`: calendário completo da temporada em ordem cronológica.
- `apostas`: composição, envio e geração `automatica` por participante/prova.
- `faltas`: contador legado atualizado exclusivamente pelo gerador automático.

## Regras

1. Leituras e mutações exigem sessão ativa de Admin ou Master.
2. Identidade e perfil do operador vêm da sessão; IDs enviados são apenas alvos.
3. Lembrete por prova inclui em CCO somente participantes sem aposta e com email válido.
4. Lembrete por usuário tem exatamente o usuário selecionado como destinatário e
   só é permitido quando ele não possui aposta na prova selecionada.
5. A geração usa `gerar_aposta_automatica`, preservando cópia da aposta anterior,
   fallback da primeira prova, contador `faltas`, auditoria e penalidade vigente.
6. Aposta manual existente nunca é substituída pela geração automática.
7. Relatórios classificam `automatica > 0` como automática e `automatica = 0`
    como manual, além de listar provas sem registro.
8. O operador pode gerar uma imagem PNG do relatório de cobertura, com logo,
    barra de progresso por participante e identidade visual institucional.
9. Nenhuma tabela ou coluna PostgreSQL é adicionada ou alterada.

## Interface, serviços e dados

- Tela: `/admin/apostas`, grupo Administração.
- Serviço: `services/admin_bets_v4_service.py` sobre os repositórios e serviços V3.
- API: `GET /api/v1/admin/bets`, `POST /api/v1/admin/bets/reminder`,
  `POST /api/v1/admin/bets/generate` e `GET /api/v1/admin/bets/report-image`.
- Tabelas: `usuarios`, `usuarios_status_historico`, `provas`, `apostas`, `log_apostas`.

## Critérios de aceite

1. Dado Admin ou Master, quando abre Por prova, então visualiza aposta ou pendência de cada participante.
2. Dada uma prova com pendentes, quando envia lembrete por prova, então somente os pendentes com email válido recebem via CCO.
3. Dado participante selecionado sem aposta, quando envia lembrete por usuário, então apenas seu email é destinatário.
4. Dado alvo elegível, quando gera aposta automática, então o serviço legado persiste e a tela recarrega o estado.
5. Dada aposta manual existente, quando tenta gerar automática, então a operação falha sem sobrescrever dados.
6. Dada a aba Por usuário, quando seleciona participante, então todas as provas da temporada exibem seu estado e composição.
7. Dada a aba Relatórios, quando há dados, então cada participante apresenta totais e listas de provas manuais, automáticas e sem registro.
8. Dada a aba Relatórios, quando solicita o download da imagem, então recebe um PNG com logo, título, tabela e data de geração.
9. Dado perfil participante ou inativo, quando consulta ou altera o módulo, então recebe acesso negado.
10. Dada temporada diferente, quando o seletor global muda, então toda a gestão e os relatórios são recarregados nesse escopo.

## Verificação

- Critérios 1–10 — testes de serviço, autorização, contrato OpenAPI e contrato estático do frontend.
- Responsividade, envio SMTP real e renderização visual da imagem — verificação manual em homologação.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Edição manual da aposta de outro participante.
- Alteração das regras do gerador automático.

## Plano de implementação

- [x] Passo 1 — serviço de leitura, relatório e autorização. Fecha: critérios 1, 6–9.
- [x] Passo 2 — lembretes e geração automática. Fecha: critérios 2–5 e 8.
- [x] Passo 3 — tela responsiva, menu, contratos e testes. Fecha: critérios 1–9.
- [x] Passo 4 — exportação do relatório de cobertura como imagem institucional. Fecha: critério 10.

## Changelog

- `1.1` — 2026-09-16 — Adicionado botão de download de imagem do relatório de cobertura de apostas.
- `1.0` — 2026-09-13 — Gestão V4 entregue com visões por prova/usuário, lembretes, geração automática e relatório anual.
- `0.1` — 2026-09-13 — Intenção, compatibilidade V3.5 e relatório anual especificados.

## Relacionados

- [[specs/apostas-de-prova]]
- [[specs/apostas-automaticas]]
- [[specs/notificacoes-por-email]]
