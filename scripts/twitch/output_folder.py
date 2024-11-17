import os


def get_output_path() -> str:
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))
    if not os.path.exists(output_path):
        os.mkdir(output_path)
    return output_path
