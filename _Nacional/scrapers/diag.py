# -*- coding: utf-8 -*-
"""Diagnostico: registra por que fallo el scraping de la tienda actual."""
import threading

_t = threading.local()


def reset():
    _t.err = None


def fallo(motivo):
    """Guarda solo el primer motivo (la causa raiz)."""
    if getattr(_t, "err", None) is None:
        _t.err = motivo


def ultimo():
    return getattr(_t, "err", None)