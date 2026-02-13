import streamlit as st
import streamlit.components.v1 as components

def main():
    st.title("📜 Regulamento BF1-2026 (Completo e Oficial)")

    st.markdown("""
REGULAMENTO BF1-2026

O BF1-2026 terá início, oficialmente, em 08 de março, no dia do GP da Austrália e término em 06 de dezembro, quando será disputado o último GP, o de Abu Dhabi.

**Inscrições**
- Inscrições para o BF1 estão liberadas a partir de qualquer etapa.
- A inscrição é de R$200,00 a ser pago no ato da inscrição via PIX (QR-Code no grupo do WhastApp).
- Em caso de desistência durante o campeonato a taxa de inscrição não será devolvida.
- Cabe ressaltar que a pontuação do novo participante será 85% da pontuação do participante mais mal colocado no bolão no momento da inscrição e terá 0 pontos na aposta de campeão, caso ocorra após o início do campeonato.

**Apostas dos Participantes**
- As apostas devem ser efetuadas até o horário oficial da prova e que está programado dentro do app.
- O app tem log e timestamp de todas as apostas efetuadas, além de enviar confirmação por e-mail.
- O participante pode enviar quantas apostas quiser até o horário limite, sendo válida a última enviada.  
- Apostas registradas após o horário da largada, por exemplo 09:01 sendo a corrida às 09h, serão desconsideradas (E isso fica logado)  
- Os horários das corridas deste ano estão listados no menu - Calendário 2026.

**Ausências e Penalizações**
- O participante que não efetuar a aposta ATÉ O PRAZO irá concorrer com a mesma aposta da última corrida.
- Quando se tratar da primeira vez que a aposta não for feita, será computado 100% dos pontos.
- Caso o apostador não aposte na primeira corrida do campeonato, sem base para repetição da aposta, será gerada uma aposta aleatória e o benefício da regra da primeira falta será mantido.
- Para o segundo atraso em diante, os pontos sofrerão desconto de 20%.

**Pontuação do Campeonato**
- Cada participante deve indicar o campeão e o vice do campeonato de pilotos e a equipe vencedora do campeonato de construtores ANTES do início da primeira prova do ano em formulário específico.
- A pontuação será 125 pontos se acertar o campeão, 100 se acertar o vice, 85 acertando equipe — que serão somados à pontuação ao final do campeonato.

**Aposta de Corrida**
- Cada participante possui 15 (quinze) fichas para serem apostadas a cada corrida:
    - A aposta deve conter no mínimo 5 pilotos de equipes diferentes (apostou no Hamilton, não pode apostar também no Leclerc).
    - Limite de 5 fichas por piloto.
    - As corridas Sprint seguem a mesma regra e são consideradas provas válidas, mas terão a pontuação dobrada.
    - Deve ser indicado o piloto que irá chegar em 11º lugar em todas as provas; em caso de acerto, serão computados 50 pontos extras.
    - Caso o piloto apostado não termine a prova, o participante receberá uma punição de 10 pontos por piloto, que serão descontados da pontuação total do participante.      
- A pontuação do participante será a multiplicação das fichas apostadas em cada piloto pelo número de pontos que ele obteve na prova (fichas x pontos) mais a pontuação do 11º lugar e menos as punições por não terminar a prova.
- As apostas e apurações ficam neste sistema, sendo o placar atualizado publicado no grupo e WhatsApp após as corridas.

**Regra de Descarte**
- Ao final do campeonato, cada participante terá o direito de descartar a pontuação de sua pior corrida, ou seja, aquela em que obteve a menor pontuação.

**Critérios de Desempate**
- Caso haja empate de pontos na classificação final, as posições serão definidas nesta ordem:
    1. Quem mais vezes acertou o 11º lugar.
    2. Quem acertou o campeão.
    3. Quem acertou a equipe campeã.
    4. Quem acertou o vice.
    5. Quem tiver apostado antes mais vezes no ano.

**Forma de Pagamento e Premiação**
- A premiação será um voucher de 40% do fundo arrecadado das inscrições para o primeiro colocado, 30% para o segundo e 20% para o terceiro, que deverão ser utilizados na compra de whiskys à escolha, a serem adquiridos após definição dos vencedores.
- 10% do fundo arrecadado será destinado para a taxa de manutenção e administração.
- A premiação será realizada em um Happy-Hour a ser agendado entre os participantes em data e local definidos posteriormente ao final do campeonato.

---

Para dúvidas, consulte a administração ou acesse o grupo oficial do BF1 e lembrem-se: The best decision is my decision! 🏁
    """)

    components.html(
        """
        <div style="display:flex; justify-content:center;">
            <div class="tenor-gif-embed" data-postid="14649753" data-share-method="host" data-aspect-ratio="1.77778" data-width="50%"><a href="https://tenor.com/view/the-best-decision-is-my-decision-the-best-decisions-my-decision-gif-14649753">The Best Decision Is My Decision Decisions GIF</a>from <a href="https://tenor.com/search/the+best+decision+is+my+decision-gifs">The Best Decision Is My Decision GIFs</a></div>
        </div>
        <script type="text/javascript" async src="https://tenor.com/embed.js"></script>
        """,
        height=520,
    )

if __name__ == "__main__":
    main()
