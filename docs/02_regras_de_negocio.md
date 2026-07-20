---
tipo: produto
area: bf1
status: implementado
versao: 4.1
atualizado: 2026-07-20
relacionados:
  - "[[01_necessidade]]"
  - "[[03_spec]]"
  - "[[04_arquitetura]]"
tags: [produto, "area/bf1", "status/implementado"]
aliases: ["Regras de Negócio"]
---

# Regras de Negócio

> [!info] Status
> **implementado** · área: `bf1` · atualizado em 2026-07-20 · relacionados: [[01_necessidade]], [[03_spec]], [[04_arquitetura]]

## RN-001 — Controle de Acesso por Perfil

- Todo acesso ao sistema requer autenticação via JWT.
- Existem 4 perfis: `master`, `admin`, `participante`, `inativo`.
- Cada rota/página e cada operação sensível possui uma matriz central de perfis autorizados.
- Escritas administrativas revalidam token, usuário, status, perfil e temporada na camada de serviço; valores enviados pela UI não constituem autoridade.
- Usuário com `status != 'ativo'` ou `perfil == 'inativo'` é tratado como **inativo**, independente do perfil cadastrado.
- Usuário inativo **com** histórico de temporadas tem acesso a: Painel, Calendário, Hall da Fama, Dashboard F1, Análise, Log de Apostas, Classificação, Regulamento, Sobre.
- Usuário inativo **sem** histórico tem acesso apenas a: Hall da Fama, Calendário, Dashboard F1 e Minha Conta.

## RN-002 — Janela de Apostas

- O participante pode registrar ou alterar uma aposta até o horário oficial de início da prova, inclusive no instante exato do limite; depois disso a submissão é bloqueada.
- O horário limite é definido pelo campo `horario_prova` da prova, interpretado no fuso **America/Sao_Paulo**.
- Após o horário limite, o sistema bloqueia qualquer submissão (inclusive edições).
- A validação é feita comparando `now_sao_paulo()` com `horario_limite_sp`.

## RN-003 — Regras de Composição da Aposta

Para cada prova, a aposta deve obedecer às regras da temporada/tipo-prova (`regras` table):

| Parâmetro            | Descrição                                                            |
|----------------------|----------------------------------------------------------------------|
| `qtd_minima_pilotos` | Número mínimo de pilotos selecionados                                |
| `quantidade_fichas`  | Total de fichas que deve ser distribuído (soma exata)                |
| `fichas_por_piloto`  | Limite máximo de fichas em um único piloto                           |
| `mesma_equipe`       | Se `False`, nenhum par de pilotos apostados pode ser da mesma equipe |

- O piloto do **11º lugar** (`piloto_11`) deve ser diferente dos demais pilotos apostados.
- Não é permitido repetir o mesmo piloto na lista.
- Todos os pilotos informados devem estar cadastrados como ativos no sistema.

## RN-004 — Fórmula de Pontuação

```
Pontos = Σ (Pontos_Regra[posição_real] × fichas_apostadas) + Bônus_11o − Penalidades
```

- `Pontos_Regra` é a tabela configurada na regra associada à temporada. Na ausência de configuração, o motor usa 25-18-15-12-10-8-6-4-2-1 em provas normais e 8-7-6-5-4-3-2-1 em sprints.
- `Bônus_11o`: valor configurável em `pontos_11_colocado` (padrão: 25 pontos) — concedido se o participante acertou o piloto que terminou em 11º.
- **Penalidade por abandono**: se `penalidade_abandono = True`, deduz `pontos_penalidade` para cada piloto apostado que abandonou a corrida.
- **Dobrada sprint**: se `pontos_dobrada = True`, a pontuação da prova sprint é multiplicada por 2.
- **Aposta automática**: apostas geradas automaticamente pelo sistema recebem penalidade percentual de `penalidade_auto_percent`% (padrão: 20%).

## RN-005 — Apostas Automáticas

- Se um participante **ativo** não registrar aposta até o horário limite, o sistema gera uma aposta automática com `automatica >= 1`.
- A aposta automática tenta reaproveitar a aposta anterior do participante, ajustando para as regras vigentes.
- Se não for possível reaproveitar, uma aposta aleatória válida é gerada.
- Apostas automáticas de 2ª geração em diante (`automatica >= 2`) sofrem penalidade percentual configurável.

## RN-006 — Regras por Temporada e Tipo de Prova

- As regras são registros nomeados em `regras`; cada temporada aponta para uma delas por `temporadas_regras`.
- O tipo da prova (`Normal` ou `Sprint`) seleciona a tabela de pontos e, se `regra_sprint` estiver ativa, ajusta a sprint para 10 fichas e mínimo de 2 pilotos.
- Sem associação para a temporada, o serviço tenta a regra `Padrão BF1`; sem ela, aplica o fallback interno documentado no RN-004.
- A regra inclui fichas, restrição de equipe, descarte, tabelas de pontos, bônus do 11º, penalidades, configuração sprint e bônus do campeonato.

## RN-007 — Descarte de Resultados na Classificação

- Quando `descarte` está ativo na regra da temporada, a classificação elimina a menor pontuação de prova de cada participante.

## RN-008 — Apostas de Campeonato

- Participantes indicam campeão e vice de pilotos e equipe campeã de construtores.
- O prazo termina no instante exato da largada da primeira prova: somente `agora < largada` permite salvar.
- Em `agora == largada` ou depois, a aposta é bloqueada.
- Prova, data ou horário ausente/inválido e falhas de cálculo bloqueiam a aposta e orientam o usuário a avisar o administrador (*fail-closed*).
- A pontuação é calculada separadamente pelos valores `pontos_campeao`, `pontos_vice` e `pontos_equipe` da regra associada.

