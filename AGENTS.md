# AGENTS.md — Guia para agentes de IA no BF1

> Este arquivo orienta qualquer agente que leia ou altere este repositório. A
> documentação em [`docs/`](docs/README.md) é canônica. Se houver divergência,
> investigue código e testes antes de decidir qual lado precisa ser atualizado.

## 0. Antes de alterar arquivos

1. Leia [`docs/README.md`](docs/README.md).
2. Leia a spec da área em `docs/specs/`; enquanto uma área ainda estiver apenas
   na spec consolidada, consulte [`docs/03_spec.md`](docs/03_spec.md).
3. Confira regras em [`docs/02_regras_de_negocio.md`](docs/02_regras_de_negocio.md).
4. Confira limites técnicos em [`docs/04_arquitetura.md`](docs/04_arquitetura.md).
5. Se o comportamento não estiver especificado, atualize ou crie a spec antes
   de implementar.

O BF1 segue o processo **spec-anchored** definido em [`docs/sdd.md`](docs/sdd.md):
specs registram intenção e critérios de aceite; código e testes são a fonte de
verdade executável. Divergências devem ser investigadas, não resolvidas por
suposição.

## 1. Fluxo obrigatório

<!-- sync:fluxo-bf1 -->
1. Localize ou crie a spec usando `docs/templates/spec-template.md`.
2. Elimine pendências que afetem o comportamento antes de codificar.
3. Atualize regras, arquitetura ou ADRs quando o escopo exigir.
4. Implemente a menor mudança que satisfaça os critérios.
5. Crie um teste por critério automatizável; marque verificações manuais.
6. Execute testes direcionados e a suíte completa proporcionalmente ao risco.
7. Atualize status, versão, data, changelog e relacionados da spec.
<!-- /sync:fluxo-bf1 -->

Nenhum documento novo começa como Markdown livre. Use o template e preserve
frontmatter, callout de status, changelog e relacionados.

## 2. Restrições arquiteturais

- O app é um monólito Streamlit hospedado na DigitalOcean App Platform.
- PostgreSQL é a fonte de verdade; o driver é `psycopg` 3 com pool gerenciado.
- `ui/` renderiza e orquestra widgets. Regras pertencem a `services/`; SQL e
  persistência pertencem a `db/` ou aos adaptadores de dados existentes.
- `services/`, `db/` e `utils/` não importam Streamlit.
- `utils/` contém funções puras e transversais, sem acesso ao banco.
- Escritas administrativas passam por autorização de operação na camada de
  serviço; valores de perfil, usuário e temporada vindos da UI não são fonte
  de autoridade.
- Migrações PostgreSQL são incrementais e idempotentes.
- Uma nova dependência, protocolo de autenticação ou mudança de fronteira de
  camadas exige ADR.

## 3. Contratos de domínio críticos

- Datas e deadlines de prova usam `America/Sao_Paulo` como referência canônica.
- Aposta só é aceita dentro da janela definida pela spec e pelas regras da
  temporada/tipo de prova.
- `Total Geral` da classificação soma provas realizadas.
- `Total Válido = Total Geral + Bônus Campeão + Bônus Vice + Bônus Equipe - Descarte`.
- Posição e diferença da classificação usam `Total Válido`.
- DataFrames públicos preservam o schema mínimo mesmo quando vazios.
- Caches de leitura devem ser invalidados pelas tags do domínio afetado após
  escritas; não limpe caches não relacionados.

## 4. Autenticação e segurança

- O login de produção é email/senha com bcrypt e JWT revogável no
  `session_state` do Streamlit.
- `JWT_SECRET` é obrigatório e não pode ser versionado.
- Novo login rotaciona sessões; logout e troca/redefinição de senha revogam os
  tokens previstos na spec.
- OIDC permanece opcional e desabilitado por padrão. Não o torne obrigatório
  nem altere o login tradicional sem spec, ADR e configuração de deploy.
- Nunca logue senhas, JWTs, segredos, credenciais de email ou conteúdo sensível
  de backups.
- Backups/restaurações mantêm limites, reautenticação e política fail-closed.

## 5. Rastreabilidade

Para regra não óbvia, cite a spec imediatamente acima do cálculo ou validação:

```python
# spec: classificacao v1.0 — critério 5
```

Ao mudar a versão de uma spec, revise as referências `spec:` no código.

## 6. Checklist de entrega

- [ ] Spec existente e sem pendência bloqueante.
- [ ] Critérios de aceite cobertos por teste ou verificação manual explícita.
- [ ] Regras e arquitetura atualizadas quando afetadas.
- [ ] ADR criado para decisão técnica não trivial.
- [ ] Limites `ui` → `services` → `db` respeitados.
- [ ] Nenhum segredo ou dado de runtime versionado.
- [ ] Testes direcionados e suíte relevante aprovados.
- [ ] Versão, data e changelog documental atualizados.

## 7. Referências rápidas

| Documento | Uso |
|---|---|
| [`docs/README.md`](docs/README.md) | Mapa de conteúdo |
| [`docs/sdd.md`](docs/sdd.md) | Processo SDD |
| [`docs/02_regras_de_negocio.md`](docs/02_regras_de_negocio.md) | Regras canônicas |
| [`docs/03_spec.md`](docs/03_spec.md) | Spec consolidada legada |
| [`docs/04_arquitetura.md`](docs/04_arquitetura.md) | Arquitetura e dados |
| [`docs/glossario.md`](docs/glossario.md) | Vocabulário |
| [`docs/templates/spec-template.md`](docs/templates/spec-template.md) | Modelo documental |
| [`docs/adr/`](docs/adr/) | Decisões técnicas |

