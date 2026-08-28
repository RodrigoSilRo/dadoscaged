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
import hashlib
import json
import os
import re
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
    s = s.replace("(", "").replace(")", "")
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


def froms_e_filtro(grande_grupamento=None, uf=None):
    """Tabelas e condições comuns a toda consulta com recorte setorial/geográfico."""
    froms = [("e", config.TAB_ECONOMICO), ("t", config.TAB_TEMPO), ("m", config.TAB_MEDIDAS)]
    where = []
    if grande_grupamento:
        where += query.filtro_em("e", "Grande Grupamento", [grande_grupamento])
    if uf:
        froms.append(("g", config.TAB_GEOGRAFICO))
        where += query.filtro_em("g", config.COL_UF, [uf])
    return froms, where


def extrair(nivel="CNAE 2.0 Subclasse", grande_grupamento="Comércio", uf=None,
            anos=None, medidas=None, dir_raw=None, verboso=True):
    """Extrai a série mensal para um setor, no nível pedido.

    grande_grupamento=None extrai todos os setores.
    Devolve (cabecalho, linhas). Se dir_raw for informado, arquiva cada resposta
    bruta da API em JSON, para que o resultado possa ser reconstruído sem rede.
    """
    medidas = medidas or list(config.MEDIDAS_PADRAO)
    anos = anos or listar_anos()
    selects, cabecalho = montar_projecoes(nivel, medidas)
    froms, filtro_base = froms_e_filtro(grande_grupamento, uf)
    n_dim = len(cabecalho) - 3 - len(medidas)  # colunas setoriais projetadas

    linhas = []
    for ano in anos:
        where = list(query.filtro_em("t", "Ano", [ano])) + filtro_base

        comando = query.montar(froms, selects, where=where)
        resposta = client.executar_consulta(comando)

        if dir_raw:
            os.makedirs(dir_raw, exist_ok=True)
            base = "%s_%s_%s_%s" % (_rotulo(grande_grupamento or "todos"),
                                    (uf or "br").lower(), _rotulo(nivel), ano)
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
            # Nulo em contagem é ausência de movimentação, e 0 representa isso
            # fielmente. Nulo em média ou razão NÃO é zero (é indefinido: não
            # houve denominador), e escrevê-lo como 0 introduziria observações
            # falsas na série. Fica vazio.
            vals = []
            for m, v in zip(medidas, r[1 + n_dim:]):
                if v is not None:
                    vals.append(v)
                else:
                    vals.append(0 if m in config.MEDIDAS_ADITIVAS else "")
            linhas.append([r[0], comp[:4], comp[4:6]] + list(dims) + vals)

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


def impressao_digital(grande_grupamento=None, uf=None):
    """Identifica a VERSÃO DOS DADOS servida pelo painel, a partir dos dados.

    Os metadados do pacote (`version`, `LastRefreshTime`) NÃO são confiáveis para
    esse fim: foi observado o painel divulgar uma competência nova e revisar a
    anterior mantendo ambos os campos inalterados (ver docs/LIMITACOES.md,
    seção 1). Usá-los como identificador de versão daria a falsa impressão de
    que duas coletas diferentes vieram do mesmo estado da fonte.

    Esta função deriva a identidade do próprio conteúdo: a lista de competências
    e os totais agregados de cada uma. Duas coletas com a mesma impressão digital
    viram exatamente a mesma série.
    """
    selects = [query.coluna("t", "competência", "competencia")]
    selects += [query.medida("m", m) for m in ("Admitidos", "Desligados", "Saldo")]
    froms, where = froms_e_filtro(grande_grupamento, uf)
    _, linhas = dsr.decodificar(
        client.executar_consulta(query.montar(froms, selects, where=where, janela=5000)))
    totais = sorted((int(l[0]), [v or 0 for v in l[1:]]) for l in linhas)
    canonico = json.dumps(totais, ensure_ascii=False, sort_keys=True)
    return {
        "escopo": "%s / %s" % (grande_grupamento or "todos os setores", uf or "Brasil"),
        "competencias": len(totais),
        "primeira_competencia": totais[0][0] if totais else None,
        "ultima_competencia": totais[-1][0] if totais else None,
        "sha256_dos_totais": hashlib.sha256(canonico.encode("utf-8")).hexdigest(),
    }


MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6,
         "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11,
         "DEZEMBRO": 12}


def mes_de_referencia_declarado(modelo=None):
    """Competência que o painel anuncia como sua referência, na capa.

    O título da capa é um texto estático do relatório, atualizado pelo órgão no
    momento da divulgação oficial. Ele pode ficar ATRÁS do que o modelo já
    serve: foi observado o modelo responder com uma competência a mais, com
    movimentações completas, enquanto a capa ainda anunciava o mês anterior —
    dados carregados mas ainda não divulgados. Comparar os dois é o que permite
    detectar essa situação em vez de incorporá-la sem perceber.

    Devolve a competência como inteiro AAAAMM, ou None se não for identificável.
    """
    modelo = modelo or client.obter_modelo()
    doc = modelo.get("exploration", {}).get("explorationContent", {}).get(
        "explorationDocument", "")
    # Só o título da capa vem em caixa alta; o texto metodológico usa minúsculas.
    achados = re.findall("([A-ZÇ]{4,9}) DE (20[0-9][0-9])", doc)
    candidatos = [(int(ano), MESES[mes]) for mes, ano in achados if mes in MESES]
    if not candidatos:
        return None
    ano, mes = max(candidatos)
    return ano * 100 + mes


def digital_dos_dados(cabecalho, linhas, medidas):
    """Impressão digital calculada A PARTIR DAS LINHAS EXTRAÍDAS.

    Preferível a uma consulta nova: o backend pode servir versões diferentes da
    série em requisições consecutivas (ver `conferir_replicas`), e uma consulta
    extra pode cair em outra versão, registrando no manifesto uma identidade que
    não é a do arquivo. Calculada sobre os próprios dados, ela sempre descreve o
    arquivo — e a validação já provou que esses totais batem com o painel.
    """
    aditivas = [m for m in medidas if m in config.MEDIDAS_ADITIVAS]
    idx = [cabecalho.index(_rotulo(m)) for m in aditivas]
    i_comp = cabecalho.index("competencia")
    acum = {}
    for l in linhas:
        c = int(l[i_comp])
        alvo = acum.setdefault(c, [0] * len(idx))
        for k, j in enumerate(idx):
            v = l[j]
            alvo[k] += int(float(v)) if v not in (None, "") else 0
    totais = sorted(acum.items())
    canonico = json.dumps(totais, ensure_ascii=False, sort_keys=True)
    return {"escopo": "linhas extraidas", "medidas": aditivas,
            "competencias": len(totais),
            "primeira_competencia": totais[0][0] if totais else None,
            "ultima_competencia": totais[-1][0] if totais else None,
            "sha256_dos_totais": hashlib.sha256(canonico.encode("utf-8")).hexdigest()}


def conferir_replicas(grande_grupamento=None, uf=None, amostras=4):
    """Detecta se o painel está servindo mais de uma versão da série agora.

    Foi observado o backend responder requisições consecutivas, do mesmo
    processo, a partir de réplicas em estados de atualização diferentes — uma
    com a competência mais recente, outra sem. Enquanto isso dura, uma extração
    particionada por ano pode misturar versões.

    Devolve (estavel, lista_de_impressoes).
    """
    vistas = [impressao_digital(grande_grupamento, uf) for _ in range(amostras)]
    shas = {v["sha256_dos_totais"] for v in vistas}
    return len(shas) == 1, vistas


def carimbo_execucao(grande_grupamento=None, uf=None, digital=None):
    """Metadados de proveniência do momento da coleta.

    `digital` deve ser a impressão digital tirada NO INÍCIO da extração. Passá-la
    é obrigatório para quem grava um arquivo: o backend serve versões diferentes
    da série em janelas de minutos, e uma consulta nova aqui pode cair em outra
    versão — registrando no manifesto uma identidade que não é a do arquivo.
    """
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
        # Declarado pelo painel, mas NAO confiavel como versao dos dados.
        "ultimo_refresh_declarado": pacote.get("LastRefreshTime"),
        "impressao_digital_dos_dados": digital or impressao_digital(grande_grupamento, uf),
    }
