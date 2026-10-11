import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Only ever debug locally — FLASK_ENV=production (set on your host) turns
    # this off. Debug mode's interactive traceback lets anyone who triggers
    # an unhandled error run arbitrary code on the server.
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug, port=port)
