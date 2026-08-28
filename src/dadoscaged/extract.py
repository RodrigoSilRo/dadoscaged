# -*- coding: utf-8 -*-
"""Extração da série setorial do Painel do Novo CAGED.

Estratégia: em vez de reproduzir cliques (aplicar filtro, expandir a matriz
nível a nível), a consulta é escrita diretamente contra o modelo semântico
pedindo, de uma só vez, o nível mais desagregado junto de todos os seus níveis
pais. Isso elimina a possibilidade de um nível ficar parcialmente expandido e
deixa o recorte explícito no código.

As consultas são particionadas por ano. Isso mantém cada resposta pequena o
suficiente para não ser truncada pelo backend e permite retomar a extração sem
refazer tudo.
"""
import json
import os
from datetime import datetime, timezone

from . import client, config, dsr, query


def _colunas_do_nivel(nivel):
    """Níveis a projetar: o nível pedido e todos os seus pais na hierarquia."""
    if nivel not in config.HIERARQUIA_SETORIAL:
        raise ValueError("nivel invalido: %r (use um de %s)"
                         % (nivel, config.HIERARQUIA_SETORIAL))
    return config.HIERARQUIA_SETORIAL[:config.HIERARQUIA_SETORIAL.index(nivel) + 1]


def _rotulo(nome):
    """Nome de coluna de saída: minúsculo, sem espaços nem pontuação."""
    troca = {"á": "a", "ã": "a", "â": "a", "é": "e", "ê": "e", "í": "i",
             "ó": "o", "ô": "o", "õ": "o", "ú": "u", "ç": "c"}
    s = nome.lower().replace("cnae 2.0 ", "").replace("código ", "cod_")
    for k, v in troca.items():
        s = s.replace(k, v)
    return s.replace(" ", "_").replace(".", "")


def montar_projecoes(nivel, medidas):
    """Devolve (projeções para a API, cabeçalho do CSV)."""
    selects = [query.coluna("t", "competência", "competencia")]
    cabecalho = ["competencia", "ano", "mes"]

    for lvl in _colunas_do_nivel(nivel):
        cod = config.CODIGO_DE.get(lvl)
        if cod:
            selects.append(query.coluna("e", cod, _rotulo(cod)))
            cabecalho.append(_rotulo(cod))
        selects.append(query.coluna("e", lvl, _rotulo(lvl)))
        cabecalho.append(_rotulo(lvl))

    for m in medidas:
        selects.append(query.medida("m", m, _rotulo(m)))
        cabecalho.append(_rotulo(m))

    return selects, cabecalho


def extrair(nivel="CNAE 2.0 Subclasse", grande_grupamento="Comércio",
            anos=None, medidas=None, dir_raw=None, verboso=True):
    """Extrai a série mensal para um setor, no nível pedido.

    grande_grupamento=None extrai todos os setores.
    Devolve (cabecalho, linhas). Se dir_raw for informado, arquiva cada resposta
    bruta da API em JSON, para que o resultado possa ser reconstruído sem rede.
    """
    medidas = medidas or list(config.MEDIDAS_PADRAO)
    anos = anos or listar_anos()
    selects, cabecalho = montar_projecoes(nivel, medidas)
    froms = [("e", config.TAB_ECONOMICO), ("t", config.TAB_TEMPO), ("m", config.TAB_MEDIDAS)]
    n_dim = len(cabecalho) - 3 - len(medidas)  # colunas setoriais projetadas

    linhas = []
    for ano in anos:
        where = list(query.filtro_em("t", "Ano", [ano]))
        if grande_grupamento:
            where += query.filtro_em("e", "Grande Grupamento", [grande_grupamento])

        comando = query.montar(froms, selects, where=where)
        resposta = client.executar_consulta(comando)

        if dir_raw:
            os.makedirs(dir_raw, exist_ok=True)
            base = "%s_%s_%s" % (_rotulo(grande_grupamento or "todos"), _rotulo(nivel), ano)
            with open(os.path.join(dir_raw, base + ".consulta.json"), "w", encoding="utf-8") as f:
                json.dump(comando, f, ensure_ascii=False, indent=1)
            with open(os.path.join(dir_raw, base + ".resposta.json"), "w", encoding="utf-8") as f:
                json.dump(resposta, f, ensure_ascii=False)

        if dsr.truncou(resposta):
            raise RuntimeError("resposta truncada em %s — aumente config.JANELA_PADRAO" % ano)

        _, brutas = dsr.decodificar(resposta)
        for r in brutas:
            comp = str(r[0])
            dims = r[1:1 + n_dim]
            vals = [v if v is not None else 0 for v in r[1 + n_dim:]]
            linhas.append([r[0], comp[:4], comp[4:6]] + list(dims) + list(vals))

        if verboso:
            print("  %s: %6d linhas" % (ano, len(brutas)))

    linhas.sort(key=lambda r: (r[0], [str(x) for x in r[3:3 + n_dim]]))
    return cabecalho, linhas


def listar_anos():
    """Anos disponíveis no modelo, em ordem."""
    comando = query.montar([("t", config.TAB_TEMPO)],
                           [query.coluna("t", "Ano", "ano")], janela=1000)
    _, linhas = dsr.decodificar(client.executar_consulta(comando))
    return sorted(str(l[0]) for l in linhas)


def listar_competencias():
    """Competências (AAAAMM) disponíveis, em ordem."""
    comando = query.montar([("t", config.TAB_TEMPO)],
                           [query.coluna("t", "competência", "competencia")], janela=5000)
    _, linhas = dsr.decodificar(client.executar_consulta(comando))
    return sorted(int(l[0]) for l in linhas)


def listar_valores(propriedade, tabela=None, filtro=None):
    """Valores distintos de uma coluna categórica (útil para inspecionar o modelo)."""
    tabela = tabela or config.TAB_ECONOMICO
    comando = query.montar([("e", tabela)],
                           [query.coluna("e", propriedade, "valor")],
                           where=filtro, janela=20000)
    _, linhas = dsr.decodificar(client.executar_consulta(comando))
    return [l[0] for l in linhas]


def carimbo_execucao():
    """Metadados de proveniência do momento da coleta."""
    modelo = client.obter_modelo()
    pacote = modelo.get("package", {})
    return {
        "coletado_em_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "painel_url": config.PAINEL_URL,
        "cluster": config.CLUSTER_HOST,
        "model_id": config.MODEL_ID,
        "dataset_id": config.DATASET_ID,
        "report_id": config.REPORT_ID,
        "pacote_nome": pacote.get("name"),
        "pacote_versao": pacote.get("version"),
        "ultimo_refresh_do_painel": pacote.get("LastRefreshTime"),
    }
