# dadoscaged

Aquisição documentada e reprodutível de dados do **Painel de Informações do Novo CAGED**
(Ministério do Trabalho e Emprego), para uso em análise quantitativa em economia.

O objetivo do repositório não é só entregar uma planilha: é deixar registrado, de forma
auditável, **de onde veio cada número, com qual consulta, em que data, e como isso foi
conferido**. Qualquer pessoa com Python 3.9+ consegue reexecutar o pipeline e obter o
mesmo arquivo, ou apontar exatamente onde ele divergiu.

---

## Fonte

| | |
|---|---|
| Painel | [Painel de Informações do Novo CAGED][painel] |
| Órgão | Ministério do Trabalho e Emprego (MTE) / Secretaria de Trabalho |
| Pacote publicado | `Painel Novo CAGED.pbix`, versão `ID-19810754` |
| Último refresh do painel | 2026-07-29T18:16:56 |
| Cobertura | competências 2020-01 a 2026-06 (78 meses) |
| Metodologia do órgão | <http://pdet.mte.gov.br/o-que-e-novo-caged> |

[painel]: https://app.powerbi.com/view?r=eyJrIjoiNWI5NWI0ODEtYmZiYy00Mjg3LTkzNWUtY2UyYjIwMDE1YWI2IiwidCI6IjNlYzkyOTY5LTVhNTEtNGYxOC04YWM5LWVmOThmYmFmYTk3OCJ9

O painel foi divulgado pelo órgão com a opção **"Publicar na web"** do Power BI, que
expõe o modelo semântico para consulta anônima. **Nenhuma credencial é usada, nenhum
controle de acesso é contornado e nenhum dado não-público é acessado** — o pipeline
consulta o mesmo backend, com a mesma chave pública do link, que o navegador de qualquer
visitante consulta ao abrir o painel.

---

## O que o pipeline faz de diferente

A alternativa manual seria abrir o painel, aplicar o filtro de setor e expandir a matriz
nível a nível. Isso é lento, não deixa rastro e tem um modo de falha silencioso: basta um
nível ficar parcialmente expandido para a tabela sair incompleta sem nenhum aviso.

Aqui a consulta é escrita explicitamente contra o modelo semântico, pedindo de uma vez o
nível mais desagregado **junto de todos os seus níveis pais**. O JSON exato de cada
consulta enviada fica arquivado ao lado da resposta que ela produziu.

### Validação

Nenhum arquivo é gravado sem passar por uma conferência independente:

> A soma das linhas desagregadas, mês a mês, é comparada com o total do setor obtido em
> **uma consulta separada, no nível agregado**, que não passa por nenhum dos níveis
> desagregados. Exige-se igualdade exata.

Esse teste pega truncamento de resposta, nível parcialmente expandido e erro de
decodificação — as três formas realistas de a extração sair errada sem estourar exceção.
Na coleta atual: **78 de 78 meses conferidos, 0 divergências.**

---

## Reprodução

```bash
git clone https://github.com/RodrigoSilRo/dadoscaged
cd dadoscaged

python scripts/00_inventario_fonte.py     # registra schema e versão do painel
python scripts/01_extrair.py              # extrai + valida + grava CSV e manifesto
python scripts/02_validar.py data/processed/caged_comercio_subclasse_mensal.csv
```

A aquisição e a validação usam **apenas a biblioteca padrão do Python**. O passo opcional
de exportação para Excel precisa de `pandas` e `openpyxl` (`pip install -r requirements.txt`):

```bash
python scripts/03_exportar_excel.py data/processed/caged_comercio_subclasse_mensal.csv
```

Testes do decodificador e dos construtores de consulta (não acessam a rede):

```bash
python -m unittest discover -s tests -v
```

### Outros recortes

```bash
# Serviços no nível de classe
python scripts/01_extrair.py --setor Serviços --nivel "CNAE 2.0 Classe"

# Todos os setores, nível de divisão, só nos anos recentes
python scripts/01_extrair.py --setor todos --nivel "CNAE 2.0 Divisão" --anos 2024 2025 2026
```

Níveis disponíveis, do mais agregado ao mais desagregado: `Grande Grupamento`,
`Grupamento`, `CNAE 2.0 Seção`, `CNAE 2.0 Divisão`, `CNAE 2.0 Grupo`, `CNAE 2.0 Classe`,
`CNAE 2.0 Subclasse`.

---

## Saída atual

`data/processed/caged_comercio_subclasse_mensal.csv`

Setor **Comércio** no menor nível disponível (**CNAE 2.0 Subclasse**), mês a mês:

- **17.675 linhas** — 78 competências (2020-01 a 2026-06) × 231 subclasses CNAE
- hierarquia CNAE completa em colunas (código e nome de cada nível), de Grande Grupamento
  até Subclasse — permite reagregar para qualquer nível sem nova extração
- medidas: `admitidos`, `desligados`, `saldo`
- separador `;`, codificação UTF-8 com BOM (abre direto no Excel em português)

Cada CSV vem acompanhado de um `.manifesto.json` com data da coleta, versão e data de
refresh do painel, consulta usada, `sha256` do arquivo e resultado da validação.

Descrição das variáveis: [`docs/DICIONARIO.md`](docs/DICIONARIO.md).

---

## Antes de usar em estimação

Leia [`docs/LIMITACOES.md`](docs/LIMITACOES.md). Em especial:

- a série do Novo CAGED é **revisada** a cada divulgação (declarações fora do prazo), então
  a data da coleta faz parte da identidade do dado;
- há **mudança de metodologia declarada pelo órgão a partir da competência de outubro de
  2021**, o que é uma quebra estrutural relevante para séries temporais;
- ausência de linha significa ausência de movimentação, não zero observado.

---

## Estrutura

```
src/dadoscaged/     config.py  client.py  query.py  dsr.py  extract.py  validate.py
scripts/            00_inventario_fonte.py  01_extrair.py  02_validar.py  03_exportar_excel.py
tests/              test_dsr.py
docs/               METODOLOGIA.md  DICIONARIO.md  LIMITACOES.md  MODELO.md
metadata/           schema_modelo.json  modelo.json  proveniencia.json
data/processed/     CSV + manifesto
data/raw/           consultas e respostas brutas da API (não versionadas)
```

Detalhamento técnico da aquisição: [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md).

---

## Licença e uso dos dados

O **código** deste repositório está sob licença MIT (ver [`LICENSE`](LICENSE)).

Os **dados** são produzidos e divulgados pelo Ministério do Trabalho e Emprego. Este
repositório não reivindica autoria sobre eles e não os modifica: apenas reorganiza em
formato tabular o que o painel público já apresenta. Ao usar em publicação, cite o MTE
como fonte primária — ver [`CITATION.cff`](CITATION.cff) para uma sugestão de citação
que separa a fonte do instrumento de coleta.
