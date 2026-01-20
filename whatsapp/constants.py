"""
Constants for the WhatsApp GTK Client.
"""

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
