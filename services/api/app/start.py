"""Initialize local/deployed schema before serving the API."""
import uvicorn

from app.db import get_engine, initialize


def main() -> None:
    initialize(get_engine())
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
