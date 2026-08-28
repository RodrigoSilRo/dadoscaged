# -*- coding: utf-8 -*-
"""Construção das consultas semânticas enviadas ao modelo.

O Power BI aceita um "SemanticQueryDataShapeCommand": uma árvore JSON que
descreve tabelas (From), projeções (Select), filtros (Where) e agregação
(Binding). É o mesmo comando que o relatório emite quando o usuário aplica um
filtro ou expande um nível da matriz na interface — aqui ele é escrito
explicitamente, o que torna cada número rastreável até a consulta que o gerou.
"""

from . import config


def fonte(alias, tabela):
    return {"Name": alias, "Entity": tabela, "Type": 0}


def coluna(alias, propriedade, nome=None):
    """Projeta uma coluna (dimensão) — vira chave de agrupamento."""
    return {"Column": {"Expression": {"SourceRef": {"Source": alias}},
                       "Property": propriedade},
            "Name": nome or "%s.%s" % (alias, propriedade)}


def medida(alias, propriedade, nome=None):
    """Projeta uma medida DAX — agregada segundo as colunas projetadas."""
    return {"Measure": {"Expression": {"SourceRef": {"Source": alias}},
                        "Property": propriedade},
            "Name": nome or "%s.%s" % (alias, propriedade)}


def filtro_em(alias, propriedade, valores):
    """Filtro categórico equivalente a `WHERE coluna IN (...)`."""
    return [{"Condition": {"In": {
        "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}},
                                    "Property": propriedade}}],
        "Values": [[{"Literal": {"Value": "'%s'" % str(v).replace("'", "''")}}]
                   for v in valores]}}}]


def montar(froms, selects, where=None, janela=config.JANELA_PADRAO):
    """Monta o comando completo.

    froms   : lista de (alias, tabela)
    selects : lista de projeções (coluna/medida), na ordem das colunas de saída
    where   : lista de condições, combinadas com AND pelo backend
    janela  : teto de linhas devolvidas (DataReduction)
    """
    consulta = {"Version": 2,
                "From": [fonte(a, t) for a, t in froms],
                "Select": selects}
    if where:
        consulta["Where"] = where
    return {"SemanticQueryDataShapeCommand": {
        "Query": consulta,
        "Binding": {
            "Primary": {"Groupings": [{"Projections": list(range(len(selects)))}]},
            "DataReduction": {"DataVolume": 4, "Primary": {"Window": {"Count": janela}}},
            "Version": 1,
        },
        "ExecutionMetricsKind": 1,
    }}
