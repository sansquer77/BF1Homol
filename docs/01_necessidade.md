# Necessidade que o Sistema Atende

## Visão Geral

O **BF1** é uma plataforma de bolão de Fórmula 1 multi-temporada, hospedada na DigitalOcean App Platform, que permite a um grupo fechado de participantes realizarem apostas sobre os resultados das corridas e sprints do campeonato da F1, com pontuação automática, classificação em tempo real e histórico completo.

## Problema que Resolve

Grupos de fãs de F1 que realizam bolões informais entre amigos enfrentam os seguintes problemas:

- **Controle manual de apostas**: registrar, validar e pontuar apostas manualmente é trabalhoso, propenso a erros e falta de transparência.
- **Regras inconsistentes entre temporadas**: as regras do bolão (fichas, pontuações, penalidades) mudam a cada ano e precisam ser versionadas.
- **Falta de histórico**: sem um sistema, o histórico de temporadas anteriores se perde.
- **Acesso justo**: sem controle de horário, participantes poderiam apostar após o início da corrida, gerando desvantagem.
- **Gestão de usuários**: controlar quem está ativo, inativo ou é administrador de forma manual é ineficiente.

## Público-Alvo

| Perfil | Descrição |
|--------|----------|
| **Master** | Administrador total do sistema (cria temporadas, gerencia regras, faz backup) |
| **Admin** | Operador do bolão (lança resultados, gerencia apostas e pilotos) |
| **Participante** | Usuário ativo que realiza apostas e acompanha a classificação |
| **Inativo** | Ex-participante com acesso somente leitura ao histórico |

## Necessidades Funcionais Atendidas

1. **Cadastro e autenticação segura** de usuários com senhas criptografadas (bcrypt) e tokens JWT.
2. **Gestão de temporadas** com regras específicas por tipo de prova (Normal, Sprint).
3. **Cadastro de pilotos e provas** do calendário oficial da F1.
4. **Apostas com deadline automático**: o sistema bloqueia apostas após o horário de início da corrida (fuso de São Paulo).
5. **Pontuação automática** baseada nas regras da temporada vigente, considerando fichas dinâmicas, bônus do 11º colocado e penalidades por abandono.
6. **Apostas automáticas** geradas pelo sistema para usuários ausentes (com penalidade percentual configurável).
7. **Classificação geral e por temporada** com suporte a descarte de piores resultados.
8. **Apostas de campeonato** (quem será o campeão e vice).
9. **Hall da Fama** com histórico de campeões de temporadas anteriores.
10. **Dashboard F1** com estatísticas e análises das apostas.
11. **Backup dos bancos de dados** (Excel e SQL) com validação de integridade.
12. **Logs de apostas e acessos** para auditoria.
13. **Regulamento** do bolão acessível a todos os participantes.
14. **PWA (Progressive Web App)** para acesso mobile via ícone na tela inicial do dispositivo.

## Benefícios Entregues

- **Transparência total**: qualquer participante pode ver a classificação e o log de apostas em tempo real.
- **Automatização**: pontuação, classificação e apostas automáticas eliminam trabalho manual.
- **Rastreabilidade**: logs de acesso e apostas garantem auditoria completa.
- **Multi-temporada**: o sistema mantém o histórico de todas as temporadas sem perda de dados.
- **Segurança**: autenticação JWT, bcrypt, rate limiting e guard de rotas por perfil.
