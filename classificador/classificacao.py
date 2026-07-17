"""Motor de classificação por objeto de ação.

A classificação é feita por regras locais (palavras-chave com peso),
sem nenhuma chamada a API de IA. Os objetos de ação e seus termos ficam
em ``objetos.json`` e podem ser editados livremente para espelhar o
sistema do escritório — é assim que o classificador "aprende": ajustando
os termos de cada objeto conforme os casos reais.

Cada termo encontrado no texto soma pontos ao objeto correspondente.
O objeto com mais pontos vence; se a pontuação ficar abaixo do mínimo,
o processo é marcado como "REVISAR" para triagem humana.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ARQUIVO_OBJETOS_PADRAO = Path(__file__).parent / "objetos.json"

# Pontuação mínima para considerar a classificação confiável.
PONTUACAO_MINIMA = 4
# Um mesmo termo repetido conta no máximo até este limite (evita que uma
# palavra genérica repetida 200 vezes domine a pontuação).
MAX_OCORRENCIAS_POR_TERMO = 5

_RE_CNJ = re.compile(r"\b(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})\b")

_SEGMENTOS_CNJ = {
    "1": "STF",
    "2": "CNJ",
    "3": "STJ",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça Estadual",
    "9": "Justiça Militar Estadual",
}

_UF_TRIBUNAL_ESTADUAL = {
    "01": "AC", "02": "AL", "03": "AP", "04": "AM", "05": "BA", "06": "CE",
    "07": "DF", "08": "ES", "09": "GO", "10": "MA", "11": "MT", "12": "MS",
    "13": "MG", "14": "PA", "15": "PB", "16": "PR", "17": "PE", "18": "PI",
    "19": "RJ", "20": "RN", "21": "RS", "22": "RO", "23": "RR", "24": "SC",
    "25": "SE", "26": "SP", "27": "TO",
}


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, preservando o tamanho da string.

    Preservar o tamanho permite localizar trechos no texto original a
    partir de posições encontradas no texto normalizado.
    """
    saida = []
    for ch in texto:
        decomposto = unicodedata.normalize("NFD", ch)
        base = decomposto[0] if decomposto else ch
        saida.append(base.lower() if not unicodedata.combining(base) else ch)
    return "".join(saida)


@dataclass
class Termo:
    texto: str
    peso: int = 1


@dataclass
class ObjetoAcao:
    id: str
    nome: str
    termos: list[Termo]


@dataclass
class TermoEncontrado:
    termo: str
    peso: int
    ocorrencias: int
    trecho: str

    @property
    def pontos(self) -> int:
        return self.peso * min(self.ocorrencias, MAX_OCORRENCIAS_POR_TERMO)


@dataclass
class PontuacaoObjeto:
    objeto: ObjetoAcao
    termos_encontrados: list[TermoEncontrado] = field(default_factory=list)

    @property
    def pontos(self) -> int:
        return sum(t.pontos for t in self.termos_encontrados)


@dataclass
class Classificacao:
    ranking: list[PontuacaoObjeto]
    numero_processo: str | None
    tribunal: str | None

    @property
    def vencedor(self) -> PontuacaoObjeto | None:
        if self.ranking and self.ranking[0].pontos >= PONTUACAO_MINIMA:
            return self.ranking[0]
        return None

    @property
    def status(self) -> str:
        return "OK" if self.vencedor else "REVISAR"

    @property
    def objeto(self) -> str:
        return self.vencedor.objeto.nome if self.vencedor else "(não classificado)"


def carregar_objetos(caminho: str | Path = ARQUIVO_OBJETOS_PADRAO) -> list[ObjetoAcao]:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    objetos = []
    for item in dados["objetos"]:
        termos = []
        for termo in item["termos"]:
            if isinstance(termo, str):
                termos.append(Termo(termo))
            else:
                termos.append(Termo(termo["t"], int(termo.get("peso", 1))))
        objetos.append(ObjetoAcao(item["id"], item["nome"], termos))
    return objetos


def salvar_objetos(objetos: list[ObjetoAcao], caminho: str | Path = ARQUIVO_OBJETOS_PADRAO) -> None:
    dados = {
        "objetos": [
            {
                "id": o.id,
                "nome": o.nome,
                "termos": [
                    t.texto if t.peso == 1 else {"t": t.texto, "peso": t.peso}
                    for t in o.termos
                ],
            }
            for o in objetos
        ]
    }
    Path(caminho).write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _regex_termo(termo: str) -> re.Pattern:
    partes = [re.escape(p) for p in normalizar(termo).split()]
    return re.compile(r"\b" + r"\s+".join(partes) + r"\b")


def _trecho(texto_original: str, inicio: int, fim: int, contexto: int = 60) -> str:
    a = max(0, inicio - contexto)
    b = min(len(texto_original), fim + contexto)
    trecho = " ".join(texto_original[a:b].split())
    prefixo = "…" if a > 0 else ""
    sufixo = "…" if b < len(texto_original) else ""
    return f"{prefixo}{trecho}{sufixo}"


def extrair_numero_processo(texto: str) -> tuple[str | None, str | None]:
    """Localiza o primeiro número CNJ e identifica o tribunal."""
    m = _RE_CNJ.search(texto)
    if not m:
        return None, None
    numero = f"{m[1]}-{m[2]}.{m[3]}.{m[4]}.{m[5]}.{m[6]}"
    segmento, tr = m[4], m[5]
    if segmento == "8":
        uf = _UF_TRIBUNAL_ESTADUAL.get(tr)
        tribunal = f"TJ{uf}" if uf else _SEGMENTOS_CNJ["8"]
    elif segmento == "4":
        tribunal = f"TRF{int(tr)}"
    elif segmento == "5":
        tribunal = f"TRT-{int(tr)}"
    else:
        tribunal = _SEGMENTOS_CNJ.get(segmento)
    return numero, tribunal


def classificar_texto(texto: str, objetos: list[ObjetoAcao]) -> Classificacao:
    texto_norm = normalizar(texto)
    ranking = []
    for objeto in objetos:
        pontuacao = PontuacaoObjeto(objeto)
        for termo in objeto.termos:
            achados = list(_regex_termo(termo.texto).finditer(texto_norm))
            if achados:
                primeiro = achados[0]
                pontuacao.termos_encontrados.append(
                    TermoEncontrado(
                        termo=termo.texto,
                        peso=termo.peso,
                        ocorrencias=len(achados),
                        trecho=_trecho(texto, primeiro.start(), primeiro.end()),
                    )
                )
        if pontuacao.termos_encontrados:
            ranking.append(pontuacao)
    ranking.sort(key=lambda p: p.pontos, reverse=True)
    numero, tribunal = extrair_numero_processo(texto)
    return Classificacao(ranking=ranking, numero_processo=numero, tribunal=tribunal)
