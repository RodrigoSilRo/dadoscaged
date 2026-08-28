# Limitações e ressalvas para uso em pesquisa

Ler antes de usar estes dados em estimação. As quatro primeiras seções são as que
mais afetam trabalho econométrico.

---

## 1. A série é revisada — a data da coleta faz parte do dado

O Novo CAGED incorpora **declarações fora do prazo**. Meses já divulgados são revisados
nas divulgações seguintes: o valor de uma competência passada muda ao longo do tempo.

Isso não é uma preocupação teórica. **Aconteceu durante a própria construção deste
repositório**, em 2026-08-28:

| horário (UTC) | competências | jun/2026 (adm / des / saldo) |
|---|---|---|
| 17:21 | 78, até 202606 | 507.660 / 488.483 / **+19.177** |
| 17:37 | 79, até 202607 | 512.443 / 496.122 / **+16.321** |

O MTE publicou a competência 202607 nos microdados às 14:31 (17:31 UTC) daquele dia — e
no intervalo entre duas extrações separadas por 16 minutos, julho entrou na série e junho
foi revisado em quase 3 mil no saldo.

Consequências práticas:

- dois arquivos coletados em datas diferentes **não são comparáveis linha a linha**, e
  concatená-los produz uma série inconsistente;
- resultados citáveis devem informar a **impressão digital dos dados** (seção 2), que fica
  no `.manifesto.json` de cada arquivo;
- para reproduzir um resultado antigo, use o CSV arquivado, não uma nova extração.

`scripts/02_validar.py` pode ser reexecutado sobre um CSV antigo a qualquer momento: se o
órgão revisou a série, a conferência acusa divergência. É o detector de revisão, não uma
falha do arquivo.

### 1.1 O painel pode servir uma competência antes de anunciá-la

Durante o mesmo episódio, o modelo passou a responder com 202607 completo enquanto a
**capa do painel ainda anunciava "JUNHO DE 2026"**, e o backend alternou entre servir 78 e
79 competências por cerca de 40 minutos. Ao fim da propagação a capa passou a anunciar
julho, coerente com os dados servidos. Ou seja: houve uma janela em que o painel serviu
uma competência que ele próprio ainda não declarava.

Por isso o pipeline compara o mês declarado na capa com a última competência servida e
**avisa** quando a segunda passa da primeira (`scripts/01_extrair.py`). Uma competência
servida mas ainda não anunciada pode ser retirada depois — confirme na divulgação oficial
antes de usar, se ela importa para o seu trabalho.

Coleta atual: **2026-08-28T18:12 UTC**, refresh do painel **2026-08-28T17:32:52**, capa
anunciando **julho de 2026**, última competência **202607**.

## 2. Os metadados de versão ficam defasados durante uma atualização

Os campos `version` e `LastRefreshTime` do pacote **acabam** refletindo a atualização, mas
não de imediato. Sequência observada em 2026-08-28:

| horário (UTC) | série servida | `version` declarada | `LastRefreshTime` declarado |
|---|---|---|---|
| 17:21 | 78 meses, até 202606 | `ID-19810754` | 2026-07-29T18:16:56 |
| 17:31 | *(MTE publica 202607 no FTP)* | | |
| 17:37 | **79 meses, até 202607** | `ID-19810754` | **2026-07-29T18:16:56** |
| 18:12 | 79 meses, até 202607 | `ID-23435724` | 2026-08-28T17:32:52 |

Por mais de meia hora o painel serviu **dados novos declarando metadados antigos**. Duas
coletas feitas nesse intervalo, com séries diferentes, teriam sido registradas como se
viessem do mesmo estado da fonte.

Por isso o manifesto registra esses campos rotulados como **declarados**, e usa como
identificador de versão a **impressão digital dos dados**: a lista de competências e os
totais agregados de cada uma, resumidos em um `sha256`. Ela é calculada sobre as linhas
efetivamente gravadas, então descreve o arquivo mesmo quando a fonte está instável. Duas
coletas com a mesma impressão digital viram a mesma série.

### 2.1 O backend serve versões diferentes em requisições consecutivas

Durante a propagação de uma atualização, requisições emitidas com segundos de diferença,
do mesmo processo, voltaram de réplicas em estados distintos — uma com a competência mais
recente, outra sem. Observado no dia da coleta.

O pipeline lida com isso em três camadas, e importa saber qual delas é o portão:

