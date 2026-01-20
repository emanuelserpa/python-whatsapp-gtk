from .ui.window import ClientWindow
from .constants import APP_NAME
from gi.repository import Gtk, GLib
import logging

def main():
    GLib.set_prgname(APP_NAME)
    
    try:
        app = ClientWindow()
        app.connect("destroy", Gtk.main_quit)
        app.show_all()
        Gtk.main()
    except KeyboardInterrupt:
        logging.info("Aplicação interrompida pelo usuário")
    except Exception as error:
        logging.critical("A aplicação caiu inesperadamente", exc_info=True)

if __name__ == "__main__":
    main()
