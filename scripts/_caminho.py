# -*- coding: utf-8 -*-
"""Torna o pacote importável sem instalação (`python scripts/...` funciona direto)."""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

DIR_DADOS = os.path.join(RAIZ, "data")
DIR_RAW = os.path.join(DIR_DADOS, "raw")
DIR_PROC = os.path.join(DIR_DADOS, "processed")
DIR_META = os.path.join(RAIZ, "metadata")
