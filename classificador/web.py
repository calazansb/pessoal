"""Interface web local do classificador.

Roda só na sua máquina (http://localhost:5000), sem enviar nada para
fora. Três telas:

- Início: upload de um PDF para classificar na hora.
- Resultado: objeto vencedor, ranking e as evidências (trechos do
  processo onde cada termo apareceu).
- Objetos: os objetos de ação do seu sistema, com os termos de cada um.
  Adicionar/remover termos aqui é o que "ensina" o classificador.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, url_for

from .classificacao import (
    ARQUIVO_OBJETOS_PADRAO,
    ObjetoAcao,
    Termo,
    carregar_objetos,
    salvar_objetos,
)
from .lote import classificar_arquivo

MAX_UPLOAD_MB = 200

_BASE = """
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Classificador de Processos</title>
<style>
  :root { --azul: #1a4d8f; --cinza: #f2f4f7; --borda: #d8dee7; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; margin: 0; background: var(--cinza); color: #1c2733; }
  header { background: var(--azul); color: #fff; padding: 14px 24px; display: flex; gap: 24px; align-items: baseline; }
  header h1 { font-size: 18px; margin: 0; }
  header a { color: #cfe0f5; text-decoration: none; font-size: 14px; }
  header a:hover { color: #fff; }
  main { max-width: 880px; margin: 24px auto; padding: 0 16px; }
  .cartao { background: #fff; border: 1px solid var(--borda); border-radius: 10px; padding: 20px 24px; margin-bottom: 16px; }
  h2 { margin-top: 0; font-size: 17px; }
  .status-OK { color: #0a7a3d; font-weight: 600; }
  .status-REVISAR, .status-ERRO { color: #b3541e; font-weight: 600; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--borda); vertical-align: top; }
  .barra { background: #e3ebf5; border-radius: 4px; height: 10px; min-width: 120px; }
  .barra > div { background: var(--azul); height: 10px; border-radius: 4px; }
  .trecho { color: #55606e; font-size: 13px; }
  .pill { display: inline-block; background: #e8eef7; border-radius: 12px; padding: 2px 10px; margin: 2px; font-size: 13px; }
  .pill form { display: inline; }
  .pill button { border: none; background: none; color: #a33; cursor: pointer; padding: 0 0 0 4px; }
  input[type=text], input[type=number] { padding: 6px 8px; border: 1px solid var(--borda); border-radius: 6px; }
  button.acao, input[type=submit] { background: var(--azul); color: #fff; border: none; border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 14px; }
  .aviso { background: #fff7e6; border: 1px solid #eeddb0; border-radius: 8px; padding: 10px 14px; font-size: 14px; }
  .meta { color: #55606e; font-size: 14px; }
</style>
</head>
<body>
<header>
  <h1>Classificador de Processos</h1>
  <a href="{{ url_for('inicio') }}">Classificar PDF</a>
  <a href="{{ url_for('tela_objetos') }}">Objetos de ação</a>
</header>
<main>{% block conteudo %}{% endblock %}</main>
</body>
</html>
"""

_TELA_INICIO = """
{% extends "base" %}
{% block conteudo %}
<div class="cartao">
  <h2>Classificar um processo</h2>
  <p class="meta">Envie o PDF do processo. A análise é feita nesta máquina,
  nada é enviado para fora. Por padrão são lidas as primeiras
  {{ max_paginas }} páginas (onde fica a petição inicial).</p>
  <form method="post" action="{{ url_for('classificar') }}" enctype="multipart/form-data">
    <p><input type="file" name="pdf" accept="application/pdf" required></p>
    <p>Páginas a analisar: <input type="number" name="max_paginas" value="{{ max_paginas }}" min="0" style="width:80px">
       <span class="meta">(0 = documento inteiro)</span></p>
    <input type="submit" value="Classificar">
  </form>
</div>
<div class="cartao">
  <h2>Carteira inteira (lote)</h2>
  <p class="meta">Para classificar centenas de PDFs de uma vez, use o modo
  lote no terminal — ele gera uma planilha CSV com um processo por linha:</p>
  <pre>python -m classificador lote /pasta/com/os/pdfs -o resultado.csv</pre>
</div>
{% endblock %}
"""

_TELA_RESULTADO = """
{% extends "base" %}
{% block conteudo %}
<div class="cartao">
  <h2>{{ item.arquivo.name }}</h2>
  {% if item.erro %}
    <p class="status-ERRO">Erro ao ler o PDF: {{ item.erro }}</p>
  {% else %}
  {% set c = item.classificacao %}
  <p class="meta">
    {% if c.numero_processo %}Processo <strong>{{ c.numero_processo }}</strong>
      {% if c.tribunal %}({{ c.tribunal }}){% endif %} ·{% endif %}
    {{ item.paginas_analisadas }} de {{ item.total_paginas }} páginas analisadas
    {% if item.paginas_sem_texto %} · {{ item.paginas_sem_texto }} páginas sem texto (digitalizadas){% endif %}
  </p>
  <p>Classificação: <strong>{{ c.objeto }}</strong> —
     <span class="status-{{ c.status }}">{{ c.status }}</span></p>
  {% if item.paginas_sem_texto and c.status == 'REVISAR' %}
    <p class="aviso">Várias páginas não têm camada de texto (provável
    digitalização em imagem). O texto dessas páginas não pôde ser lido.</p>
  {% endif %}
  {% if c.ranking %}
  {% set maximo = c.ranking[0].pontos %}
  <table>
    <tr><th>Objeto</th><th>Pontos</th><th></th></tr>
    {% for p in c.ranking[:5] %}
    <tr>
      <td>{{ p.objeto.nome }}</td>
      <td>{{ p.pontos }}</td>
      <td><div class="barra"><div style="width: {{ (100 * p.pontos / maximo) | round }}%"></div></div></td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p>Nenhum termo dos objetos configurados foi encontrado no texto.</p>
  {% endif %}
  {% endif %}
</div>
{% if not item.erro and item.classificacao.ranking %}
<div class="cartao">
  <h2>Evidências — {{ item.classificacao.ranking[0].objeto.nome }}</h2>
  <table>
    <tr><th>Termo</th><th>Vezes</th><th>Trecho do processo</th></tr>
    {% for t in item.classificacao.ranking[0].termos_encontrados %}
    <tr>
      <td>{{ t.termo }}</td>
      <td>{{ t.ocorrencias }}</td>
      <td class="trecho">{{ t.trecho }}</td>
    </tr>
    {% endfor %}
  </table>
  <p class="meta">Classificou errado? Ajuste os termos na tela
  <a href="{{ url_for('tela_objetos') }}">Objetos de ação</a> — adicione ao
  objeto correto uma expressão que aparece neste processo.</p>
</div>
{% endif %}
<p><a href="{{ url_for('inicio') }}">← Classificar outro processo</a></p>
{% endblock %}
"""

_TELA_OBJETOS = """
{% extends "base" %}
{% block conteudo %}
<div class="cartao">
  <h2>Objetos de ação do sistema</h2>
  <p class="meta">Estes são os objetos usados na classificação, com os termos
  que pontuam para cada um (o número é o peso do termo). Para "ensinar" o
  classificador, adicione aos objetos os termos que aparecem nos seus
  processos reais. As alterações são salvas em <code>{{ arquivo }}</code>.</p>
</div>
{% for o in objetos %}
<div class="cartao">
  <h2>{{ o.nome }}</h2>
  {% for t in o.termos %}
    <span class="pill">{{ t.texto }}{% if t.peso != 1 %} · {{ t.peso }}{% endif %}
      <form method="post" action="{{ url_for('remover_termo') }}">
        <input type="hidden" name="objeto" value="{{ o.id }}">
        <input type="hidden" name="termo" value="{{ t.texto }}">
        <button title="Remover termo">×</button>
      </form>
    </span>
  {% endfor %}
  <form method="post" action="{{ url_for('adicionar_termo') }}" style="margin-top:10px">
    <input type="hidden" name="objeto" value="{{ o.id }}">
    <input type="text" name="termo" placeholder="novo termo ou expressão" required>
    peso <input type="number" name="peso" value="1" min="1" max="9" style="width:60px">
    <button class="acao">Adicionar</button>
  </form>
</div>
{% endfor %}
<div class="cartao">
  <h2>Novo objeto de ação</h2>
  <form method="post" action="{{ url_for('adicionar_objeto') }}">
    <input type="text" name="nome" placeholder="nome do objeto (ex.: Usucapião)" required style="width:60%">
    <button class="acao">Criar objeto</button>
  </form>
</div>
{% endblock %}
"""


def criar_app(arquivo_objetos: str | Path = ARQUIVO_OBJETOS_PADRAO, max_paginas: int = 30) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    arquivo_objetos = Path(arquivo_objetos)

    telas = {
        "base": _BASE,
        "inicio": _TELA_INICIO,
        "resultado": _TELA_RESULTADO,
        "objetos": _TELA_OBJETOS,
    }
    app.jinja_loader = None
    from jinja2 import DictLoader

    app.jinja_env.loader = DictLoader(telas)

    def _render(tela: str, **contexto):
        return render_template_string(telas[tela], **contexto)

    @app.get("/")
    def inicio():
        return _render("inicio", max_paginas=max_paginas)

    @app.post("/classificar")
    def classificar():
        enviado = request.files.get("pdf")
        if not enviado or not enviado.filename:
            return redirect(url_for("inicio"))
        try:
            paginas = int(request.form.get("max_paginas", max_paginas))
        except ValueError:
            paginas = max_paginas
        objetos = carregar_objetos(arquivo_objetos)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / Path(enviado.filename).name
            enviado.save(destino)
            item = classificar_arquivo(destino, objetos, max_paginas=paginas)
        return _render("resultado", item=item)

    @app.get("/objetos")
    def tela_objetos():
        return _render(
            "objetos", objetos=carregar_objetos(arquivo_objetos), arquivo=arquivo_objetos
        )

    @app.post("/objetos/termo/adicionar")
    def adicionar_termo():
        objetos = carregar_objetos(arquivo_objetos)
        termo = request.form.get("termo", "").strip()
        try:
            peso = max(1, int(request.form.get("peso", 1)))
        except ValueError:
            peso = 1
        for o in objetos:
            if o.id == request.form.get("objeto") and termo:
                if termo.lower() not in {t.texto.lower() for t in o.termos}:
                    o.termos.append(Termo(termo, peso))
                    salvar_objetos(objetos, arquivo_objetos)
        return redirect(url_for("tela_objetos"))

    @app.post("/objetos/termo/remover")
    def remover_termo():
        objetos = carregar_objetos(arquivo_objetos)
        for o in objetos:
            if o.id == request.form.get("objeto"):
                o.termos = [t for t in o.termos if t.texto != request.form.get("termo")]
                salvar_objetos(objetos, arquivo_objetos)
        return redirect(url_for("tela_objetos"))

    @app.post("/objetos/adicionar")
    def adicionar_objeto():
        objetos = carregar_objetos(arquivo_objetos)
        nome = request.form.get("nome", "").strip()
        if nome:
            base = "".join(c if c.isalnum() else "_" for c in nome.lower()).strip("_")
            novo_id, n = base or "objeto", 2
            ids = {o.id for o in objetos}
            while novo_id in ids:
                novo_id, n = f"{base}_{n}", n + 1
            objetos.append(ObjetoAcao(novo_id, nome, []))
            salvar_objetos(objetos, arquivo_objetos)
        return redirect(url_for("tela_objetos"))

    return app


def rodar(host: str = "127.0.0.1", porta: int = 5000, **kwargs) -> None:
    criar_app(**kwargs).run(host=host, port=porta, debug=False)
