# dadoscaged

Aquisição documentada e reprodutível de dados do **Painel de Informações do Novo CAGED**
(Ministério do Trabalho e Emprego), para uso em análise quantitativa em economia.

O objetivo não é entregar uma planilha. É deixar registrado, de forma auditável, **de onde
veio cada número, com qual consulta, em que versão da fonte, e como isso foi conferido** —
inclusive contra os microdados oficiais. Qualquer pessoa com Python 3.9+ reexecuta o
pipeline e obtém o mesmo arquivo, ou descobre exatamente onde ele divergiu.

```bash
git clone https://github.com/RodrigoSilRo/dadoscaged
cd dadoscaged
python scripts/01_extrair.py     # extrai, valida e grava; nada é gravado sem passar
```

---

## Índice

- [Fonte](#fonte)
- [O que o pipeline faz de diferente](#o-que-o-pipeline-faz-de-diferente)
- [Validação](#validação)
- [Reprodução](#reprodução)
- [Saída atual](#saída-atual)
- [Antes de usar em estimação](#antes-de-usar-em-estimação)
- [Painel ou microdados?](#painel-ou-microdados)
- [Estrutura](#estrutura)
- [Como citar](#como-citar)
- [Licença](#licença)

---

## Fonte

| | |
|---|---|
| Painel | [Painel de Informações do Novo CAGED][painel] |
| Órgão | Ministério do Trabalho e Emprego (MTE) / Secretaria de Trabalho |
| Pacote publicado | `Painel Novo CAGED.pbix` |
| Cobertura da coleta atual | competências 2020-01 a 2026-07 (79 meses) |
| Metodologia do órgão | <http://pdet.mte.gov.br/o-que-e-novo-caged> |
| Microdados oficiais | `ftp://ftp.mtps.gov.br/pdet/microdados/NOVO CAGED/` |

[painel]: https://app.powerbi.com/view?r=eyJrIjoiNWI5NWI0ODEtYmZiYy00Mjg3LTkzNWUtY2UyYjIwMDE1YWI2IiwidCI6IjNlYzkyOTY5LTVhNTEtNGYxOC04YWM5LWVmOThmYmFmYTk3OCJ9

O painel foi divulgado pelo órgão com a opção **"Publicar na web"** do Power BI, que expõe
o modelo semântico para consulta anônima. **Nenhuma credencial é usada, nenhum controle de
acesso é contornado, nenhum dado não-público é acessado** — o pipeline consulta o mesmo
backend, com a mesma chave pública do link, que o navegador de qualquer visitante consulta
ao abrir o painel.

## O que o pipeline faz de diferente

A alternativa manual seria abrir o painel, aplicar o filtro de setor e expandir a matriz
nível a nível. É lento, não deixa rastro e tem um modo de falha silencioso: basta um nível
ficar parcialmente expandido para a tabela sair incompleta sem nenhum aviso.

Aqui a consulta é escrita explicitamente contra o modelo semântico, pedindo de uma vez o
nível mais desagregado **junto de todos os seus níveis pais**. O JSON exato de cada
consulta enviada fica arquivado ao lado da resposta que ela produziu.

Três coisas que este repositório trata e que uma extração ingênua erraria em silêncio:

**Decodificação.** A resposta do Power BI não é tabular: usa dicionários de valores,
supressão de valores repetidos por bitmask, máscara de nulos, e alterna entre duas
codificações de linha. Ler errado produz uma tabela plausível e incorreta. Ver
[`docs/METODOLOGIA.md`](docs/METODOLOGIA.md), seção 5.

**Aditividade.** `Tempo de Emprego` e `Vr. Relativa` são média e razão calculadas em DAX;
somá-las entre categorias não significa nada. O pipeline classifica cada medida e valida
cada tipo com a prova apropriada.

**Versão da fonte.** Os metadados do painel (`version`, `LastRefreshTime`) **ficam
defasados** durante uma atualização — foi observado o painel servir dados novos declarando
metadados de um mês antes, por mais de meia hora. A identidade da versão é, por isso,
derivada dos próprios dados gravados.

## Validação

Nenhum arquivo é gravado sem passar por três conferências independentes:

1. **Medidas aditivas × total do painel.** A soma das linhas desagregadas é comparada,
   mês a mês, com o total do setor obtido em consulta separada no nível agregado.
   Igualdade exata.
2. **Exatidão no nível pai.** Para medidas com desvio conhecido da fonte no nível mais
   fino, exige-se igualdade exata no nível imediatamente acima, e o resíduo do nível
   extraído é **medido e registrado**, não tolerado em silêncio.
3. **Célula a célula.** Competências sorteadas são reconsultadas no mesmo nível de
   desagregação, mas **particionando por competência em vez de por ano**, e comparadas
   valor a valor em todas as medidas — inclusive as que não podem ser somadas.

Resultado da coleta atual: **79/79 meses**, **8.196 células**, **0 divergências**.

Há ainda uma quarta conferência, opcional e mais forte, que não compara o painel consigo
mesmo: [`scripts/04_conferir_microdados.py`](scripts/04_conferir_microdados.py)
reconstrói uma competência a partir dos **microdados oficiais do FTP** e verifica se o
agregado bate. Para março/2022 no Comércio, 95,9% da revisão de admissões e 98,8% da de
desligamentos são explicados somando nove meses de declarações posteriores — confirmando
que o painel é agregação exata desses microdados.

## Reprodução

A aquisição e a validação usam **apenas a biblioteca padrão do Python** (3.9+).

```bash
python scripts/00_inventario_fonte.py     # registra schema e versão do painel
python scripts/01_extrair.py              # extrai + valida + grava CSV e manifesto
python scripts/02_validar.py data/processed/caged_comercio_subclasse_mensal.csv
```

Passos opcionais:

```bash
pip install -r requirements.txt                      # pandas, openpyxl, py7zr
python scripts/03_exportar_excel.py data/processed/caged_comercio_subclasse_mensal.csv
python scripts/04_conferir_microdados.py --competencia 202203 --revisoes 9
```

Testes (não acessam a rede):

```bash
python -m unittest discover -s tests -v
```

### Outros recortes

```bash
python scripts/01_extrair.py --setor Serviços --nivel "CNAE 2.0 Classe"
python scripts/01_extrair.py --setor todos --nivel "CNAE 2.0 Divisão" --anos 2024 2025 2026
python scripts/01_extrair.py --medidas Admitidos Desligados Saldo
```

Níveis, do mais agregado ao mais desagregado: `Grande Grupamento`, `Grupamento`,
`CNAE 2.0 Seção`, `CNAE 2.0 Divisão`, `CNAE 2.0 Grupo`, `CNAE 2.0 Classe`,
`CNAE 2.0 Subclasse`.

O modelo também expõe dimensões geográfica (região, UF, município), ocupacional (CBO),
pessoais (sexo, faixa etária, grau de instrução, nacionalidade) e de vínculo (aprendiz,
intermitente, temporário, estrangeiro) — ver [`docs/MODELO.md`](docs/MODELO.md).

## Saída atual

`data/processed/caged_comercio_subclasse_mensal.csv` — setor **Comércio** no menor nível
disponível (**CNAE 2.0 Subclasse**), mês a mês:

- **18.023 linhas** — 79 competências (2020-01 a 2026-07) × 231 subclasses CNAE
- hierarquia CNAE completa em colunas (código e nome de cada nível), de Grande Grupamento
  até Subclasse — permite reagregar para qualquer nível sem nova extração
- medidas: `admitidos`, `desligados`, `saldo`, `estoque_mensal`,
  `tempo_de_emprego_desligados`, `vr_relativa`
- separador `;`, UTF-8 com BOM, decimais com ponto

Cada CSV vem com um `.manifesto.json` contendo data da coleta, identificadores do modelo,
a impressão digital dos dados, o `sha256` do arquivo e o resultado completo das três
provas de validação.

Descrição das variáveis, incluindo quais podem ser somadas:
[`docs/DICIONARIO.md`](docs/DICIONARIO.md).

## Antes de usar em estimação

Leia [`docs/LIMITACOES.md`](docs/LIMITACOES.md) — são 15 seções, e estas quatro mudam
resultados:

- **A série é revisada.** Meses já divulgados mudam quando chegam declarações fora do
  prazo. A data da coleta faz parte da identidade do dado. Aconteceu *durante a construção
  deste repositório*: em 16 minutos, julho/2026 entrou na série e junho foi revisado.
- **O primeiro valor publicado pode ter o sinal oposto do final.** O saldo de março/2022
  no Comércio foi ao ar **+467** e hoje é **−8.750**. Se o seu desenho depende do que os
  agentes observavam à época, o painel é a fonte errada — use os microdados.
- **Quebra estrutural em outubro de 2021**, declarada pelo próprio órgão: a metodologia de
  consolidação mudou para captar mais movimentações.
- **Ausência de linha não é zero**, e medidas compostas não são somáveis.

## Painel ou microdados?

| | painel (este repositório) | microdados do FTP |
|---|---|---|
| granularidade | agregados por setor/mês | registro individual |
| variáveis | 6 medidas + dimensões do modelo | 28 colunas, inclusive **salário**, idade exata, raça/cor, tipo de movimentação |
| estoque de vínculos | **sim** | não (só movimentações) |
| controle de safra | não (só a série revisada) | **sim** (`competênciadec`) |
| esforço | uma linha de comando | ~55 MB/mês, reconstrução manual da série |

**São os mesmos dados** — verificado, não presumido. Use este repositório para agregados
setoriais prontos e conferidos; use os microdados para salário, cruzamentos livres ou
dados *as-first-published*. Comparação completa em
[`docs/LIMITACOES.md`](docs/LIMITACOES.md), seção 12.

## Estrutura

```
src/dadoscaged/   config.py  client.py  query.py  dsr.py  extract.py  validate.py
scripts/          00_inventario_fonte.py  01_extrair.py  02_validar.py
                  03_exportar_excel.py    04_conferir_microdados.py
tests/            test_dsr.py
docs/             METODOLOGIA.md  DICIONARIO.md  LIMITACOES.md  MODELO.md
metadata/         schema_modelo.json  modelo.json  proveniencia.json
data/processed/   CSV + manifesto + xlsx
data/raw/         consultas e respostas brutas da API (não versionadas)
```

## Como citar

Os **dados** são do Ministério do Trabalho e Emprego — cite o MTE como fonte primária,
informando a data da coleta e a última competência, que estão no manifesto. Cite este
repositório apenas como instrumento de coleta, se for relevante descrever o procedimento.
Ver [`CITATION.cff`](CITATION.cff).

## Licença

O **código** está sob licença MIT (ver [`LICENSE`](LICENSE)).

Os **dados** são produzidos e divulgados pelo MTE. Este repositório não reivindica autoria
sobre eles e não os modifica: apenas reorganiza em formato tabular o que o painel público
já apresenta.

---

<details>
<summary><b>English summary</b></summary>

Reproducible, documented acquisition of Brazilian formal-employment data (Novo CAGED)
from the Ministry of Labour's public Power BI dashboard, for quantitative economics
research.

The dashboard is published with Power BI's "publish to web", exposing its semantic model
for anonymous queries. This pipeline queries that model explicitly instead of scripting UI
clicks, requesting the finest CNAE level together with all its parent levels in one query.

Nothing is written without passing three independent checks: additive measures must sum
exactly to the dashboard's own sector totals; measures with a known source-side residual
must be exact at the parent level, with the residual measured and recorded; and randomly
sampled months are re-queried **under a different partitioning** and compared cell by cell,
covering the non-additive measures (a mean and a ratio) that summing cannot verify.
Current run: 79/79 months, 8,196 cells, 0 discrepancies.

A fourth, optional check reconstructs a month from the ministry's official microdata (FTP)
and confirms the dashboard is an exact aggregation of it.

Two findings matter for research use. The series is **revised** as late declarations
arrive — March 2022 retail trade was published at **+467** net jobs and now reads
**−8,750**, a sign flip. And the dashboard's own version metadata does **not** change when
its data changes, so version identity here is derived from the data itself and the
collection aborts if the source shifts mid-run.

Data © Ministry of Labour and Employment (Brazil). Code under MIT. See
`docs/LIMITACOES.md` before estimating anything.

</details>
