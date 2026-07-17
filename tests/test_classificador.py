"""Testes do classificador de processos.

Rodar com: python tests/test_classificador.py
"""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz

from classificador.classificacao import (
    carregar_objetos,
    classificar_texto,
    extrair_numero_processo,
    normalizar,
    salvar_objetos,
)
from classificador.extracao import extrair_texto
from classificador.lote import classificar_arquivo, classificar_pasta, gravar_csv

PETICAO_NEGATIVA = """
EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA VARA CÍVEL DE BELO HORIZONTE

Processo nº 5012345-67.2024.8.13.0024

AÇÃO DE OBRIGAÇÃO DE FAZER COM PEDIDO DE TUTELA DE URGÊNCIA

O autor é beneficiário do plano de saúde réu e recebeu negativa de cobertura
para a cirurgia prescrita pelo médico assistente. A recusa de cobertura é
abusiva, pois o procedimento consta do rol da ANS. Requer a autorização do
procedimento e a internação imediata, sob pena de multa diária.
"""

PETICAO_COBRANCA = """
AÇÃO DE COBRANÇA

Processo 1000000-11.2023.5.03.0001

A autora prestou serviços médico-hospitalares e emitiu notas fiscais de
serviço, havendo faturas em aberto não quitadas pela ré. O inadimplemento
persiste apesar das notificações. Houve glosa indevida do faturamento.
"""


def _criar_pdf(caminho: Path, texto: str, paginas_vazias: int = 0) -> None:
    doc = fitz.open()
    pagina = doc.new_page()
    pagina.insert_textbox(fitz.Rect(50, 50, 545, 792), texto, fontsize=11)
    for _ in range(paginas_vazias):
        doc.new_page()
    doc.save(str(caminho))
    doc.close()


class TestNormalizacao(unittest.TestCase):
    def test_remove_acentos_e_baixa_caixa(self):
        self.assertEqual(normalizar("Ação de Cobrança"), "acao de cobranca")

    def test_preserva_tamanho(self):
        original = "Petição às fls. 12 — João"
        self.assertEqual(len(normalizar(original)), len(original))


class TestNumeroProcesso(unittest.TestCase):
    def test_cnj_justica_estadual(self):
        numero, tribunal = extrair_numero_processo(
            "autos nº 5012345-67.2024.8.13.0024 em curso"
        )
        self.assertEqual(numero, "5012345-67.2024.8.13.0024")
        self.assertEqual(tribunal, "TJMG")

    def test_cnj_trabalhista(self):
        numero, tribunal = extrair_numero_processo("proc 1000000-11.2023.5.03.0001")
        self.assertEqual(tribunal, "TRT-3")

    def test_sem_numero(self):
        self.assertEqual(extrair_numero_processo("sem numeração aqui"), (None, None))


