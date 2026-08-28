# -*- coding: utf-8 -*-
"""Cliente HTTP para a API pública ("publish to web") do Power BI.

Usa apenas a biblioteca padrão para manter o pipeline auditável e sem
dependências de rede além de urllib.
"""
import gzip
import json
import time
import urllib.error
import urllib.request
import uuid

from . import config

USER_AGENT = "dadoscaged/1.0 (pesquisa academica; +https://github.com/RodrigoSilRo/dadoscaged)"


class ErroAPI(RuntimeError):
    """Falha na comunicação com o backend do Power BI."""


def _requisitar(caminho, payload=None, tentativas=4, espera=3.0):
    """Executa uma requisição ao cluster e devolve o JSON decodificado.

    payload=None -> GET; caso contrário POST com corpo JSON.
    Repete em erros transitórios (5xx, 429, conexão) com espera progressiva.
    """
    url = config.CLUSTER_HOST + caminho
    corpo = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")

    ultimo = None
    for tentativa in range(1, tentativas + 1):
        req = urllib.request.Request(url, data=corpo, method="GET" if corpo is None else "POST")
        # A chave de recurso substitui o token OAuth em relatórios publicados na web.
        req.add_header("X-PowerBI-ResourceKey", config.RESOURCE_KEY)
        req.add_header("Accept", "application/json, text/plain, */*")
        req.add_header("Accept-Encoding", "gzip")
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("ActivityId", str(uuid.uuid4()))
        req.add_header("RequestId", str(uuid.uuid4()))
        req.add_header("Origin", "https://app.powerbi.com")
        req.add_header("Referer", "https://app.powerbi.com/")
        if corpo is not None:
            req.add_header("Content-Type", "application/json;charset=UTF-8")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                bruto = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    bruto = gzip.decompress(bruto)
            return json.loads(bruto.decode("utf-8"))
        except urllib.error.HTTPError as e:
            ultimo = "HTTP %s em %s" % (e.code, caminho)
            if e.code not in (429, 500, 502, 503, 504):
                raise ErroAPI("%s: %s" % (ultimo, e.read()[:400])) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ultimo = "conexao: %s" % e
        if tentativa < tentativas:
            time.sleep(espera * tentativa)
    raise ErroAPI("falha apos %d tentativas (%s)" % (tentativas, ultimo))


def obter_modelo():
    """Metadados do relatório: modelo, páginas, pacote e data do último refresh."""
    return _requisitar(config.EP_MODELO.format(key=config.RESOURCE_KEY))


def obter_schema():
    """Schema conceitual: todas as tabelas, colunas e medidas do modelo."""
    return _requisitar(config.EP_SCHEMA,
                       {"modelIds": [config.MODEL_ID], "userPreferredLocale": "pt-BR"})


def executar_consulta(comando):
    """Envia um SemanticQueryDataShapeCommand e devolve a resposta bruta."""
    payload = {
        "version": "1.0.0",
        "queries": [{
            "Query": {"Commands": [comando]},
            "CacheKey": "",
            "QueryId": "",
            "ApplicationContext": {"DatasetId": config.DATASET_ID,
                                   "Sources": [{"ReportId": config.REPORT_ID}]},
        }],
        "cancelQueries": [],
        "modelId": config.MODEL_ID,
    }
    return _requisitar(config.EP_QUERY, payload)