## RN-009 — Gestão de Usuários

- Apenas o perfil `master` pode criar, editar e inativar usuários.
- Senhas são armazenadas com hash bcrypt (nunca em texto claro).
- Usuários novos podem ser criados com flag `must_change_password = True`, obrigando troca no primeiro acesso.
- O usuário **master** é criado automaticamente no bootstrap da aplicação via `MasterUserManager`.

## RN-010 — Backup e Integridade de Dados

- Apenas o perfil `master` pode acionar backups.
- São suportados backups em Excel (`.xlsx`) e SQL.
- O sistema valida a integridade do backup antes de disponibilizá-lo para download.
- Backups incluem todas as tabelas: usuários, pilotos, provas, apostas, resultados, posições, regras e logs.

## RN-011 — Logs de Auditoria

- Todo acesso autenticado ao sistema é registrado na tabela de logs de acesso.
- Toda submissão de aposta (manual ou automática) é registrada no log de apostas.
- Todos os logs são salvos no banco de dados com o horário do servidor — isso garante que o horário é igual para todos.
- O valor do log visualizado no sistema é ajustado com base no fuso horário escolhido no menu lateral — mas isso é apenas na visualização; o dado no banco ainda é o valor do servidor.
- O Log de Apostas é visível para usuários autenticados conforme o menu e restringe perfis individuais aos próprios dados; o Log de Acessos é exclusivo do `master`.

## RN-012 — Multi-Temporada

- Todos os registros de provas, apostas e posições possuem campo `temporada`.
- O sistema filtra dados por temporada em todas as telas relevantes.
- Um usuário pode ter participado de temporadas anteriores como ativo e estar inativo na temporada atual.
- Ao criar uma nova temporada o sistema mantém os dados das temporadas anteriores como histórico.

## RN-013 — Histórico Consolidado do Participante *(v3.6)*

> [!note] Nova regra adicionada na versão 3.6

- A aba **"Histórico"** no [[03_spec#2.1 Painel do Participante|Histórico no Painel]] consolida dados de **todas as temporadas** em que o participante esteve presente.
- O resumo exibe: melhor colocação (+ ano), melhor pontuação (+ ano), média das posições, média das pontuações e quantidade de acertos do 11º colocado.
- O gráfico de barras empilhadas compara fichas apostadas por piloto em cada temporada.
- O piloto mais apostado (total de fichas em todas as temporadas) é destacado abaixo do gráfico.
- A aba é exibida para **todos os perfis** (ativos e inativos com histórico) quando há ao menos uma aposta cadastrada.
- A lógica reside em `services/historico_service.py` — separada da UI, testável de forma independente.
- **Regra de parse**: chaves do dicionário de posições são normalizadas para `int` em `_parse_posicoes()` para evitar mismatch de tipo ao detectar o 11º colocado.

## RN-014 — Regulamento oficial BF1-2026

- Temporada: 08/03/2026 (GP da Austrália) a 06/12/2026 (GP de Abu Dhabi).
- Inscrição: R$ 200,00 via PIX, permitida a partir de qualquer etapa e sem devolução. Quem entra depois do início recebe 85% da pontuação do último colocado naquele momento e zero nos palpites de campeonato.
- Corridas: 15 fichas, pelo menos 5 pilotos de equipes diferentes, no máximo 5 fichas por piloto, palpite obrigatório do 11º (50 pontos) e penalidade de 10 pontos por piloto apostado que não terminar.
- Sprints seguem a mesma composição e têm pontuação dobrada.
- Ausência: repete-se a última aposta; na primeira falta mantém-se 100% dos pontos. Sem aposta anterior, gera-se uma aposta aleatória. Da segunda falta em diante, aplica-se desconto de 20%.
- Campeonato: 125 pontos por campeão, 100 por vice e 85 pela equipe campeã.
- Descarte: a pior prova de cada participante é eliminada ao fim da temporada.
- Desempate: mais acertos do 11º; acerto do campeão; equipe campeã; vice; maior quantidade de apostas feitas antes dos demais.
- Premiação: vouchers de whisky equivalentes a 40%, 30% e 20% do fundo para 1º, 2º e 3º; 10% para manutenção/administração; entrega em happy hour.

> [!warning] Configuração obrigatória para 2026
> Os fallbacks do motor não representam o regulamento oficial. A regra associada a 2026 deve registrar 15 fichas, mínimo 5, máximo 5 por piloto, equipes distintas, bônus 11º de 50, penalidade de abandono de 10, desconto automático de 20%, descarte ativo, sprint dobrada e bônus 125/100/85. `regra_sprint` deve permanecer desativada para não substituir a composição oficial da sprint por 10 fichas/mínimo 2.

> [!danger] Lacunas conhecidas entre regulamento e código
> A atribuição de 85% para participante inscrito durante a temporada e a distribuição financeira dos prêmios ainda dependem de operação administrativa.

### Changelog

- `4.1` — 2026-07-20 — Deadline de campeonato fail-closed e autorização obrigatória nas operações sensíveis.
- `4.0` — 2026-07-19 — Regras alinhadas ao modelo atual e ao regulamento BF1-2026.
- `3.6` — 2026-05-03 — RN-013 (Histórico Consolidado do Participante) adicionado.
- `3.5` — — Versão base.

### Relacionados

- [[01_necessidade]]
- [[03_spec]]
- [[04_arquitetura]]
