"""
System Tray Icon implementation.
"""
import logging
import gi
from gi.repository import Gtk
from ..constants import APP_NAME

# Tenta importar AppIndicator3
app_indicator_enabled = False
try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
    app_indicator_enabled = True
except (ValueError, ImportError):
    logging.warning("AppIndicator3 não encontrado. O ícone na bandeja será desativado.")


class TrayIcon:
    def __init__(self, window):
        self.window = window
        self.indicator = None
        
        if app_indicator_enabled:
            self._init_indicator()

    def _init_indicator(self):
        try:
            # Tenta usar ícone local como preferência
            icon_name = "whatsapp"
            if self.window.icon_path.exists():
                icon_name = str(self.window.icon_path)
            
            self.indicator = AppIndicator3.Indicator.new(
                APP_NAME,
                icon_name,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            
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

    def _show_window(self, widget):
        self.window.show()
        self.window.present()

    def _quit_application(self, widget):
        self.window.save_window_state(widget, None)
        Gtk.main_quit()
