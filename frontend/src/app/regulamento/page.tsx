import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { TenorEmbed } from "@/components/tenor-embed";

export const metadata: Metadata = { title: "Regulamento" };

export default function RegulationPage() {
  return (
    <AppShell>
      <article className="institutional-page regulation-page">
        <header className="institutional-hero">
          <p className="eyebrow">Documento oficial · Temporada 2026</p>
          <h1>Regulamento BF1-2026</h1>
          <p>Regras completas do campeonato, da largada à premiação.</p>
        </header>

        <div className="institutional-layout">
          <aside className="document-index" aria-label="Índice do regulamento">
            <span>Conteúdo</span>
            <a href="#inscricoes">01 · Inscrições</a>
            <a href="#apostas">02 · Apostas</a>
            <a href="#ausencias">03 · Ausências</a>
            <a href="#campeonato">04 · Campeonato</a>
            <a href="#corrida">05 · Corrida</a>
            <a href="#descarte">06 · Descarte</a>
            <a href="#desempate">07 · Desempate</a>
            <a href="#premiacao">08 · Premiação</a>
          </aside>

          <div className="document-content">
            <p className="document-lead">O BF1-2026 terá início oficialmente em 08 de março, no dia do GP da Austrália, e terminará em 06 de dezembro, quando será disputado o último GP, o de Abu Dhabi.</p>

            <section id="inscricoes">
              <p className="section-number">01</p><h2>Inscrições</h2>
              <ul>
                <li>As inscrições para o BF1 estão liberadas a partir de qualquer etapa.</li>
                <li>A inscrição é de R$ 200,00, paga no ato da inscrição via PIX, com QR Code disponível no grupo do WhatsApp.</li>
                <li>Em caso de desistência durante o campeonato, a taxa de inscrição não será devolvida.</li>
                <li>A pontuação do novo participante será 85% da pontuação do participante mais mal colocado no bolão no momento da inscrição. Se a entrada ocorrer após o início do campeonato, sua aposta de campeão receberá zero ponto.</li>
              </ul>
            </section>

            <section id="apostas">
              <p className="section-number">02</p><h2>Apostas dos participantes</h2>
              <ul>
                <li>As apostas devem ser efetuadas até o horário oficial da prova programado no app.</li>
                <li>O app mantém log e timestamp de todas as apostas, além de enviar confirmação por e-mail.</li>
                <li>O participante pode enviar quantas apostas quiser; será válida a última enviada dentro do prazo.</li>
                <li>Apostas registradas após o horário da largada serão desconsideradas e permanecerão registradas no log.</li>
                <li>Os horários das corridas estão disponíveis no Calendário.</li>
              </ul>
            </section>

            <section id="ausencias">
              <p className="section-number">03</p><h2>Ausências e penalizações</h2>
              <ul>
                <li>Quem não apostar dentro do prazo concorrerá com a mesma aposta da corrida anterior.</li>
                <li>Na primeira ausência, serão computados 100% dos pontos.</li>
                <li>Se o participante não apostar na primeira corrida e não houver aposta para repetição, será gerada uma aposta aleatória, preservando o benefício da primeira ausência.</li>
                <li>A partir do segundo atraso, a pontuação receberá desconto de 20%.</li>
              </ul>
            </section>

            <section id="campeonato">
              <p className="section-number">04</p><h2>Pontuação do campeonato</h2>
              <p>Cada participante deve indicar o campeão e o vice do campeonato de pilotos e a equipe campeã de construtores antes do início da primeira prova do ano.</p>
              <div className="score-grid" aria-label="Bônus das apostas do campeonato">
                <span><strong>125</strong><small>Campeão</small></span>
                <span><strong>100</strong><small>Vice</small></span>
                <span><strong>85</strong><small>Equipe</small></span>
              </div>
              <p>Os bônus correspondentes aos acertos serão somados à pontuação ao final do campeonato.</p>
            </section>

            <section id="corrida">
              <p className="section-number">05</p><h2>Aposta de corrida</h2>
              <p>Cada participante possui 15 fichas para distribuir a cada corrida:</p>
              <ul>
                <li>A aposta deve conter no mínimo cinco pilotos de equipes diferentes.</li>
                <li>O limite é de cinco fichas por piloto.</li>
                <li>Corridas Sprint seguem a mesma regra, são provas válidas e têm pontuação dobrada.</li>
                <li>Deve ser indicado o piloto que chegará em 11º lugar; o acerto vale 50 pontos extras.</li>
                <li>Se um piloto apostado não terminar a prova, são descontados 10 pontos por piloto.</li>
              </ul>
              <div className="formula-card"><span>Cálculo da prova</span><strong>fichas × pontos do piloto + bônus do 11º − punições por abandono</strong></div>
              <p>As apostas e apurações ficam registradas no sistema, e o placar atualizado é publicado no grupo do WhatsApp após as corridas.</p>
            </section>

            <section id="descarte">
              <p className="section-number">06</p><h2>Regra de descarte</h2>
              <p>Ao final do campeonato, cada participante terá descartada a pontuação de sua pior corrida. Durante a temporada, a classificação apresenta o descarte provisório considerando apenas provas realizadas; a prova descartada pode mudar após cada resultado.</p>
            </section>

            <section id="desempate">
              <p className="section-number">07</p><h2>Critérios de desempate</h2>
              <p>Em caso de empate na classificação final, as posições são definidas nesta ordem:</p>
              <ol>
                <li>Maior quantidade de acertos do 11º lugar.</li>
                <li>Acerto do campeão.</li>
                <li>Acerto da equipe campeã.</li>
                <li>Acerto do vice.</li>
                <li>Maior quantidade de apostas enviadas primeiro ao longo do ano.</li>
              </ol>
            </section>

            <section id="premiacao">
              <p className="section-number">08</p><h2>Pagamento e premiação</h2>
              <ul>
                <li>O primeiro colocado recebe voucher de 40% do fundo, o segundo 30% e o terceiro 20%, destinados à compra de whiskys à escolha.</li>
                <li>Os 10% restantes são destinados à manutenção e administração.</li>
                <li>A premiação será realizada em um happy hour definido com os participantes após o final do campeonato.</li>
              </ul>
            </section>

            <footer className="regulation-signoff">
              <p>Para dúvidas, consulte a administração ou o grupo oficial do BF1.</p>
              <strong>The best decision is my decision! 🏁</strong>
            </footer>

            <TenorEmbed />
          </div>
        </div>
      </article>
    </AppShell>
  );
}
