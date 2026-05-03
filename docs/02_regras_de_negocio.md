# Regras de Negócio

## RN-001 — Controle de Acesso por Perfil

- Todo acesso ao sistema requer autenticação via JWT.
- Existem 4 perfis: `master`, `admin`, `participante`, `inativo`.
- Cada rota/página possui uma lista de perfis autorizados (`ROLE_GUARDS`).
- Usuário com `status != 'ativo'` ou `perfil == 'inativo'` é tratado como **inativo**, independente do perfil cadastrado.
- Usuário inativo **com** histórico de temporadas tem acesso a: Painel, Calendário, Hall da Fama, Dashboard F1, Análise, Log de Apostas, Classificação, Regulamento, Sobre.
- Usuário inativo **sem** histórico tem acesso apenas a: Hall da Fama, Calendário, Dashboard F1 e Minha Conta.

## RN-002 — Janela de Apostas

- O participante só pode registrar ou alterar uma aposta até o horário de início da prova.
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

- `Pontos_Regra` é a tabela de pontos por posição definida na regra da temporada (Normal ou Sprint). Fallback: tabela oficial da FIA (25-18-15-12-10-8-6-4-2-1 para corridas normais; 8-7-6-5-4-3-2-1 para sprints).
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

- As regras são cadastradas por par `(temporada, tipo_prova)` com `UNIQUE` no banco.
- Tipos de prova suportados: `Normal`, `Sprint`.
- Se não houver regra cadastrada para uma temporada/tipo, o sistema usa os valores FIA hardcoded como fallback.
- Regras incluem: tabela de pontos por posição (JSON array), pontos sprint, bônus 11º, penalidades, limite de fichas e restrição de equipe.

## RN-007 — Descarte de Resultados na Classificação

- A classificação suporta descarte das piores `N` provas de cada participante (configurável por temporada).
- A pontuação total exibida na classificação considera o descarte.

## RN-008 — Apostas de Campeonato

- Participantes podem apostar no campeão e vice-campeão do campeonato de construtores e pilotos.
- Apostas de campeonato têm prazo próprio, independente das apostas de corrida.
- Pontuação de apostas de campeonato é calculada separadamente.

## RN-009 — Gestão de Usuários

- Apenas o perfil `master` pode criar, editar e inativar usuários.
- Senhas são armazenadas com hash bcrypt (nunca em texto claro).
- Usuários novos podem ser criados com flag `must_change_password = True`, obrigando troca no primeiro acesso.
- O usuário **master** é criado automaticamente no bootstrap da aplicação via `MasterUserManager`.

## RN-010 — Backup e Integridade de Dados

- Apenas o perfil `master` pode acionar backups.
- São suportados backups em Excel (`.xlsx`) e SQL dump.
- O sistema valida a integridade do backup antes de disponibilizá-lo para download.
- Backups incluem todas as tabelas: usuários, pilotos, provas, apostas, resultados, posições, regras e logs.

## RN-011 — Logs de Auditoria

- Todo acesso autenticado ao sistema é registrado na tabela de logs de acesso.
- Toda submissão de aposta (manual ou automática) é registrada no log de apostas.
- Todos os logs são salvos no Banco de dados com o horário do servidor - isso garante que que o horário é igual para todos.
- O valor do log visualizado no sistema é ajustado com base no fuso horário escolhido no menu lateral para ajustar ao horário do participante - Mas isso é apenas na visualização, o dado no Banco ainda é o valor do servidor.
- Logs são visíveis apenas para perfis `master` e `admin`.

## RN-012 — Multi-Temporada

- Todos os registros de provas, apostas e posições possuem campo `temporada`.
- O sistema filtra dados por temporada em todas as telas relevantes.
- Um usuário pode ter participado de temporadas anteriores como ativo e estar inativo na temporada atual.
- Ao criar uma nova temporada o sistema mantem os dados das temporadas como histórico.
