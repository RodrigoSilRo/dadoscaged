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

`k` é a **chave de recurso** do relatório publicado; `t` é o **tenant** do órgão. Em
relatórios publicados com a opção "Publicar na web" do Power BI, a chave de recurso
substitui o token OAuth: vai no cabeçalho `X-PowerBI-ResourceKey` e autoriza consultas
anônimas ao modelo semântico. É o mesmo mecanismo que o navegador de qualquer visitante
usa ao abrir o painel.

## 2. Resolução do backend

A página do relatório declara em seu HTML o cluster regional que o atende — neste caso
`brazil-south`. Um detalhe prático, registrado porque custou tempo:

- `wabi-brazil-south-d-primary-**redirect**.analysis.windows.net` encerra a conexão
  (TCP reset) para clientes que não sejam navegador;
- `wabi-brazil-south-d-primary-**api**.analysis.windows.net` responde normalmente.

O host está fixado em `config.CLUSTER_HOST`. Se o órgão migrar o relatório de região, é o
único valor a mudar — a página do relatório continuará declarando o cluster correto.

## 3. Descoberta do modelo

Dois endpoints são consultados antes de qualquer extração
(`scripts/00_inventario_fonte.py`):

| Endpoint | Conteúdo |
|---|---|
| `GET /public/reports/{k}/modelsAndExploration` | identificadores do modelo, layout das páginas e, em `package`, o nome do `.pbix`, sua versão e o `LastRefreshTime` |
| `POST /public/reports/conceptualschema` | todas as tabelas, colunas e medidas do modelo |

As respostas ficam em `metadata/`. O inventário legível está em [`MODELO.md`](MODELO.md),
gerado automaticamente.

## 4. Consulta

O endpoint de dados é `POST /public/reports/querydata?synchronous=true`. O corpo contém um
`SemanticQueryDataShapeCommand`: uma árvore JSON com tabelas (`From`), projeções
(`Select`), filtros (`Where`) e agregação (`Binding`). É exatamente o comando que o
relatório emite quando o usuário aplica um filtro ou expande um nível da matriz — a
diferença é que aqui ele é escrito de forma explícita, versionada e arquivada.

Forma da consulta usada na extração setorial:

- **From** — `Econômico` (dimensão setorial), `TabelaDeDatas` (tempo), `Medidas`
- **Select** — `competência`; para cada nível da hierarquia até o nível pedido, o código e
  o nome; e as medidas pedidas
- **Where** — `Ano = <ano>` e, quando há recorte setorial, `Grande Grupamento = <setor>`
- **Binding** — agrupamento por todas as projeções, janela de 60.000 linhas

Projetar o nível pedido **junto de todos os seus níveis pais** é deliberado: elimina a
necessidade de expandir a hierarquia por etapas e deixa a saída reagregável para qualquer
nível sem nova consulta.

### Particionamento por ano

As consultas são emitidas ano a ano. Isso mantém cada resposta pequena o bastante para não
ser truncada pelo backend e torna a extração retomável. A partição é por `Ano` da tabela
de datas, portanto não corta nenhuma competência ao meio. O código verifica o indicador de
truncamento em cada resposta (`dsr.truncou`) e aborta em vez de gravar arquivo incompleto.

## 5. Decodificação da resposta (DSR)

A resposta não é uma tabela plana. O Power BI a comprime de formas combinadas, e ignorar
qualquer uma produz **dados silenciosamente errados** — plausíveis e incorretos. É o ponto
mais delicado do pipeline:

1. **Dicionários de valores** (`ValueDicts`). Colunas de texto vêm como índices inteiros;
   o descritor `S` de cada coluna indica em `DN` qual dicionário resolve o índice.
2. **Supressão de repetição** (`R`). Bitmask: bit `i` ligado significa que a coluna `i`
   repete o valor da linha anterior e foi **omitida** do payload.
3. **Nulos** (`Ø`). Bitmask: bit `i` ligado significa coluna nula.
4. **Duas codificações de linha**, às vezes na mesma resposta: um array posicional `C` com
   só os valores transmitidos, ou uma chave por coluna (`G0`, `G1`, `M0`, …).

