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

# Tenta importar AppIndicator3 para o ícone da bandeja
app_indicator_enabled = False
try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
    app_indicator_enabled = True
except (ValueError, ImportError):
    logging.warning("AppIndicator3 não encontrado. O ícone na bandeja será desativado.")


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
DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

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

def load_or_create_config(base_path: Path) -> Dict[str, str]:
    """Carrega as configurações do arquivo JSON ou cria um novo com valores padrão."""
    config_file = base_path / "config.json"
    default_config = {
        "user_agent": DEFAULT_USER_AGENT
    }

    if not config_file.exists():
        try:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            logging.info(f"Arquivo de configuração criado em: {config_file}")
            return default_config
        except Exception as e:
            logging.error(f"Falha ao criar arquivo de configuração: {e}")
            return default_config

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            # Garante que chaves essenciais existam (merge com defaults)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        logging.error(f"Falha ao ler arquivo de configuração: {e}. Usando padrões.")
        return default_config

class ClientWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title=WINDOW_TITLE)
        
        self.base_path: Path = get_app_data_path()
        self.state_file: Path = self.base_path / "window_state.json"
        self.lock_file_path: Path = self.base_path / "app.lock"
        self.icon_path: Path = self.base_path / "icon.png"

        # Setup Logging
        log_file: Path = self.base_path / "application.log"
        # Reconfigura o logger básico para arquivo
        # Nota: basicConfig faz nada se o root logger já estiver configurado, 
        # mas aqui garantimos que não passamos argumentos inválidos.
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Cria um arquivo de trava. Se já estiver trancado por outro, fecha este.
        try:
            self.lock_fp = open(self.lock_file_path, 'w')
            fcntl.lockf(self.lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            logging.warning("Outra instância já está rodando. Encerrando")
            sys.exit(0)

        # Carrega configuração (User Agent, etc)
        self.config = load_or_create_config(self.base_path)

        if not self.load_window_state():
            self.set_default_size(DEFAULT_WIDTH, DEFAULT_HEIGHT)
            self.maximize()

        # Configurar ícone da janela
        try:
            # Tenta usar o ícone do sistema ou do diretório local
            if self.icon_path.exists():
                self.set_icon_from_file(str(self.icon_path))
            else:
                self.set_icon_name("whatsapp")
        except Exception as e:
            logging.warning(f"Erro ao definir ícone da janela: {e}")

        self._init_webview()
        self._setup_signals()

        self.webview.load_uri(WHATSAPP_URL)
        self.add(self.webview)

    def _setup_signals(self):
        self.connect("key-press-event", self._on_key_press)
        
        if app_indicator_enabled:
            # Se tem bandeja, intercepta o fechar para minimizar
            self.connect("delete-event", self._on_window_delete_event)
        else:
            # Se não, fecha normal
            self.connect("delete-event", self.save_window_state)

    def _init_webview(self):
        # Configurar Profile (sessão persistente)
        data_manager = WebKit2.WebsiteDataManager(
            base_data_directory=str(self.base_path),
            base_cache_directory=str(self.base_path)
        )
        
        context = WebKit2.WebContext.new_with_website_data_manager(data_manager)
        
        # Configurações do WebView
        self.webview = WebKit2.WebView.new_with_context(context)
        content_manager = self.webview.get_user_content_manager()
        
        # Inject CSS
        style = WebKit2.UserStyleSheet.new(
            INJECTED_STYLES,
            WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserStyleLevel.USER,
            None,
            None
        )
        content_manager.add_style_sheet(style)
        
        settings = self.webview.get_settings()
        settings.set_enable_developer_extras(False)
        settings.set_enable_page_cache(True)
        settings.set_enable_html5_local_storage(True)
        settings.set_javascript_can_open_windows_automatically(False)
        settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)

        # User Agent
        current_ua = self.config.get("user_agent", DEFAULT_USER_AGENT)
        settings.set_user_agent(current_ua)
        logging.info(f"User-Agent definido: {current_ua}")

        # Drag & Drop fix
        self.drag_dest_unset()

        # Connect Signals for Webiew
        self.webview.connect("load-failed", self._on_load_failed)
        self.webview.connect("show-notification", self._on_show_notification)
        self.webview.connect("permission-request", self._on_permission_request)
        self.webview.connect("decide-policy", self._on_decide_policy)
        self.webview.connect("create", self._on_create_web_view)
        
        # Download Manager
        context.connect("download-started", self._on_download_started)

        # Dark Mode
        self._apply_dark_mode_if_needed(content_manager)

        # Tray Icon initialization (depende da UI)
        self.indicator = None
        if app_indicator_enabled:
            self._init_tray_icon()

    def _setup_signals(self):
        self.connect("key-press-event", self._on_key_press)
        
        if app_indicator_enabled:
            # Se tem bandeja, intercepta o fechar para minimizar
            self.connect("delete-event", self._on_window_delete_event)
        else:
            # Se não, fecha normal
            self.connect("delete-event", self.save_window_state)

    def _init_tray_icon(self):
        try:
            # Tenta usar ícone local como preferência se existir (garantia de visual), senão fallback pro sistema
            icon_name = "whatsapp"
            # Em alguns sistemas AppIndicator precisa do caminho absoluto se não for ícone de tema
            if self.icon_path.exists():
                icon_name = str(self.icon_path)
            
            self.indicator = AppIndicator3.Indicator.new(
                APP_NAME,
                icon_name,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            
            # Se o ícone não carregou pelo caminho, tenta o nome genérico como fallback
            # (A API do AppIndicator não tem um check fácil de 'is_valid', então confiamos no GTK Theme se falhar visualmente)

            menu = Gtk.Menu()
            
            item_show = Gtk.MenuItem(label="Abrir WhatsApp")
            item_show.connect("activate", self._show_window)
            menu.append(item_show)
            
            menu.append(Gtk.SeparatorMenuItem())
            
            item_quit = Gtk.MenuItem(label="Sair")
            item_quit.connect("activate", self._quit_application)
            menu.append(item_quit)
            
            menu.show_all()
            self.indicator.set_menu(menu)
            
            logging.info(f"Ícone na bandeja inicializado (Icon: {icon_name}).")
        except Exception as e:
            logging.warning(f"Erro ao criar ícone na bandeja: {e}")
            self.indicator = None

    def _apply_dark_mode_if_needed(self, content_manager: WebKit2.UserContentManager):
        try:
            settings = Gtk.Settings.get_default()
            theme_name = settings.get_property("gtk-theme-name")
            prefer_dark = settings.get_property("gtk-application-prefer-dark-theme")
            
            is_dark = "dark" in theme_name.lower() or prefer_dark

            if is_dark:
                logging.info(f"Modo escuro detectado (Tema: {theme_name}). Aplicando...")
                
                # Script para adicionar a classe 'dark' ao body quando o documento carregar
                js_dark_mode = """
                    window.addEventListener('load', function() {
                        document.body.classList.add('dark');
                    });
                    // Caso o carregamento já tenha ocorrido ou seja dinâmico:
                    if (document.body) {
                        document.body.classList.add('dark');
                    }
                    // Observador para garantir que a classe persista
                    const observer = new MutationObserver(function(mutations) {
                        if (!document.body.classList.contains('dark')) {
                            document.body.classList.add('dark');
                        }
                    });
                    if (document.body) {
                        observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
                    }
                """
                
                script = WebKit2.UserScript.new(
                    js_dark_mode,
                    WebKit2.UserContentInjectedFrames.TOP_FRAME,
                    WebKit2.UserScriptInjectionTime.END,
                    None,
                    None
                )
                content_manager.add_script(script)
        except Exception as e:
            logging.warning(f"Erro ao tentar aplicar modo escuro: {e}")

    def _show_window(self, widget: Any):
        self.show()
        self.present()

    def _quit_application(self, widget: Any):
        self.save_window_state(self, None)
        Gtk.main_quit()

    def _on_window_delete_event(self, widget: Gtk.Widget, event: Any) -> bool:
        # Salva o estado antes de esconder
        self.save_window_state(widget, event)
        # Esconde a janela mas mantém o app rodando
        self.hide()
        return True

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

        # Se não tiver indicador, retorna False para propagar o evento destroy (fechar app)
        # Se tiver indicador, o método _on_window_delete_event já retornou True para impedir o fechamento
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

    # --- Download Manager Handlers ---

    def _on_download_started(self, context: WebKit2.WebContext, download: WebKit2.Download):
        logging.info("Iniciando download...")
        # Conecta aos sinais do objeto Download
        download.connect("decide-destination", self._on_download_decide_destination)
        download.connect("finished", self._on_download_finished)
        download.connect("failed", self._on_download_failed)

    def _on_download_decide_destination(self, download: WebKit2.Download, suggested_filename: str) -> bool:
        logging.info(f"Solicitado destino para arquivo: {suggested_filename}")
        
        dialog = Gtk.FileChooserDialog(
            title="Salvar arquivo",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.ACCEPT
        )

        # Define o nome sugerido
        if suggested_filename:
            dialog.set_current_name(suggested_filename)
        else:
            dialog.set_current_name("whatsapp_download")
        
        # Tenta definir o diretório de downloads padrão
        downloads_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        if downloads_dir:
            dialog.set_current_folder(downloads_dir)

        response = dialog.run()
        
        if response == Gtk.ResponseType.ACCEPT:
            uri = dialog.get_uri()
            logging.info(f"Destino definido: {uri}")
            download.set_destination(uri)
            dialog.destroy()
            return True # Retorna True para indicar que nós lidamos com a decisão
        
        dialog.destroy()
        return False # Retorna False se o usuário cancelou (o download pode falhar ou ser cancelado)

    def _on_download_finished(self, download: WebKit2.Download):
        logging.info("Download concluído com sucesso.")
        if notifications_enabled:
            try:
                n = Notify.Notification.new("Download Concluído", "Arquivo salvo com sucesso.", "document-save")
                n.show()
            except Exception:
                pass

    def _on_download_failed(self, download: WebKit2.Download, error: GLib.Error):
        logging.warning(f"Download falhou: {error}")
        if notifications_enabled:
            try:
                n = Notify.Notification.new("Falha no Download", f"Erro: {error}", "dialog-error")
                n.show()
            except Exception:
                pass

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
