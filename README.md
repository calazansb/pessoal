# Ferramentas pessoais

- **[Classificador de Processos](classificador/README.md)** — lê o PDF de
  um processo judicial e classifica o objeto da ação localmente, sem API
  de IA. Modo lote gera planilha da carteira inteira.
- **Instagram Follower Tracker** (abaixo) — acompanha seguidores e
  seguindo, com histórico local.

# Instagram Follower Tracker

Ferramenta de linha de comando que acessa o seu Instagram, baixa a lista de
**seguidores** e de **quem você segue**, compara as duas e guarda o histórico
em uma base local (SQLite). A cada execução ela mostra:

- 😤 **Quem você segue e NÃO te segue de volta**
- 🔴 **Quem parou de te seguir** desde a última execução
- 🟢 **Novos seguidores**
- ➕ / ➖ Quem você **começou** ou **parou** de seguir
- 📜 Histórico completo de todas as execuções e mudanças

Todos os dados ficam só na sua máquina, na pasta `data/` (que não vai para o
git).

## Instalação

Requer Python 3.10+.

```bash
pip install -r requirements.txt
```

## Uso

### Atualizar a base (uso normal, toda vez que quiser rodar)

```bash
python -m tracker sync
```

Na primeira vez ele pede seu usuário e senha do Instagram (e o código de
verificação, se você tiver 2FA). O login fica salvo em `data/session.json`,
então nas próximas execuções ele entra direto.

Se preferir, defina as credenciais por variável de ambiente para não digitar:

```bash
export IG_USERNAME=seu_usuario
export IG_PASSWORD=sua_senha
python -m tracker sync
```

A primeira execução cria a base. Da segunda em diante, ele mostra o que mudou
(quem saiu, quem entrou) e a situação atual.

### Ver a situação atual sem acessar o Instagram

```bash
python -m tracker report              # resumo + quem não te segue de volta
python -m tracker report --completo   # inclui também quem você não segue de volta
```

### Histórico

```bash
python -m tracker history                        # todas as execuções
python -m tracker events                         # últimas 50 mudanças
python -m tracker events --tipo lost_follower    # só quem deixou de seguir
python -m tracker events -n 200                  # mais resultados
```

Tipos de evento: `new_follower`, `lost_follower`, `started_following`,
`stopped_following`.

## Alternativa sem senha: importar o export oficial do Instagram

O Instagram pode bloquear ou pedir verificação em logins automatizados. Se
isso acontecer (ou se você preferir não digitar a senha em ferramenta
nenhuma), use o export oficial de dados:

1. No app do Instagram: **Configurações → Central de Contas → Suas
   informações e permissões → Baixar suas informações**
2. Escolha o formato **JSON** e marque **Seguidores e seguindo**
3. Quando o ZIP chegar por e-mail, rode:

```bash
python -m tracker import-export ~/Downloads/instagram-seuusuario.zip
```

Funciona igual ao `sync`: cria um snapshot, compara com o anterior e atualiza
o histórico.

> ⚠️ Não misture snapshots de `sync` (API) com snapshots de `import-export`
> na mesma base: o export oficial não traz o id numérico dos perfis, então a
> comparação entre os dois modos geraria falsos positivos. Escolha um modo e
> mantenha-o (ou use `--data-dir` para bases separadas).

## Avisos importantes

- O modo `sync` usa a API privada do Instagram (via
  [instagrapi](https://github.com/subzeroid/instagrapi)), a mesma que o app
  oficial usa, mas de forma não oficial. **Existe risco de o Instagram pedir
  verificação ou restringir temporariamente a conta**, principalmente se você
  rodar com muita frequência. Recomendação: rode no máximo 1–2 vezes por dia.
- Sua senha não é gravada em lugar nenhum; apenas o token de sessão fica em
  `data/session.json`. Se quiser deslogar, apague esse arquivo.

## Testes

```bash
python tests/test_tracker.py
```
