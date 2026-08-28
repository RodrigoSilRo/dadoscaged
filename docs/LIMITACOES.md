# Limitações e ressalvas para uso em pesquisa

Ler antes de usar estes dados em estimação. As três primeiras seções são as que mais
afetam trabalho econométrico.

---

## 1. A série é revisada — a data da coleta faz parte do dado

O Novo CAGED incorpora **declarações fora do prazo**. Meses já divulgados são revisados
nas divulgações seguintes: o valor de uma competência passada muda ao longo do tempo.

Consequência prática:

- dois arquivos coletados em datas diferentes **não são comparáveis linha a linha**, e
  concatená-los produz uma série inconsistente;
- resultados citáveis devem informar a data da coleta e o `LastRefreshTime` do painel —
  ambos estão no `.manifesto.json` de cada arquivo;
- para reproduzir um resultado antigo, use o CSV arquivado, não uma nova extração.

Coleta atual: **2026-08-28**, painel com refresh de **2026-07-29**, última competência
disponível **2026-06**.

`scripts/02_validar.py` pode ser reexecutado a qualquer momento sobre um CSV antigo: se o
órgão tiver revisado a série, a conferência acusa divergência. Isso é o comportamento
desejado — é o detector de revisão, não uma falha do arquivo.

## 2. Quebra estrutural declarada pelo órgão em outubro de 2021

Nota metodológica do próprio painel (página "O que é o Novo Caged?"), reproduzida na
íntegra:

> A partir da divulgação da competência de outubro de 2021 a metodologia de consolidação
> das informações dos três sistemas foi atualizada para captar um maior número de
> movimentações aperfeiçoando a divulgação das estatísticas do mercado de trabalho formal.

Uma mudança que "capta um maior número de movimentações" desloca o nível da série. Em
análise de séries temporais que cruze essa data, isso é uma **quebra estrutural conhecida
e datada** — trate-a explicitamente (dummy, teste de quebra, ou amostra restrita a um dos
regimes) em vez de assumir série homogênea de 2020 a 2026.

## 3. A série depende de imputação

Ainda da nota metodológica do painel:

> Embora a maior parte das empresas esteja obrigada a declarar o eSocial, muitas deixaram
> de prestar informações de desligamentos a este sistema. Para viabilizar a divulgação das
> estatísticas do emprego formal durante esse período de transição, foi feita a imputação
> de dados de outras fontes.

O Novo CAGED consolida três sistemas — **eSocial, CAGED e Empregador Web** — com imputação
para declarações faltantes, principalmente de desligamentos, com maior peso no período de
transição a partir de 2020. Os valores não são, portanto, contagem administrativa pura.
A metodologia completa está em <http://pdet.mte.gov.br/o-que-e-novo-caged>.

---

## 4. Cobertura: só emprego formal celetista

O CAGED cobre movimentações de vínculos **celetistas**. Ficam de fora servidores
estatutários, autônomos, informais, PJ e trabalho por conta própria. Não é medida de
emprego total nem de desemprego — para isso, PNAD Contínua.

## 5. Setor é o da empresa, não do posto

A classificação CNAE é do **estabelecimento empregador**, não da função exercida. Um
programador contratado por uma rede varejista entra em Comércio. Para recorte por natureza
da ocupação, cruze com a dimensão ocupacional (CBO), disponível no modelo.

## 6. Ausência de linha ≠ zero

Combinações competência × subclasse sem movimentação não aparecem no arquivo. Ver
[`DICIONARIO.md`](DICIONARIO.md).

## 7. Nome de subclasse não é chave

Um nome de subclasse aparece com dois códigos distintos sob Comércio. Agrupe por
`cod_subclasse`.

## 8. "Não Identificado" é uma categoria real

`Grande Grupamento` inclui o valor **"Não Identificado"**, com movimentações cujo setor
não pôde ser classificado. Extrações com `--setor todos` o incluem. Ele não é ruído a
descartar sem critério: é massa de movimentações que existe e some das somas setoriais se
ignorada. Documente o tratamento.

## 9. Dados sem ajuste sazonal

As séries são brutas. Comércio tem sazonalidade forte e regular (contratações de fim de
ano, desligamentos em janeiro). Comparações mês contra mês sem dessazonalização, ou sem
comparar contra o mesmo mês do ano anterior, tendem a confundir sazonalidade com
tendência.

## 10. Valores nominais e o que não está aqui

Esta extração traz apenas contagens (`admitidos`, `desligados`, `saldo`). Não há salário.
Análises de rendimento exigem os microdados do PDET e deflacionamento explícito.

## 11. Estabilidade da fonte

O pipeline depende de um endpoint de API não documentado publicamente pela Microsoft e da
decisão do MTE de manter o painel publicado na web. Ambos podem mudar sem aviso. Por isso:

- as respostas brutas ficam arquiváveis em `data/raw/`;
- os CSVs gerados e seus manifestos são o registro durável do trabalho;
- para arquivamento de longo prazo junto a uma publicação, versione o `data/raw/` da
  coleta usada.
