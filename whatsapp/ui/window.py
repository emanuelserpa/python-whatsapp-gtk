"""
Main Application Window Logic.
"""
import os
import signal
import sys
import json
import fcntl
import logging
from pathlib import Path
from typing import Optional, Any

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, Gdk, WebKit2, GLib

from ..constants import (
    APP_NAME, WINDOW_TITLE, DEFAULT_WIDTH, DEFAULT_HEIGHT, 
    WHATSAPP_URL, DEFAULT_USER_AGENT, INJECTED_STYLES
)
from ..utils import get_app_data_path, setup_logging
from ..config import load_or_create_config
from .tray import TrayIcon, app_indicator_enabled

# Notification Support
notifications_enabled = False
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    notifications_enabled = True
except ValueError:
    pass


class ClientWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title=WINDOW_TITLE)
        
        self.base_path: Path = get_app_data_path()
        self.state_file: Path = self.base_path / "window_state.json"
        self.lock_file_path: Path = self.base_path / "app.lock"
        self.icon_path: Path = self.base_path / "icon.png"

        # Setup Logging
        setup_logging(self.base_path)

        # Single Instance Lock & IPC
        # Usamos 'a+' para não truncar o arquivo se outra instância abrir
        self.lock_fp = open(self.lock_file_path, 'a+')
        self.lock_fp.seek(0)
        
        try:
            # Tenta adquirir o lock
            fcntl.lockf(self.lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Sucesso: Somos a instância principal. Salva o PID.
            self.lock_fp.seek(0)
            self.lock_fp.truncate()
            self.lock_fp.write(str(os.getpid()))
            self.lock_fp.flush()
            
            # Registra handler para restaurar janela ao receber sinal
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._on_app_signal, None)
            
        except IOError:
            # Falha: Outra instância existe. Tenta notificar.
            logging.warning("Outra instância já está rodando.")
            self.lock_fp.seek(0)
            pid_str = self.lock_fp.read().strip()
            
            if pid_str and pid_str.isdigit():
                target_pid = int(pid_str)
                logging.info(f"Enviando sinal de restauração para PID {target_pid}")
                try:
                    os.kill(target_pid, signal.SIGUSR1)
                except ProcessLookupError:
                    pass
                except Exception as e:
                    logging.warning(f"Erro ao enviar sinal: {e}")
            
            sys.exit(0)

        # Load Config
        self.config = load_or_create_config(self.base_path)

        if not self.load_window_state():
            self.set_default_size(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        
        # Window Icon
        try:
            if self.icon_path.exists():
                self.set_icon_from_file(str(self.icon_path))
            else:
                self.set_icon_name("whatsapp")
        except Exception as e:
            logging.warning(f"Erro ao definir ícone da janela: {e}")

        # Initialize Components
        self._init_webview()
        
        # Tray Icon
        self.tray = TrayIcon(self) # Handles logic internally if enabled

        self._setup_signals()

        self.webview.load_uri(WHATSAPP_URL)
        self.add(self.webview)

    def _setup_signals(self):
        self.connect("key-press-event", self._on_key_press)
        
        if app_indicator_enabled:
            self.connect("delete-event", self._on_window_delete_event)
        else:
            self.connect("delete-event", self.save_window_state)

    def _init_webview(self):
        data_manager = WebKit2.WebsiteDataManager(
            base_data_directory=str(self.base_path),
            base_cache_directory=str(self.base_path)
        )
        
        context = WebKit2.WebContext.new_with_website_data_manager(data_manager)
        self.webview = WebKit2.WebView.new_with_context(context)
        content_manager = self.webview.get_user_content_manager()
        
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

        current_ua = self.config.get("user_agent", DEFAULT_USER_AGENT)
        settings.set_user_agent(current_ua)
        logging.info(f"User-Agent definido: {current_ua}")

        self.drag_dest_unset()

        self.webview.connect("load-failed", self._on_load_failed)
        self.webview.connect("show-notification", self._on_show_notification)
        self.webview.connect("permission-request", self._on_permission_request)
        self.webview.connect("decide-policy", self._on_decide_policy)
        self.webview.connect("create", self._on_create_web_view)
        
        context.connect("download-started", self._on_download_started)

        self._apply_dark_mode_if_needed(content_manager)

    def _apply_dark_mode_if_needed(self, content_manager: WebKit2.UserContentManager):
        try:
            settings = Gtk.Settings.get_default()
            theme_name = settings.get_property("gtk-theme-name")
            prefer_dark = settings.get_property("gtk-application-prefer-dark-theme")
            
            is_dark = "dark" in theme_name.lower() or prefer_dark

            if is_dark:
                logging.info(f"Modo escuro detectado (Tema: {theme_name}). Aplicando...")
                js_dark_mode = """
                    window.addEventListener('load', function() {
                        document.body.classList.add('dark');
                    });
                    if (document.body) {
                        document.body.classList.add('dark');
                    }
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

    def _on_window_delete_event(self, widget: Gtk.Widget, event: Any) -> bool:
        self.save_window_state(widget, event)
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
        if event.keyval == Gdk.KEY_F5:
            logging.info("Tecla F5 pressionada. Recarregando página...")
            self.webview.reload()
            return True
        return False

    def _on_load_failed(self, webview: WebKit2.WebView, load_event: WebKit2.LoadEvent, failing_uri: str, error: GLib.Error) -> bool:
        logging.error(f"Falha ao carregar {failing_uri}: {error.message}")
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
        GLib.timeout_add_seconds(10, self.webview.reload)
        return True

    def _on_show_notification(self, webview: WebKit2.WebView, notification: WebKit2.Notification) -> bool:
        if notifications_enabled:
            try:
                Notify.init(WINDOW_TITLE)
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

    def _on_download_started(self, context: WebKit2.WebContext, download: WebKit2.Download):
        logging.info("Iniciando download...")
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
        if suggested_filename:
            dialog.set_current_name(suggested_filename)
        else:
            dialog.set_current_name("whatsapp_download")
        downloads_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        if downloads_dir:
            dialog.set_current_folder(downloads_dir)
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            uri = dialog.get_uri()
            logging.info(f"Destino definido: {uri}")
            download.set_destination(uri)
            dialog.destroy()
            return True
        dialog.destroy()
        return False

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

    def _on_app_signal(self, user_data=None):
        """Handler para sinal de IPC (SIGUSR1). Restaura a janela."""
        logging.info("Sinal recebido: Restaurando janela...")
        try:
            self.show()
            self.present()
            # Se estava minimizada/iconificada, restaura
            self.deiconify()
        except Exception as e:
            logging.warning(f"Erro ao restaurar janela via sinal: {e}")
        return True # Retorna True para manter o handler ativo no GLib main loop (se necessário)