class TestClassificacao(unittest.TestCase):
    def setUp(self):
        self.objetos = carregar_objetos()

    def test_negativa_de_cobertura(self):
        c = classificar_texto(PETICAO_NEGATIVA, self.objetos)
        self.assertEqual(c.status, "OK")
        self.assertEqual(c.ranking[0].objeto.id, "negativa_procedimento")
        self.assertEqual(c.numero_processo, "5012345-67.2024.8.13.0024")
        self.assertEqual(c.tribunal, "TJMG")

    def test_cobranca(self):
        c = classificar_texto(PETICAO_COBRANCA, self.objetos)
        self.assertEqual(c.status, "OK")
        self.assertEqual(c.ranking[0].objeto.id, "glosa_prestador")

    def test_texto_sem_relacao_vira_revisar(self):
        c = classificar_texto("receita de bolo de cenoura com chocolate", self.objetos)
        self.assertEqual(c.status, "REVISAR")
        self.assertEqual(c.objeto, "(não classificado)")

    def test_evidencias_trazem_trecho(self):
        c = classificar_texto(PETICAO_NEGATIVA, self.objetos)
        termos = {t.termo for t in c.ranking[0].termos_encontrados}
        self.assertIn("negativa de cobertura", termos)
        encontrado = next(
            t for t in c.ranking[0].termos_encontrados if t.termo == "negativa de cobertura"
        )
        self.assertIn("negativa de cobertura", encontrado.trecho)

    def test_salvar_e_carregar_objetos(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "objetos.json"
            salvar_objetos(self.objetos, destino)
            recarregados = carregar_objetos(destino)
        self.assertEqual(
            [(o.id, [(t.texto, t.peso) for t in o.termos]) for o in recarregados],
            [(o.id, [(t.texto, t.peso) for t in o.termos]) for o in self.objetos],
        )


class TestExtracaoEForLote(unittest.TestCase):
    def test_extrai_texto_e_detecta_paginas_vazias(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "processo.pdf"
            _criar_pdf(pdf, PETICAO_NEGATIVA, paginas_vazias=2)
            resultado = extrair_texto(str(pdf))
        self.assertEqual(resultado.total_paginas_pdf, 3)
        self.assertEqual(resultado.paginas_sem_texto, 2)
        self.assertIn("negativa de cobertura", resultado.texto)

    def test_limite_de_paginas(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "grande.pdf"
            _criar_pdf(pdf, PETICAO_COBRANCA, paginas_vazias=10)
            resultado = extrair_texto(str(pdf), max_paginas=3)
        self.assertEqual(resultado.paginas_analisadas, 3)
        self.assertEqual(resultado.total_paginas_pdf, 11)

    def test_lote_gera_csv(self):
        objetos = carregar_objetos()
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            _criar_pdf(pasta / "a_negativa.pdf", PETICAO_NEGATIVA)
            _criar_pdf(pasta / "b_cobranca.pdf", PETICAO_COBRANCA)
            (pasta / "ignorar.txt").write_text("não é pdf")
            itens = classificar_pasta(pasta, objetos)
            destino = gravar_csv(itens, pasta / "resultado.csv")
            with destino.open(encoding="utf-8-sig") as f:
                linhas = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(len(linhas), 2)
        self.assertEqual(
            linhas[0]["objeto"], "Negativa de cobertura — procedimento / cirurgia"
        )
        self.assertEqual(linhas[1]["objeto"], "Cobrança de prestador — glosas / faturamento")
        self.assertEqual({l["status"] for l in linhas}, {"OK"})

    def test_pdf_corrompido_reporta_erro(self):
        objetos = carregar_objetos()
        with tempfile.TemporaryDirectory() as tmp:
            falso = Path(tmp) / "quebrado.pdf"
            falso.write_bytes(b"isto nao e um pdf")
            item = classificar_arquivo(falso, objetos)
        self.assertIsNotNone(item.erro)
        self.assertEqual(item.linha_csv()["status"], "ERRO")


class TestWeb(unittest.TestCase):
    def setUp(self):
        from classificador.classificacao import carregar_objetos as _carregar
        from classificador.web import criar_app

        self.tmp = tempfile.TemporaryDirectory()
        self.objetos_json = Path(self.tmp.name) / "objetos.json"
        salvar_objetos(_carregar(), self.objetos_json)
        self.cliente = criar_app(arquivo_objetos=self.objetos_json).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_inicio(self):
        resposta = self.cliente.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Classificar um processo", resposta.get_data(as_text=True))

    def test_upload_e_classificacao(self):
        pdf = Path(self.tmp.name) / "processo.pdf"
        _criar_pdf(pdf, PETICAO_NEGATIVA)
        with pdf.open("rb") as f:
            resposta = self.cliente.post(
                "/classificar",
                data={"pdf": (f, "processo.pdf"), "max_paginas": "30"},
                content_type="multipart/form-data",
            )
        corpo = resposta.get_data(as_text=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Negativa de cobertura", corpo)
        self.assertIn("5012345-67.2024.8.13.0024", corpo)

    def test_adicionar_e_remover_termo(self):
        self.cliente.post(
            "/objetos/termo/adicionar",
            data={"objeto": "glosa_prestador", "termo": "duplicata mercantil", "peso": "3"},
        )
        objetos = carregar_objetos(self.objetos_json)
        cobranca = next(o for o in objetos if o.id == "glosa_prestador")
        self.assertIn(("duplicata mercantil", 3), [(t.texto, t.peso) for t in cobranca.termos])

        self.cliente.post(
            "/objetos/termo/remover",
            data={"objeto": "glosa_prestador", "termo": "duplicata mercantil"},
        )
        objetos = carregar_objetos(self.objetos_json)
        cobranca = next(o for o in objetos if o.id == "glosa_prestador")
        self.assertNotIn("duplicata mercantil", [t.texto for t in cobranca.termos])

    def test_adicionar_objeto(self):
        self.cliente.post("/objetos/adicionar", data={"nome": "Usucapião"})
        objetos = carregar_objetos(self.objetos_json)
        self.assertIn("Usucapião", [o.nome for o in objetos])


if __name__ == "__main__":
    unittest.main(verbosity=2)
