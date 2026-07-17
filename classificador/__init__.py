"""Classificador local de processos judiciais em PDF.

Extrai o texto do PDF (com OCR opcional para páginas escaneadas) e
classifica o processo pelos objetos de ação configurados em objetos.json,
tudo localmente, sem chamar nenhuma API de IA.
"""

__version__ = "0.1.0"