Medidas compostas (médias, razões) voltam como **string decimal de alta precisão**
(`"22.220152413209146"`), não como float — a precisão é preservada até a gravação.

A implementação está em `src/dadoscaged/dsr.py`, coberta por testes de regressão em
`tests/test_dsr.py` com recortes reais de respostas, incluindo repetição em várias colunas
simultâneas e nulo seguido de repetição.

## 6. Comportamento das medidas sob agregação

Verificado empiricamente contra o painel, e determinante para como cada medida é validada:

| Medida | Comportamento | Verificação |
|---|---|---|
| `Admitidos`, `Desligados`, `Saldo` | aditivas | soma bate exato nas 79 competências |
| `Estoque Mensal` | aditiva | exato até Classe (Brasil) ou Grupo (recorte por UF); resíduo ≤0,38% nos níveis abaixo, só nos anos iniciais |
| `Tempo de Emprego (Desligados)` | média | não somável |
| `Vr. Relativa` | razão | não somável; vale `saldo / (estoque − saldo)` em todas as linhas |

## 7. Validação

Em `src/dadoscaged/validate.py`, executada por `01_extrair.py` antes de gravar. São três
provas, porque aplicar a prova errada a uma medida dá falso conforto ou falso alarme.

**[1] Aditivas × total agregado.** A soma das linhas desagregadas é comparada com o total
do setor obtido em consulta separada, no nível agregado, sem passar por nenhum nível
desagregado. Igualdade exata.

**[2] Perfil do resíduo, para medidas com desvio conhecido da fonte.** `Estoque Mensal`
não soma exato nos níveis mais finos, e **o nível em que isso começa depende do recorte**:
nacionalmente é exato até Classe; com recorte por UF, só até Grupo. Em vez de exigir
exatidão num nível fixo — o que daria falso alarme num caso e falso conforto no outro — a
conferência **mede** o resíduo em cada nível da hierarquia até o extraído, registra o nível
mais fino ainda exato, e grava o perfil no manifesto. O resíduo não reprova a extração:
reprovar por ele seria culpar o pipeline por uma propriedade do painel.

**[3] Célula a célula, com particionamento diferente.** Competências sorteadas (semente
fixa) são reconsultadas **no mesmo nível de desagregação, particionando por competência
em vez de por ano**, e comparadas célula a célula, em todas as medidas. Como as duas
partições só coincidem se o decodificador estiver reconstruindo corretamente repetições,
nulos e dicionários, essa prova cobre também as compostas, que não podem ser somadas.

O que cada prova detecta:

| Falha | Como aparece |
|---|---|
| resposta truncada | faltam linhas → soma menor que o total |
| nível parcialmente expandido | idem |
| erro na máscara de repetição | valores na linha errada → soma e células divergem |
| erro nos dicionários | agrupamento errado → soma por competência diverge |
| medida composta mal lida | prova [3] acusa, prova [1] não teria como |

Qualquer divergência: saída com código 1 e **nenhum arquivo gravado**.
`scripts/02_validar.py` reexecuta a mesma conferência sobre um CSV existente, a qualquer
momento.

## 8. Proveniência e identidade da versão

O painel pode ser republicado a qualquer momento, e **os metadados do pacote demoram a
acompanhar a mudança**: foram observadas duas coletas com séries diferentes reportando o
mesmo `version` e o mesmo `LastRefreshTime`, defasagem que durou mais de meia hora antes
de os campos se atualizarem (ver [`LIMITACOES.md`](LIMITACOES.md), seções 1 e 2). Usá-los
como identificador de versão, em qualquer momento dado, seria uma falsa garantia.

A identidade da versão é derivada dos próprios dados — `extract.impressao_digital()`: a
lista de competências e os totais agregados de cada uma, resumidos em um `sha256`. Duas
coletas com a mesma impressão digital viram a mesma série.

