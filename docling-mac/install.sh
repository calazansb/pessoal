#!/bin/bash
#
# Instalador do Docling para macOS
# --------------------------------
# Instala o Docling (https://docling-project.github.io/docling/) e as
# ferramentas de conveniência deste kit:
#
#   1. CLI `docling` (isolada via uv, Python 3.12)
#   2. Script `docling-convert` (converte arquivos para Markdown com 1 comando)
#   3. App "Docling Converter.app" em ~/Applications (arraste arquivos nele)
#   4. Ação Rápida do Finder "Converter com Docling" (clique-direito no arquivo)
#
# Uso:
#   bash install.sh                # instalação completa (baixa modelos, ~1 GB)
#   bash install.sh --sem-modelos  # não pré-baixa os modelos de IA
#
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "❌ Este instalador é para macOS. Rode-o no Terminal do seu Mac." >&2
  exit 1
fi

SKIP_MODELS=0
for arg in "$@"; do
  case "$arg" in
    --sem-modelos|--skip-models) SKIP_MODELS=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Opção desconhecida: $arg (use --sem-modelos ou --help)" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCH="$(uname -m)"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
export PATH="$BIN_DIR:$PATH"

echo ""
echo "=== Instalando Docling para macOS ($ARCH) ==="
echo ""

# ---------------------------------------------------------------- 1. uv
echo "==> [1/6] Verificando o gerenciador de pacotes uv..."
if ! command -v uv >/dev/null 2>&1; then
  echo "    uv não encontrado — instalando via https://astral.sh/uv ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "    uv $(uv --version | head -1)"

# ---------------------------------------------------------------- 2. docling
echo "==> [2/6] Instalando o Docling (primeira vez pode levar alguns minutos)..."
if [[ "$ARCH" == "arm64" ]]; then
  # Apple Silicon: docling + OCR nativo do macOS (Vision)
  uv tool install --force --python 3.12 "docling[ocrmac]"
else
  # Mac Intel: PyTorch novo não tem mais wheels para x86_64 — o extra
  # mac_intel fixa uma versão compatível (por isso o Python 3.12)
  uv tool install --force --python 3.12 "docling[mac_intel,ocrmac]"
fi
uv tool update-shell >/dev/null 2>&1 || true
echo "    $("$BIN_DIR/docling" --version 2>/dev/null | head -1 || echo 'docling instalado')"

# ---------------------------------------------------------------- 3. docling-convert
echo "==> [3/6] Instalando o utilitário docling-convert em $BIN_DIR ..."
install -m 0755 "$SCRIPT_DIR/docling-convert" "$BIN_DIR/docling-convert"

# ---------------------------------------------------------------- 4. app droplet
echo "==> [4/6] Criando o app 'Docling Converter' em ~/Applications ..."
mkdir -p "$HOME/Applications"
rm -rf "$HOME/Applications/Docling Converter.app"
osacompile -o "$HOME/Applications/Docling Converter.app" \
  "$SCRIPT_DIR/DoclingConverter.applescript"
echo "    ok — arraste arquivos para o app para converter em Markdown"

# ---------------------------------------------------------------- 5. Ação Rápida
echo "==> [5/6] Instalando a Ação Rápida 'Converter com Docling' no Finder..."
mkdir -p "$HOME/Library/Services"
rm -rf "$HOME/Library/Services/Converter com Docling.workflow"
cp -R "$SCRIPT_DIR/Converter com Docling.workflow" "$HOME/Library/Services/"
/System/Library/CoreServices/pbs -update >/dev/null 2>&1 || true
echo "    ok — clique-direito num arquivo > Ações Rápidas > Converter com Docling"
echo "    (se não aparecer de imediato, faça logout/login ou veja o README)"

# ---------------------------------------------------------------- 6. modelos
if [[ "$SKIP_MODELS" -eq 0 ]]; then
  echo "==> [6/6] Pré-baixando os modelos de IA (~1 GB, evita espera no 1º uso)..."
  "$BIN_DIR/docling-tools" models download || \
    echo "    ⚠️  Falha ao pré-baixar modelos — serão baixados no primeiro uso."
else
  echo "==> [6/6] Pulando download de modelos (serão baixados no primeiro uso)."
fi

echo ""
echo "=== ✅ Instalação concluída! ==="
echo ""
echo "Formas de usar:"
echo "  • Finder: clique-direito no arquivo > Ações Rápidas > Converter com Docling"
echo "  • App:    arraste PDFs/DOCX/etc. para ~/Applications/Docling Converter.app"
echo "  • Shell:  docling-convert arquivo.pdf        (gera arquivo.md ao lado)"
echo "  • CLI:    docling --help                     (todas as opções)"
echo ""
echo "Teste rápido:"
echo "  docling-convert ~/Downloads/algum-arquivo.pdf"
echo ""
echo "Se o comando não for encontrado, abra um novo Terminal ou rode:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
