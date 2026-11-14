class ErrorServicio(Exception):
    status_code = 500

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NoEncontrado(ErrorServicio):
    status_code = 404


class ReglaDeNegocio(ErrorServicio):
    status_code = 409


class FalloRegistro(ErrorServicio):
    status_code = 503