A impressão digital gravada no manifesto é calculada **sobre as linhas extraídas**
(`extract.digital_dos_dados`), não por uma consulta extra: durante uma atualização em
propagação, requisições consecutivas podem vir de réplicas diferentes, e uma consulta a
mais registraria uma identidade que não é a do arquivo.

`01_extrair.py` também amostra a fonte quatro vezes antes de começar
(`extract.conferir_replicas`) e avisa se as amostras discordarem. Esse aviso não é o
portão — o portão é a validação da seção 7, que confere cada mês contra consultas novas
com igualdade exata. Ver [`LIMITACOES.md`](LIMITACOES.md), seção 2.1.

O script também compara o **mês declarado na capa** do painel com a última competência
servida, e avisa quando a segunda passa da primeira — situação observada na prática, de
dados carregados antes da divulgação oficial.

Cada CSV recebe um `.manifesto.json` com: data/hora da coleta (UTC); URL, cluster e
identificadores do modelo; nome, versão e `LastRefreshTime` declarados (rotulados como não
confiáveis); a impressão digital dos dados; o recorte extraído; o `sha256` do arquivo; e o
resultado completo das três provas de validação.

Com `--sem-raw` desligado (padrão), a consulta e a resposta bruta de cada ano são
arquivadas em `data/raw/`, permitindo reconstruir o CSV sem acesso à rede.

## 9. Conferência contra os microdados oficiais

A validação mais forte não compara o painel consigo mesmo: reconstrói uma competência a
partir dos registros individuais publicados pelo MTE. É o que faz
`scripts/04_conferir_microdados.py` (opcional, requer `py7zr`).

Os microdados ficam em `ftp://ftp.mtps.gov.br/pdet/microdados/NOVO CAGED/`, organizados
por **competência de declaração**, três arquivos por mês: `MOV` (dentro do prazo), `FOR`
(fora do prazo) e `EXC` (exclusões). O painel organiza por **competência de movimentação**.
Logo, um mês do painel é:

```
MOV_m  +  Σ_{d > m} (FOR_d − EXC_d)  restritos a compmov = m
```

Resultado para março/2022, Comércio (seção G da CNAE): partindo de `MOV202203`
(saldo +467) e somando nove meses de declarações posteriores chega-se a −8.894, contra
−8.750 do painel — **95,9% da revisão de admissões e 98,8% da de desligamentos**
explicados; o restante vem de declarações de 2023 a 2026. Confirma que o painel é
agregação exata desses microdados.

## 10. Sobre usar o painel em vez dos microdados

O painel entrega agregados setoriais mensais prontos e consolidados, com a metodologia de
imputação já aplicada pelo órgão. Os microdados têm 20 variáveis a mais — inclusive
salário, idade exata, raça/cor e, decisivo, `competênciadec`, que permite reconstruir a
safra de cada mês. Em contrapartida, a pasta NOVO CAGED não contém estoque.

A comparação completa está em [`LIMITACOES.md`](LIMITACOES.md), seção 12. Para trabalhos
que precisem de salário, de cruzamentos livres ou de dados *as-first-published*, os
microdados são a fonte apropriada e este pipeline não os substitui.

---

## Referências

- Painel e metodologia do Novo CAGED — <http://pdet.mte.gov.br/o-que-e-novo-caged>
- Microdados RAIS e CAGED (página oficial do MTE) — <http://pdet.mte.gov.br>
- `Leia-me.txt`, `Sobre o Novo Caged.pdf` e
  `Comunicado - Grupamento de Atividades Econômicas.pdf`, na raiz da pasta NOVO CAGED do
  FTP — definem os arquivos `MOV`/`FOR`/`EXC` e o agrupamento setorial de divulgação
- O caminho do FTP foi localizado a partir do tutorial "Baixar os Microdados do Novo CAGED
  (pesquisa de salários)", comunidade GestGov —
  <https://gestgov.discourse.group/t/tutorial-baixar-os-microdados-do-novo-caged-pesquisa-de-salarios/34420>
  (material de comunidade, não oficial; a fonte canônica é a página do PDET acima)
