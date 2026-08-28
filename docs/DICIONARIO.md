# Dicionário de variáveis

Referente a `data/processed/caged_comercio_subclasse_mensal.csv` e a qualquer saída de
`scripts/01_extrair.py`. As colunas de hierarquia presentes variam com o `--nivel` pedido:
o arquivo sempre traz o nível escolhido e todos os seus níveis pais.

Formato: CSV, separador `;`, codificação UTF-8 com BOM, sem aspas.

## Tempo

| Coluna | Tipo | Descrição |
|---|---|---|
| `competencia` | inteiro `AAAAMM` | Competência da movimentação. Ex.: `202606` = junho/2026. Chave temporal da série. |
| `ano` | texto `AAAA` | Ano da competência. Derivado de `competencia`. |
| `mes` | texto `MM` | Mês da competência, com zero à esquerda. Derivado de `competencia`. |

> A competência é a **da movimentação**, não a da declaração. É o critério usado pelo
> próprio painel nos gráficos "por Competência da Movimentação".

## Hierarquia setorial (CNAE 2.0)

Do mais agregado ao mais desagregado. Os códigos são **identificadores, não números** —
leia-os sempre como texto, sob risco de perder zeros à esquerda.

| Coluna | Descrição | Cardinalidade sob Comércio |
|---|---|---|
| `cod_grande_grupamento` / `grande_grupamento` | Agrupamento de divulgação do MTE: Agropecuária, Indústria, Construção, Comércio, Serviços, Não Identificado | 1 |
| `grupamento` | Grupamento intermediário de divulgação (sem coluna de código no modelo) | 1 |
| `cod_secao` / `secao` | Seção CNAE 2.0 (letra) | 1 |
| `cod_divisao` / `divisao` | Divisão CNAE 2.0 (2 dígitos) | 3 |
| `cod_grupo` / `grupo` | Grupo CNAE 2.0 (3 dígitos) | 21 |
| `cod_classe` / `classe` | Classe CNAE 2.0 (5 dígitos) | 94 |
| `cod_subclasse` / `subclasse` | Subclasse CNAE 2.0 (7 dígitos) — menor nível disponível | 231 códigos / 230 nomes |

> **Use o código como chave, nunca o nome.** Sob Comércio há um nome de subclasse
> associado a dois códigos distintos ("Comércio varejista especializado de equipamentos e
> suprimentos de informática"). Agrupar por nome funde as duas.

## Medidas

Todas são contagens de movimentações no mês, agregadas segundo as colunas de hierarquia
presentes na linha.

| Coluna | Descrição |
|---|---|
| `admitidos` | Admissões na competência |
| `desligados` | Desligamentos na competência |
| `saldo` | `admitidos - desligados` (saldo de empregos formais) |

Verificado na coleta atual: `saldo = admitidos - desligados` vale em todas as 17.675
linhas, e a soma por competência reproduz exatamente o total do setor no painel.

### Outras medidas disponíveis no modelo

Não incluídas na extração padrão, mas acessíveis via `--medidas`:

`Estoque Mensal`, `Saldo Acumulado`, `Taxa de Rotatividade`, `Vr. Relativa`,
`Tempo de Emprego (Desligados)`.

> Cuidado ao pedi-las no nível desagregado: são medidas DAX com lógica própria
> (acumulação, razões, médias). Diferente de contagens, **não são aditivas** — somar
> `Taxa de Rotatividade` ou `Vr. Relativa` entre subclasses não produz o valor do
> agregado, e a validação de `01_extrair.py` corretamente acusará divergência. Extraia
> essas medidas no nível em que pretende usá-las.

## Dimensões não usadas nesta extração

O modelo permite cruzar o recorte setorial com outras dimensões, disponíveis para
extrações futuras (ver [`MODELO.md`](MODELO.md)):

- **Geográfico** — região, UF, município, estrato
- **Ocupacional** — CBO: grande grupo, principal subgrupo, subgrupo, família, ocupação
- **Pessoais** — sexo, faixa etária, grau de instrução, nacionalidade
- **Vínculo** — aprendiz, intermitente, temporário, estrangeiro

## Linhas ausentes

Uma combinação competência × subclasse **sem movimentação não gera linha**; ela não
aparece zerada. Para análises que exijam painel balanceado, construa a grade completa
(78 competências × 231 subclasses = 18.018 células, contra 17.675 observadas) e preencha
as ausências com zero — conscientemente, e documentando a escolha.
