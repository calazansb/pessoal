#!/usr/bin/env python3
"""Converte arquivos PDF em Markdown usando o Marker 2 (marker-pdf).

Uso:
    python pdf2md.py documento.pdf              # converte um arquivo
    python pdf2md.py pasta/com/pdfs/            # converte todos os PDFs da pasta
    python pdf2md.py documento.pdf -o saida/    # escolhe a pasta de saída
    python pdf2md.py documento.pdf --paginas 0,5-10
    python pdf2md.py digitalizado.pdf --ocr     # força OCR (PDF escaneado)

O resultado fica em <saida>/<nome-do-pdf>/<nome-do-pdf>.md, junto com as
imagens extraídas e um JSON de metadados.

Requer o Marker 2 instalado: pip install -r requirements-pdf2md.txt
Na primeira execução o Marker baixa os modelos de IA (~alguns GB) de
models.datalab.to; depois disso funciona offline.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PASTA_SAIDA_PADRAO = "convertidos"


def montar_comando(entrada: Path, args: argparse.Namespace) -> list[str]:
    if entrada.is_dir():
        cmd = ["marker", str(entrada)]
        if args.pular_existentes:
            cmd.append("--skip_existing")
    else:
        cmd = ["marker_single", str(entrada)]
        if args.paginas:
            cmd += ["--page_range", args.paginas]
    cmd += ["--output_dir", args.saida]
    if args.modo:
        cmd += ["--mode", args.modo]
    if args.ocr:
        cmd.append("--force_ocr")
    if args.sem_imagens:
        cmd.append("--disable_image_extraction")
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Converte PDF em Markdown com o Marker 2.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Uso:")[1],
    )
    parser.add_argument("entrada", help="arquivo PDF ou pasta com PDFs")
    parser.add_argument(
        "-o", "--saida", default=PASTA_SAIDA_PADRAO,
        help=f"pasta de saída (padrão: {PASTA_SAIDA_PADRAO}/)",
    )
    parser.add_argument(
        "--paginas", default=None,
        help="páginas a converter, ex.: 0,5-10,20 (só para arquivo único)",
    )
    parser.add_argument(
        "--ocr", action="store_true",
        help="força OCR na página inteira (bom para PDF escaneado)",
    )
    parser.add_argument(
        "--modo", choices=["fast", "balanced"], default=None,
        help="fast = leve, ideal em CPU; balanced = melhor qualidade, ideal em GPU "
             "(padrão: o Marker escolhe conforme o hardware)",
    )
    parser.add_argument(
        "--sem-imagens", action="store_true",
        help="não extrai as imagens do PDF",
    )
    parser.add_argument(
        "--pular-existentes", action="store_true",
        help="ao converter uma pasta, pula PDFs já convertidos",
    )
    args = parser.parse_args()

    entrada = Path(args.entrada).expanduser()
    if not entrada.exists():
        print(f"❌ Não encontrei: {entrada}", file=sys.stderr)
        return 1
    if entrada.is_file() and entrada.suffix.lower() != ".pdf":
        print(f"❌ {entrada} não é um PDF.", file=sys.stderr)
        return 1
    if shutil.which("marker_single") is None:
        print(
            "❌ O Marker não está instalado. Rode:\n"
            "   pip install -r requirements-pdf2md.txt",
            file=sys.stderr,
        )
        return 1

    cmd = montar_comando(entrada, args)
    print("▶ " + " ".join(cmd))
    resultado = subprocess.run(cmd)
    if resultado.returncode != 0:
        print("❌ A conversão falhou (veja as mensagens acima).", file=sys.stderr)
        return resultado.returncode

    saida = Path(args.saida)
    gerados = sorted(saida.glob("*/*.md"))
    if gerados:
        print("\n✅ Markdown gerado:")
        for md in gerados:
            print(f"   {md}")
    else:
        print(f"\n✅ Conversão concluída. Veja a pasta {saida}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
