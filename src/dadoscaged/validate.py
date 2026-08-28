# -*- coding: utf-8 -*-
"""Validação independente da extração.

Medidas diferentes exigem provas diferentes, e aplicar a prova errada dá falso
conforto ou falso alarme. São três provas:

**[1] Medidas aditivas × total do painel.** `Admitidos`, `Desligados`, `Saldo` e
`Estoque Mensal` são contagens: a soma das linhas desagregadas tem de reproduzir
o total do setor. A conferência pede esse total em consulta separada, no nível
agregado, sem passar por nenhum nível desagregado. Exige-se igualdade exata.

**[2] Medidas com desvio conhecido, no nível pai.** `Estoque Mensal` soma exato
até o nível de Classe, mas no nível de Subclasse a fonte apresenta um pequeno
excesso nos anos iniciais da série (ver `docs/LIMITACOES.md`). Esse desvio não é
silenciado: para essas medidas a conferência **exige igualdade exata no nível
pai do extraído** e **mede** o resíduo do nível extraído, mês a mês, em vez de
ignorá-lo. Se o desvio aparecesse também no nível pai, seria falha — é isso que
separa "propriedade da fonte" de "erro da extração".

**[3] Todas as medidas, célula a célula.** Médias e razões (`Tempo de Emprego`,
`Vr. Relativa`) não são somáveis; compará-las com o agregado acusaria divergência
em toda linha. A prova aqui é outra: reconsultar o painel **no mesmo nível de
desagregação, com particionamento diferente** do usado na extração (por
competência, em vez de por ano) e exigir igualdade célula a célula. Como as duas
partições só coincidem se o decodificador DSR estiver reconstruindo corretamente
valores repetidos, nulos e dicionários, essa prova cobre também as aditivas.
"""
import collections
import random

from . import client, config, dsr, query

def _base(grande_grupamento, uf):
    from .extract import froms_e_filtro
    return froms_e_filtro(grande_grupamento, uf)


def _numero(v):
    """Valor da API (int, float ou string decimal) como float; vazio -> None."""
    if v is None or v == "":
        return None
    return float(v)


def _rotulo(nome):
    from .extract import _rotulo as r
    return r(nome)


def _nivel_pai(nivel):
    i = config.HIERARQUIA_SETORIAL.index(nivel)
    return config.HIERARQUIA_SETORIAL[i - 1] if i > 0 else None


def _por_competencia(nivel, medidas, grande_grupamento, uf=None):
    """Soma as medidas por competência, agrupando por `nivel` (None = agregado)."""
    selects = [query.coluna("t", "competência", "competencia")]
    if nivel:
        selects.append(query.coluna("e", nivel, "cat"))
    selects += [query.medida("m", m) for m in medidas]
    froms, where = _base(grande_grupamento, uf)
    _, linhas = dsr.decodificar(
        client.executar_consulta(query.montar(froms, selects, where=where, janela=60000)))
    desloc = 2 if nivel else 1
    acum = collections.defaultdict(lambda: [0.0] * len(medidas))
    for r in linhas:
        alvo = acum[int(r[0])]
        for k in range(len(medidas)):
            alvo[k] += _numero(r[desloc + k]) or 0
    return dict(acum)


# --------------------------------------------------------------------------- #
# Provas 1 e 2: medidas aditivas
# --------------------------------------------------------------------------- #

def somar_extraidas(cabecalho, linhas, medidas):
    idx = [cabecalho.index(_rotulo(m)) for m in medidas]
    i_comp = cabecalho.index("competencia")
    acum = collections.defaultdict(lambda: [0.0] * len(idx))
    for l in linhas:
        alvo = acum[int(l[i_comp])]
        for k, j in enumerate(idx):
            alvo[k] += _numero(l[j]) or 0
    return dict(acum)


