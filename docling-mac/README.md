# Docling no Mac 📄→📝

Kit de instalação e uso do [Docling](https://docling-project.github.io/docling/)
no macOS. O Docling converte documentos (PDF, Word, PowerPoint, Excel, HTML,
imagens escaneadas…) em **Markdown**, HTML ou JSON — preservando tabelas,
estrutura e fazendo OCR quando necessário. Ótimo para preparar documentos para
usar com IA (Claude, RAG, etc.).

## Instalação (1 comando)

Abra o **Terminal** no seu Mac e rode:

```bash
git clone -b claude/docling-mac-setup-rjn23p https://github.com/calazansb/pessoal.git ~/pessoal-docling \
  && bash ~/pessoal-docling/docling-mac/install.sh
```

> Se você já tem este repositório clonado, basta:
> `git fetch && git checkout claude/docling-mac-setup-rjn23p && bash docling-mac/install.sh`

O instalador:

1. Instala o **uv** (gerenciador de pacotes Python) se necessário;
2. Instala o **Docling** de forma isolada (não bagunça seu Python), com o
   OCR nativo do macOS (`ocrmac`) e, em Macs Intel, o PyTorch compatível;
3. Instala o comando **`docling-convert`** em `~/.local/bin`;
4. Cria o app **Docling Converter** em `~/Applications`;
5. Instala a Ação Rápida **"Converter com Docling"** no Finder;
6. Pré-baixa os modelos de IA (~1 GB) — pule com `--sem-modelos`.

## Como usar no dia a dia

### 1. Clique-direito no Finder (mais rápido)

Clique com o botão direito em qualquer PDF/DOCX/PPTX →
**Ações Rápidas → Converter com Docling**.
O arquivo `.md` aparece na mesma pasta e uma notificação avisa quando terminar.

*Não apareceu no menu?* Vá em **Ajustes do Sistema → Geral → Extensões →
Ações Rápidas** e ative "Converter com Docling" (ou faça logout/login).

### 2. App de arrastar e soltar

Abra `~/Applications` e **arraste documentos para o "Docling Converter"**
(vale a pena mantê-lo no Dock). Clique duplo abre um seletor de arquivos.

### 3. Terminal

```bash
docling-convert relatorio.pdf                 # gera relatorio.md ao lado
docling-convert --to html contrato.docx      # converte para HTML
docling-convert a.pdf b.docx c.pptx          # vários de uma vez
```

Ou a CLI oficial, com todas as opções:

```bash
docling arquivo.pdf                           # imprime o Markdown na tela
docling --to md --output ~/Desktop arq.pdf   # salva em outra pasta
docling https://arxiv.org/pdf/2408.09869     # converte direto de uma URL
docling --help                                # todas as opções
```

### 4. Com o Claude

Me peça a qualquer momento — por exemplo:
*"converte esse PDF pra Markdown com o docling"* ou
*"extrai as tabelas desse documento"*. Em sessões com acesso a arquivos,
eu rodo o Docling para você; no Mac, você roda `docling-convert` e me manda
o `.md` gerado (Markdown é o formato que eu leio melhor).

## Formatos suportados

| Entrada | Saída |
| - | - |
| PDF (inclusive escaneado, com OCR), DOCX, XLSX, PPTX, HTML, Markdown, AsciiDoc, CSV, imagens (PNG, JPG, TIFF), áudio (com extra `asr`) | Markdown (padrão), HTML, JSON, texto puro, DocTags |

## Dicas e manutenção

- **Primeiro uso**: se você pulou o pré-download, a primeira conversão baixa
  os modelos (~1 GB) — as seguintes são rápidas.
- **Tudo local**: a conversão roda 100% no seu Mac; nenhum documento é
  enviado para a internet.
- **Atualizar**: `uv tool upgrade docling`
- **Desinstalar**:
  ```bash
  uv tool uninstall docling
  rm -f ~/.local/bin/docling-convert
  rm -rf "$HOME/Applications/Docling Converter.app" \
         "$HOME/Library/Services/Converter com Docling.workflow" \
         "$HOME/.cache/docling"
  ```
- **Interface web (opcional)**: o projeto tem também o
  [docling-serve](https://github.com/docling-project/docling-serve), que sobe
  uma interface no navegador:
  ```bash
  uv tool install "docling-serve[ui]"
  docling-serve run --enable-ui   # abre em http://127.0.0.1:5001/ui
  ```

## Solução de problemas

| Problema | Solução |
| - | - |
| `docling: command not found` | Abra um novo Terminal, ou rode `export PATH="$HOME/.local/bin:$PATH"` |
| Ação Rápida não aparece | Ative em Ajustes do Sistema → Geral → Extensões → Ações Rápidas; se ainda assim não aparecer, abra o Automator, crie uma "Ação Rápida" com a ação "Executar Script Shell" (entrada: *como argumentos*) contendo `export PATH="$HOME/.local/bin:$PATH"; "$HOME/.local/bin/docling-convert" --notify "$@"` e salve como "Converter com Docling" |
| Mac Intel com erro de PyTorch | O instalador já usa o extra `mac_intel` com Python 3.12 — rode `bash install.sh` de novo |
| Conversão lenta | Normal em PDFs escaneados grandes (OCR página a página). Em Apple Silicon o Docling usa aceleração MPS automaticamente |
| PDF escaneado sai vazio | Force OCR: `docling --force-ocr --to md --output . arquivo.pdf` |
