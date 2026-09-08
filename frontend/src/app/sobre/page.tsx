import type { Metadata } from "next";
import { AboutVersion } from "@/components/about-version";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = { title: "Sobre" };

const capabilities = [
  "Apostas manuais e automáticas por corrida",
  "Palpites de campeão, vice e construtores",
  "Classificação geral, por prova e por temporada",
  "Análises, histórico e trilhas de auditoria",
  "Gestão de usuários, pilotos, provas e regras",
  "Backup e restauração compatíveis com a V3.x",
];

export default function AboutPage() {
  return (
    <AppShell>
      <article className="institutional-page about-page">
        <header className="institutional-hero about-hero">
          <div>
            <p className="eyebrow">Sobre o BF1</p>
            <h1>Estratégia entre amigos, com memória de campeonato.</h1>
            <p>Uma plataforma criada para organizar apostas, classificação e histórico da Fórmula 1 com transparência, rastreabilidade e diversão.</p>
          </div>
          <AboutVersion />
        </header>

        <div className="about-grid">
          <section className="about-card about-card--mission">
            <p className="section-number">01 · Missão</p>
            <h2>Da primeira aposta ao pódio final</h2>
            <p>O BF1 nasceu da paixão por corrida e da vontade de manter uma disputa entre amigos organizada, justa e divertida, com regras claras e histórico confiável.</p>
          </section>
          <section className="about-card">
            <p className="section-number">02 · Capacidades</p>
            <h2>O campeonato em um só lugar</h2>
            <ul>{capabilities.map((item) => <li key={item}>{item}</li>)}</ul>
          </section>
          <section className="about-card">
            <p className="section-number">03 · Engenharia</p>
            <h2>Construído para a V4</h2>
            <dl className="stack-list">
              <div><dt>Interface</dt><dd>Next.js, TypeScript e ApexCharts</dd></div>
              <div><dt>API e domínio</dt><dd>FastAPI e regras Python</dd></div>
              <div><dt>Dados</dt><dd>PostgreSQL compatível com backups V3.x</dd></div>
              <div><dt>Segurança</dt><dd>bcrypt, sessão revogável, CSRF e autorização por objeto</dd></div>
            </dl>
          </section>
          <section className="about-card">
            <p className="section-number">04 · Desenvolvimento</p>
            <h2>Créditos e contato</h2>
            <p><strong>Desenvolvedor:</strong> Cristiano Gaspar</p>
            <p>Para dúvidas, sugestões ou relatos de erro:</p>
            <a className="contact-link" href="mailto:cristiano_gaspar@outlook.com">cristiano_gaspar@outlook.com</a>
          </section>
          <section className="about-card about-card--wide">
            <p className="section-number">05 · Infraestrutura</p>
            <h2>Continuidade com custo consciente</h2>
            <p>O BF1 roda na DigitalOcean App Platform com PostgreSQL gerenciado. Logs operacionais permanecem no banco com exportação administrativa, e os backups locais preservam a estratégia de continuidade definida para o projeto.</p>
            <a className="secondary-action" href="https://www.digitalocean.com/?refcode=7a57329868da&utm_campaign=Referral_Invite&utm_medium=Referral_Program&utm_source=badge" target="_blank" rel="noreferrer">Conhecer a DigitalOcean <span aria-hidden="true">↗</span></a>
          </section>
        </div>
      </article>
    </AppShell>
  );
}
