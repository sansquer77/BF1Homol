import streamlit as st
from utils.helpers import render_page_header

def main():
    render_page_header(st, "Sobre o BF1")

    st.markdown("""
    ## 🏁 BF1 - Bolão de Fórmula 1

    **BF1** é um sistema digital de bolão esportivo dedicado à Fórmula 1, criado para proporcionar organização, transparência e diversão para grupos de amigos e entusiastas da categoria. O aplicativo centraliza apostas, classificação, estatísticas e comunicação em uma plataforma intuitiva, segura e acessível via web.

    ### ✒️ Funcionalidades principais (v3.0)

    - Cadastro e gestão de apostas para cada corrida
    - Aposta especial do campeonato (campeão, vice e equipe)
    - Classificação geral e por corrida
    - Relatórios, análise detalhada e logs de apostas
    - Painel de usuários e administração completa
    - Exportação/importação de dados e backup seguro
    - Regulamento oficial, gestão de provas e pilotos
    - Registro de abandonos (DNF) com penalidade automática
    - Pontuação de Sprint ajustada por regra e opção de pontos dobrados
    - Pontos por posição por temporada (com histórico preservado)
    - Classificação com bônus de campeonato detalhados e exportação da tabela

    ### 👨‍💻 Desenvolvimento

    - **Desenvolvedor:** Cristiano Gaspar (administração e código).
    - **Tecnologias:** Python, Streamlit, SQLite, pandas, Plotly, bcrypt, JWT, extra-streamlit-components

    ### 💡 Missão e inspiração

    O BF1 nasceu da paixão pelas corridas e pela convivência entre amigos—buscando promover interação, rivalidade saudável, controle rigoroso das apostas e distribuição transparente dos prêmios.

    ### 📬 Contato e créditos

    - Para dúvidas, sugestões ou reportar bugs:
        - **E-mail:** cristiano_gaspar@outlook.com
    
    - Agradecimentos a todos os participantes e beta testers do bolão ao longo dos anos.

    ### ☁️ Infraestrutura

    O BF1 está hospedado em ambiente cloud, e serveless utilizando serviços como Digital Ocean para performance, redundância e automação de backups.

    ---
    <small>Versão atual: 3.0-2026. Todos os direitos reservados.</small>

    <a href="https://www.digitalocean.com/?refcode=7a57329868da&utm_campaign=Referral_Invite&utm_medium=Referral_Program&utm_source=badge"><img src="https://web-platforms.sfo2.cdn.digitaloceanspaces.com/WWW/Badge%201.svg" alt="DigitalOcean Referral Badge" /></a>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
