"""Processamento em lote: classifica uma pasta inteira de PDFs.

Gera um CSV (abre direto no Excel) com uma linha por processo — é o modo
indicado para sanear a carteira: aponte para a pasta com todos os PDFs e
revise depois só as linhas marcadas como REVISAR.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .classificacao import Classificacao, ObjetoAcao, classificar_texto
from .extracao import extrair_texto

COLUNAS = [
    "arquivo",
    "numero_processo",
    "tribunal",
    "objeto",
    "pontuacao",
    "status",
    "segundo_objeto",
    "segunda_pontuacao",
    "paginas_analisadas",
    "total_paginas",
    "paginas_sem_texto",
    "erro",
]


@dataclass
class ItemLote:
    arquivo: Path
    classificacao: Classificacao | None = None
    paginas_analisadas: int = 0
    total_paginas: int = 0
    paginas_sem_texto: int = 0
    erro: str | None = None

    def linha_csv(self) -> dict:
        c = self.classificacao
        segundo = c.ranking[1] if c and len(c.ranking) > 1 else None
        return {
            "arquivo": self.arquivo.name,
            "numero_processo": (c.numero_processo if c else None) or "",
            "tribunal": (c.tribunal if c else None) or "",
            "objeto": c.objeto if c else "",
            "pontuacao": c.ranking[0].pontos if c and c.ranking else 0,
            "status": "ERRO" if self.erro else (c.status if c else "REVISAR"),
            "segundo_objeto": segundo.objeto.nome if segundo else "",
            "segunda_pontuacao": segundo.pontos if segundo else "",
            "paginas_analisadas": self.paginas_analisadas,
            "total_paginas": self.total_paginas,
            "paginas_sem_texto": self.paginas_sem_texto,
            "erro": self.erro or "",
        }


def listar_pdfs(pasta: str | Path) -> list[Path]:
    return sorted(
        p for p in Path(pasta).rglob("*") if p.suffix.lower() == ".pdf" and p.is_file()
    )


def classificar_arquivo(
    caminho: str | Path, objetos: list[ObjetoAcao], max_paginas: int = 30
) -> ItemLote:
    item = ItemLote(arquivo=Path(caminho))
    try:
        extracao = extrair_texto(str(caminho), max_paginas=max_paginas)
        item.paginas_analisadas = extracao.paginas_analisadas
        item.total_paginas = extracao.total_paginas_pdf
        item.paginas_sem_texto = extracao.paginas_sem_texto
        item.classificacao = classificar_texto(extracao.texto, objetos)
    except Exception as exc:  # PDF corrompido, protegido por senha etc.
        item.erro = str(exc)
    return item


def classificar_pasta(
    pasta: str | Path,
    objetos: list[ObjetoAcao],
    max_paginas: int = 30,
    ao_concluir_item: Callable[[ItemLote], None] | None = None,
) -> list[ItemLote]:
    itens = []
    for pdf in listar_pdfs(pasta):
        item = classificar_arquivo(pdf, objetos, max_paginas=max_paginas)
        itens.append(item)
        if ao_concluir_item:
            ao_concluir_item(item)
    return itens


def gravar_csv(itens: Iterable[ItemLote], destino: str | Path) -> Path:
    destino = Path(destino)
    # utf-8-sig para o Excel abrir os acentos corretamente.
    with destino.open("w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        for item in itens:
            escritor.writerow(item.linha_csv())
    return destino