1. **Amostragem inicial** (`extract.conferir_replicas`): a impressão digital é pedida
   quatro vezes antes de começar. Se discordarem, a extração avisa que há atualização em
   propagação — mas não aborta, porque a amostragem é probabilística: "todas iguais" não
   prova estabilidade.
2. **Identidade calculada sobre o arquivo** (`extract.digital_dos_dados`): a impressão
   digital gravada no manifesto vem das **linhas extraídas**, não de uma consulta extra.
   Assim ela descreve sempre o que está no disco. O manifesto registra se ela coincidiu
   com a amostra inicial — e, na coleta atual, ela **não** coincidiu.
3. **A validação é o portão duro.** Cada mês do arquivo é conferido contra consultas novas
   ao painel, com igualdade exata. Um arquivo que misturasse versões falharia ali, porque
   os totais não fechariam.

As versões observadas diferiam **apenas nas competências mais recentes**, e a extração é
particionada por ano — logo os meses que distinguem as versões vêm todos de uma única
requisição, o que impede que o arquivo fique internamente incoerente neles.

## 3. Quebra estrutural declarada pelo órgão em outubro de 2021

Nota metodológica do próprio painel (página "O que é o Novo Caged?"):

> A partir da divulgação da competência de outubro de 2021 a metodologia de consolidação
> das informações dos três sistemas foi atualizada para captar um maior número de
> movimentações aperfeiçoando a divulgação das estatísticas do mercado de trabalho formal.

Uma mudança que "capta um maior número de movimentações" desloca o nível da série. Em
séries temporais que cruzem essa data, é uma **quebra estrutural conhecida e datada** —
trate-a explicitamente (dummy, teste de quebra, ou amostra restrita a um regime) em vez de
assumir série homogênea de 2020 a 2026.

## 4. O primeiro valor publicado pode ter o sinal oposto do valor final

Consequência da seção 1 que merece destaque próprio, porque inverte conclusões.

Reconstruindo março de 2022 (Comércio) a partir dos microdados oficiais — o que
`scripts/04_conferir_microdados.py` faz e documenta:

| | admitidos | desligados | **saldo** |
|---|---|---|---|
| `MOV202203`, dentro do prazo (como publicado à época) | 435.190 | 434.723 | **+467** |
| + declarações de 202204 | 439.924 | 449.893 | −9.969 |
| + declarações até 202212 | 443.519 | 452.413 | −8.894 |
| painel hoje | 443.875 | 452.625 | **−8.750** |

O saldo de março de 2022 no Comércio foi ao ar **positivo (+467)** e hoje é
**negativo (−8.750)**. A virada vem quase toda de um único arquivo: `FOR202204` trouxe
15.421 desligamentos declarados fora do prazo contra 4.877 admissões.

Se o seu desenho de pesquisa depende do que os agentes observavam no momento
(expectativas, resposta a divulgação, avaliação de política em tempo real), **a série
revisada é a fonte errada** — e o painel só oferece a revisada. Nesse caso use os
microdados, que permitem reconstruir a safra de cada mês.

---

## 5. Cobertura: só emprego formal celetista

O CAGED cobre movimentações de vínculos **celetistas**. Ficam de fora servidores
estatutários, autônomos, informais, PJ e trabalho por conta própria. Não é medida de
emprego total nem de desemprego — para isso, PNAD Contínua.

## 6. A série depende de imputação

> Embora a maior parte das empresas esteja obrigada a declarar o eSocial, muitas deixaram
> de prestar informações de desligamentos a este sistema. Para viabilizar a divulgação das
> estatísticas do emprego formal durante esse período de transição, foi feita a imputação
> de dados de outras fontes.

O Novo CAGED consolida **eSocial, CAGED e Empregador Web** com imputação para declarações
faltantes, principalmente de desligamentos, com maior peso no período de transição a
partir de 2020. Metodologia completa em <http://pdet.mte.gov.br/o-que-e-novo-caged>.

## 7. Setor é o da empresa, não do posto

A classificação CNAE é do **estabelecimento empregador**, não da função exercida. Um
programador contratado por uma rede varejista entra em Comércio. Para recorte por natureza
da ocupação, cruze com a dimensão ocupacional (CBO), disponível no modelo.

## 8. Medidas compostas não são somáveis

