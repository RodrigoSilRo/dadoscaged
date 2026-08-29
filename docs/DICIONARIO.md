# Dicionário de variáveis

Referente aos arquivos em `data/processed/` e a qualquer saída de `scripts/01_extrair.py`.

O nome do arquivo codifica o recorte: `caged_<setor>_<uf>_<nivel>_mensal.csv`. Há quatro
publicados — Comércio (`caged_comercio_br_subclasse_mensal.csv`,
`caged_comercio_sc_subclasse_mensal.csv`) e Serviços
(`caged_servicos_br_subclasse_mensal.csv`, `caged_servicos_sc_subclasse_mensal.csv`),
cada um em Brasil e Santa Catarina. As colunas de hierarquia
presentes variam com o `--nivel` pedido: o arquivo sempre traz o nível escolhido e todos
os seus níveis pais. O recorte geográfico não vira coluna — ele está no nome do arquivo e
no campo `uf` do manifesto.

**Formato:** CSV, separador `;`, codificação UTF-8 com BOM, sem aspas. Os decimais usam
**ponto**, não vírgula — é o formato de intercâmbio que pandas, R e Stata leem sem
configuração. Para Excel em português, use o `.xlsx` gerado por
`scripts/03_exportar_excel.py`, que traz células numéricas de verdade.

## Tempo

| Coluna | Tipo | Descrição |
|---|---|---|
| `competencia` | inteiro `AAAAMM` | Competência da movimentação. Ex.: `202606` = junho/2026. Chave temporal da série. |
| `ano` | texto `AAAA` | Ano da competência. Derivado de `competencia`. |
| `mes` | texto `MM` | Mês da competência, com zero à esquerda. Derivado de `competencia`. |

> A competência é a **da movimentação**, não a da declaração — critério usado pelo próprio
> painel nos gráficos "por Competência da Movimentação". Os microdados do FTP são
> organizados pelo outro critério; ver [`LIMITACOES.md`](LIMITACOES.md), seção 12.

## Hierarquia setorial (CNAE 2.0)

Do mais agregado ao mais desagregado. Os códigos são **identificadores, não números** —
leia-os sempre como texto, sob risco de perder zeros à esquerda.

| Coluna | Descrição | Cardinalidade sob Comércio | Cardinalidade sob Serviços |
|---|---|---|---|
| `cod_grande_grupamento` / `grande_grupamento` | Agrupamento de divulgação do MTE: Agropecuária, Indústria, Construção, Comércio, Serviços, Não Identificado | 1 | 1 |
| `grupamento` | Grupamento intermediário de divulgação (sem coluna de código no modelo) | 1 | 1 |
| `cod_secao` / `secao` | Seção CNAE 2.0 (letra) — Comércio corresponde exatamente à seção `G`; Serviços agrupa 14 seções (`H` a `U`) | 1 | 14 |
| `cod_divisao` / `divisao` | Divisão CNAE 2.0 (2 dígitos) | 3 | 44 |
| `cod_grupo` / `grupo` | Grupo CNAE 2.0 (3 dígitos) | 21 | 121 no Brasil / 116 em SC |
| `cod_classe` / `classe` | Classe CNAE 2.0 (5 dígitos) | 94 | 231 no Brasil / 222 em SC |
| `cod_subclasse` / `subclasse` | Subclasse CNAE 2.0 (7 dígitos) — menor nível disponível | 231 no Brasil / 226 em SC | 460 no Brasil / 425 em SC |

> **Use o código como chave, nunca o nome.** Sob Comércio há um nome de subclasse
> associado a dois códigos distintos ("Comércio varejista especializado de equipamentos e
> suprimentos de informática"). Agrupar por nome funde as duas.

## Medidas

A distinção abaixo é a mais importante deste documento: ela determina o que pode ser
somado. O pipeline a usa para escolher como validar cada medida.

### Aditivas (contagens) — somáveis entre categorias

| Coluna | Descrição |
|---|---|
| `admitidos` | Admissões na competência |
| `desligados` | Desligamentos na competência |
| `saldo` | `admitidos − desligados` (saldo de empregos formais) |
| `estoque_mensal` | Estoque de vínculos ativos ao fim da competência |

Verificado na coleta atual: `saldo = admitidos − desligados` vale em **todas** as linhas,
e a soma por competência reproduz exatamente o total do setor no painel.

> `estoque_mensal` é a única com resíduo da fonte nos níveis finos, e **até onde ele é
> exato depende do recorte**: Classe no arquivo nacional, Grupo no de SC. O perfil medido
> nível a nível está em `perfil_do_residuo_da_fonte`, no manifesto do seu arquivo. Ver
> [`LIMITACOES.md`](LIMITACOES.md), seção 9.

### Compostas (médias e razões) — **não** somáveis

| Coluna | Descrição |
|---|---|
| `tempo_de_emprego_desligados` | Tempo médio de emprego, em meses, dos desligados na competência |
| `vr_relativa` | Variação relativa do estoque. Vale a identidade, verificada em todas as linhas: `vr_relativa = saldo / (estoque_mensal − saldo)`, isto é, saldo sobre o estoque no início da competência. Fração, não percentual: `0,0084` = 0,84% |

Somar essas colunas entre subclasses **não** produz o valor do agregado. Para reagregar a
um nível superior, recalcule a partir das contagens:

```python
# certo
g = df.groupby(["competencia", "cod_divisao"], as_index=False)[
        ["admitidos", "desligados", "saldo", "estoque_mensal"]].sum()
g["vr_relativa"] = g["saldo"] / (g["estoque_mensal"] - g["saldo"])

# errado: g["vr_relativa"] = ... .sum() ou .mean()
```

`tempo_de_emprego_desligados` só pode ser reagregado com média ponderada por
`desligados` — e ainda assim de forma aproximada, por ser média de médias.

### Célula vazia

Vazio em coluna composta significa **indefinido**, não zero: não houve denominador
(nenhum desligamento no mês, por exemplo). O pipeline preserva o vazio de propósito —
escrevê-lo como `0` criaria observações falsas. Contagens ausentes, ao contrário, são
gravadas como `0`, porque ausência de movimentação é genuinamente zero.

### Outras medidas do modelo

Acessíveis via `--medidas`, não incluídas por padrão: `Saldo Acumulado`,
`Taxa de Rotatividade`. Ambas compostas — extraia no nível em que pretende usá-las.

## Dimensões não usadas nesta extração

O modelo permite cruzar o recorte setorial com outras dimensões (ver [`MODELO.md`](MODELO.md)):

- **Geográfico** — região, UF, município, estrato
- **Ocupacional** — CBO: grande grupo, principal subgrupo, subgrupo, família, ocupação
- **Pessoais** — sexo, faixa etária, grau de instrução, nacionalidade
- **Vínculo** — aprendiz, intermitente, temporário, estrangeiro

Salário, idade exata, raça/cor, tipo de movimentação e horas contratuais **não existem no
painel** — só nos microdados do FTP. Ver [`LIMITACOES.md`](LIMITACOES.md), seção 12.

## Linhas ausentes

Uma combinação competência × subclasse sem movimentação nem estoque **não gera linha**.
Para análises que exijam painel balanceado, construa a grade completa e preencha as
ausências — conscientemente, e documentando a escolha: zero nas contagens, vazio nas
compostas.

Comércio — Brasil: 79 × 231 = 18.249 células, contra 18.023 observadas. SC: 79 × 226 =
17.854, contra 17.516.

Serviços — Brasil: 79 × 460 = 36.340 células, contra 35.564 observadas. SC: 79 × 425 =
33.575, contra 31.813.
