# -*- coding: utf-8 -*-
"""Validação independente da extração.

A conferência não compara o arquivo com ele mesmo: ela pede ao painel o total
agregado do setor, por mês, em uma consulta separada — sem passar pelos níveis
desagregados — e exige igualdade exata com a soma das linhas extraídas.

Se um nível tivesse sido expandido apenas parcialmente, se a resposta tivesse
sido truncada, ou se o decodificador DSR errasse a reconstrução de valores
repetidos, a soma divergiria. É esse o ponto do teste.
"""
import collections

from . import client, config, dsr, query


def totais_do_painel(grande_grupamento="Comércio", medidas=None):
    """Totais mensais do setor, direto no nível agregado."""
    medidas = medidas or list(config.MEDIDAS_PADRAO)
    selects = [query.coluna("t", "competência", "competencia")]
    selects += [query.medida("m", m) for m in medidas]
    where = query.filtro_em("e", "Grande Grupamento", [grande_grupamento]) if grande_grupamento else None
    comando = query.montar(
        [("e", config.TAB_ECONOMICO), ("t", config.TAB_TEMPO), ("m", config.TAB_MEDIDAS)],
        selects, where=where, janela=5000)
    _, linhas = dsr.decodificar(client.executar_consulta(comando))
    return {int(l[0]): [v or 0 for v in l[1:]] for l in linhas}


def somar_extraidas(cabecalho, linhas, medidas=None):
    """Soma as linhas desagregadas por competência."""
    medidas = medidas or list(config.MEDIDAS_PADRAO)
    idx = [cabecalho.index(m.lower()) for m in medidas]
    i_comp = cabecalho.index("competencia")
    acum = collections.defaultdict(lambda: [0] * len(idx))
    for l in linhas:
        alvo = acum[int(l[i_comp])]
        for k, j in enumerate(idx):
            alvo[k] += int(l[j])
    return dict(acum)


def conferir(cabecalho, linhas, grande_grupamento="Comércio", medidas=None):
    """Compara soma desagregada x total do painel.

    Devolve um relatório; `ok` é False se houver qualquer divergência.
    """
    medidas = medidas or list(config.MEDIDAS_PADRAO)
    oficial = totais_do_painel(grande_grupamento, medidas)
    nosso = somar_extraidas(cabecalho, linhas, medidas)

    divergencias = []
    for comp in sorted(set(oficial) | set(nosso)):
        a, b = oficial.get(comp), nosso.get(comp)
        if a is None:
            divergencias.append((comp, "ausente no painel", None, b))
        elif b is None:
            divergencias.append((comp, "ausente na extracao", a, None))
        elif a != b:
            divergencias.append((comp, "valores diferentes", a, b))

    return {
        "medidas": medidas,
        "meses_no_painel": len(oficial),
        "meses_na_extracao": len(nosso),
        "linhas_extraidas": len(linhas),
        "divergencias": divergencias,
        "ok": not divergencias and len(oficial) == len(nosso) and len(oficial) > 0,
    }


def imprimir(rel):
    print("medidas conferidas : %s" % ", ".join(rel["medidas"]))
    print("meses no painel    : %d" % rel["meses_no_painel"])
    print("meses na extracao  : %d" % rel["meses_na_extracao"])
    print("linhas extraidas   : %d" % rel["linhas_extraidas"])
    if rel["divergencias"]:
        print("DIVERGENCIAS       : %d" % len(rel["divergencias"]))
        for comp, motivo, a, b in rel["divergencias"][:25]:
            print("   %s  %-22s painel=%s extracao=%s" % (comp, motivo, a, b))
    else:
        print("divergencias       : 0")
    print("RESULTADO          : %s" % ("OK" if rel["ok"] else "FALHOU"))
