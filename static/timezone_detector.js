/**
 * Script para detectar timezone do cliente e passar para Streamlit
 * Injeta automaticamente em cada página
 */

(function() {
  /**
   * Detecta o timezone do cliente usando Intl API nativa (suportada em todos os navegadores modernos)
   * @returns {string} IANA timezone string (ex: "America/Sao_Paulo")
   */
  function getClientTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch (e) {
      console.warn("Erro ao detectar timezone:", e);
      return "UTC";
    }
  }

  /**
   * Comunica o timezone detectado ao Streamlit via sessionStorage
   * Streamlit pode acessar via st.session_state
   */
  function initializeTimezone() {
    const timezone = getClientTimezone();
    
    // Armazena no sessionStorage
    sessionStorage.setItem("client_timezone", timezone);
    
    // Dispatch custom event para componentes Streamlit ouvirem
    window.dispatchEvent(new CustomEvent("timezoneDetected", {
      detail: { timezone: timezone }
    }));
    
    console.log("🌍 Client Timezone detectado:", timezone);
  }

  // Aguarda o DOM estar pronto
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeTimezone);
  } else {
    initializeTimezone();
  }

  // Re-sincroniza quando o Streamlit recarrega (rerun)
  window.addEventListener("message", function(event) {
    // Streamlit pode enviar mensagens; sincroniza timezone quando necessário
    if (event.data.type === "streamlit:render") {
      // Garante que o timezone está sempre atualizado
      const timezone = getClientTimezone();
      sessionStorage.setItem("client_timezone", timezone);
    }
  });
})();