`Tempo de Emprego (Desligados)` e `Vr. Relativa` são média e razão calculadas em DAX.
Somá-las entre subclasses não produz o valor do agregado. Para reagregar, recalcule a
partir das contagens. Ver [`DICIONARIO.md`](DICIONARIO.md).

## 9. `Estoque Mensal` tem resíduo da fonte no nível de subclasse

Verificado nas 79 competências: `Estoque Mensal` soma **exatamente** igual ao agregado nos
níveis de Divisão, Grupo e **Classe**. Só no nível de **Subclasse** a soma excede o
agregado, e apenas nos anos iniciais:

| competência | desvio |
|---|---|
| 2020-06 | +0,167% (máximo) |
| 2022-01 | +0,001% |
| 2023-01 em diante | 0,000% (exato) |

O desvio se concentra em quatro classes CNAE e desaparece a partir de 2023 — período em
que a atribuição de subclasse na base de estoque ainda estava em consolidação. **É desvio
da fonte, não da extração**: a validação exige exatidão no nível pai e mede o resíduo do
nível extraído, em vez de tolerá-lo em silêncio.

Se você precisa de estoque, use **Classe ou acima**, ou restrinja a 2023+.

## 10. Ausência de linha ≠ zero

Combinações competência × subclasse sem movimentação nem estoque não aparecem no arquivo.
Ver [`DICIONARIO.md`](DICIONARIO.md).

## 11. Nome de subclasse não é chave

Um nome de subclasse aparece com dois códigos distintos sob Comércio. Agrupe por
`cod_subclasse`.

## 12. Os microdados do FTP são a fonte mais completa

O MTE publica os registros individuais em
`ftp://ftp.mtps.gov.br/pdet/microdados/NOVO CAGED/`, por competência de declaração, em
três arquivos por mês: `MOV` (dentro do prazo), `FOR` (fora do prazo) e `EXC` (exclusões).

**São os mesmos dados**: `scripts/04_conferir_microdados.py` reconstrói uma competência a
partir deles e chega ao valor do painel — 95,9% da revisão de admissões e 98,8% da de
desligamentos de março/2022 são explicados somando apenas nove meses de declarações
posteriores; o restante vem de declarações de 2023 a 2026.

O microdado tem **20 variáveis que o painel não expõe**, entre elas `salário`,
`valorsaláriofixo`, `horascontratuais`, `idade` (exata, não faixa), `raçacor`,
`tipomovimentação`, `tipoempregador`, `tamestabjan`, `município`, `uf`, e — decisivo para
a seção 4 — `competênciadec` e `indicadordeforadoprazo`, que permitem reconstruir a safra
de qualquer mês.

O painel tem **8 campos que o microdado não identificado não traz**: as medidas prontas
`Admitidos`/`Desligados`/`Saldo`, `faixaetária`, `nacionalidade`, `indestrangeiro`,
`indtrabtemp` e `tempoemprego`. E, sobretudo, **`Estoque Mensal`** — a pasta NOVO CAGED
contém apenas movimentações; estoque exige RAIS mais acumulação.

Use este repositório quando quiser agregados setoriais mensais prontos, conferidos e com
proveniência. Use os microdados quando precisar de salário, de cruzamentos livres, ou de
controle de safra. Custo: ~55 MB comprimidos por mês, e reconstruir a série completa exige
`MOV` mais todos os `FOR`/`EXC` posteriores.

## 13. Dados sem ajuste sazonal

As séries são brutas. Comércio tem sazonalidade forte e regular (contratações de fim de
ano, desligamentos em janeiro). Comparações mês contra mês sem dessazonalização, ou sem
comparar contra o mesmo mês do ano anterior, confundem sazonalidade com tendência.

## 14. "Não Identificado" é uma categoria real

`Grande Grupamento` inclui o valor **"Não Identificado"**, com movimentações cujo setor
não pôde ser classificado. Extrações com `--setor todos` o incluem. É massa de
movimentações que existe e some das somas setoriais se ignorada. Documente o tratamento.

## 15. Estabilidade da fonte

O pipeline depende de um endpoint de API não documentado publicamente pela Microsoft e da
decisão do MTE de manter o painel publicado na web. Ambos podem mudar sem aviso. Por isso:

- as respostas brutas ficam arquiváveis em `data/raw/`;
- os CSVs gerados e seus manifestos são o registro durável do trabalho;
- para arquivamento de longo prazo junto a uma publicação, versione o `data/raw/` da
  coleta usada — ou, melhor, os microdados do FTP correspondentes.
