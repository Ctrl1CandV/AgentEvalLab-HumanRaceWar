"""Builder-only commands; deliberately absent from the task export."""
from arena import calibrate, grade


def register(commands):
    grade.register(commands)
    calibrate.register(commands)
