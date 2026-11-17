"""Capa de servicios: consultas SQL y reglas de negocio (sin Flask)."""


class ErrorNegocio(Exception):
    """Error esperado (validación, regla de negocio). El mensaje se muestra al usuario."""

    def __init__(self, mensaje, status=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status
