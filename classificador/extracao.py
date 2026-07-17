"""Extração de texto de PDFs de processos judiciais.

Os PDFs de processos eletrônicos (PJe, e-SAJ, eproc, Projudi) já trazem a
camada de texto embutida, então a leitura é direta com o PyMuPDF — rápida
e sem custo, página a página.

Para arquivos grandes, por padrão só as primeiras páginas são analisadas:
o objeto da ação quase sempre está na petição inicial, que abre os autos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import fitz  # PyMuPDF

# Menos caracteres que isso numa página indica digitalização sem texto.
MIN_CARACTERES_PAGINA = 30


@dataclass
class PaginaExtraida:
    numero: int  # 1-indexada, como nos autos
    texto: str
    com_texto: bool


@dataclass
class ResultadoExtracao:
    arquivo: str
    total_paginas_pdf: int
    paginas: list[PaginaExtraida] = field(default_factory=list)
    paginas_sem_texto: int = 0

    @property
    def paginas_analisadas(self) -> int:
        return len(self.paginas)

    @property
    def texto(self) -> str:
        return "\n".join(p.texto for p in self.paginas if p.texto)


def extrair_texto(caminho: str, max_paginas: int = 30) -> ResultadoExtracao:
    """Extrai o texto das primeiras ``max_paginas`` do PDF.

    ``max_paginas=0`` analisa o documento inteiro.
    """
    with fitz.open(caminho) as pdf:
        resultado = ResultadoExtracao(arquivo=caminho, total_paginas_pdf=pdf.page_count)
        limite = pdf.page_count if max_paginas <= 0 else min(max_paginas, pdf.page_count)
        for indice in range(limite):
            texto = pdf[indice].get_text().strip()
            com_texto = len(texto) >= MIN_CARACTERES_PAGINA
            if not com_texto:
                resultado.paginas_sem_texto += 1
            resultado.paginas.append(PaginaExtraida(indice + 1, texto, com_texto))
        return resultado
