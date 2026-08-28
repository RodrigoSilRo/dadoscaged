# -*- coding: utf-8 -*-
"""Decodificação do formato DSR (Data Shape Result) do Power BI.

A resposta não vem como uma tabela plana. Ela é comprimida de três formas
combinadas, e ignorar qualquer uma delas produz dados silenciosamente errados:

1. Dicionários de valores (`ValueDicts`). Colunas de texto vêm como índices
   inteiros que apontam para uma lista de strings; o descritor `S` de cada
   coluna informa em `DN` qual dicionário usar.
2. Supressão de repetição (`R`). Bitmask: se o bit i está ligado, o valor da
   coluna i é idêntico ao da linha anterior e foi omitido do payload.
3. Nulos (`Ø`). Bitmask: se o bit i está ligado, a coluna i é nula.

Os valores efetivamente transmitidos ficam no array `C`, na ordem das colunas,
pulando as posições cobertas por `R` e por `Ø`.
"""

MASCARA_NULOS = "\u00d8"  # a chave é literalmente o caractere "Ø"


class ErroDSR(ValueError):
    """Resposta com formato inesperado."""


def _primeiro_dataset(resposta):
    try:
        return resposta["results"][0]["result"]["data"]["dsr"]["DS"][0]
    except (KeyError, IndexError, TypeError) as e:
        raise ErroDSR("resposta sem bloco DSR: %r" % (str(resposta)[:300],)) from e


def decodificar(resposta):
    """Converte a resposta da API em (nomes_das_colunas, linhas)."""
    ds = _primeiro_dataset(resposta)
    dicionarios = ds.get("ValueDicts", {})

    descritor = None
    nomes_dic = []
    anterior = []
    linhas = []

    for bloco in ds.get("PH", []):
        for _, registros in bloco.items():
            for registro in registros:
                # O descritor aparece na primeira linha de cada bloco.
                if "S" in registro:
                    descritor = registro["S"]
                    nomes_dic = [d.get("DN") for d in descritor]
                    anterior = [None] * len(descritor)
                if descritor is None:
                    raise ErroDSR("bloco de dados sem descritor de colunas")

                repetidos = registro.get("R", 0)
                nulos = registro.get(MASCARA_NULOS, 0)

                # O backend usa duas codificações de linha, às vezes na mesma
                # resposta: um array posicional "C" com apenas os valores
                # efetivamente transmitidos, ou uma chave por coluna ("G0",
                # "M0", ...) conforme o campo N do descritor.
                posicional = "C" in registro
                transmitidos = registro.get("C", [])

                atual = []
                pos = 0
                for i, campo in enumerate(descritor):
                    if nulos & (1 << i):
                        valor = None
                    elif repetidos & (1 << i):
                        valor = anterior[i]
                    else:
                        if posicional:
                            if pos >= len(transmitidos):
                                raise ErroDSR("linha truncada: %r" % (registro,))
                            valor = transmitidos[pos]
                            pos += 1
                        else:
                            valor = registro.get(campo["N"])
                        dic = nomes_dic[i]
                        if dic and isinstance(valor, int) and dic in dicionarios:
                            valor = dicionarios[dic][valor]
                    atual.append(valor)
                anterior = atual
                linhas.append(atual)

    colunas = [d["N"] for d in descritor] if descritor else []
    return colunas, linhas


def truncou(resposta):
    """True se o backend limitou o resultado (indício de janela pequena demais)."""
    ds = _primeiro_dataset(resposta)
    return bool(ds.get("RT")) or bool(resposta["results"][0].get("truncated"))
