# -*- coding: utf-8 -*-
"""Passo 3 — conveniência: gera .xlsx a partir do CSV validado.

O CSV é o artefato canônico. Este passo é opcional e não altera nenhum número:
acrescenta uma coluna `data` (primeiro dia da competência) e monta duas visões
derivadas para inspeção rápida.

    python scripts/03_exportar_excel.py data/processed/caged_comercio_subclasse_mensal.csv
"""
import argparse
import os

import pandas as pd

import _caminho


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv")
    p.add_argument("--saida", default=None)
    args = p.parse_args()

    # Todos os códigos são lidos como texto: são identificadores, não números
    # (perderiam zeros à esquerda).
    df = pd.read_csv(args.csv, sep=";", encoding="utf-8-sig", dtype=str)

    # Contagens viram inteiro; medidas compostas (media, razao) viram float e
    # preservam o vazio como NaN — vazio nelas significa indefinido, nao zero.
    contagens = [c for c in ("admitidos", "desligados", "saldo", "estoque_mensal")
                 if c in df.columns]
    compostas = [c for c in ("tempo_de_emprego_desligados", "vr_relativa",
                             "taxa_de_rotatividade", "saldo_acumulado")
                 if c in df.columns]
    for c in contagens:
        df[c] = pd.to_numeric(df[c], errors="raise").astype("int64")
    for c in compostas:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    medidas = contagens + compostas
    df.insert(1, "data", pd.to_datetime(df["competencia"], format="%Y%m"))

    nivel = df.columns[df.columns.get_loc(contagens[0]) - 1]
    cod = "cod_" + nivel if "cod_" + nivel in df.columns else nivel

    saida = args.saida or os.path.splitext(args.csv)[0] + ".xlsx"
    with pd.ExcelWriter(saida, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="dados", index=False)
        df.pivot_table(index=[cod, nivel], columns="competencia", values="saldo",
                       aggfunc="sum", fill_value=0).to_excel(xw, sheet_name="saldo_por_mes")
        if "divisao" in df.columns:
            # So contagens sao somadas: medidas compostas nao sao aditivas.
            (df.groupby(["competencia", "divisao"], as_index=False)[contagens].sum()
               .to_excel(xw, sheet_name="resumo_divisao", index=False))

    print("gravado: %s" % saida)
    print("linhas : %d | periodo: %s a %s | %s distintos: %d"
          % (len(df), df["competencia"].min(), df["competencia"].max(),
             nivel, df[cod].nunique()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
