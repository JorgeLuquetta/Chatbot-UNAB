"""El asistente solo atiende consultas universitarias INFORMATIVAS: sin operaciones, ejercicios ni tareas."""
import pytest

from app.rules import check_input

BLOQUEAR = [
    "¿Cuánto es 25+17?", "suma 3 y 4", "Resuelve esta ecuación: 2x + 3 = 7", "Hazme la tarea de cálculo",
    "Escríbeme un ensayo sobre la paz", "Traduce este texto al inglés", "Dame una receta de arepas",
    "Calcula el 20% de 50", "Programa en Python un juego", "dame las respuestas del parcial", "10 - 3",
    "Recomiéndame un casino", "Escribe un poema", "¿cuánto da 7 por 8?", "¿Cuál es la derivada de x^2?",
    "Redáctame una carta para mi jefe", "resuélveme el taller de física", "¿Cómo está el clima en Bucaramanga?",
]
PERMITIR = [
    "¿Cómo se calcula el promedio ponderado?", "¿Qué prerrequisitos tiene Cálculo Integral?",
    "¿Cuántos créditos me faltan?", "¿Qué materias debo matricular?", "Envíame mi informe de avance al correo",
    "¿Qué pasa el 2026-12-01?", "¿Cómo puedo resolver mi problema de matrícula?",
    "¿Qué necesito para hacer mi proyecto de grado?", "Noticias del ranking mundial de universidades",
    "¿Hay torneo de fútbol en bienestar?", "¿Qué es el clima organizacional?", "¿Cuándo son los parciales?",
    "sí", "unab.nuevo@yopmail.com", "¿Qué programa de posgrado hay?", "Dame recomendaciones para tener éxito",
    "¿Cuál es mi estado académico?", "¿Cuántas materias tengo pendientes?", "U00000010",
    "Envíame las noticias de tecnología al correo", "¿Qué dice el reglamento sobre la habilitación?",
]


@pytest.mark.parametrize("msg", BLOQUEAR)
def test_bloquea_tareas_y_temas_no_universitarios(msg):
    v = check_input(msg)
    assert not v.allowed
    assert v.rejection_type in ("input_task", "input_scope")


@pytest.mark.parametrize("msg", PERMITIR)
def test_permite_consultas_informativas(msg):
    assert check_input(msg).allowed, check_input(msg).reason
