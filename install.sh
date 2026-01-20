#!/bin/bash

# Cores para saída
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SOURCE_FILE="python-whatsapp-gtk.py"
APP_NAME="python-whatsapp-gtk"
ICON_SOURCE="assets/icon.png"

INSTALL_BIN="$HOME/.local/bin"
INSTALL_SHARE="$HOME/.local/share/python-whatsapp-gtk"
INSTALL_DESKTOP="$HOME/.local/share/applications"

print_header() {
    echo -e "${BLUE}"
    echo "=============================================="
    echo "      Python WhatsApp GTK - Instalador"
    echo "=============================================="
    echo -e "${NC}"
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERRO]${NC} $1"
}

print_header

# =============================================
# VERIFICAÇÃO DAS DEPENDÊNCIAS
# =============================================

print_status "Verificando dependências..."

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 não foi encontrado."
    echo "Por favor, instale o Python 3 antes de continuar."
    exit 1
fi
print_success "Python 3 encontrado."

# Verifica PyGObject
python3 -c "import gi" 2>/dev/null
if [ $? -ne 0 ]; then
    print_error "Biblioteca PyGObject (GTK) não encontrada."
    echo "Instale os bindings GTK para Python (ex: python3-gi ou python-gobject)."
    exit 1
fi
print_success "PyGObject (GTK) encontrado."

# Verifica AppIndicator3 (Opcional, para Tray Icon)
python3 -c "import gi; gi.require_version('AppIndicator3', '0.1')" 2>/dev/null
if [ $? -ne 0 ]; then
    print_warning "Biblioteca AppIndicator3 não encontrada."
    echo "    O aplicativo funcionará, mas o ícone na bandeja (Tray Icon) não será exibido."
    echo "    Para ativar essa função, instale: libappindicator-gtk3 ou gir1.2-appindicator3-0.1"
else
    print_success "AppIndicator3 (Tray Icon) encontrado."
fi

# =============================================
# PREPARAÇÃO DOS DIRETÓRIOS
# =============================================

print_status "Preparando diretórios de instalação..."
mkdir -p "$INSTALL_BIN"
mkdir -p "$INSTALL_SHARE"
mkdir -p "$INSTALL_DESKTOP"

# =============================================
# INSTALAÇÃO DO EXECUTÁVEL
# =============================================

if [ ! -f "$SOURCE_FILE" ]; then
    print_error "Arquivo $SOURCE_FILE não encontrado na pasta atual."
    exit 1
fi

cp "$SOURCE_FILE" "$INSTALL_BIN/$APP_NAME"
chmod +x "$INSTALL_BIN/$APP_NAME"
print_success "Executável instalado em $INSTALL_BIN"

# =============================================
# INSTALAÇÃO DO ÍCONE
# =============================================

if [ -f "$ICON_SOURCE" ]; then
    cp "$ICON_SOURCE" "$INSTALL_SHARE/icon.png"
    print_success "Ícone copiado para $INSTALL_SHARE"
else
    print_warning "Ícone padrão não encontrado ($ICON_SOURCE). Usando genérico."
fi

# =============================================
# CRIAÇÃO DO ATALHO
# =============================================

cat > "$INSTALL_DESKTOP/$APP_NAME.desktop" <<FIM
[Desktop Entry]
Name=WhatsApp
Comment=Cliente WhatsApp não-oficial
Exec=$INSTALL_BIN/$APP_NAME
Icon=$INSTALL_SHARE/icon.png
Terminal=false
Type=Application
Categories=Network;Chat;
StartupWMClass=whatsapp
X-GNOME-SingleWindow=true
FIM

print_success "Atalho criado em $INSTALL_DESKTOP"

# =============================================
# FINALIZAÇÃO
# =============================================

update-desktop-database "$INSTALL_DESKTOP" 2>/dev/null

echo ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}      Instalação Concluída com Sucesso!       ${NC}"
echo -e "${GREEN}==============================================${NC}"
echo ""
echo "O app 'WhatsApp' deve aparecer no seu menu de aplicativos."
echo "Para desinstalar, remova:"
echo "  - $INSTALL_BIN/$APP_NAME"
echo "  - $INSTALL_SHARE"
echo "  - $INSTALL_DESKTOP/$APP_NAME.desktop"
echo ""
