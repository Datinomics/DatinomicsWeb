# -*- coding: utf-8 -*-
"""Diagnostico: registra por que fallo el scraping de la tienda actual.
Tambien maneja un tope de tiempo por tienda (por hilo): pasado el tope, toda
request de ese hilo falla al instante y el scraper corta con lo que ya junto."""
import threading
import time

import requests

_t = threading.local()


def reset():
    _t.err = None
    _t.deadline = None
    _t.corto = False


def fallo(motivo):
    """Guarda solo el primer motivo (la causa raiz)."""
    if getattr(_t, "err", None) is None:
        _t.err = motivo


def ultimo():
    return getattr(_t, "err", None)


class TopeDeTiempo(requests.exceptions.RequestException):
    pass


def tope(segundos):
    """Fija el tope de tiempo de la tienda actual (0 = sin tope)."""
    _t.deadline = time.time() + segundos if segundos else None
    _t.corto = False


def corto_por_tope():
    return getattr(_t, "corto", False)


_request_original = requests.Session.request


def _request_con_tope(self, *a, **kw):
    dl = getattr(_t, "deadline", None)
    if dl is not None and time.time() > dl:
        _t.corto = True
        raise TopeDeTiempo("tope de tiempo por tienda")
    return _request_original(self, *a, **kw)


requests.Session.request = _request_con_tope