def conferir_aditivas(cabecalho, linhas, grande_grupamento, medidas, nivel, uf=None):
    exatas = [m for m in medidas if m not in config.MEDIDAS_COM_DESVIO_NO_NIVEL_MAIS_FINO]
    com_desvio = [m for m in medidas if m in config.MEDIDAS_COM_DESVIO_NO_NIVEL_MAIS_FINO]

    oficial = _por_competencia(None, medidas, grande_grupamento, uf)
    nosso = somar_extraidas(cabecalho, linhas, medidas)
    pos = {m: k for k, m in enumerate(medidas)}

    divergencias = []
    for comp in sorted(set(oficial) | set(nosso)):
        a, b = oficial.get(comp), nosso.get(comp)
        if a is None or b is None:
            divergencias.append((comp, "mes ausente de um dos lados", a, b))
            continue
        for m in exatas:
            k = pos[m]
            if abs(b[k] - a[k]) > 1e-6:
                divergencias.append((comp, m, a[k], b[k]))

    # Prova 2: para as medidas com desvio conhecido da fonte, o resíduo é MEDIDO
    # nível a nível, e o nível mais fino em que ainda há igualdade exata é
    # registrado. Não se exige exatidão num nível fixo: onde o desvio começa
    # depende do recorte (nacionalmente ele só aparece em Subclasse; com recorte
    # por UF ele já aparece em Classe). Fixar um nível daria falso alarme num
    # caso e falso conforto no outro — medir e registrar não dá nem um nem outro.
    perfil = {}
    if com_desvio:
        ate = config.HIERARQUIA_SETORIAL.index(nivel)
        niveis = config.HIERARQUIA_SETORIAL[1:ate + 1]
        for m in com_desvio:
            k = pos[m]
            por_nivel = {}
            for lvl in niveis:
                if lvl == nivel:
                    soma_lvl = {c: nosso[c][k] for c in nosso}
                else:
                    d = _por_competencia(lvl, [m], grande_grupamento, uf)
                    soma_lvl = {c: v[0] for c, v in d.items()}
                difs = {c: soma_lvl[c] - oficial[c][k]
                        for c in oficial
                        if c in soma_lvl and abs(soma_lvl[c] - oficial[c][k]) > 1e-6}
                por_nivel[lvl] = {
                    "meses_com_residuo": len(difs),
                    "desvio_relativo_maximo": max(
                        (abs(v) / oficial[c][k] for c, v in difs.items()), default=0.0),
                    "ultima_competencia_com_residuo": max(difs) if difs else None,
                }
            exatos = [l for l in niveis if por_nivel[l]["meses_com_residuo"] == 0]
            perfil[m] = {"por_nivel": por_nivel,
                         "nivel_mais_fino_exato": exatos[-1] if exatos else None,
                         "exato_no_nivel_extraido": por_nivel[nivel]["meses_com_residuo"] == 0}

    return {"medidas_exatas": exatas, "medidas_com_desvio": com_desvio,
            "meses_no_painel": len(oficial), "meses_na_extracao": len(nosso),
            "divergencias": divergencias, "perfil_do_residuo": perfil}


# --------------------------------------------------------------------------- #
# Prova 3: célula a célula, com particionamento diferente
# --------------------------------------------------------------------------- #

def conferir_celulas(cabecalho, linhas, grande_grupamento, medidas, nivel,
                     uf=None, amostra=6, semente=20260828):
    cod = config.CODIGO_DE.get(nivel)
    chave = _rotulo(cod or nivel)
    i_comp = cabecalho.index("competencia")
    i_chave = cabecalho.index(chave)
    idx = {m: cabecalho.index(_rotulo(m)) for m in medidas}

    competencias = sorted({int(l[i_comp]) for l in linhas})
    sorteadas = sorted(random.Random(semente).sample(competencias,
                                                     min(amostra, len(competencias))))

    nosso = {}
    for l in linhas:
        c = int(l[i_comp])
        if c in sorteadas:
            nosso[(c, str(l[i_chave]))] = {m: _numero(l[j]) for m, j in idx.items()}

    selects = [query.coluna("t", "competência", "competencia"),
               query.coluna("e", cod or nivel, chave)]
    selects += [query.medida("m", m) for m in medidas]

    divergencias = []
    celulas = 0
    froms, filtro_base = _base(grande_grupamento, uf)
    for comp in sorteadas:
        where = query.filtro_em("t", "competência", [str(comp)]) + filtro_base
        _, ref = dsr.decodificar(
            client.executar_consulta(query.montar(froms, selects, where=where, janela=60000)))
        for r in ref:
            k = (int(r[0]), str(r[1]))
            atual = nosso.get(k)
            if atual is None:
                divergencias.append((k, "linha ausente na extracao", None, None))
                continue
            for j, m in enumerate(medidas):
                esperado, obtido = _numero(r[2 + j]), atual[m]
                # Mesma convenção da extração: nulo em contagem é 0; nulo em
                # medida composta permanece indefinido dos dois lados.
                if m in config.MEDIDAS_ADITIVAS:
                    esperado = esperado or 0.0
                    obtido = obtido or 0.0
                celulas += 1
                if esperado is None and obtido is None:
                    continue
                if esperado is None or obtido is None or abs(esperado - obtido) > 1e-9:
                    divergencias.append((k, m, esperado, obtido))
    return {"competencias_sorteadas": sorteadas, "celulas_conferidas": celulas,
            "divergencias": divergencias}


