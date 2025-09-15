from pathlib import Path

# 프로젝트 루트 기준 docs/openapi.yml 경로
SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.yml"
SPEC_TEXT = SPEC_PATH.read_text(encoding="utf-8")

SWAGGER_HTML = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>API Docs</title>
    <link rel="stylesheet"
      href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = () => {
        SwaggerUIBundle({
          url: "/openapi.yml",   // 여기서 스펙 요청
          dom_id: "#swagger-ui",
          docExpansion: "none",
          deepLinking: true,
        });
      };
    </script>
  </body>
</html>"""


def serve_swagger_ui(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": SWAGGER_HTML,
    }


def serve_openapi(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/yml; charset=utf-8"},
        "body": SPEC_TEXT,
    }
