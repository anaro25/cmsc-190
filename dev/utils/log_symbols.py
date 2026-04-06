from dev.core.composite_elements import (
    HorizontalTransition,
    Special,
    Vertex,
    VerticalTransition,
)


AGENT_LOG_SYMBOL = "■"
TARGET_LOG_SYMBOL = "▲"


def convert_element_to_log_symbol(element):
    # Agent / target overlays
    if element == AGENT_LOG_SYMBOL or element == TARGET_LOG_SYMBOL:
        return element

    if isinstance(element, str) and len(element) == 1:
        return element

    if element == Vertex.FREE_SPACE:
        return " "
    elif element == Vertex.OBSTACLE:
        return "#"

    elif element == Special.PLACEHOLDER:
        return " "

    elif element == VerticalTransition.UP:
        return "↑"
    elif element == VerticalTransition.DOWN:
        return "↓"
    elif element == VerticalTransition.UP_AND_DOWN:
        return "↕"
    elif element == VerticalTransition.NO_VERTICAL_TRANSITION:
        return " "

    elif element == HorizontalTransition.LEFT:
        return "←"
    elif element == HorizontalTransition.RIGHT:
        return "→"
    elif element == HorizontalTransition.LEFT_AND_RIGHT:
        return "↔"
    elif element == HorizontalTransition.NO_HORIZONTAL_TRANSITION:
        return " "

    return str(element)
