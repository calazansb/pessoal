"""Linha de comando do classificador.

Uso:
    python -m classificador arquivo caminho/do/processo.pdf
    python -m classificador lote /pasta/com/pdfs -o resultado.csv
    python -m classificador web
    python -m classificador objetos
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .classificacao import ARQUIVO_OBJETOS_PADRAO, carregar_objetos
from .lote import ItemLote, classificar_arquivo, classificar_pasta, gravar_csv


def _console():
    try:
        from rich.console import Console

        return Console()
    except ImportError:
        return None


def _imprimir_item(item: ItemLote, console) -> None:
    c = item.classificacao
    if item.erro:
        linha = f"[ERRO] {item.arquivo.name}: {item.erro}"
    else:
        numero = f" {c.numero_processo}" if c.numero_processo else ""
        pontos = c.ranking[0].pontos if c.ranking else 0
        linha = f"[{c.status}] {item.arquivo.name}{numero} → {c.objeto} ({pontos} pts)"
    if console:
        cor = "green" if not item.erro and c.status == "OK" else "yellow"
        console.print(linha, style=cor, highlight=False)
    else:
        print(linha)


def _cmd_arquivo(args, objetos) -> int:
    item = classificar_arquivo(args.pdf, objetos, max_paginas=args.paginas)
    console = _console()
    _imprimir_item(item, console)
    c = item.classificacao
    if c and c.ranking:
        print()
        for p in c.ranking[:5]:
            print(f"  {p.pontos:4d} pts  {p.objeto.nome}")
        print("\nEvidências do primeiro colocado:")
        for t in c.ranking[0].termos_encontrados:
            print(f"  - '{t.termo}' ({t.ocorrencias}x): {t.trecho}")
    return 1 if item.erro else 0


def _cmd_lote(args, objetos) -> int:
    console = _console()
    itens = classificar_pasta(
        args.pasta,
        objetos,
        max_paginas=args.paginas,
        ao_concluir_item=lambda item: _imprimir_item(item, console),
    )
    if not itens:
        print(f"Nenhum PDF encontrado em {args.pasta}")
        return 1
    destino = gravar_csv(itens, args.saida)
    ok = sum(1 for i in itens if not i.erro and i.classificacao.status == "OK")
    revisar = sum(1 for i in itens if not i.erro and i.classificacao.status == "REVISAR")
    erros = sum(1 for i in itens if i.erro)
    print(
        f"\n{len(itens)} processos: {ok} classificados, {revisar} para revisar, "
        f"{erros} com erro.\nPlanilha gravada em {destino}"
    )
    return 0


def _cmd_objetos(objetos) -> int:
    for o in objetos:
        print(f"{o.nome} ({o.id})")
        for t in o.termos:
            peso = f" [peso {t.peso}]" if t.peso != 1 else ""
            print(f"  - {t.texto}{peso}")
    return 0


def _cmd_web(args) -> int:
    from .web import rodar

    print(f"Abra http://127.0.0.1:{args.porta} no navegador (Ctrl+C para parar)")
    rodar(porta=args.porta, arquivo_objetos=args.objetos, max_paginas=args.paginas)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="classificador", description="Classificador local de processos em PDF"
    )
    parser.add_argument(
        "--objetos",
        default=ARQUIVO_OBJETOS_PADRAO,
        help="arquivo objetos.json alternativo",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_arq = sub.add_parser("arquivo", help="classifica um único PDF")
    p_arq.add_argument("pdf", help="caminho do PDF do processo")
    p_arq.add_argument("--paginas", type=int, default=30, help="páginas a analisar (0 = todas)")

    p_lote = sub.add_parser("lote", help="classifica todos os PDFs de uma pasta")
    p_lote.add_argument("pasta", help="pasta com os PDFs (inclui subpastas)")
    p_lote.add_argument("-o", "--saida", default="resultado.csv", help="CSV de saída")
    p_lote.add_argument("--paginas", type=int, default=30, help="páginas a analisar (0 = todas)")

    p_web = sub.add_parser("web", help="abre a interface web local")
    p_web.add_argument("--porta", type=int, default=5000)
    p_web.add_argument("--paginas", type=int, default=30)

    sub.add_parser("objetos", help="lista os objetos de ação configurados")

    args = parser.parse_args(argv)
    if args.comando == "web":
        return _cmd_web(args)

    objetos = carregar_objetos(args.objetos)
    if args.comando == "arquivo":
        return _cmd_arquivo(args, objetos)
    if args.comando == "lote":
        return _cmd_lote(args, objetos)
    return _cmd_objetos(objetos)


if __name__ == "__main__":
    sys.exit(main())
