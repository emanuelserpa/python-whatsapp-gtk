#!/usr/bin/env python3

"""
Python WhatsApp GTK
-------------------
Um cliente não-oficial e leve para o WhatsApp Web utilizando Webkit2 e GTK3.
Destaques:
- Economia de recursos (RAM/CPU) comparado a navegadores completos.
- Sessão isolada: não mistura cookies/cache com seu navegador principal.
- Integração com o ambiente gráfico Linux (GNOME/XDG).

Autor: Lourival Dantas
Licença: GPLv3
"""

import fcntl
import gi
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# Tenta importar a biblioteca de notificações. Se não tiver, segue sem ela.
notifications_enabled = False
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    notifications_enabled = True
except ValueError:
    logging.warning("Biblioteca de notificações não encontrada. Iniciando sem ela.")

# Garante que as versões corretas das bibliotecas do sistema operacional sejam carregadas.
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, Gdk, WebKit2, GLib

# --- Configuration & Constants ---
APP_NAME = "python-whatsapp-gtk"
WINDOW_TITLE = "WhatsApp"
DEFAULT_WIDTH = 1000
DEFAULT_HEIGHT = 700
WHATSAPP_URL = "https://web.whatsapp.com/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# CSS para ocultar banners e limpar a interface
INJECTED_STYLES = """
    svg[viewBox="0 0 228 152"] { display: none !important; }

    h1.html-h1 { display: none !important; }
    h1.html-h1 ~ div button { display: none !important; }
    
    div:has(> h1.html-h1) { display: none !important; }

    span[data-icon="wa-square-icon"] { display: none !important; }

    div[role="button"]:has(span[data-icon="wa-square-icon"]) { display: none !important; }
    
    div[role="button"]:has(> div > span[data-icon="wa-square-icon"]) { display: none !important; }

    div:has(> div > span[data-icon="web-login-desktop-upsell-illustration"]) { display: none !important; }          

    div:has(> div > div > span[data-icon="web-login-desktop-upsell-illustration"]) { display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }

    div:has(> div > div > div > span[data-icon="web-login-desktop-upsell-illustration"]) { display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }
"""

def get_app_data_path() -> Path:
    """Retorna o diretório padrão do usuário (XDG Standard) para dados da aplicação."""
    path = Path(GLib.get_user_data_dir()) / APP_NAME
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError as error:
        sys.stderr.write(f"CRITICAL: Falha ao criar repositório de dados: {error}\n")
        sys.exit(1)

class ClientWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title=WINDOW_TITLE)
        
        self.base_path: Path = get_app_data_path()
        self.state_file: Path = self.base_path / "window_state.json"
        self.lock_file_path: Path = self.base_path / "app.lock"
        
        # Cria um arquivo de trava. Se já estiver trancado por outro, fecha este.
        try:
            self.lock_fp = open(self.lock_file_path, 'w')
            # Tenta adquirir bloqueio exclusivo (LOCK_EX) e sem esperar (LOCK_NB).
            fcntl.lockf(self.lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            logging.warning("Outra instância já está rodando. Encerrando")
            sys.exit(0)

        if not self.load_window_state():
            self.set_default_size(DEFAULT_WIDTH, DEFAULT_HEIGHT)

        log_file: Path = self.base_path / "application.log"

        # Salva logs em arquivos para auditoria.
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        try:
            # isola cookies e cache na pasta designada, sem misturar com o navegador do sistema operacional.
            data_manager = WebKit2.WebsiteDataManager(
                base_data_directory=str(self.base_path),
                base_cache_directory=str(self.base_path)
            )

            context = WebKit2.WebContext.new_with_website_data_manager(data_manager)

            # Otimiza o gerenciamento de RAM para Single SPA.
            context.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
            # Desativa o corretor ortográfico para economizar RAM
            context.set_spell_checking_enabled(False)

            if notifications_enabled:
                try:
                    Notify.init(WINDOW_TITLE)
                    context.connect("show-notification", self._on_show_notification)
                except Exception as error:
                    logging.warning(f"Erro ao inicializar notificações: {error}")

            self.webview = WebKit2.WebView.new_with_context(context)
            content_manager = self.webview.get_user_content_manager()

            # Injeta CSS para limpar a interface
            style = WebKit2.UserStyleSheet.new(
                INJECTED_STYLES,
                WebKit2.UserContentInjectedFrames.TOP_FRAME,
                WebKit2.UserStyleLevel.USER,
                None,
                None
            )

            content_manager.add_style_sheet(style)

            # ----- WebView Connect -----
            self.connect("delete-event", self.save_window_state)
            self.connect("key-press-event", self._on_key_press)
            self.webview.connect("load-failed", self._on_load_failed)
            self.webview.connect("decide-policy", self._on_decide_policy) # Evita que links externos sejam abertos no wrapper.
            self.webview.connect("create", self._on_create_web_view) # Captura tentativas de abrir novas janelas por JavaScript.
            self.webview.connect("permission-request", self._on_permission_request) # Gerencia as permissões de microfone e câmera.

            settings = self.webview.get_settings()

            # Força o uso da GPU para renderização.
            settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)

            settings.set_enable_write_console_messages_to_stdout(False) # Limpa o terminal,
            settings.set_enable_developer_extras(False) # Desativa funções de desenvolvedor.
            
            # Define o User-Agent
            settings.set_user_agent(USER_AGENT)

            # Carrega a aplicação
            self.webview.load_uri(WHATSAPP_URL)
            self.add(self.webview)
        except Exception as error:
            # Captura falhas na engine do navegador.
            logging.critical(f"Erro fatal ao iniciar WebKit: {error}", exc_info=True)
            raise error

    def save_window_state(self, widget: Gtk.Widget, event: Any) -> bool:
        try:
            size = self.get_size()
            position = self.get_position()
            is_maximized = self.is_maximized()

            state = {
                "width": size[0],
                "height": size[1],
                "x": position[0],
                "y": position[1],
                "is_maximized": is_maximized
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f)
            
            logging.info("Estado de janela salvo.")

        except Exception as error:
            logging.warning(f"Erro ao salvar estado: {error}")

        return False

    def load_window_state(self) -> bool:
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

                self.resize(state.get("width", DEFAULT_WIDTH), state.get("height", DEFAULT_HEIGHT))

                if state.get("is_maximized", False):
                    self.maximize()
                else:
                    self.move(state.get("x", 0), state.get("y", 0))

                logging.info("Estado de janela restaurado com sucesso.")
                return True
        except Exception as error:
            logging.warning(f"Não foi possível restaurar o estado da janela: {error}")
        return False

    def _on_key_press(self, widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        # Permite recarregar a página pressionando F5
        if event.keyval == Gdk.KEY_F5:
            logging.info("Tecla F5 pressionada. Recarregando página...")
            self.webview.reload()
            return True
        return False

    def _on_load_failed(self, webview: WebKit2.WebView, load_event: WebKit2.LoadEvent, failing_uri: str, error: GLib.Error) -> bool:
        # Tenta reconexão caso a internet fique fora do ar.
        logging.error(f"Falha ao carregar {failing_uri}: {error.message}")
        
        # Cria um pop-up nativo de erro
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            message_format="Falha de Conexão"
        )
        dialog.format_secondary_text(
            f"Não foi possível carregar o WhatsApp Web.\n\nVerifique sua internet.\nDetalhe: {error.message}\n\nTentando reconectar em 10 segundos..."
        )
        dialog.run()
        dialog.destroy()
        
        # Tenta recarregar a página automaticamente após 10 segundos
        GLib.timeout_add_seconds(10, self.webview.reload)
        
        return True

    def _on_show_notification(self, webview: WebKit2.WebView, notification: WebKit2.Notification) -> bool:
        # Exibe notificações nativas.
        try:
            n = Notify.Notification.new(
                notification.get_title(),
                notification.get_body(),
                "dialog-information"
            )
            n.show()
            logging.info("notificação enviada ao sistema.")
            return True
        except Exception as error:
            logging.warning(f"Erro ao exibir notificação; {error}")
            return False

    def _on_permission_request(self, webview: WebKit2.WebView, request: WebKit2.PermissionRequest) -> bool:
        # Aceita automaticamente solicitações de microfone e câmera.
        logging.info("Permissão de dispositivo solicitada. Acesso concedido.")
        request.allow()
        return True

    def _on_decide_policy(self, webview: WebKit2.WebView, decision: WebKit2.PolicyDecision, decision_type: WebKit2.PolicyDecisionType) -> bool:
        if decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            navigation_action = decision.get_navigation_action()
            request = navigation_action.get_request()
            uri = request.get_uri()
            
            if uri and "whatsapp.com" not in uri and "javascript:" not in uri:
                try:
                    Gtk.show_uri_on_window(self, uri, Gtk.get_current_event_time())
                    decision.ignore()
                    logging.info(f"Link externo aberto no navegador: {uri}")
                    return True
                except Exception as error:
                    logging.warning(f"Falha ao abrir link externo: {error}")
        
        return False

    def _on_create_web_view(self, webview: WebKit2.WebView, navigation_action: WebKit2.NavigationAction) -> Optional[WebKit2.WebView]:
        request = navigation_action.get_request()
        uri = request.get_uri()
        
        if uri:
            try:
                Gtk.show_uri_on_window(self, uri, Gtk.get_current_event_time())
                logging.info(f"Popup/nova janela aberta no navegador: {uri}")
            except Exception as error:
                logging.warning(f"Falha ao abrir popup no navegador: {error}")
        
        return None

if __name__ == "__main__":
    
    GLib.set_prgname(APP_NAME)
    
    try:
        app = ClientWindow()
        app.connect("destroy", Gtk.main_quit)
        app.show_all()
        Gtk.main()
    except KeyboardInterrupt:
        # Permite fechar via Terminal com Ctrl+C sem exibir erro.
        logging.info("Aplicação interrompida pelo usuário")
    except Exception as error:
        # Loga qualquer erro não tratado que derrube a aplicação.
        logging.critical("A aplicação caiu inesperadamente", exc_info=True)
