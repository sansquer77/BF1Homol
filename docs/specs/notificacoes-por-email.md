---
tipo: spec
area: notificacoes
status: implementado
versao: 1.0
atualizado: 2026-07-31
relacionados: ["[[specs/autenticacao-e-sessao]]", "[[specs/resultados-de-provas]]", "[[04_arquitetura]]"]
tags: [spec, "area/notificacoes", "status/implementado"]
aliases: ["Notificações por email"]
---

# Notificações por email

> [!info] Status
> **implementado** · área: `notificacoes` · atualizado em 2026-07-31 · relacionados: [[specs/autenticacao-e-sessao]], [[specs/resultados-de-provas]], [[04_arquitetura]]

## Problema

Enviar comunicações transacionais de recuperação de senha e resultado de prova sem tornar o email um ponto único de falha do domínio.

## Usuários

- Usuário com email cadastrado: recebe recuperação e, quando elegível, resumo de resultado.
- Operador: visualiza estatísticas de sucesso/falha do envio iniciado pelo fluxo.

## Jornada

1. Recuperação de senha ou publicação de resultado cria uma notificação elegível.
2. O serviço monta a mensagem e tenta o envio com a configuração do ambiente.
3. Sucessos e falhas são consolidados; falha parcial não desfaz o resultado já salvo.

## Dados

- Destinatário: email cadastrado e validado.
- Recuperação: token de uso limitado, sem exposição da senha.
- Resultado: prova, pontuação e resumo permitido da aposta do destinatário.
- Configuração: remetente, credencial SMTP e parâmetros de transporte via ambiente.

## Regras

1. Credenciais de email não ficam em `secrets.toml` de produção nem no repositório; vêm do ambiente seguro.
2. Recuperação envia token limitado e nunca senha em texto claro.
3. Notificação de resultado considera somente participantes elegíveis com email válido.
4. Destinatário ausente ou inválido é ignorado e contabilizado sem interromper os demais.
5. Falha parcial de SMTP é reportada, mas não reverte um resultado de prova já confirmado.
6. Logs não contêm senha, token completo nem credencial SMTP.
7. Sem configuração de email, o app permanece utilizável e informa indisponibilidade no fluxo dependente.

## Interface, serviços e dados

- Telas: recuperação de senha e confirmação de resultado manual.
- Serviços: `services/email_service.py` e `services/result_notification_service.py`.
- Persistência: usuários, tokens de recuperação, apostas e resultados.
- Integração externa: servidor SMTP configurado em produção.

## Critérios de aceite

1. Dado pedido válido de recuperação, quando o SMTP responde, então o usuário recebe link/token limitado sem senha.
2. Dado resultado confirmado, quando notificar, então cada participante elegível recebe apenas o próprio resumo.
3. Dado participante sem email, quando enviar lote, então os demais continuam e a omissão é contabilizada.
4. Dada falha em um destinatário, quando concluir o lote, então sucessos anteriores permanecem e o operador recebe resumo parcial.
5. Dado SMTP indisponível, quando um resultado já foi salvo, então o resultado permanece persistido.
6. Dada configuração ausente, quando disparar email, então a falha é controlada e não revela credenciais.
7. Dado qualquer envio, quando registrar logs, então token e segredo não aparecem integralmente.

## Verificação

- Critérios 1 e 7 — testes de segurança relacionados em `tests/test_security_utils.py`; revisar payloads com valores sentinela.
- Critérios 2–6 — teste manual/integrado com SMTP de homologação, incluindo um destinatário inválido e servidor indisponível.

## Pendências

- Nenhuma pendência conhecida.

## Fora de escopo

- Campanhas de marketing, notificações push e garantia de entrega após aceitação pelo servidor SMTP.

## Plano de implementação

- [x] Implementar transporte e recuperação segura. Fecha: critérios 1, 6 e 7.
- [x] Integrar notificação de resultado com tolerância parcial. Fecha: critérios 2–5.

## Changelog

- `1.0` — 2026-07-31 — Especificação operacional inicial.

## Relacionados

- [[specs/autenticacao-e-sessao]]
- [[specs/resultados-de-provas]]
- [[04_arquitetura]]
