# Classificador de Processos Judiciais

Ferramenta local para sanear a carteira de processos: lê o PDF de cada
processo, identifica o **objeto da ação** e o **número CNJ/tribunal**, e
gera uma planilha com a carteira classificada.

Tudo roda **na sua máquina, sem nenhuma API de IA** — sem custo por
processo e sem enviar autos para fora do escritório. A leitura usa a
camada de texto que os PDFs de processo eletrônico (PJe, e-SAJ, eproc,
Projudi) já trazem embutida, então é rápida mesmo em arquivos grandes.

## Como funciona

1. **Leitura do PDF**: extrai o texto das primeiras páginas (padrão: 30),
   onde fica a petição inicial — é ela que define o objeto da ação. Dá
   para analisar o documento inteiro com `--paginas 0`.
2. **Classificação por regras**: cada objeto de ação tem uma lista de
   termos com peso (em `classificador/objetos.json`). Os termos
   encontrados no texto somam pontos; o objeto com mais pontos vence.
   A comparação ignora acentos e maiúsculas.
3. **Triagem**: se a pontuação ficar abaixo do mínimo, o processo sai
   como **REVISAR** — você só olha manualmente esses.

O classificador "aprende" quando você ajusta os termos: classificou
errado, adicione ao objeto correto uma expressão que aparece naquele tipo
de processo (a tela de resultado mostra as evidências para facilitar).

## Instalação

Requer Python 3.10+.

```bash
pip install -r requirements.txt
```

## Uso

### Interface web (um processo por vez)

```bash
python -m classificador web
```

Abra <http://127.0.0.1:5000>, envie o PDF e veja o resultado com as
evidências. Na aba **Objetos de ação** você edita os objetos e termos do
seu sistema (adicionar, remover, criar objeto novo) — as alterações valem
imediatamente para as próximas classificações.

### Carteira inteira (lote) — o modo para o saneamento

```bash
python -m classificador lote /pasta/com/os/pdfs -o resultado.csv
```

Varre a pasta (e subpastas), classifica cada PDF e grava um CSV que abre
direto no Excel, com: arquivo, número do processo, tribunal, objeto,
pontuação, status (OK/REVISAR/ERRO) e o segundo colocado no ranking.

### Um arquivo só, pelo terminal

```bash
python -m classificador arquivo processo.pdf
python -m classificador arquivo processo.pdf --paginas 0   # documento inteiro
```

### Ver os objetos configurados

```bash
python -m classificador objetos
```

## Ajustando ao seu sistema

Os objetos de ação vêm pré-configurados com casos comuns (negativa de
cobertura, reembolso, cobrança, monitória, execução, cumprimento de
sentença, danos morais/materiais, reajuste de plano, revisional,
consignação, declaratória de inexistência, trabalhista…). **Edite-os para
espelhar exatamente os objetos do seu sistema** — pela interface web ou
direto no `classificador/objetos.json`:

```json
{
  "id": "meu_objeto",
  "nome": "Nome como está no meu sistema",
  "termos": [
    {"t": "expressão bem específica desse objeto", "peso": 4},
    "termo mais genérico (peso 1)"
  ]
}
```

Dicas:

- Termos **específicos** (ex.: "ação monitória") merecem peso 4–5;
  termos **genéricos** (ex.: "internação") ficam com peso 1.
- Use as **evidências** da tela de resultado para descobrir quais
  expressões distinguem um objeto do outro nos seus processos reais.
- Rode o lote de novo depois de ajustar — é rápido e não custa nada.

## Limitações

- Páginas **digitalizadas como imagem** (sem camada de texto) não são
  lidas — o relatório indica quantas páginas ficaram sem texto para você
  saber quando isso aconteceu. Em processos eletrônicos isso é raro na
  petição inicial.
- PDFs protegidos por senha ou corrompidos saem com status **ERRO** no
  CSV, sem interromper o lote.

## Testes

```bash
python tests/test_classificador.py
```
