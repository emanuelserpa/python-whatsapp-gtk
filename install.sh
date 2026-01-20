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

# =============================================
# INSTALAÇÃO DO PACOTE E EXECUTÁVEL
# =============================================

print_status "Copiando arquivos da aplicação..."

# Limpa instalação anterior se existir para evitar conflitos
rm -rf "$INSTALL_SHARE/whatsapp"

# Copia o pacote Python para ~/.local/share/python-whatsapp-gtk/whatsapp
if [ -d "whatsapp" ]; then
    cp -r whatsapp "$INSTALL_SHARE/"
    print_success "Pacote Python copiado para $INSTALL_SHARE"
else
    print_error "Diretório 'whatsapp' não encontrado!"
    exit 1
fi

# Cria o script de lançamento em ~/.local/bin/python-whatsapp-gtk
print_status "Criando executável..."
cat > "$INSTALL_BIN/$APP_NAME" <<EOF
#!/bin/bash
export PYTHONPATH="$INSTALL_SHARE"
exec python3 -m whatsapp "\$@"
EOF

chmod +x "$INSTALL_BIN/$APP_NAME"
print_success "Executável instalado em $INSTALL_BIN/$APP_NAME"
# =============================================
# INSTALAÇÃO DO ÍCONE
# =============================================

# The icon is already copied in the previous step, so this block can be simplified or removed.
# For now, keeping it as is, but it will effectively re-copy the icon.
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
