# Metodologia da aquisição

Documento técnico: o que exatamente é feito para transformar o painel público em uma
tabela. Escrito para que um revisor consiga auditar cada etapa sem executar o código.

---

## 1. Identificação da fonte

O link de divulgação do painel carrega um parâmetro `r` que é um JSON em base64:

```json
{"k": "5b95b481-bfbc-4287-935e-ce2b20015ab6",
 "t": "3ec92969-5a51-4f18-8ac9-ef98fbafa978"}
```

`k` é a **chave de recurso** (resource key) do relatório publicado; `t` é o **tenant** do
órgão. Em relatórios publicados com a opção "Publicar na web" do Power BI, a chave de
recurso substitui o token OAuth: ela é enviada no cabeçalho `X-PowerBI-ResourceKey` e
autoriza consultas anônimas ao modelo semântico. É o mesmo mecanismo que o navegador de
qualquer visitante usa.

## 2. Resolução do backend

A página do relatório declara em seu HTML o cluster regional que atende o relatório —
neste caso `brazil-south`. Um detalhe prático, registrado aqui porque custou tempo:

- `wabi-brazil-south-d-primary-**redirect**.analysis.windows.net` encerra a conexão
  (TCP reset) para clientes que não sejam navegador;
- `wabi-brazil-south-d-primary-**api**.analysis.windows.net` responde normalmente.

O host usado está fixado em `config.CLUSTER_HOST`. Se o órgão migrar o relatório de
região, esse é o único valor a mudar — a página do relatório continuará declarando o
cluster correto.

## 3. Descoberta do modelo

Dois endpoints são consultados antes de qualquer extração
(`scripts/00_inventario_fonte.py`):

| Endpoint | Conteúdo |
|---|---|
| `GET /public/reports/{k}/modelsAndExploration` | identificadores do modelo, layout das páginas e, em `package`, o nome do `.pbix`, sua versão e o `LastRefreshTime` |
| `POST /public/reports/conceptualschema` | todas as tabelas, colunas e medidas do modelo |

As respostas são salvas em `metadata/`. São elas que fixam o estado do painel no momento
da coleta: se o órgão republicar o painel, a diferença fica documentada em vez de
desaparecer.

O inventário legível do modelo está em [`MODELO.md`](MODELO.md), gerado automaticamente.

## 4. Consulta

O endpoint de dados é `POST /public/reports/querydata?synchronous=true`. O corpo contém um
`SemanticQueryDataShapeCommand`: uma árvore JSON com tabelas (`From`), projeções
(`Select`), filtros (`Where`) e agregação (`Binding`). É exatamente o comando que o
relatório emite quando o usuário aplica um filtro ou expande um nível da matriz — a
diferença é que aqui ele é escrito de forma explícita, versionada e arquivada.

Forma da consulta usada na extração setorial:

- **From** — `Econômico` (dimensão setorial), `TabelaDeDatas` (tempo), `Medidas` (medidas DAX)
- **Select** — `competência`; para cada nível da hierarquia até o nível pedido, o código e
  o nome; e as medidas `Admitidos`, `Desligados`, `Saldo`
- **Where** — `Ano = <ano>` e, quando há recorte setorial, `Grande Grupamento = <setor>`
- **Binding** — agrupamento por todas as projeções, com janela de 60.000 linhas

Projetar o nível pedido **junto de todos os seus níveis pais** é deliberado: elimina a
necessidade de expandir a hierarquia por etapas e deixa a saída reagregável para qualquer
nível sem nova consulta.

### Particionamento por ano

As consultas são emitidas ano a ano, não de uma vez. Isso mantém cada resposta pequena o
bastante para não ser truncada pelo backend, e torna a extração retomável. A partição é
por `Ano` da tabela de datas, portanto não corta nenhuma competência ao meio.

O código verifica explicitamente o indicador de truncamento em cada resposta
(`dsr.truncou`) e aborta se ele aparecer, em vez de gravar um arquivo incompleto.

