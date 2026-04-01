from enum import Enum, auto

class Vertex(Enum):
    FREE_SPACE = auto()
    OBSTACLE = auto()

class VerticalTransition(Enum):
    UP = auto()
    DOWN = auto()
    UP_AND_DOWN = auto()
    NO_VERTICAL_TRANSITION = auto()

class HorizontalTransition(Enum):
    LEFT = auto()
    RIGHT = auto()
    LEFT_AND_RIGHT = auto()
    NO_HORIZONTAL_TRANSITION = auto()

class Special(Enum):
	PLACEHOLDER = auto()