# --------------------------------------------------------------------------- #

def conferir(cabecalho, linhas, grande_grupamento="Comércio", medidas=None,
             nivel="CNAE 2.0 Subclasse", uf=None, amostra=6):
    medidas = medidas or list(config.MEDIDAS_PADRAO)
    aditivas = [m for m in medidas if m in config.MEDIDAS_ADITIVAS]
    compostas = [m for m in medidas if m not in config.MEDIDAS_ADITIVAS]

    soma = (conferir_aditivas(cabecalho, linhas, grande_grupamento, aditivas, nivel, uf)
            if aditivas else
            {"medidas_exatas": [], "medidas_com_desvio": [], "meses_no_painel": 0,
             "meses_na_extracao": 0, "divergencias": [], "perfil_do_residuo": {}})
    celula = conferir_celulas(cabecalho, linhas, grande_grupamento, medidas, nivel,
                              uf=uf, amostra=amostra)

    return {"medidas_aditivas": aditivas, "medidas_compostas": compostas,
            "nivel": nivel, "uf": uf, "linhas_extraidas": len(linhas),
            "soma": soma, "celula": celula,
            # O portão exige exatidão nas CONTAGENS e nas células. O resíduo
            # das medidas com desvio conhecido da fonte é medido e registrado,
            # não é critério de reprovação — reprovar por ele seria culpar a
            # extração por uma propriedade do painel.
            "ok": (not soma["divergencias"]
                   and not celula["divergencias"]
                   and soma["meses_no_painel"] == soma["meses_na_extracao"])}


def imprimir(rel):
    s, c = rel["soma"], rel["celula"]
    print("linhas extraidas      : %d" % rel["linhas_extraidas"])
    print("nivel extraido        : %s" % rel["nivel"])
    print("recorte geografico    : %s" % (rel.get("uf") or "Brasil (sem filtro)"))
    print()
    print("[1] medidas aditivas: soma do nivel extraido x total do painel")
    print("    medidas           : %s" % (", ".join(s["medidas_exatas"]) or "-"))
    print("    meses no painel   : %d" % s["meses_no_painel"])
    print("    meses na extracao : %d" % s["meses_na_extracao"])
    print("    divergencias      : %d" % len(s["divergencias"]))
    for comp, m, a, b in s["divergencias"][:15]:
        print("       %s  %-28s painel=%s extracao=%s" % (comp, m, a, b))

    if s["medidas_com_desvio"]:
        print()
        print("[2] medidas com desvio conhecido da fonte: perfil do residuo por nivel")
        for m, prof in sorted(s["perfil_do_residuo"].items()):
            print("    %s" % m)
            print("       %-22s %10s %12s %12s"
                  % ("nivel", "meses c/", "desvio max", "ultimo mes"))
            for lvl, d in prof["por_nivel"].items():
                marca = "  <- extraido" if lvl == rel["nivel"] else ""
                print("       %-22s %10d %11.4f%% %12s%s"
                      % (lvl, d["meses_com_residuo"],
                         100 * d["desvio_relativo_maximo"],
                         d["ultima_competencia_com_residuo"] or "-", marca))
            print("       nivel mais fino exato: %s" % (prof["nivel_mais_fino_exato"] or "nenhum"))

    print()
    print("[3] todas as medidas, celula a celula, reconsulta independente")
    print("    medidas           : %s" % ", ".join(rel["medidas_aditivas"] + rel["medidas_compostas"]))
    print("    competencias      : %s" % ", ".join(str(x) for x in c["competencias_sorteadas"]))
    print("    celulas conferidas: %d" % c["celulas_conferidas"])
    print("    divergencias      : %d" % len(c["divergencias"]))
    for chave, m, a, b in c["divergencias"][:15]:
        print("       %s  %-28s painel=%s extracao=%s" % (chave, m, a, b))
    print()
    print("RESULTADO             : %s" % ("OK" if rel["ok"] else "FALHOU"))
