"""`python -m hwserver.keygen` — print a fresh HW_SECRET_KEY."""

from .crypto import generate_key

if __name__ == "__main__":
    print(generate_key())
