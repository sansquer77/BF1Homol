import streamlit as st
from utils.helpers import render_page_header

def main():
    render_page_header(st, "Sobre o BF1")

    st.markdown("""
    ## 🏁 BF1 - Bolão de Fórmula 1

    O **BF1** é uma plataforma de bolão de Fórmula 1 criada para organizar apostas,
    classificação e histórico da temporada com transparência e praticidade.
    O sistema concentra em um único app os fluxos de participantes e administração,
    mantendo rastreabilidade das ações e regras claras de pontuação.

    ### ✒️ Funcionalidades principais (v3.5)

    - Cadastro e gestão de apostas para cada corrida
    - Geração de aposta automática e modo "Sem ideias" com apoio estratégico
    - Aposta especial do campeonato (campeão, vice e equipe)
    - Classificação geral, por corrida e histórico por temporada
    - Análises detalhadas e logs de apostas
    - Gestão de usuários, pilotos, provas, regras e resultados
    - Backup/restauração completa e importação/exportação por tabela
    - Registro de abandonos (DNF) com penalidade automática
    - Regras por temporada (normal/sprint), incluindo pontos dobrados e bônus
    - Hall da Fama e painel com indicadores da temporada

    ### 👨‍💻 Desenvolvimento

    - **Desenvolvedor:** Cristiano Gaspar
    - **Tecnologias utilizadas no app:**
        - **Frontend/App:** Streamlit, streamlit-option-menu, extra-streamlit-components
        - **Backend e dados:** Python, PostgreSQL (psycopg + psycopg-pool), SQLite (legado/migração), pandas, numpy
        - **Visualização:** Plotly, Altair, Matplotlib
        - **Segurança e autenticação:** bcrypt, PyJWT, cryptography
        - **Integrações e utilitários:** httpx, requests, openpyxl, python-dotenv

    ### 💡 Missão e inspiração

    O BF1 nasceu da paixão por corrida e da vontade de manter a disputa entre amigos
    organizada, justa e divertida, com histórico confiável e operação simples no dia a dia.

    ### 📬 Contato e créditos

    - Para dúvidas, sugestões ou reportar bugs:
        - **E-mail:** cristiano_gaspar@outlook.com
    - Agradecimentos a todos os participantes e beta testers do bolão ao longo dos anos.

    ### ☁️ Infraestrutura

    O BF1 roda em infraestrutura cloud, com banco PostgreSQL gerenciado,
    foco em disponibilidade e rotinas de backup/restauração para continuidade do serviço.

    ---
    <small>Versão atual: 3.0-2026. Todos os direitos reservados.</small>

    <a href="https://www.digitalocean.com/?refcode=7a57329868da&utm_campaign=Referral_Invite&utm_medium=Referral_Program&utm_source=badge"><img src="https://web-platforms.sfo2.cdn.digitaloceanspaces.com/WWW/Badge%201.svg" alt="DigitalOcean Referral Badge" /></a>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