## 5. Decodificação da resposta (DSR)

A resposta não é uma tabela plana. O Power BI a comprime de três formas combinadas, e
ignorar qualquer uma produz **dados silenciosamente errados** — plausíveis e incorretos.
Este é o ponto mais delicado do pipeline:

1. **Dicionários de valores** (`ValueDicts`). Colunas de texto vêm como índices inteiros;
   o descritor `S` de cada coluna indica em `DN` qual dicionário resolve o índice.
2. **Supressão de repetição** (`R`). Bitmask: bit `i` ligado significa que a coluna `i`
   repete o valor da linha anterior e foi **omitida** do payload.
3. **Nulos** (`Ø`). Bitmask: bit `i` ligado significa coluna nula.

Além disso, o backend alterna entre **duas codificações de linha**, às vezes na mesma
resposta: um array posicional `C` contendo só os valores efetivamente transmitidos, ou uma
chave por coluna (`G0`, `G1`, `M0`, …). O decodificador trata as duas.

A implementação está em `src/dadoscaged/dsr.py` e é coberta por testes de regressão em
`tests/test_dsr.py`, com recortes reais de respostas do painel, incluindo os casos de
repetição em várias colunas simultâneas e de nulo seguido de repetição.

## 6. Validação

Implementada em `src/dadoscaged/validate.py` e executada automaticamente por
`01_extrair.py` antes de gravar qualquer arquivo.

A conferência **não compara o arquivo com ele mesmo**. Ela emite uma consulta
independente, pedindo o total do setor por competência **no nível agregado**, sem passar
por nenhum dos níveis desagregados, e exige igualdade exata com a soma das linhas
extraídas, medida a medida.

Isso detecta:

| Falha | Como apareceria |
|---|---|
| resposta truncada | faltam linhas → soma menor que o total |
| nível parcialmente expandido | idem |
| erro na máscara de repetição | valores atribuídos à linha errada → soma diverge |
| erro nos dicionários de valores | agrupamento errado → soma por competência diverge |

Se houver qualquer divergência, o script termina com código de saída 1 e **não grava o
CSV**. Um arquivo em `data/processed/` só existe se passou na conferência.

`scripts/02_validar.py` reexecuta a mesma conferência sobre um CSV já existente, a
qualquer momento. Serve para auditar um arquivo recebido de terceiros e para detectar que
o órgão revisou a série desde a coleta.

## 7. Proveniência

Cada CSV gravado recebe um `.manifesto.json` ao lado, contendo:

- data e hora da coleta (UTC);
- URL do painel, cluster, `model_id`, `dataset_id`, `report_id`;
- nome, versão e `LastRefreshTime` do pacote publicado;
- recorte extraído (setor, nível, anos, medidas) e nomes das colunas;
- `sha256` do arquivo gerado;
- resultado da validação (meses conferidos, divergências).

Com `--sem-raw` desligado (padrão), a consulta e a resposta bruta de cada ano são
arquivadas em `data/raw/`, permitindo reconstruir o CSV sem acesso à rede. Esse diretório
não é versionado por padrão (volume); para arquivar uma coleta específica junto ao
trabalho, comente a linha correspondente no `.gitignore`.

---

## Sobre usar o painel em vez dos microdados

O MTE também publica os **microdados** do Novo CAGED pelo PDET
(<http://pdet.mte.gov.br>), com granularidade maior do que qualquer painel — inclusive
variáveis não expostas aqui, como salário e movimentação individual.

Este repositório consulta o painel porque o recorte pedido (agregados setoriais mensais
por CNAE) já está pronto e consolidado nele, com a mesma metodologia de imputação aplicada
pelo órgão. Para trabalhos que precisem de salário, tempo de emprego individual, ou
recortes fora dos que o painel expõe, os microdados são a fonte apropriada — e este
pipeline não os substitui.
