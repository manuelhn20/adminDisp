"""Mapeo y utilidades para `estado_documentacion`.

Definición actualizada (TINYINT):
0  => Sin documentacion

Caso A - Digital:
11 => Generación inicial + revisión (con checkbox términos)
12 => Captura de firmas (Empleado + Usuario)
13 => Regeneración con firmas + revisión final
14 => Estado final Digital (vista final)

Caso B - Manual:
21 => Generación inicial + revisión (sin checkbox)
22 => Subida de archivos firmados
23 => Revisión + aprobación de archivos subidos
24 => Estado final Manual (vista final, solo cerrar)

Este módulo centraliza el mapeo y funciones helper para normalizar
entradas, obtener la representación textual y facilitar migraciones
o validaciones desde otros módulos (p. ej. `docgen`, `docexp`, servicios).

Recomendación de uso: importar funciones desde aquí en lugar de
duplicar lógica en `docgen`/`docexp`. Mantener la lógica en un módulo
común evita inconsistencias y facilita cambios futuros en los códigos.
"""

from typing import Union, Dict

# Constantes públicas
SIN_DOCUMENTACION = 0

# Caso A - Digital (11-14)
DIGITAL_GENERACION_INICIAL = 11
DIGITAL_CAPTURA_FIRMAS = 12
DIGITAL_REGENERACION_FINAL = 13
DIGITAL_COMPLETADO = 14

# Caso B - Manual (21-24)
MANUAL_GENERACION_INICIAL = 21
MANUAL_SUBIDA_FIRMADOS = 22
MANUAL_REVISION_APROBACION = 23
MANUAL_COMPLETADO = 24

# Estado final unificado
COMPLETADO_FINAL = 90

_INT_TO_LABEL: Dict[int, str] = {
    SIN_DOCUMENTACION: 'sin_documentacion',
    # Digital
    DIGITAL_GENERACION_INICIAL: 'digital_generacion_inicial',
    DIGITAL_CAPTURA_FIRMAS: 'digital_captura_firmas',
    DIGITAL_REGENERACION_FINAL: 'digital_regeneracion_final',
    DIGITAL_COMPLETADO: 'digital_completado',
    # Manual
    MANUAL_GENERACION_INICIAL: 'manual_generacion_inicial',
    MANUAL_SUBIDA_FIRMADOS: 'manual_subida_firmados',
    MANUAL_REVISION_APROBACION: 'manual_revision_aprobacion',
    MANUAL_COMPLETADO: 'manual_completado',
    # Final unificado
    COMPLETADO_FINAL: 'completado_final'
}

# Reverse mapping
_LABEL_TO_INT: Dict[str, int] = {v: k for k, v in _INT_TO_LABEL.items()}


def to_label(code: int) -> str:
    """Devuelve la etiqueta (string) asociada al código entero.

    Si el código no existe, lanza KeyError.
    """
    return _INT_TO_LABEL[code]


def to_int(label: Union[str, int]) -> int:
    """Normaliza una entrada a su código entero.

    - Si se pasa un entero válido, se devuelve tal cual.
    - Si se pasa una etiqueta (por ejemplo 'pendiente_subir'), devuelve el entero.
    - Si la etiqueta no existe, lanza KeyError.
    """
    if isinstance(label, int):
        if label in _INT_TO_LABEL:
            return label
        raise KeyError(f'Código de estado desconocido: {label}')
    if not isinstance(label, str):
        raise TypeError('label debe ser str o int')
    key = label.strip().lower()
    if key in _LABEL_TO_INT:
        return _LABEL_TO_INT[key]
    # también permitir etiquetas con guiones bajos/espacios/variantes
    key_norm = key.replace(' ', '_')
    if key_norm in _LABEL_TO_INT:
        return _LABEL_TO_INT[key_norm]
    raise KeyError(f'Etiqueta de estado desconocida: {label}')


def is_valid_code(code: int) -> bool:
    return code in _INT_TO_LABEL


def is_valid_label(label: str) -> bool:
    try:
        to_int(label)
        return True
    except Exception:
        return False


def choices_for_sql() -> str:
    """Retorna una representación para usar en documentación/migrations.

    Ejemplo: "0:sin_documentacion,11:digital_generacion_inicial,..."
    """
    return ','.join(f"{k}:{v}" for k, v in _INT_TO_LABEL.items())


def is_digital_flow(code: int) -> bool:
    """Verifica si el código pertenece al flujo Digital (11-14)"""
    return 11 <= code <= 14


def is_manual_flow(code: int) -> bool:
    """Verifica si el código pertenece al flujo Manual (21-24)"""
    return 21 <= code <= 24


def is_completed(code: int) -> bool:
    """Verifica si el proceso está completado (estado final)"""
    return code in (DIGITAL_COMPLETADO, MANUAL_COMPLETADO)


def get_next_state(current: int) -> int:
    """Retorna el siguiente estado en el flujo. Si es final, retorna el mismo."""
    next_states = {
        0: None,  # Debe elegir Digital o Manual
        # Digital flow
        11: DIGITAL_CAPTURA_FIRMAS,
        12: DIGITAL_REGENERACION_FINAL,
        13: DIGITAL_COMPLETADO,
        14: DIGITAL_COMPLETADO,  # Final
        # Manual flow
        21: MANUAL_SUBIDA_FIRMADOS,
        22: MANUAL_REVISION_APROBACION,
        23: MANUAL_COMPLETADO,
        24: MANUAL_COMPLETADO  # Final
    }
    return next_states.get(current, current)


__all__ = [
    'SIN_DOCUMENTACION',
    'DIGITAL_GENERACION_INICIAL', 'DIGITAL_CAPTURA_FIRMAS', 'DIGITAL_REGENERACION_FINAL', 'DIGITAL_COMPLETADO',
    'MANUAL_GENERACION_INICIAL', 'MANUAL_SUBIDA_FIRMADOS', 'MANUAL_REVISION_APROBACION', 'MANUAL_COMPLETADO',
    'to_label', 'to_int', 'is_valid_code', 'is_valid_label', 'choices_for_sql',
    'is_digital_flow', 'is_manual_flow', 'is_completed', 'get_next_state'
]
