"""Run the one-time persistence migrations."""

from lakegen.core.persistence import persistence
from lakegen.core.persistence.migrations import migrate


def main() -> None:
    with persistence.transaction() as connection:
        migrate(connection)


if __name__ == "__main__":
    main()
