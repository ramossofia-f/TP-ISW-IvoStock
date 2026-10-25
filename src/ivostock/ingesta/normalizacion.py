"""Normalización de una corrida con descarte trazado (RF-21).

Reglas:
- El SKU es siempre texto: hay ISBN alfanuméricos y ceros a la izquierda que no se pierden.
- Stock en blanco significa sin stock (0), no dato ausente.
- Stock con texto o negativo es error de parseo: la fila se descarta.
- SKU repetido: vale la última ocurrencia y la anterior queda registrada como descarte.
"""

from dataclasses import dataclass, field

from ivostock.ingesta.proveedor import ConfigProveedor

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")

MAL_FORMADA = "mal_formada"
SKU_VACIO = "sku_vacio"
STOCK_NO_NUMERICO = "stock_no_numerico"
STOCK_NEGATIVO = "stock_negativo"
SKU_DUPLICADO = "sku_duplicado"

ERRORES_PARSEO = {MAL_FORMADA, SKU_VACIO, STOCK_NO_NUMERICO, STOCK_NEGATIVO}


@dataclass(frozen=True)
class Descarte:
    linea: int
    motivo: str
    contenido: str


@dataclass
class Normalizacion:
    stock: dict[str, int] = field(default_factory=dict)
    filas: int = 0
    descartes: list[Descarte] = field(default_factory=list)
    encoding: str = "utf-8"

    @property
    def errores_parseo(self) -> int:
        return sum(1 for d in self.descartes if d.motivo in ERRORES_PARSEO)

    @property
    def duplicados(self) -> int:
        return sum(1 for d in self.descartes if d.motivo == SKU_DUPLICADO)

    @property
    def tasa_error(self) -> float:
        return self.errores_parseo / self.filas if self.filas else 0.0


def decodificar(crudo: bytes) -> tuple[str, str]:
    for encoding in ENCODINGS:
        try:
            return crudo.decode(encoding), encoding.removesuffix("-sig")
        except UnicodeDecodeError:
            continue
    raise ValueError("No se pudo decodificar la corrida")  # latin-1 no falla nunca


def _posicion(columna: int | str, encabezado: list[str]) -> int:
    if isinstance(columna, int):
        return columna
    nombres = [c.strip() for c in encabezado]
    if columna not in nombres:
        raise ValueError(f"La columna '{columna}' no está en el encabezado: {nombres}")
    return nombres.index(columna)


def normalizar(crudo: bytes, config: ConfigProveedor) -> Normalizacion:
    texto, encoding = decodificar(crudo)
    lineas = texto.splitlines()
    resultado = Normalizacion(encoding=encoding)

    inicio = 0
    encabezado: list[str] = []
    if config.encabezado:
        if not lineas:
            raise ValueError("La corrida está vacía y se esperaba un encabezado")
        encabezado = lineas[0].split(config.separador)
        inicio = 1
    pos_sku = _posicion(config.col_sku, encabezado)
    pos_stock = _posicion(config.col_stock, encabezado)
    minimo = max(pos_sku, pos_stock)

    ultima_aparicion: dict[str, tuple[int, str]] = {}
    for numero, linea in enumerate(lineas[inicio:], start=inicio + 1):
        if not linea.strip():
            continue
        resultado.filas += 1
        campos = linea.split(config.separador)
        if len(campos) <= minimo:
            resultado.descartes.append(Descarte(numero, MAL_FORMADA, linea))
            continue
        sku = campos[pos_sku].strip()
        if not sku:
            resultado.descartes.append(Descarte(numero, SKU_VACIO, linea))
            continue
        valor_crudo = campos[pos_stock].strip()
        if valor_crudo == "":
            valor = 0
        else:
            try:
                valor = int(valor_crudo)
            except ValueError:
                resultado.descartes.append(Descarte(numero, STOCK_NO_NUMERICO, linea))
                continue
            if valor < 0:
                resultado.descartes.append(Descarte(numero, STOCK_NEGATIVO, linea))
                continue
        if sku in ultima_aparicion:
            linea_previa, contenido_previo = ultima_aparicion[sku]
            resultado.descartes.append(Descarte(linea_previa, SKU_DUPLICADO, contenido_previo))
        ultima_aparicion[sku] = (numero, linea)
        resultado.stock[sku] = valor

    return resultado
